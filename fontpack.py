# -*- coding: utf-8 -*-
"""fontpack.py — TTF 를 마인크래프트 폰트 리소스팩(zip)으로 변환.

구조:
  <이름>.zip
   ├ pack.mcmeta                  ← 반드시 zip 루트 (MC 가 이걸로 팩을 인식)
   └ assets/minecraft/font/
      ├ default.json             (기본 폰트를 이 ttf 로 교체)
      └ font.ttf                 (원본 ttf, 이름만 font.ttf 로)
zip 파일명 = 원본 ttf 파일명(확장자 제외).

⚠️ pack.mcmeta 는 zip 루트에 있어야 한다. 폴더째 압축해 <이름>/pack.mcmeta 로
   한 겹 들어가면 MC 가 리소스팩으로 인식하지 못해 인게임 목록에 안 뜬다
   (사용자 제공 예시 zip 이 이 실수였다).

build_font_pack 은 순수 함수(파일 IO 만) — 단위 테스트 가능.
"""

import json
import os
import re
import zipfile

# default.json — 바닐라 기본 폰트를 이 ttf 로 덮어써 인게임 전체 글꼴을 바꾼다.
_DEFAULT_JSON = {
    "providers": [
        {
            "type": "ttf",
            "file": "minecraft:font.ttf",
            "shift": [0, 0],
            "size": 9.0,
            "oversample": 3,
        }
    ]
}


def _safe_name(filename: str) -> str:
    """원본 파일명 → zip/폴더 이름. 확장자 제거 + 경로 위험 문자 치환."""
    base = os.path.splitext(os.path.basename(filename))[0].strip()
    base = re.sub(r'[\\/:*?"<>|]', "_", base)
    return base or "font"


def build_font_pack(ttf_bytes: bytes, filename: str, dest_dir: str) -> str:
    """ttf 바이트로 폰트 리소스팩 zip 을 만들어 dest_dir 에 저장하고 경로 반환.

    같은 이름의 zip 이 있으면 덮어쓴다(재생성).
    """
    if not ttf_bytes:
        raise ValueError("TTF 데이터가 비어 있습니다.")
    name = _safe_name(filename)
    os.makedirs(dest_dir, exist_ok=True)
    zip_path = os.path.join(dest_dir, name + ".zip")

    mcmeta = {
        "pack": {
            "description": name + " 폰트",
            "min_format": 70,
            "max_format": 99,
        }
    }
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        # ⚠️ 반드시 zip 루트에 — 하위 폴더로 감싸면 MC 가 팩을 인식하지 못한다.
        z.writestr("pack.mcmeta",
                   json.dumps(mcmeta, ensure_ascii=False, indent=2))
        z.writestr("assets/minecraft/font/default.json",
                   json.dumps(_DEFAULT_JSON, indent=4))
        z.writestr("assets/minecraft/font/font.ttf", ttf_bytes)
    return zip_path
