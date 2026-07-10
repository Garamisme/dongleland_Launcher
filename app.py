"""app.py — pywebview 진입점 (v3).

pywebview(WebView2) 기반 v3 진입점.
백엔드 3모듈(modrinth_api, preflight, mod_catalog)은 그대로 재사용하고,
UI 는 frontend/ 의 HTML 을 WebView2 로 렌더링한다.

Nether Glass HTML UI 를 WebView2 로 렌더링하고,
Api 클래스를 js_api 브릿지로 연결한다.
"""

import os
import sys

import webview

from api import Api
import app_meta


def _resource(rel: str) -> str:
    """PyInstaller onefile 에서도 동작하는 리소스 경로 해석."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def main():
    # Windows 작업표시줄 아이콘 그룹화 (tkinter 판과 동일 로직)
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "dongleland.modinstaller.2"
        )
    except Exception:
        pass

    api = Api()

    html_path = _resource(os.path.join(
        "frontend", "nether-glass-launcher-standalone.html"
    ))

    window = webview.create_window(
        title=f"동글랜드 런처 v{app_meta.APP_VERSION}",
        url=html_path,
        js_api=api,
        width=1000,
        height=720,
        min_size=(880, 640),
        frameless=True,       # OS 타이틀바 제거 → HTML 커스텀 타이틀바 사용
        easy_drag=False,      # 전체 드래그 비활성 (제목표시줄 drag-region 만 이동)
    )
    api._window = window  # Python→JS push(evaluate_js)용 참조

    # 앱 종료 시 플레이 시간 세션을 최종 정리(누적). 종료 경로가 여러 개라
    # (창 X, OS 종료, 코드 destroy) 가능한 모든 이벤트에 같은 정리를 건다.
    def _finalize_session():
        try:
            api._flush_playtime()
            api._config["session_start"] = None
            import preflight as _pf
            _pf.save_config(api._config)
        except Exception:
            pass

    api._finalize_session = _finalize_session   # win_close 등에서도 호출 가능
    try:
        window.events.closing += _finalize_session   # 창 닫히기 직전
    except Exception:
        pass
    try:
        window.events.closed += _finalize_session    # 완전히 닫힌 뒤(백업)
    except Exception:
        pass

    # 어떤 HTML 을 로드하는지 콘솔에 남긴다(파일 혼동 방지 진단).
    print(f"[app.py] loading HTML: {html_path}", flush=True)

    # ★ 파이썬 쪽에서 부트를 확실히 트리거한다 ★
    #   JS 폴링만으로도 되지만, DOM 로드 완료(loaded) 시점에 Python 이
    #   evaluate_js 로 bootFromBackend() 를 한 번 더 호출해 이중 안전망을
    #   둔다. bootFromBackend 는 idempotent(중복 무시)라 두 번 불려도 안전.
    def _trigger_boot():
        try:
            window.evaluate_js(
                "window.bootFromBackend ? (bootFromBackend(), 'boot triggered')"
                " : 'bootFromBackend missing'"
            )
            print("[app.py] boot triggered via evaluate_js", flush=True)
        except Exception as e:
            print(f"[app.py] evaluate_js failed: {e}", flush=True)

    # pywebview 버전에 따라 loaded 이벤트 접근 방식이 다르다 — 둘 다 대응.
    try:
        window.events.loaded += _trigger_boot            # pywebview 4.x+
        print("[app.py] hooked window.events.loaded", flush=True)
    except AttributeError:
        try:
            window.loaded += _trigger_boot               # 구버전
            print("[app.py] hooked window.loaded", flush=True)
        except Exception as e:
            print(f"[app.py] could not hook loaded event: {e}", flush=True)

    # 릴리스 빌드는 debug=False (exe 에서 devtools 안 뜨게).
    # 개발 중 브릿지/화면 디버깅이 필요하면 잠시 debug=True 로 바꿔 우클릭→검사 사용.
    webview.start(debug=False)


if __name__ == "__main__":
    main()
