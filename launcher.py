"""launcher.py — 게임 직접 실행 + 동글랜드 서버 자동 접속 (v3 Phase 3).

preflight.launch_minecraft()(공식 런처 열기)를 대체한다.

커맨드 조립은 mll 의 get_minecraft_command 에 위임:
  classpath + Fabric KnotClient 메인클래스 + JVM 인자 +
  게임 인자(username/uuid/accessToken/version/assets/gameDir) 를
  버전 JSON 규칙대로 생성. 여기에 우리가 얹는 것:
    - executablePath: preflight 가 찾은 Java 21+ (javaw 우선)
    - quickPlayMultiplayer: "dongleland.com" → 실행 즉시 서버 입장
      (모던 클라이언트가 SRV 자동 해석 → mvp2.dongleland.com:25565)
    - -Xmx 메모리 인자

Java 는 preflight.find_valid_java() 재사용 (HANDOFF §5.4 — 핵심 자산).
"""

import os
import subprocess
import sys

import app_meta
import auth
import instance
import preflight

from minecraft_launcher_lib import command as _command


class LaunchError(Exception):
    def __init__(self, message: str, code: str = "launch_failed"):
        super().__init__(message)
        self.message = message
        self.code = code


DEFAULT_MAX_MEM_MB = 4096


def _java_executable() -> str:
    """실행에 쓸 java 경로.

    우선순위:
      1) 인스턴스에 설치된 Mojang 공식 런타임 (버전 JSON 의 javaVersion)
         → Mojang 이 그 버전으로 테스트한 정확한 JVM. 격리돼 있어 시스템 영향 없음.
      2) 시스템 Java (구버전처럼 javaVersion 이 없는 경우의 폴백)

    ⚠️ '더 최신 Java' 를 쓰지 않는다. Java 가 요구보다 높으면 Mixin/ASM 이
       새 클래스 파일을 읽지 못해(Unsupported class file major version) 깨진다.
    Windows 에서는 콘솔창이 뜨지 않도록 javaw 를 우선한다.
    """
    # 1) 인스턴스 런타임
    try:
        import game_installer
        java = game_installer.java_executable()
        if java:
            return java
    except Exception:
        pass

    # 2) 시스템 Java 폴백
    info = preflight.find_valid_java()
    if not info:
        raise LaunchError(
            "게임 실행에 필요한 Java 를 찾을 수 없습니다.\n"
            "게임을 다시 실행하면 자동으로 내려받습니다.",
            code="no_java")
    java = info["path"] if isinstance(info, dict) else info
    if java == "java":
        return "javaw" if sys.platform == "win32" else "java"
    if sys.platform == "win32" and os.path.basename(java).lower().startswith("java"):
        javaw = os.path.join(os.path.dirname(java), "javaw.exe")
        if os.path.isfile(javaw):
            return javaw
    return java


def build_command(account: dict, *, quick_connect: bool = True,
                  max_mem_mb: int = DEFAULT_MAX_MEM_MB) -> list[str]:
    """실행 커맨드 조립 (실행은 안 함 — 테스트 가능하도록 분리)."""
    version_id = instance.installed_version_id()
    if not version_id or not instance.is_version_ready(version_id):
        raise LaunchError("게임이 설치되지 않았습니다.\n먼저 설치를 진행해주세요.",
                          code="not_installed")

    options = {
        "username": account["mc_username"],
        "uuid": account["mc_uuid"],
        "token": account["mc_access_token"],
        "executablePath": _java_executable(),
        "jvmArguments": [f"-Xmx{max_mem_mb}M"],
        "launcherName": "DonglelandClient",
        "launcherVersion": app_meta.APP_VERSION,
        "gameDirectory": instance.instance_dir(),
    }
    if quick_connect:
        # 도메인만 넘기면 클라이언트가 SRV 해석 (HANDOFF §5.1)
        options["quickPlayMultiplayer"] = app_meta.SERVER_HOST

    return _command.get_minecraft_command(
        version_id, instance.instance_dir(), options)


_running_proc = None  # 마지막으로 실행한 게임 프로세스 (실행중 여부 확인용)


def launch(*, quick_connect: bool = True,
           max_mem_mb: int = DEFAULT_MAX_MEM_MB) -> dict:
    """로그인 계정 확보(자동 갱신 포함) → 커맨드 조립 → 게임 프로세스 실행.

    반환: {"ok":True, "pid":int, "version_id":str, "username":str}
    실패: LaunchError / auth.AuthError
    """
    global _running_proc
    account = auth.get_account()  # 만료 시 자동 리프레시, 불가 시 AuthError(relogin)
    cmd = build_command(account, quick_connect=quick_connect,
                        max_mem_mb=max_mem_mb)

    kwargs: dict = {"cwd": instance.instance_dir()}
    if sys.platform == "win32":
        # 런처와 분리된 독립 프로세스 + 콘솔창 없이
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except Exception as e:
        raise LaunchError(f"게임 프로세스 실행에 실패했습니다:\n{e}")

    _running_proc = proc
    return {"ok": True, "pid": proc.pid,
            "version_id": instance.installed_version_id(),
            "username": account["mc_username"]}


def is_game_running() -> bool:
    """마지막으로 실행한 게임 프로세스가 아직 살아있는지."""
    global _running_proc
    if _running_proc is None:
        return False
    # poll() 이 None 이면 아직 실행 중, 아니면 종료됨(종료코드 반환)
    if _running_proc.poll() is None:
        return True
    _running_proc = None
    return False
