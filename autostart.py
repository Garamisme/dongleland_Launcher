"""autostart.py — Windows 시작 프로그램 등록 (HKCU Run 키).

레지스트리 `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run` 에 값을
하나 넣고 빼는 게 전부다. 표준 라이브러리(`winreg`)만 쓰고 관리자 권한도
필요 없다. 값 이름은 `app_meta.STARTUP_REG_NAME` (제품별 심 — 다른 제품과
서로의 등록을 덮지 않게).

주의 두 가지:

1. **얼린 exe 에서만 의미가 있다.** 개발 실행(`python app.py`)에서는
   `sys.executable` 이 python.exe 라, 등록해도 부팅 때 런처가 아니라 파이썬이
   뜬다. → `supported()` 로 막는다.
2. **작업 관리자 → 시작 프로그램에서 '사용 안 함'** 하면 Windows 가
   `Explorer\\StartupApproved\\Run` 에 따로 기록한다. Run 키는 그대로 남아
   있는데 실행은 되지 않는다. 우리가 다시 써도 안 먹고, 사용자 의사를 뒤집는
   것이라 **되돌리지 않고 알리기만** 한다(`blocked()`).
"""

import sys

import app_meta

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"


def supported() -> bool:
    """등록이 실제로 의미 있는 환경인가 (Windows + PyInstaller 로 얼린 exe)."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def _command() -> str:
    """부팅 시 실행될 커맨드. 경로에 공백이 있으므로 반드시 따옴표."""
    return f'"{sys.executable}" --autostart'


def is_enabled() -> bool:
    """Run 키에 우리 값이 있는가."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, app_meta.STARTUP_REG_NAME)
        return True
    except OSError:
        return False


def blocked() -> bool:
    """사용자가 작업 관리자에서 '사용 안 함' 했는가 (Run 키가 있어도 안 뜨는 상태).

    StartupApproved 값은 12바이트 바이너리로, 첫 바이트가 홀수면 사용 안 함
    (0x02/0x06 = 사용, 0x03 = 사용 안 함). 문서화된 포맷이 아니라 표시용 추정치다.
    """
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _APPROVED_KEY) as key:
            data, _ = winreg.QueryValueEx(key, app_meta.STARTUP_REG_NAME)
        return bool(data) and (data[0] % 2 == 1)
    except OSError:
        return False


def set_enabled(on: bool) -> dict:
    """등록/해제. 반환: {"ok":bool, "enabled":bool, "message":str}"""
    if sys.platform != "win32":
        return {"ok": False, "enabled": False,
                "message": "시작 프로그램 등록은 Windows 에서만 지원합니다."}
    if on and not supported():
        return {"ok": False, "enabled": is_enabled(),
                "message": "개발 실행에서는 시작 프로그램을 등록할 수 없습니다.\n"
                           "빌드된 런처(exe)에서 사용해주세요."}
    try:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, app_meta.STARTUP_REG_NAME, 0,
                                  winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, app_meta.STARTUP_REG_NAME)
                except FileNotFoundError:
                    pass  # 이미 없음 = 원하는 상태
    except OSError as e:
        return {"ok": False, "enabled": is_enabled(),
                "message": f"시작 프로그램 설정에 실패했습니다: {e}"}
    return {"ok": True, "enabled": bool(on), "message": ""}


def status() -> dict:
    """{"supported":bool, "enabled":bool, "blocked":bool}"""
    return {"supported": supported(), "enabled": is_enabled(), "blocked": blocked()}
