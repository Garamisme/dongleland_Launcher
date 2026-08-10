"""authtest.py — 토큰 갱신 규칙 (네트워크 없이).

로그인이 '어쩔 때만' 풀리던 원인 3가지를 잠근다:
  1. 일시적 장애(5xx·네트워크)를 만료로 오인해 재로그인을 요구하지 않는다
  2. 회전된 refresh_token 을 Xbox 체인보다 먼저 저장한다 (체인이 실패해도 살아남게)
  3. 동시 갱신은 직렬화 — 같은 토큰으로 두 번 요청하지 않는다
"""

import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="authtest-")

import auth  # noqa: E402

fails = []


def check(name, cond):
    print(("✅ " if cond else "❌ [FAIL] ") + name)
    if not cond:
        fails.append(name)


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def seed(refresh="RT-OLD"):
    """만료된 MC 토큰 + 살아있는 refresh_token 을 가진 계정 하나."""
    auth._save_account({
        "mc_username": "Tester",
        "mc_uuid": "0" * 32,
        "mc_access_token": "MC-OLD",
        "mc_expires_at": int(time.time()) - 10,   # 이미 만료 → 갱신 유발
        "ms_refresh_token": refresh,
        "saved_at": int(time.time()),
    })


def stored():
    return auth._load_account()


def run(post, chain):
    auth.requests.post = post
    auth._complete_xbox_chain = chain


# ── 1. 서버 장애는 만료가 아니다 ──────────────────────────────────────────
seed()
run(lambda *a, **k: FakeResp(503, None), None)
try:
    auth.get_account()
    check("5xx 는 오류를 낸다", False)
except auth.AuthError as e:
    check("5xx → network (재로그인 아님)", e.code == "network")
check("5xx 후에도 계정이 남아 있다", stored() is not None)

# ── 2. 네트워크 예외도 만료가 아니다 ──────────────────────────────────────
def boom(*a, **k):
    raise OSError("연결 끊김")


run(boom, None)
try:
    auth.get_account()
    check("네트워크 예외는 오류를 낸다", False)
except auth.AuthError as e:
    check("네트워크 예외 → network", e.code == "network")

# ── 3. 죽은 토큰만 재로그인 ───────────────────────────────────────────────
run(lambda *a, **k: FakeResp(400, {"error": "invalid_grant"}), None)
try:
    auth.get_account()
    check("invalid_grant 는 오류를 낸다", False)
except auth.AuthError as e:
    check("invalid_grant → relogin", e.code == "relogin")

# ── 4. 회전된 토큰은 체인이 실패해도 저장돼 있다 ──────────────────────────
seed("RT-OLD")


def chain_fails(_data):
    raise auth.AuthError("Xbox Live 인증에 실패했습니다")


run(lambda *a, **k: FakeResp(200, {"access_token": "MS-NEW", "refresh_token": "RT-NEW"}),
    chain_fails)
try:
    auth.get_account()
except auth.AuthError:
    pass
check("체인 실패 후에도 회전된 refresh_token 이 저장됨",
      stored()["ms_refresh_token"] == "RT-NEW")

# ── 5. 동시 갱신은 한 번만 요청한다 ───────────────────────────────────────
seed("RT-OLD")
calls = []


def slow_post(*a, **k):
    calls.append(k.get("data", {}).get("refresh_token"))
    time.sleep(0.2)
    return FakeResp(200, {"access_token": "MS-NEW", "refresh_token": "RT-NEW2"})


def chain_ok(_data):
    return {
        "mc_username": "Tester",
        "mc_uuid": "0" * 32,
        "mc_access_token": "MC-NEW",
        "mc_expires_at": int(time.time()) + 86400,
        "ms_refresh_token": _data["refresh_token"],
        "saved_at": int(time.time()),
    }


run(slow_post, chain_ok)
threads = [threading.Thread(target=auth.get_account) for _ in range(2)]
for t in threads:
    t.start()
for t in threads:
    t.join()
check("동시 호출이 토큰을 한 번만 소비한다 (호출 %d회)" % len(calls), len(calls) == 1)
check("갱신 결과가 저장됨", stored()["mc_access_token"] == "MC-NEW")

# ── 6. 읽지 못한 저장소를 덮어쓰지 않는다 ─────────────────────────────────
path = auth.instance.accounts_path()
with open(path, "wb") as f:
    f.write(b"DPAPI\n!!!not-base64!!!")     # 손상 파일
store = auth._load_store()
check("손상 파일은 빈 저장소 + 표시", store.get("_unreadable") is True)
auth._save_account({"mc_username": "New", "mc_uuid": "1" * 32,
                    "mc_access_token": "x", "mc_expires_at": 0,
                    "ms_refresh_token": "y", "saved_at": 0})
check("손상 파일은 .bak 으로 보존됨", os.path.isfile(path + ".bak"))

print()
if fails:
    print("실패 %d건: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("모두 통과")
