"""auth.py — Microsoft 계정 로그인 (v3 Phase 1).

플로우 (HANDOFF §5.2):
  MS OAuth2 device code → access_token
    → Xbox Live(XBL) → XSTS → Minecraft Services → MC access_token
    → 프로필(username, uuid)

디바이스 코드 플로우를 쓰는 이유:
  - 임베디드 브라우저/리다이렉트 서버 불필요 (pywebview 와 궁합 좋음)
  - 유저가 microsoft.com/link 에서 코드만 입력하면 끝
  - client_secret 불필요 (public client)

XBL/XSTS/MC 체인은 minecraft-launcher-lib(mll) 의 검증된 구현을 재사용하고,
디바이스 코드 획득/폴링/리프레시만 이 모듈이 직접 수행한다.
(mll 8.0 은 authorization-code+PKCE 헬퍼만 제공, 디바이스 코드는 미제공)

⚠️ 선행 조건 (개발자 1회 작업):
  1. Azure Portal 에서 앱 등록 (지원 계정: '개인 Microsoft 계정')
  2. '인증 → 고급 설정 → 공용 클라이언트 흐름 허용' = 예  (디바이스 코드 필수)
  3. Mojang 승인 폼 제출 (aka.ms/mce-reviewappid) — 미승인 시
     login_with_xbox 에서 403(AzureAppNotPermitted) 발생.
     ※ 폼 제출 전에 최소 1회 로그인 시도가 있어야 함(활동 기록 요구).
  4. 발급된 Application(client) ID 를 app_meta.AZURE_CLIENT_ID 에 기입
     (client id 는 비밀값 아님 — 코드에 넣어도 됨)

토큰 저장:
  %APPDATA%/DonglelandClient/account.dat
  Windows DPAPI(CryptProtectData, 현재 사용자 스코프)로 암호화.
  비 Windows(컨테이너 테스트)에서는 평문 JSON 폴백 + 경고 필드.

만료 처리:
  - MC access_token: 24h 유효 → 만료 임박 시 MS refresh_token 으로
    MS 토큰 재발급 후 Xbox 체인 재수행 (get_account 에서 자동).
  - MS refresh_token 자체가 죽으면(90일 미사용 등) 재로그인 요구.
"""

import base64
import json
import os
import sys
import time

import requests

import app_meta
import instance

from minecraft_launcher_lib import microsoft_account as _msa

# ── 상수 ──────────────────────────────────────────────────────────────────

# 개인 MS 계정 전용 테넌트. (organizations/common 아님 — MC 는 개인 계정)
_TENANT = "consumers"
_DEVICECODE_URL = f"https://login.microsoftonline.com/{_TENANT}/oauth2/v2.0/devicecode"
_AUTHORIZE_URL = f"https://login.microsoftonline.com/{_TENANT}/oauth2/v2.0/authorize"
_TOKEN_URL = f"https://login.microsoftonline.com/{_TENANT}/oauth2/v2.0/token"
_SCOPE = "XboxLive.signin offline_access"
# 로컬 콜백: authorization code flow 에서 브라우저가 로그인 후 코드를 이 주소로 돌려준다.
# Azure 는 http 스킴을 'localhost' 에만 허용하고(127.0.0.1 은 매니페스트 직접 편집 필요),
# localhost 매칭 시 포트는 무시한다. 경로가 다르면 다른 URI 로 취급되므로 경로도 비운다.
# → 포털에 http://localhost 하나만 등록하면 임의 포트로 동작.
_REDIRECT_HOST = "localhost"
_REDIRECT_PATH = "/"

# MC 토큰 만료 여유 (초). 남은 시간이 이보다 짧으면 선제 갱신.
_EXPIRY_MARGIN = 300

# XSTS 오류 코드 → 사용자 안내 (wiki.vg 문서 기준)
_XERR_MESSAGES = {
    2148916233: "이 Microsoft 계정에 Xbox 프로필이 없습니다.\nxbox.com 에서 프로필을 먼저 만들어주세요.",
    2148916235: "Xbox Live 를 사용할 수 없는 국가의 계정입니다.",
    2148916236: "성인 인증이 필요한 계정입니다. Xbox 설정을 확인해주세요.",
    2148916237: "성인 인증이 필요한 계정입니다. Xbox 설정을 확인해주세요.",
    2148916238: "미성년자 계정입니다. 보호자의 Microsoft 가족 그룹에 추가된 뒤 다시 시도해주세요.",
}


class AuthError(Exception):
    """사용자에게 그대로 보여줄 수 있는 한글 메시지를 담는 인증 오류."""

    def __init__(self, message: str, code: str = "auth_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def _client_id() -> str:
    cid = getattr(app_meta, "AZURE_CLIENT_ID", "") or ""
    if not cid or cid.startswith("<"):
        raise AuthError(
            "Azure 클라이언트 ID가 설정되지 않았습니다.\n"
            "app_meta.AZURE_CLIENT_ID 를 확인해주세요. (개발자 작업 필요)",
            code="no_client_id",
        )
    return cid


# ── 1) 디바이스 코드 발급 / 폴링 ─────────────────────────────────────────

def begin_device_login() -> dict:
    """디바이스 코드 발급.

    반환(JS 로 그대로 전달):
      {"ok":True, "user_code":"ABC-DEF", "verification_uri":"https://microsoft.com/link",
       "device_code":..., "interval":5, "expires_in":900}
    """
    r = requests.post(
        _DEVICECODE_URL,
        data={"client_id": _client_id(), "scope": _SCOPE},
        timeout=15,
    )
    data = r.json()
    if r.status_code != 200 or "device_code" not in data:
        desc = data.get("error_description") or data.get("error") or str(data)
        raise AuthError(f"로그인 코드 발급에 실패했습니다:\n{desc}")
    return {
        "ok": True,
        "user_code": data["user_code"],
        "verification_uri": data.get("verification_uri", "https://microsoft.com/link"),
        # 코드가 이미 포함된 URL — 열면 코드 입력 없이 바로 로그인 화면으로 감
        "verification_uri_complete": data.get("verification_uri_complete", ""),
        "device_code": data["device_code"],
        "interval": int(data.get("interval", 5)),
        "expires_in": int(data.get("expires_in", 900)),
    }


def open_login_window(auth_url: str) -> bool:
    """앱 내부에 로그인 창(pywebview)을 띄운다 (Lunar Client 방식).

    외부 브라우저로 나가지 않고 런처 안에서 로그인이 완결된다.
    로컬 콜백 서버가 코드를 받으면 close_login_window() 로 닫는다.
    반환: 창을 띄웠으면 True, 실패하면 False (→ 외부 브라우저로 폴백).

    주의: webview.start() 루프가 이미 돌고 있는 상태에서 create_window 로
    두 번째 창을 추가하는 방식이다(pywebview 가 지원). js_api 브릿지 호출은
    별도 스레드에서 오므로, 실패하면 조용히 False 를 반환해 브라우저로 폴백한다.
    """
    global _login_window
    try:
        import webview
    except Exception:
        return False
    try:
        _login_window = webview.create_window(
            "Microsoft 계정 로그인",
            url=auth_url,
            width=520, height=680,
            resizable=True,
        )
        return True
    except Exception:
        _login_window = None
        return False


def close_login_window():
    """로그인 창이 열려 있으면 닫는다 (콜백 수신 후 호출)."""
    global _login_window
    if _login_window is None:
        return
    try:
        _login_window.destroy()
    except Exception:
        pass
    _login_window = None


_login_window = None


# ── Authorization Code flow (브라우저 로그인창 — WAM 폴백용) ─────────────
# device code 대신 이걸 쓰면 계정 선택/로그인 화면이 브라우저에 바로 뜨고,
# 로그인 후 로컬 서버로 코드가 돌아와 자동으로 토큰 교환까지 끝난다.

import base64 as _b64
import hashlib as _hashlib
import secrets as _secrets
import threading as _threading
import http.server as _httpserver
import urllib.parse as _urlparse

_auth_flow = {}  # 진행 중인 flow 상태 (code_verifier, redirect_uri, 결과 등)


def _make_pkce():
    """PKCE code_verifier / code_challenge(S256) 생성."""
    verifier = _b64.urlsafe_b64encode(_secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = _hashlib.sha256(verifier.encode()).digest()
    challenge = _b64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def begin_auth_code_login() -> dict:
    """브라우저 로그인 시작. 로컬 콜백 서버를 띄우고 authorize URL 을 반환한다.

    반환: {"ok":True, "auth_url":..., "state":...}
    이후 프론트가 auth_url 을 브라우저로 열면, 사용자가 로그인/계정선택 →
    로컬 서버가 코드를 받아 poll_auth_code() 가 완료를 보고한다.
    """
    verifier, challenge = _make_pkce()
    state = _secrets.token_urlsafe(16)

    # 로컬 서버를 임의 빈 포트에 띄운다.
    result_holder = {"code": None, "error": None, "done": False}

    class _Handler(_httpserver.BaseHTTPRequestHandler):
        def log_message(self, *a):  # 콘솔 로그 억제
            pass

        def do_GET(self):
            parsed = _urlparse.urlparse(self.path)
            if parsed.path != _REDIRECT_PATH:
                self.send_response(404); self.end_headers(); return
            qs = _urlparse.parse_qs(parsed.query)
            if "code" in qs:
                result_holder["code"] = qs["code"][0]
            else:
                result_holder["error"] = qs.get("error_description", qs.get("error", ["알 수 없는 오류"]))[0]
            result_holder["done"] = True
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = ("로그인이 완료되었습니다. 이 창을 닫고 런처로 돌아가세요."
                   if result_holder["code"] else
                   "로그인에 실패했습니다. 런처로 돌아가 다시 시도해주세요.")
            self.wfile.write(
                f"<html><head><meta charset='utf-8'></head><body "
                f"style='font-family:sans-serif;text-align:center;padding-top:80px;"
                f"background:#0c111b;color:#cdd6e4'><h2>동글랜드 런처</h2>"
                f"<p>{msg}</p></body></html>".encode("utf-8"))

    # 서버는 IPv4 루프백에 바인딩(Azure 는 IPv6 [::1] 미지원).
    # redirect_uri 는 'localhost' 로 알려야 Azure 의 http://localhost 등록과 매칭된다.
    server = _httpserver.HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    redirect_uri = f"http://{_REDIRECT_HOST}:{port}{_REDIRECT_PATH}"

    params = {
        "client_id": _client_id(),
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": _SCOPE,
        "response_mode": "query",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",  # 항상 계정 선택 화면부터
    }
    auth_url = _AUTHORIZE_URL + "?" + _urlparse.urlencode(params)

    # 콜백을 백그라운드에서 1회 처리
    def _serve():
        server.timeout = 300  # 5분 대기
        while not result_holder["done"]:
            server.handle_request()
        try:
            server.server_close()
        except Exception:
            pass

    t = _threading.Thread(target=_serve, daemon=True)
    t.start()

    _auth_flow.clear()
    _auth_flow.update({
        "verifier": verifier, "state": state, "redirect_uri": redirect_uri,
        "result": result_holder, "server": server,
    })
    return {"ok": True, "auth_url": auth_url, "state": state}


def poll_auth_code() -> dict:
    """로컬 콜백 도착 여부 확인 후, 코드가 오면 토큰 교환 + 전체 체인 완료.

    반환:
      {"status":"pending"}                 → 아직 로그인 대기 중
      {"status":"ok", "account":{...}}     → 완료, 저장까지 끝
      실패 시 AuthError
    """
    flow = _auth_flow
    if not flow or "result" not in flow:
        raise AuthError("진행 중인 로그인이 없습니다. 다시 시도해주세요.", code="no_flow")
    res = flow["result"]
    if not res["done"]:
        return {"status": "pending"}
    # 콜백이 도착했으면 임베디드 로그인 창을 닫는다 (열려 있었다면).
    close_login_window()
    if res["error"]:
        raise AuthError(f"로그인에 실패했습니다:\n{res['error']}", code="oauth_error")
    code = res["code"]
    if not code:
        raise AuthError("로그인 코드를 받지 못했습니다.", code="no_code")

    # 코드 → 토큰 교환 (PKCE verifier 포함)
    r = requests.post(
        _TOKEN_URL,
        data={
            "client_id": _client_id(),
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": flow["redirect_uri"],
            "code_verifier": flow["verifier"],
            "scope": _SCOPE,
        },
        timeout=15,
    )
    data = r.json()
    if "access_token" not in data:
        desc = data.get("error_description") or data.get("error") or str(data)
        raise AuthError(f"토큰 교환에 실패했습니다:\n{desc}")

    account = _complete_xbox_chain(data)
    _save_account(account)
    _auth_flow.clear()
    return {"status": "ok", "account": public_view(account)}


def poll_device_login(device_code: str) -> dict:
    """토큰 엔드포인트 1회 폴링.

    반환:
      {"status":"pending"}                    → interval 후 재호출
      {"status":"slow_down", "interval_add":5}→ 간격 늘려 재호출
      {"status":"ok", "account":{...}}        → 전체 체인 완료, 저장까지 끝
      실패 시 AuthError
    """
    r = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": _client_id(),
            "device_code": device_code,
        },
        timeout=15,
    )
    data = r.json()

    if "access_token" in data:
        account = _complete_xbox_chain(data)
        _save_account(account)
        return {"status": "ok", "account": public_view(account)}

    err = data.get("error", "")
    if err == "authorization_pending":
        return {"status": "pending"}
    if err == "slow_down":
        return {"status": "slow_down", "interval_add": 5}
    if err == "expired_token":
        raise AuthError("로그인 코드가 만료됐습니다. 다시 시도해주세요.", code="expired")
    if err == "authorization_declined":
        raise AuthError("로그인이 취소됐습니다.", code="declined")
    desc = data.get("error_description") or err or str(data)
    raise AuthError(f"로그인에 실패했습니다:\n{desc}")


# ── 2) Xbox → XSTS → Minecraft 체인 (mll 재사용) ─────────────────────────

def _complete_xbox_chain(ms_token_resp: dict) -> dict:
    """MS access_token → XBL → XSTS → MC 토큰 → 프로필. 내부 계정 dict 반환."""
    ms_access = ms_token_resp["access_token"]
    ms_refresh = ms_token_resp.get("refresh_token", "")

    try:
        xbl = _msa.authenticate_with_xbl(ms_access)
        xbl_token = xbl["Token"]
        userhash = xbl["DisplayClaims"]["xui"][0]["uhs"]
    except Exception as e:
        raise AuthError(f"Xbox Live 인증에 실패했습니다:\n{e}")

    try:
        xsts = _msa.authenticate_with_xsts(xbl_token)
        xsts_token = xsts["Token"]
    except requests.HTTPError as e:
        raise AuthError(_xsts_error_message(e))
    except Exception as e:
        raise AuthError(f"XSTS 인증에 실패했습니다:\n{e}")

    # mll 의 authenticate_with_minecraft 는 HTTP 상태를 예외로 안 던지고
    # 응답 dict 를 그대로 반환한다 → 승인 전 403 진단이 묻힘.
    # 직접 호출해서 상태 코드 기반으로 정확히 분기한다.
    try:
        r = requests.post(
            "https://api.minecraftservices.com/authentication/login_with_xbox",
            json={"identityToken": f"XBL3.0 x={userhash};{xsts_token}"},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=15,
        )
    except Exception as e:
        raise AuthError(f"Minecraft 인증 서버에 연결하지 못했습니다:\n{e}")
    if r.status_code == 403:
        raise AuthError(
            "이 앱(Azure Client ID)이 아직 Minecraft API 사용 승인을 받지 못했습니다.\n"
            "개발자: aka.ms/mce-reviewappid 폼 승인 상태를 확인해주세요.",
            code="app_not_permitted",
        )
    try:
        mc = r.json()
    except Exception:
        mc = {}
    if r.status_code != 200 or "access_token" not in mc:
        detail = mc.get("errorMessage") or mc.get("error") or r.text[:200]
        raise AuthError(
            f"Minecraft 인증에 실패했습니다 (HTTP {r.status_code}):\n{detail}")
    mc_access = mc["access_token"]
    mc_expires_at = int(time.time()) + int(mc.get("expires_in", 86400))

    try:
        profile = _msa.get_profile(mc_access)
    except Exception as e:
        raise AuthError(f"프로필 조회에 실패했습니다:\n{e}")
    if "id" not in profile or "error" in profile:
        # Game Pass 유저가 공식 런처 최초 로그인을 안 했거나, 게임 미보유
        raise AuthError(
            "이 계정에 Minecraft 프로필이 없습니다.\n"
            "· 게임을 보유하고 있는지 확인해주세요.\n"
            "· Game Pass 이용자는 공식 런처에 1회 로그인해 닉네임을 만든 뒤 다시 시도해주세요.",
            code="no_profile",
        )

    return {
        "mc_username": profile["name"],
        "mc_uuid": profile["id"],            # 하이픈 없는 32자 (DB 스키마와 동일 규칙)
        "mc_access_token": mc_access,
        "mc_expires_at": mc_expires_at,
        "ms_refresh_token": ms_refresh,
        "saved_at": int(time.time()),
    }


def _xsts_error_message(e) -> str:
    try:
        xerr = int(e.response.json().get("XErr", 0))
        if xerr in _XERR_MESSAGES:
            return _XERR_MESSAGES[xerr]
    except Exception:
        pass
    return f"Xbox 인증(XSTS)에 실패했습니다:\n{e}"


# ── 3) 리프레시 (MS refresh_token → 체인 재수행) ─────────────────────────

def _refresh(account: dict) -> dict:
    refresh_token = account.get("ms_refresh_token")
    if not refresh_token:
        raise AuthError("저장된 로그인 정보가 만료됐습니다. 다시 로그인해주세요.", code="relogin")
    r = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": _client_id(),
            "refresh_token": refresh_token,
            "scope": _SCOPE,
        },
        timeout=15,
    )
    data = r.json()
    if "access_token" not in data:
        raise AuthError("로그인이 만료됐습니다. 다시 로그인해주세요.", code="relogin")
    # MS 는 refresh 시 새 refresh_token 을 줄 수 있음 → 교체 저장
    if not data.get("refresh_token"):
        data["refresh_token"] = refresh_token
    new_account = _complete_xbox_chain(data)
    _save_account(new_account)
    return new_account


# ── 4) 저장/로드 (DPAPI 암호화) ───────────────────────────────────────────

def _dpapi_protect(raw: bytes) -> bytes | None:
    """Windows DPAPI 암호화. 실패/비 Windows 면 None."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes as wt

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        blob_in = DATA_BLOB(len(raw), ctypes.cast(ctypes.create_string_buffer(raw, len(raw)),
                                                  ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        ok = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
        if not ok:
            return None
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    except Exception:
        return None


def _dpapi_unprotect(enc: bytes) -> bytes | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes as wt

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        blob_in = DATA_BLOB(len(enc), ctypes.cast(ctypes.create_string_buffer(enc, len(enc)),
                                                  ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        ok = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
        if not ok:
            return None
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    except Exception:
        return None


# 파일 포맷: 1행 헤더("DPAPI" | "PLAIN") + base64 페이로드
def _encrypt_blob(obj) -> bytes:
    raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    enc = _dpapi_protect(raw)
    header, payload = ("DPAPI", enc) if enc else ("PLAIN", raw)
    return header.encode() + b"\n" + base64.b64encode(payload)


def _decrypt_blob(data: bytes):
    header, payload_b64 = data.split(b"\n", 1)
    payload = base64.b64decode(payload_b64)
    if header == b"DPAPI":
        raw = _dpapi_unprotect(payload)
        if raw is None:
            return None  # 다른 PC/유저 → 복호 불가
    else:
        raw = payload
    return json.loads(raw.decode("utf-8"))


# ── 다중 계정 저장소 ──────────────────────────────────────────────────────
# 구조: {"active": "<uuid32>", "accounts": {"<uuid32>": {account dict}, ...}}
def _load_store() -> dict:
    path = instance.accounts_path()
    if os.path.isfile(path):
        try:
            with open(path, "rb") as f:
                store = _decrypt_blob(f.read())
            if isinstance(store, dict) and "accounts" in store:
                return store
        except Exception:
            pass
        return {"active": None, "accounts": {}}
    legacy = _migrate_legacy()  # 레거시 단일 계정 → 마이그레이션
    return legacy or {"active": None, "accounts": {}}


def _migrate_legacy():
    old = instance.account_path()
    if not os.path.isfile(old):
        return None
    try:
        with open(old, "rb") as f:
            acc = _decrypt_blob(f.read())
        if acc and acc.get("mc_uuid"):
            store = {"active": acc["mc_uuid"], "accounts": {acc["mc_uuid"]: acc}}
            _save_store(store)
            os.remove(old)  # 이관 완료 → 구 파일 제거
            return store
    except Exception:
        pass
    return None


def _save_store(store: dict):
    os.makedirs(instance.root_dir(), exist_ok=True)
    tmp = instance.accounts_path() + ".tmp"
    with open(tmp, "wb") as f:
        f.write(_encrypt_blob(store))
    os.replace(tmp, instance.accounts_path())


def _save_account(account: dict):
    """계정 추가/갱신 후 활성으로 지정 (로그인·전환 성공 시)."""
    store = _load_store()
    uuid = account["mc_uuid"]
    store["accounts"][uuid] = account
    store["active"] = uuid
    _save_store(store)


def _load_account():
    """현재 활성 계정."""
    store = _load_store()
    active = store.get("active")
    return store["accounts"].get(active) if active else None


def list_accounts() -> list:
    """저장된 모든 계정의 공개 정보 (활성 여부 포함)."""
    store = _load_store()
    active = store.get("active")
    out = []
    for uuid, acc in store["accounts"].items():
        v = public_view(acc)
        v["active"] = (uuid == active)
        out.append(v)
    out.sort(key=lambda x: (not x["active"], x["username"].lower()))
    return out


def switch_account(uuid: str) -> dict:
    """저장된 계정으로 활성 전환. 토큰 유효하면 재로그인 불필요."""
    store = _load_store()
    if uuid not in store["accounts"]:
        raise AuthError("저장된 계정을 찾을 수 없습니다.", code="not_found")
    store["active"] = uuid
    _save_store(store)
    return {"ok": True, "account": public_view(store["accounts"][uuid])}


def remove_account(uuid: str) -> dict:
    """계정 목록에서 제거. 활성이면 남은 계정으로 이양(없으면 None)."""
    store = _load_store()
    store["accounts"].pop(uuid, None)
    if store.get("active") == uuid:
        remaining = list(store["accounts"].keys())
        store["active"] = remaining[0] if remaining else None
    _save_store(store)
    return {"ok": True, "active": store.get("active")}


def logout():
    """활성 계정만 제거 (다른 계정 유지). 활성은 남은 계정으로 이양."""
    store = _load_store()
    active = store.get("active")
    if active:
        store["accounts"].pop(active, None)
        remaining = list(store["accounts"].keys())
        store["active"] = remaining[0] if remaining else None
        _save_store(store)
    return {"ok": True, "active": store.get("active")}


# ── 5) 공개 API ───────────────────────────────────────────────────────────

def public_view(account: dict) -> dict:
    """토큰을 제외한, UI 에 보여줄 수 있는 계정 정보."""
    return {
        "logged_in": True,
        "username": account["mc_username"],
        "uuid": account["mc_uuid"],
        # 스킨 헤드 (UI 아바타용, 외부 렌더 서비스)
        "avatar_url": f"https://mc-heads.net/avatar/{account['mc_uuid']}/64",
    }


def get_status() -> dict:
    """로그인 상태 (토큰 검증 없이 저장 파일 기준, 빠름)."""
    acc = _load_account()
    if not acc:
        return {"logged_in": False}
    return public_view(acc)


def get_account(auto_refresh: bool = True) -> dict:
    """실행에 쓸 유효한 계정 반환 (필요 시 자동 갱신).

    launcher.py 가 게임 실행 직전에 호출한다.
    반환 dict 에는 mc_access_token 포함 (JS 로 내보내지 말 것).
    """
    acc = _load_account()
    if not acc:
        raise AuthError("로그인이 필요합니다.", code="relogin")
    if time.time() < acc.get("mc_expires_at", 0) - _EXPIRY_MARGIN:
        return acc
    if not auto_refresh:
        raise AuthError("로그인이 만료됐습니다. 다시 로그인해주세요.", code="relogin")
    return _refresh(acc)
