#!/usr/bin/env python3
"""전체 검증 러너 — 변경 후 이것만 돌리면 된다.

    python3 tests/run_all.py

검사 항목
  1. 백엔드 컴파일 (모든 .py)
  2. 프론트 ↔ api.py 계약 (프론트가 부르는 메서드가 실제로 있는가)
  3. 프론트 함수 중복 정의 (같은 이름을 두 번 선언하면 나중 것이 이긴다)
  4. 인라인 JS 문법
  5. jsdom E2E / UI 스위트 전체
"""
import collections
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
HTML = os.path.join(ROOT, "frontend", "nether-glass-launcher-standalone.html")

# 오래 걸리는 순서대로. e2e 가 가장 넓게 잡는다.
SUITES = [
    "e2e.js", "boot2.js", "modui.js", "libtest.js", "vertest.js",
    "vermenu.js", "fix5.js", "scroll.js", "upd.js", "terms.js",
    "logo.js", "canceltest.js", "memtest.js", "beta.js",
]

fails = []


def step(name):
    print(f"\n── {name} " + "─" * max(0, 56 - len(name)))


def compile_backend():
    step("백엔드 컴파일")
    pys = sorted(glob.glob(os.path.join(ROOT, "*.py")))
    r = subprocess.run([sys.executable, "-m", "py_compile", *pys],
                       capture_output=True, text=True)
    if r.returncode:
        fails.append("컴파일")
        print(r.stderr.strip()[:800])
    else:
        print(f"✅ {len(pys)}개 모듈")


def contract():
    step("프론트 ↔ api.py 계약")
    html = open(HTML, encoding="utf-8").read()
    api = open(os.path.join(ROOT, "api.py"), encoding="utf-8").read()
    calls = set(re.findall(r"Bridge\.api\.([a-zA-Z_0-9]+)\(", html))
    calls |= set(re.findall(r"V3\(\)\.([a-zA-Z_0-9]+)\(", html))
    methods = set(re.findall(r"^    def ([a-zA-Z_0-9]+)\(", api, re.M))
    missing = sorted(calls - methods)
    if missing:
        fails.append("계약")
        print(f"❌ api.py 에 없는 메서드: {missing}")
    else:
        print(f"✅ {len(calls)}개 호출, 누락 없음")


def js_and_dupes():
    step("프론트 JS 문법 + 함수 중복")
    html = open(HTML, encoding="utf-8").read()
    js = "\n;\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))
    tmp = os.path.join(TESTS, "_plain.js")
    open(tmp, "w").write(js)
    r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
    if r.returncode:
        fails.append("JS 문법")
        print(r.stderr.strip()[:600])
    else:
        print("✅ 문법")
    os.remove(tmp)

    names = re.findall(r"^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", js, re.M)
    dup = {n: c for n, c in collections.Counter(names).items() if c > 1}
    if dup:
        # 이 프로젝트를 한 번 크게 깨뜨린 실수다 (continueBoot 중복 → 무한 로딩)
        fails.append("함수 중복")
        print(f"❌ 중복 정의: {dup}")
    else:
        print(f"✅ 함수 {len(names)}개, 중복 없음")


def suites():
    step("jsdom 스위트")
    # jsdom 이 없으면 14개가 전부 실패해 원인을 알기 어렵다. 먼저 확인한다.
    probe = subprocess.run(["node", "-e", "require('jsdom')"],
                           capture_output=True, text=True, cwd=TESTS)
    if probe.returncode:
        fails.append("jsdom 없음")
        print("❌ jsdom 을 찾을 수 없다.  →  npm install jsdom")
        return

    for s in SUITES:
        path = os.path.join(TESTS, s)
        if not os.path.isfile(path):
            print(f"⏭  {s} (없음)")
            continue
        r = subprocess.run(["node", path], capture_output=True, text=True,
                           timeout=200, cwd=TESTS)
        out = r.stdout
        bad = r.returncode != 0 or "[FAIL]" in out or "❌" in out
        if bad:
            fails.append(s)
            print(f"❌ {s}")
            for line in out.splitlines():
                if "[FAIL]" in line or "❌" in line:
                    print("   " + line.strip())
            if r.stderr.strip():
                print("   " + r.stderr.strip().splitlines()[-1][:160])
        else:
            print(f"✅ {s}")


if __name__ == "__main__":
    compile_backend()
    contract()
    js_and_dupes()
    suites()

    print("\n" + "=" * 60)
    if fails:
        print(f"실패 {len(fails)}건: {', '.join(fails)}")
        sys.exit(1)
    print("전체 통과 ✅")
