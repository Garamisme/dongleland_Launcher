"""game_installer.py — 게임 파일 설치 (v3 Phase 2).

책임:
  Mojang piston-meta 에서 대상 버전(app_meta.GAME_VERSION)의
  client.jar / libraries / assets / natives 를 격리 인스턴스에 다운로드하고,
  Fabric 로더 프로필을 설치한다. 전부 minecraft-launcher-lib(mll) 에 위임.

  다운로드 출처는 Mojang 공식 CDN(piston-meta/piston-data/resources)뿐 —
  mll 이 버전 JSON 의 공식 URL 만 따라가므로 재배포 이슈 없음 (ToS §3.3).

진행률:
  mll 콜백(setStatus/setProgress/setMax) → on_progress(pct:int, msg:str)
  단일 콜백으로 변환해 기존 UI 진행률 배관(onProgress push)에 그대로 태운다.
  바닐라 설치 0~80%, Fabric 설치 80~100% 로 구간 배분.
"""

import os
import shutil
import sys
import threading

import app_meta
import instance
import preflight

from minecraft_launcher_lib import fabric as _fabric
from minecraft_launcher_lib import install as _install
from minecraft_launcher_lib import runtime as _runtime
from minecraft_launcher_lib import utils as _utils


class InstallError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InstallCancelled(Exception):
    """사용자가 설치를 취소함."""
    def __init__(self, message="설치를 취소했습니다."):
        super().__init__(message)
        self.message = message


# 설치/검증 취소 신호 (스레드 간 공유)
_cancel = threading.Event()


def request_cancel():
    """진행 중인 설치/검증을 취소 요청."""
    _cancel.set()


def clear_cancel():
    _cancel.clear()


def is_cancelled() -> bool:
    return _cancel.is_set()


# mll 이 setStatus 로 알려주는 단계 → (한글 라벨, 전체 중 몇 번째)
_STAGES = {
    "Download Libraries": ("라이브러리", 1),
    "Download Assets": ("리소스", 2),
    "Install java runtime": ("Java 런타임", 3),
    "Installation complete": ("마무리", 4),
}
_STAGE_TOTAL = 4


def _make_callback(on_progress, base: float = 0, span: float = 99):
    """mll CallbackDict 생성.

    mll 은 단계(Download Libraries / Download Assets / Install java runtime)마다
    setMax 를 새로 호출하고 setProgress 를 0 부터 다시 올린다.
    → 단계 비율을 그대로 %로 쓰면 100% → 0% 로 널뛴다.

    이전에는 남은 구간을 점근적으로 소비해 단조 증가를 만들었지만,
    그러면 끝에서 퍼센트가 멈춰 보인다(NN/g 가 지적하는 안티패턴).

    지금은 **전체 %를 추정하지 않고** 정직하게 알린다:
      - 현재 단계 이름과 단계 번호 (예: 리소스 2/4)
      - 그 단계의 실제 진행 (예: 342/1200 파일)
    on_progress(pct, msg, detail) 로 전달한다.
      pct    : 현재 단계 내 퍼센트 (0~100) — 진행바용
      detail : {"stage":"리소스", "stage_no":2, "stage_total":4,
                "cur":342, "max":1200, "raw":"Download Assets"}
    """
    state = {"max": 0, "cur": 0, "status": "",
             "stage": "준비", "stage_no": 0}

    def _emit():
        if _cancel.is_set():
            raise InstallCancelled()
        if not on_progress:
            return
        mx = state["max"]
        pct = int(min(state["cur"] / mx, 1.0) * 100) if mx > 0 else 0
        detail = {
            "stage": state["stage"],
            "stage_no": state["stage_no"],
            "stage_total": _STAGE_TOTAL,
            "cur": state["cur"],
            "max": mx,
            "raw": state["status"],
        }
        try:
            on_progress(pct, state["status"], detail)
        except InstallCancelled:
            raise
        except TypeError:
            # 2-인자 콜백 하위호환
            on_progress(pct, state["status"])
        except Exception:
            pass

    def set_status(s):
        s = str(s)
        state["status"] = s
        if s in _STAGES:
            state["stage"], state["stage_no"] = _STAGES[s]
            state["cur"] = 0            # 새 단계 시작
        _emit()

    def set_progress(v):
        state["cur"] = int(v)
        _emit()

    def set_max(v):
        state["max"] = max(int(v), 0)
        state["cur"] = 0
        _emit()

    return {"setStatus": set_status, "setProgress": set_progress, "setMax": set_max}

    return {"setStatus": set_status, "setProgress": set_progress, "setMax": set_max}


def fabric_version_id(loader_version: str, mc_version: str | None = None) -> str:
    """Fabric 설치 결과로 생성되는 버전 id (versions/ 폴더명 규칙)."""
    return f"fabric-loader-{loader_version}-{mc_version or app_meta.GAME_VERSION}"


def is_installed() -> bool:
    """설치 완료 상태인지 (state.json 기록 + 버전 JSON 실재 확인)."""
    return instance.is_version_ready()


def _is_file_locked(path: str) -> bool:
    """다른 프로세스가 이 파일을 잡고 있는지 (Windows 기준).

    쓰기 모드로 열어보고 PermissionError 가 나면 잠긴 것으로 본다.
    파일이 없으면 잠기지 않은 것.
    """
    if not os.path.isfile(path):
        return False
    try:
        with open(path, "a+b"):
            pass
        return False
    except PermissionError:
        return True
    except OSError:
        return True


def _assert_installable():
    """설치를 시작해도 되는 상태인지 확인.

    실행 중인 게임이 버전 jar 를 잠그고 있으면 설치가 실패하므로
    (java.nio.file.FileSystemException), 미리 막고 사용자에게 안내한다.

    강제 종료(taskkill)는 하지 않는다 — 잠근 프로세스가 플레이 중인
    마인크래프트일 수 있고, 강제로 죽이면 월드 데이터가 손상될 수 있다.
    """
    # 1) 우리가 띄운 게임이 실행 중인가
    try:
        import launcher
        if launcher.is_game_running():
            raise InstallError(
                "마인크래프트가 실행 중입니다.\n"
                "게임을 완전히 종료한 뒤 다시 시도해주세요.")
    except InstallError:
        raise
    except Exception:
        pass

    # 2) 설치 대상 폴더의 jar 가 잠겨 있는가 (공식 런처로 켠 경우 등)
    try:
        versions = os.path.join(instance.instance_dir(), "versions")
        if os.path.isdir(versions):
            for name in os.listdir(versions):
                jar = os.path.join(versions, name, name + ".jar")
                if _is_file_locked(jar):
                    raise InstallError(
                        "게임 파일이 사용 중이라 설치할 수 없습니다.\n"
                        f"({name})\n\n"
                        "실행 중인 마인크래프트를 완전히 종료한 뒤\n"
                        "다시 시도해주세요.")
    except InstallError:
        raise
    except Exception:
        pass


def install(on_progress=None) -> dict:
    """바닐라 + Fabric 설치 (블로킹 — 호출측에서 스레드 처리).

    반환: {"ok":True, "version_id":..., "mc_version":..., "loader_version":...}
    실패: InstallError (한글 메시지) / InstallCancelled (사용자 취소)
    """
    clear_cancel()
    _assert_installable()
    mc_version = app_meta.GAME_VERSION
    mc_dir = instance.ensure_dirs()
    preflight.write_log(f"[설치] 시작 mc_version={mc_version}")

    # 0) 대상 버전이 Mojang 매니페스트에 실재하는지 선확인 (오타/미출시 방지)
    try:
        if not _utils.is_version_valid(mc_version, mc_dir):
            raise InstallError(
                f"마인크래프트 {mc_version} 버전을 찾을 수 없습니다.\n"
                "버전 표기(app_meta.GAME_VERSION)를 확인해주세요.")
    except InstallError:
        raise
    except Exception:
        pass  # 매니페스트 조회 실패는 아래 설치 단계에서 다시 드러남

    # 1) Fabric 지원 여부 + 최신 안정 로더 버전 결정
    try:
        if not _fabric.is_minecraft_version_supported(mc_version):
            raise InstallError(
                f"Fabric 이 아직 {mc_version} 을 지원하지 않습니다.")
        loader_version = _pick_stable_loader()
    except InstallError:
        raise
    except Exception as e:
        raise InstallError(f"Fabric 메타 조회에 실패했습니다:\n{e}")

    # 2) Fabric 설치.
    #    ⚠️ 근본 원인(WinError 2): mll 의 install_fabric 은 Fabric 설치 프로그램(jar)을
    #       실행할 때 java= 인자를 안 주면 시스템 PATH 의 맨 "java" 를 존재 확인 없이
    #       그대로 subprocess 에 넘긴다(minecraft_launcher_lib/fabric.py). 시스템에
    #       Java 가 전혀 없는 첫 사용자는 여기서 FileNotFoundError(WinError 2)로 죽는다.
    #       → 바닐라를 먼저 우리가 설치해 Mojang 런타임을 확보하고, 그 절대경로를
    #         java= 로 넘겨 PATH 의존을 완전히 제거한다.
    #    (install_fabric 도 내부에서 install_minecraft_version 을 다시 부르지만
    #     sha1 이 일치하므로 재다운로드 없이 즉시 통과한다.)
    # 설치 진행은 0~99% 까지만. 100% 는 아래 검증을 통과한 뒤에만 내보낸다.
    cb = _make_callback(on_progress, base=0, span=99)
    try:
        _install.install_minecraft_version(mc_version, mc_dir, callback=cb)
        java = _resolve_installer_java(mc_version, mc_dir)
        preflight.write_log(f"[설치] Fabric 설치 프로그램 java={java or '(PATH)'}")
        _fabric.install_fabric(
            mc_version, mc_dir, loader_version=loader_version, callback=cb, java=java)
    except InstallCancelled:
        preflight.write_log("[설치] 사용자 취소")
        raise
    except Exception as e:
        text = str(e)
        # 설치 도중 게임이 켜져 파일이 잠긴 경우 (FileSystemException / PermissionError)
        if ("다른 프로세스" in text or "being used by another process" in text
                or "FileSystemException" in text or isinstance(e, PermissionError)):
            preflight.write_log(f"[설치실패] 파일 사용 중: {e}")
            raise InstallError(
                "게임 파일이 사용 중이라 설치를 마치지 못했습니다.\n"
                "실행 중인 마인크래프트를 완전히 종료한 뒤 다시 시도해주세요.")
        preflight.write_log(f"[설치실패] {type(e).__name__}: {e}")
        raise InstallError(f"게임 파일 다운로드에 실패했습니다:\n{e}\n"
                           "네트워크 상태를 확인한 뒤 다시 시도해주세요.")

    version_id = fabric_version_id(loader_version, mc_version)
    # 실제로 실행 가능한 상태인지 검증한 뒤에야 '완료' 로 본다.
    if not instance.is_version_ready(version_id):
        preflight.write_log(f"[설치실패] 검증 실패: {version_id}")
        raise InstallError("설치가 완료되지 않았습니다 (버전 파일 누락). 다시 시도해주세요.")

    instance.set_installed_version_id(version_id, mc_version, loader_version)
    preflight.write_log(f"[설치완료] version_id={version_id}")
    # 여기서만 100% (검증 통과 = 게임 실행 가능)
    if on_progress:
        try:
            on_progress(100, "설치 완료", {"stage":"완료","stage_no":4,"stage_total":4,"cur":0,"max":0,"raw":"done"})
        except Exception:
            pass
    return {"ok": True, "version_id": version_id,
            "mc_version": mc_version, "loader_version": loader_version}


def verify_and_repair(on_progress=None) -> dict:
    """실행 전 무결성 검증 + 복구.

    mll 공식 문서: install_minecraft_version 은 설치가 올바른지 검증하고
    기존 설치를 복구하므로 '실행 전에 매번' 호출해야 한다.
    빠졌거나 손상된(sha1 불일치) 파일만 다시 내려받는다.

    로컬에 versions/<id>/<id>.json 이 있으면 그걸 읽어 처리하므로,
    Fabric 버전 id 를 그대로 넘기면 inheritsFrom 을 따라 바닐라까지
    검증·복구하고, javaVersion 이 명시돼 있으면 Java 런타임도 설치한다.

    반환: {"ok":True, "version_id":..., "repaired":bool}
    실패: InstallError / InstallCancelled
    """
    clear_cancel()
    _assert_installable()

    version_id = instance.installed_version_id()
    if not version_id:
        raise InstallError("게임이 설치되어 있지 않습니다. 먼저 게임을 설치해주세요.")

    preflight.write_log(f"[검증] 시작 version_id={version_id}")
    mc_dir = instance.instance_dir()
    json_path = os.path.join(mc_dir, "versions", version_id, f"{version_id}.json")
    if not os.path.isfile(json_path):
        preflight.write_log(f"[검증실패] 버전 정보 없음: {json_path}")
        raise InstallError("게임 파일이 손상되었습니다 (버전 정보 없음).\n"
                           "게임을 다시 설치해주세요.")

    # 복구가 실제로 일어났는지 보기 위해 다운로드 이벤트를 센다
    downloaded = {"n": 0}

    def _wrap(pct, msg, detail=None):
        # mll 은 파일을 받을 때 setStatus("Download <파일명>") 을 부른다
        if msg and str(msg).startswith("Download ") and str(msg) not in (
                "Download Libraries", "Download Assets"):
            downloaded["n"] += 1
        if on_progress:
            on_progress(pct, msg, detail)

    cb = _make_callback(_wrap, base=0, span=99)
    try:
        _install.install_minecraft_version(version_id, mc_dir, callback=cb)
    except InstallCancelled:
        preflight.write_log("[검증] 사용자 취소")
        raise
    except Exception as e:
        text = str(e)
        if ("다른 프로세스" in text or "being used by another process" in text
                or "FileSystemException" in text or isinstance(e, PermissionError)):
            preflight.write_log(f"[검증실패] 파일 사용 중: {e}")
            raise InstallError(
                "게임 파일이 사용 중이라 검증하지 못했습니다.\n"
                "실행 중인 마인크래프트를 완전히 종료한 뒤 다시 시도해주세요.")
        preflight.write_log(f"[검증실패] {type(e).__name__}: {e}")
        raise InstallError(f"게임 파일 검증에 실패했습니다:\n{e}\n"
                           "네트워크 상태를 확인한 뒤 다시 시도해주세요.")

    if not instance.is_version_ready(version_id):
        preflight.write_log(f"[검증실패] 필수 파일 누락: {version_id}")
        raise InstallError("게임 파일 검증에 실패했습니다 (필수 파일 누락).\n"
                           "게임을 다시 설치해주세요.")

    preflight.write_log(f"[검증완료] version_id={version_id} repaired={downloaded['n']>0} files={downloaded['n']}")
    if on_progress:
        try:
            on_progress(100, "검증 완료", {"stage":"완료","stage_no":4,"stage_total":4,"cur":0,"max":0,"raw":"done"})
        except Exception:
            pass
    return {"ok": True, "version_id": version_id,
            "repaired": downloaded["n"] > 0, "files": downloaded["n"]}


def runtime_info() -> dict:
    """이 인스턴스가 요구하는 Mojang 공식 Java 런타임 정보.

    버전 JSON 의 javaVersion 컴포넌트가 정답지다 (Mojang 이 테스트한 JVM).
    최신 LTS 로 올리면 Mixin/ASM 이 새 클래스 파일을 못 읽어 깨질 수 있으므로
    '더 높은 Java' 를 쓰지 않는다.

    반환: {"ok":True, "name":"java-runtime-delta", "major":21,
           "installed":bool, "path":str|None}
          {"ok":False, "reason":...}
    """
    vid = instance.installed_version_id()
    if not vid:
        return {"ok": False, "reason": "not_installed"}
    mc_dir = instance.instance_dir()
    try:
        info = _runtime.get_version_runtime_information(vid, mc_dir)
    except Exception:
        info = None
    if not info:
        # 아주 오래된 버전은 javaVersion 이 없다 → 시스템 Java 폴백
        return {"ok": False, "reason": "no_java_version"}

    name = info["name"]
    path = _runtime.get_executable_path(name, mc_dir)
    return {"ok": True, "name": name,
            "major": info.get("javaMajorVersion"),
            "installed": bool(path), "path": path}


def _resolve_installer_java(mc_version: str, mc_dir: str) -> str | None:
    """Fabric 설치 프로그램(jar)을 실행할 Java 경로.

    근본 해결: 시스템 PATH 에 의존하지 않는다. 방금 확보한 이 버전의 Mojang
    런타임을 최우선으로 쓴다(시스템에 Java 가 전혀 없어도 항상 존재). 못 구하면
    존재가 검증된 시스템 java 로 폴백하고, 그마저 없으면 None 을 반환해 mll 이
    명확한 에러로 드러내게 둔다.
    """
    try:
        info = _runtime.get_version_runtime_information(mc_version, mc_dir)
        if info:
            path = _runtime.get_executable_path(info["name"], mc_dir)
            if path and os.path.isfile(path):
                return path
    except Exception:
        pass
    return shutil.which("java")


def java_executable() -> str | None:
    """인스턴스에 설치된 Mojang 런타임의 실행 파일 경로.

    Windows 에서는 콘솔창이 뜨지 않도록 javaw.exe 를 우선한다.
    설치돼 있지 않으면 None (호출측이 시스템 Java 로 폴백).
    """
    ri = runtime_info()
    if not ri.get("ok") or not ri.get("path"):
        return None
    java = ri["path"]
    if sys.platform == "win32":
        javaw = os.path.join(os.path.dirname(java), "javaw.exe")
        if os.path.isfile(javaw):
            return javaw
    return java


def ensure_runtime(on_progress=None) -> dict:
    """요구 런타임이 없으면 설치. 이미 있으면 즉시 반환.

    install_jvm_runtime 은 sha1 검증 + 병렬 다운로드로 인스턴스 안에 격리 설치한다.
    (관리자 권한/설치 마법사 불필요)
    """
    ri = runtime_info()
    if not ri.get("ok"):
        return ri
    if ri.get("installed"):
        return ri
    preflight.write_log(f"[런타임설치] 시작 name={ri.get('name')} major={ri.get('major')}")
    mc_dir = instance.instance_dir()
    cb = _make_callback(on_progress, base=0, span=99)
    try:
        _runtime.install_jvm_runtime(ri["name"], mc_dir, callback=cb)
    except Exception as e:
        preflight.write_log(f"[런타임설치실패] {type(e).__name__}: {e}")
        raise InstallError(f"Java 런타임 설치에 실패했습니다:\n{e}")
    preflight.write_log(f"[런타임설치완료] name={ri.get('name')} major={ri.get('major')}")
    if on_progress:
        try:
            on_progress(100, "Java 준비 완료", {"stage":"완료","stage_no":4,"stage_total":4,"cur":0,"max":0,"raw":"done"})
        except Exception:
            pass
    return runtime_info()


def check_loader_update() -> dict:
    """설치된 Fabric 로더와 최신 stable 로더를 비교.

    반환:
      {"status":"not_installed"}                       게임 미설치
      {"status":"up_to_date", "installed":...}         최신
      {"status":"update_available", "installed":..., "latest":...}
      {"status":"check_failed", "message":...}         네트워크 오류 등
    """
    try:
        st = instance.load_state()
        installed = st.get("fabric_loader_version")
        if not installed or not instance.is_version_ready():
            return {"status": "not_installed"}
        latest = _pick_stable_loader()
        if latest and latest != installed:
            return {"status": "update_available",
                    "installed": installed, "latest": latest}
        return {"status": "up_to_date", "installed": installed}
    except Exception as e:
        return {"status": "check_failed", "message": str(e)}


def update_loader(on_progress=None) -> dict:
    """Fabric 로더를 최신 stable 로 갱신.

    install_fabric 을 새 loader_version 으로 호출하면
    versions/fabric-loader-<새버전>-<mc> 폴더가 새로 만들어진다.
    설치 검증 후 state.json 을 새 version_id 로 전환하고,
    더 이상 쓰지 않는 옛 로더 폴더는 정리한다.

    반환: {"ok":True, "version_id":..., "loader_version":..., "previous":...}
    실패: InstallError / InstallCancelled
    """
    clear_cancel()
    _assert_installable()

    st = instance.load_state()
    old_loader = st.get("fabric_loader_version")
    old_version_id = st.get("installed_version_id")
    if not old_loader or not instance.is_version_ready():
        raise InstallError("게임이 설치되어 있지 않습니다. 먼저 게임을 설치해주세요.")

    mc_version = app_meta.GAME_VERSION
    mc_dir = instance.ensure_dirs()

    try:
        new_loader = _pick_stable_loader()
    except Exception as e:
        raise InstallError(f"최신 Fabric 로더 정보를 가져오지 못했습니다:\n{e}")

    if new_loader == old_loader:
        return {"ok": True, "version_id": old_version_id,
                "loader_version": old_loader, "previous": old_loader,
                "unchanged": True}

    cb = _make_callback(on_progress, base=0, span=99)
    # 근본 원인 동일 (install() 주석 참고): 기존 설치가 있으므로 런타임은 이미
    # 존재 → 그 절대경로를 java= 로 넘겨 PATH 의존 제거.
    java = _resolve_installer_java(mc_version, mc_dir)
    try:
        _fabric.install_fabric(
            mc_version, mc_dir, loader_version=new_loader, callback=cb, java=java)
    except InstallCancelled:
        raise
    except Exception as e:
        text = str(e)
        if ("다른 프로세스" in text or "being used by another process" in text
                or "FileSystemException" in text or isinstance(e, PermissionError)):
            raise InstallError(
                "게임 파일이 사용 중이라 업데이트를 마치지 못했습니다.\n"
                "실행 중인 마인크래프트를 완전히 종료한 뒤 다시 시도해주세요.")
        raise InstallError(f"Fabric 로더 업데이트에 실패했습니다:\n{e}")

    new_version_id = fabric_version_id(new_loader, mc_version)
    if not instance.is_version_ready(new_version_id):
        raise InstallError("업데이트가 완료되지 않았습니다 (버전 파일 누락). 다시 시도해주세요.")

    # 검증 통과 → 새 버전으로 전환
    instance.set_installed_version_id(new_version_id, mc_version, new_loader)
    _cleanup_old_version(old_version_id, keep=new_version_id)

    if on_progress:
        try:
            on_progress(100, "업데이트 완료", {"stage":"완료","stage_no":4,"stage_total":4,"cur":0,"max":0,"raw":"done"})
        except Exception:
            pass
    return {"ok": True, "version_id": new_version_id,
            "loader_version": new_loader, "previous": old_loader}


def _cleanup_old_version(version_id: str | None, keep: str):
    """더 이상 쓰지 않는 옛 Fabric 로더 버전 폴더 제거.

    바닐라 버전 폴더(26.1.2 등)는 새 로더도 상속해 쓰므로 절대 지우지 않는다.
    실패해도 무시 (디스크만 조금 쓸 뿐).
    """
    if not version_id or version_id == keep:
        return
    if not version_id.startswith("fabric-loader-"):
        return  # 안전장치: fabric 로더 폴더만 대상
    try:
        import shutil
        target = os.path.join(instance.instance_dir(), "versions", version_id)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
    except Exception:
        pass


def _pick_stable_loader() -> str:
    """가장 최신의 stable 로더 버전. stable 이 없으면 최신."""
    loaders = _fabric.get_all_loader_versions()
    for entry in loaders:  # 최신순 정렬로 제공됨
        if entry.get("stable"):
            return entry["version"]
    return _fabric.get_latest_loader_version()
