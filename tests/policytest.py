"""policytest.py — 원격 허용 모드 정책 (네트워크 없이).

허용 모드를 런처 출시 없이 늘리기 위해, 서버 정책 API(GET /server-mods)를 읽어
카탈로그 위에 덮어쓴다:
  1. 원격 허용 목록에만 있는 슬러그 → 카드가 새로 생긴다(Modrinth 메타로 이름)
  2. 허용에서 빠진 카탈로그 모드 → 목록에서 빠진다. 단 이미 설치돼 있으면 남겨 제거할 수 있게
  3. 금지 모드 → banned 표시(경고만, 자동 삭제 안 함)
  4. 원격 실패 → 마지막 성공값 → 그것도 없으면 카탈로그 그대로
"""

import importlib
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="policytest-")

import mod_catalog  # noqa: E402
import preflight  # noqa: E402

fails = []


def check(name, cond):
    print(("✅ " if cond else "❌ [FAIL] ") + name)
    if not cond:
        fails.append(name)


def fresh():
    return importlib.reload(mod_catalog)


slugged = [m for m in mod_catalog.VISIBLE_MODS if m.get("slug")]
keep, drop, ban = slugged[0], slugged[1], slugged[2]
others = [m["slug"] for m in slugged[3:]]

# ── 1~3. 정책 적용 ──────────────────────────────────────────────────────────
c = fresh()
ids_before = {id(c.MODS), id(c.VISIBLE_MODS), id(c.MOD_BY_ID)}
policy = {"mod_policy": "curated",
          "allowed_mods": [keep["slug"], "brand-new-mod"] + others,
          "required_mods": [{"id": "fabric-api", "name": "Fabric API"}],
          "banned_mods": [ban["slug"]]}
c.apply_policy(policy, lambda slugs: {"brand-new-mod": {"title": "Brand New"}} if slugs else {})
check("제자리 수정(from-import 한 참조가 그대로 유효)",
      {id(c.MODS), id(c.VISIBLE_MODS), id(c.MOD_BY_ID)} == ids_before)
new = c.MOD_BY_ID.get("brand-new-mod")
check("원격에만 있는 슬러그 → 새 항목", bool(new) and new["slug"] == "brand-new-mod"
      and new in c.VISIBLE_MODS)
check("새 항목 이름 = Modrinth 제목", bool(new) and new["name"] == "Brand New")
check("새 항목 분류 '기타' 가 카테고리에 추가", "기타" in c.CATEGORIES)
check("허용 유지 모드는 정상", not c.MOD_BY_ID[keep["id"]].get("off_policy"))
check("허용에서 빠진 모드 → off_policy", c.MOD_BY_ID[drop["id"]].get("off_policy") is True)
check("금지 모드 → banned + off_policy", c.MOD_BY_ID[ban["id"]].get("banned") is True
      and c.MOD_BY_ID[ban["id"]].get("off_policy") is True)
check("슬러그 없는 번들 모드는 건드리지 않음",
      all(not m.get("off_policy") for m in c.MODS if not m.get("slug")))

# 두 번 적용해도 항목이 중복되지 않는다
c.apply_policy(policy, lambda slugs: {})
check("재적용 시 중복 없음", sum(1 for m in c.MODS if m["id"] == "brand-new-mod") == 1)

# open 정책: 금지만 반영
c = fresh()
c.apply_policy({"mod_policy": "open", "allowed_mods": [], "required_mods": [],
                "banned_mods": [ban["slug"]]}, lambda s: {})
check("open 정책: 목록에 없어도 허용", not c.MOD_BY_ID[drop["id"]].get("off_policy"))
check("open 정책: 금지는 반영", c.MOD_BY_ID[ban["id"]].get("banned") is True)

# 정책 없음 → 그대로
c = fresh()
n = len(c.MODS)
c.apply_policy(None, lambda s: {})
check("정책 없음: 카탈로그 그대로", len(c.MODS) == n
      and not any(m.get("off_policy") for m in c.MODS))

# ── 4. 원격 가져오기 폴백 ────────────────────────────────────────────────────
saved = []
preflight.save_config = lambda cfg: saved.append(dict(cfg))
good = {"servers": {"dongleland": policy}}


def urlopen_returning(payload):
    import io
    import json

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    return lambda *a, **k: R(json.dumps(payload).encode())


def urlopen_fail(*a, **k):
    raise OSError("down")


cfg = {}
preflight.urllib.request.urlopen = urlopen_returning(good)
check("성공: 정책 반환", preflight.fetch_mod_policy(cfg) == policy)
check("성공: config 에 마지막 성공값 저장", cfg.get("_mod_policy") == policy and saved)
preflight.urllib.request.urlopen = urlopen_fail
check("실패: 마지막 성공값으로 폴백", preflight.fetch_mod_policy(cfg) == policy)
check("실패 + 캐시 없음: None(카탈로그 그대로)", preflight.fetch_mod_policy({}) is None)
preflight.urllib.request.urlopen = urlopen_returning({"servers": {"other": policy}})
check("우리 서버 항목 없음: 캐시/None", preflight.fetch_mod_policy({}) is None)
preflight.urllib.request.urlopen = urlopen_returning(
    {"servers": {"dongleland": {"allowed_mods": "nope"}}})
check("형식 오류: 버림", preflight.fetch_mod_policy({}) is None)

print(f"\n{len(fails)} 실패" if fails else "\n전부 통과")
sys.exit(1 if fails else 0)
