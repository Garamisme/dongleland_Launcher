"""windowtest.py — 게임 창 설정 (창모드·크기).

  1. 창모드/전체화면이면 --width/--height 가 실행 인자에 들어간다. '그대로'면 안 들어간다
  2. options.txt 는 fullscreen: 한 줄만 바뀌고 나머지 줄은 그대로다
  3. 파일이 없을 때 창모드는 파일을 만들지 않는다(이미 바닐라 기본값)
  4. 설정값은 범위로 잘리고, 모르는 모드는 거부된다
"""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="windowtest-")

import launcher  # noqa: E402

fails = []


def check(name, cond):
    print(("✅ " if cond else "❌ [FAIL] ") + name)
    if not cond:
        fails.append(name)


# ── 1. 실행 인자 ─────────────────────────────────────────────────────────
captured = {}
launcher.instance.installed_version_id = lambda: "26.1"
launcher.instance.is_version_ready = lambda v=None: True
launcher._java_executable = lambda: "java"
launcher._command.get_minecraft_command = lambda v, d, opts: captured.update(opts) or ["java"]
acc = {"mc_username": "T", "mc_uuid": "0" * 32, "mc_access_token": "x"}

launcher.build_command(acc, window={"mode": "windowed", "width": 1600, "height": 900})
check("창모드 → 사용자 지정 해상도", captured.get("customResolution") is True
      and captured.get("resolutionWidth") == "1600" and captured.get("resolutionHeight") == "900")
captured.clear()
launcher.build_command(acc, window={"mode": "keep", "width": 1600, "height": 900})
check("'그대로' → 해상도 인자 없음", "customResolution" not in captured)
captured.clear()
launcher.build_command(acc)
check("설정 없음 → 해상도 인자 없음", "customResolution" not in captured)

# ── 2·3. options.txt ─────────────────────────────────────────────────────
d = tempfile.mkdtemp(prefix="windowtest-inst-")
launcher.instance.instance_dir = lambda *a, **k: d
opts = os.path.join(d, "options.txt")

launcher._set_fullscreen_option(False)
check("파일 없음 + 창모드 → 만들지 않음", not os.path.exists(opts))
launcher._set_fullscreen_option(True)
check("파일 없음 + 전체화면 → 한 줄짜리 생성", open(opts, encoding="utf-8").read() == "fullscreen:true\n")

with open(opts, "w", encoding="utf-8") as f:
    f.write("version:4000\nfullscreen:true\nguiScale:2\n")
launcher._set_fullscreen_option(False)
check("fullscreen 줄만 바뀐다",
      open(opts, encoding="utf-8").read() == "version:4000\nfullscreen:false\nguiScale:2\n")

# ── 4. 설정 저장 (api) ───────────────────────────────────────────────────
import api  # noqa: E402

a = api.Api()
r = a.set_window("windowed", 100, 99999)
check("크기는 범위로 잘린다", r.get("ok") and r["width"] == 640 and r["height"] == 4320)
check("저장값이 다시 읽힌다", a.window_info().get("mode") == "windowed")
check("모르는 모드는 거부", a.set_window("borderless", 1280, 720).get("ok") is False)
check("숫자가 아니면 거부", a.set_window("windowed", "abc", 720).get("ok") is False)

print()
if fails:
    print("실패 %d건: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("모두 통과")
