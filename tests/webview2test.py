"""webview2test.py — WebView2 없는 PC 에서 흰 화면 대신 안내 (창 없이).

pywebview 는 WebView2 런타임이 없으면 IE(MSHTML) 엔진으로 조용히 대체한다.
우리 화면은 IE 에서 안 돌아 흰 창만 남는다 → 창을 만들기 전에 판정해 안내하고 끝낸다.
  1. pywebview 판정이 'chromium 아님'이면 안내 후 창을 만들지 않는다
  2. 판정 자체가 실패하면 기존대로 실행(오탐으로 런처를 막지 않는다)
"""

import os
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="wv2test-")

import app  # noqa: E402
import webview  # noqa: E402

fails = []


def check(name, cond):
    print(("✅ " if cond else "❌ [FAIL] ") + name)
    if not cond:
        fails.append(name)


def with_winforms(mod):
    key = "webview.platforms.winforms"
    saved = sys.modules.get(key)
    if mod is None:
        sys.modules[key] = None          # import 가 ImportError 를 던지게
    else:
        sys.modules[key] = mod
    try:
        return app._webview2_missing()
    finally:
        if saved is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = saved


check("WebView2 있음 → 정상 진행", with_winforms(types.SimpleNamespace(is_chromium=True)) is False)
check("WebView2 없음(MSHTML 대체) → 안내", with_winforms(types.SimpleNamespace(is_chromium=False)) is True)
check("판정 실패 → 막지 않음", with_winforms(None) is False)

# main(): 안내가 필요하면 창을 만들지 않는다
shown, created = [], []
app._webview2_missing = lambda: True
app._show_webview2_help = lambda: shown.append(1)
webview.create_window = lambda **k: created.append(1)
webview.start = lambda **k: created.append("start")
app.main()
check("WebView2 없음: 안내 표시", shown == [1])
check("WebView2 없음: 창·웹뷰 시작 안 함", created == [])

print(f"\n{len(fails)} 실패" if fails else "\n전부 통과")
sys.exit(1 if fails else 0)
