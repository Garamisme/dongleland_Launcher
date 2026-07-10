"""skin.py — 스킨 조회/변경/초기화 (v3 스킨 탭 백엔드).

Minecraft 서비스 공식 API 사용 (MC access_token 필요 → auth.get_account 재사용):
  GET    /minecraft/profile               현재 프로필(스킨 variant/url 포함)
  POST   /minecraft/profile/skins         스킨 업로드 (multipart: variant, file)
  DELETE /minecraft/profile/skins/active  기본(스티브/알렉스) 스킨으로 초기화

주의: 스킨 API 도 Mojang 앱 승인 후에만 동작한다 (인증과 동일 조건).
업로드 규격: PNG, 64x64(모던) 또는 64x32(레거시), 24KB 이하.
"""

import os
import shutil
import struct

import requests

import auth

_BASE = "https://api.minecraftservices.com/minecraft/profile"
_MAX_BYTES = 24576  # Mojang 업로드 제한 (24KB)


class SkinError(Exception):
    def __init__(self, message: str, code: str = "skin_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def _headers():
    acc = auth.get_account()  # 만료 시 자동 갱신, 불가 시 AuthError(relogin)
    return {"Authorization": f"Bearer {acc['mc_access_token']}"}


def get_skin() -> dict:
    """현재 활성 스킨. {"ok":True,"variant":"classic|slim","url":...} """
    r = requests.get(_BASE, headers=_headers(), timeout=15)
    if r.status_code != 200:
        raise SkinError(f"스킨 정보를 가져오지 못했습니다 (HTTP {r.status_code}).")
    data = r.json()
    active = next((s for s in data.get("skins", []) if s.get("state") == "ACTIVE"), None)
    if not active:
        return {"ok": True, "variant": "classic", "url": None, "default": True}
    return {"ok": True,
            "variant": (active.get("variant") or "CLASSIC").lower(),
            "url": active.get("url"), "default": False}


def _png_size(path: str) -> tuple[int, int]:
    """PNG 헤더에서 (width, height). PNG 가 아니면 SkinError."""
    with open(path, "rb") as f:
        head = f.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        raise SkinError("PNG 파일이 아닙니다. 스킨은 PNG 형식만 지원해요.")
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def change_skin(variant: str, png_path: str) -> dict:
    """스킨 업로드. variant: 'classic'(스티브 팔) / 'slim'(알렉스 팔)."""
    variant = "slim" if str(variant).lower() == "slim" else "classic"
    if not os.path.isfile(png_path):
        raise SkinError("선택한 파일을 찾을 수 없습니다.")
    if os.path.getsize(png_path) > _MAX_BYTES:
        raise SkinError("파일이 너무 큽니다 (24KB 이하 PNG 만 가능).")
    w, h = _png_size(png_path)
    if (w, h) not in ((64, 64), (64, 32)):
        raise SkinError(f"스킨 크기가 올바르지 않습니다 ({w}x{h}).\n"
                        "64x64 (또는 구형 64x32) PNG 만 업로드할 수 있어요.")
    with open(png_path, "rb") as f:
        r = requests.post(
            _BASE + "/skins",
            headers=_headers(),
            data={"variant": variant},
            files={"file": (os.path.basename(png_path), f, "image/png")},
            timeout=30,
        )
    if r.status_code not in (200, 204):
        detail = ""
        try:
            detail = r.json().get("errorMessage") or ""
        except Exception:
            pass
        raise SkinError(f"스킨 변경에 실패했습니다 (HTTP {r.status_code}).\n{detail}".strip())
    return {"ok": True, "variant": variant}


def reset_skin() -> dict:
    """기본 스킨(스티브/알렉스)으로 초기화."""
    r = requests.delete(_BASE + "/skins/active", headers=_headers(), timeout=15)
    if r.status_code not in (200, 204):
        raise SkinError(f"스킨 초기화에 실패했습니다 (HTTP {r.status_code}).")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# 스킨 라이브러리 — 로컬 저장(DonglelandClient/skins/) + 적용
#   skins.json: {"used_id": str|None, "items":[{id,name,variant,cape_id,
#                cape_name,file,added_at}]}
# ═══════════════════════════════════════════════════════════════════════
import base64 as _b64
import json as _json
import time as _time
import uuid as _uuid

import instance as _instance

_CAPE_URL = "https://api.minecraftservices.com/minecraft/profile/capes/active"


def _lib_dir() -> str:
    d = os.path.join(_instance.root_dir(), "skins")
    os.makedirs(d, exist_ok=True)
    return d


def _index_path() -> str:
    return os.path.join(_lib_dir(), "skins.json")


def _load_index() -> dict:
    try:
        with open(_index_path(), "r", encoding="utf-8") as f:
            d = _json.load(f)
            d.setdefault("used_id", None)
            d.setdefault("items", [])
            return d
    except Exception:
        return {"used_id": None, "items": []}


def _save_index(d: dict):
    tmp = _index_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        _json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _index_path())


def _data_url(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return "data:image/png;base64," + _b64.b64encode(f.read()).decode()
    except Exception:
        return None


def validate_png(path: str):
    """규격 검증 (change_skin 과 동일 기준). 실패 시 SkinError."""
    if not os.path.isfile(path):
        raise SkinError("선택한 파일을 찾을 수 없습니다.")
    if os.path.getsize(path) > _MAX_BYTES:
        raise SkinError("파일이 너무 큽니다 (24KB 이하 PNG 만 가능).")
    w, h = _png_size(path)
    if (w, h) not in ((64, 64), (64, 32)):
        raise SkinError(f"스킨 크기가 올바르지 않습니다 ({w}x{h}).\n"
                        "64x64 (또는 구형 64x32) PNG 만 사용할 수 있어요.")


def lib_list() -> dict:
    """라이브러리 전체 (각 항목에 미리보기 data_url 포함)."""
    idx = _load_index()
    items = []
    for it in idx["items"]:
        e = dict(it)
        e["data_url"] = _data_url(os.path.join(_lib_dir(), it["file"]))
        items.append(e)
    return {"ok": True, "used_id": idx["used_id"], "items": items}


def lib_add(name: str, variant: str, cape_id, cape_name, src_path: str) -> dict:
    validate_png(src_path)
    variant = "slim" if str(variant).lower() == "slim" else "classic"
    sid = _uuid.uuid4().hex[:12]
    fname = f"{sid}.png"
    shutil.copy2(src_path, os.path.join(_lib_dir(), fname))
    idx = _load_index()
    entry = {"id": sid, "name": (name or "이름 없는 스킨").strip()[:40],
             "variant": variant, "cape_id": cape_id or None,
             "cape_name": cape_name or None, "file": fname,
             "added_at": int(_time.time())}
    idx["items"].append(entry)
    _save_index(idx)
    return {"ok": True, "id": sid}


def lib_update(sid: str, name: str, variant: str, cape_id, cape_name,
               src_path: str | None) -> dict:
    idx = _load_index()
    it = next((x for x in idx["items"] if x["id"] == sid), None)
    if not it:
        raise SkinError("스킨을 찾을 수 없습니다.")
    if src_path:  # 파일 교체 (미지정이면 기존 파일 유지)
        validate_png(src_path)
        shutil.copy2(src_path, os.path.join(_lib_dir(), it["file"]))
    it["name"] = (name or it["name"]).strip()[:40]
    it["variant"] = "slim" if str(variant).lower() == "slim" else "classic"
    it["cape_id"] = cape_id or None
    it["cape_name"] = cape_name or None
    _save_index(idx)
    return {"ok": True}


def lib_duplicate(sid: str) -> dict:
    """스킨 복제 (파일 사본 + '사본' 이름)."""
    idx = _load_index()
    it = next((x for x in idx["items"] if x["id"] == sid), None)
    if not it:
        raise SkinError("스킨을 찾을 수 없습니다.")
    nid = _uuid.uuid4().hex[:12]
    nfile = f"{nid}.png"
    shutil.copy2(os.path.join(_lib_dir(), it["file"]),
                 os.path.join(_lib_dir(), nfile))
    dup = dict(it, id=nid, file=nfile,
               name=(it["name"] + " 사본")[:40], added_at=int(_time.time()))
    # 원본 바로 뒤에 삽입 (맨 뒤가 아니라 옆에 → 어디 생겼는지 바로 보임)
    pos = next((i for i, x in enumerate(idx["items"]) if x["id"] == sid), len(idx["items"]) - 1)
    idx["items"].insert(pos + 1, dup)
    _save_index(idx)
    return {"ok": True, "id": nid}


def lib_delete(sid: str) -> dict:
    idx = _load_index()
    it = next((x for x in idx["items"] if x["id"] == sid), None)
    if not it:
        raise SkinError("스킨을 찾을 수 없습니다.")
    idx["items"] = [x for x in idx["items"] if x["id"] != sid]
    if idx["used_id"] == sid:
        idx["used_id"] = None
    _save_index(idx)
    try:
        os.remove(os.path.join(_lib_dir(), it["file"]))
    except OSError:
        pass
    return {"ok": True}


def lib_use(sid: str) -> dict:
    """라이브러리 스킨 적용: 스킨 업로드 + 망토 선택(또는 해제)."""
    idx = _load_index()
    it = next((x for x in idx["items"] if x["id"] == sid), None)
    if not it:
        raise SkinError("스킨을 찾을 수 없습니다.")
    change_skin(it["variant"], os.path.join(_lib_dir(), it["file"]))
    cape_warn = None
    try:
        if it.get("cape_id"):
            r = requests.put(_CAPE_URL, headers=_headers(),
                             json={"capeId": it["cape_id"]}, timeout=15)
            if r.status_code not in (200, 204):
                cape_warn = f"망토 적용 실패 (HTTP {r.status_code})"
        else:
            r = requests.delete(_CAPE_URL, headers=_headers(), timeout=15)
            if r.status_code not in (200, 204):
                cape_warn = None  # 망토 없는 계정의 해제 실패는 무시
    except Exception as e:
        cape_warn = f"망토 적용 실패: {e}"
    idx["used_id"] = sid
    _save_index(idx)
    out = {"ok": True, "used_id": sid}
    if cape_warn:
        out["warning"] = cape_warn
    return out


def get_capes() -> dict:
    """계정이 보유한 망토 목록. {"ok":True,"capes":[{id,name,active}]}"""
    r = requests.get(_BASE, headers=_headers(), timeout=15)
    if r.status_code != 200:
        raise SkinError(f"프로필을 가져오지 못했습니다 (HTTP {r.status_code}).")
    capes = [{"id": c.get("id"), "name": c.get("alias") or "망토",
              "url": c.get("url"),
              "active": c.get("state") == "ACTIVE"}
             for c in r.json().get("capes", [])]
    return {"ok": True, "capes": capes}
