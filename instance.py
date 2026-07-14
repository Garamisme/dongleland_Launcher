"""instance.py — 동글랜드 전용 격리 인스턴스 관리 (v3 신규).

핵심 원칙 (HANDOFF_v3_CLIENT.md §1.1):
  공유 .minecraft 대신 자체 게임 디렉토리를 쓴다.
  → 바닐라/타 모드팩과 충돌 없음, modcheck 경로 문제 원천 해소.

디렉토리 구조 (v3.x 멀티 프로필 대비 — 지금은 dongleland 프로필만 사용):
  %APPDATA%/DonglelandLauncher/
    ├─ instances/
    │   └─ dongleland/      ← minecraft-launcher-lib 의 minecraft_directory
    │   ├─ versions/        (버전 JSON + client.jar + fabric 프로필)
    │   ├─ libraries/
    │   ├─ assets/
    │   ├─ mods/            ← modrinth_api 설치 대상 (v3 전환 시)
    │   ├─ shaderpacks/
    │   └─ options.txt 등 게임 데이터
    ├─ account.dat          ← 암호화된 계정 토큰 (auth.py) — 계정은 전역(프로필 무관)
    └─ instances/<id>/state.json  ← 프로필별 설치 상태

멀티 프로필 확장 시: profile_id 파라미터만 실값으로 넘기면 됨.
지금 구조를 미리 파두는 이유 — 첫 실제 설치 후 경로를 바꾸면
유저 전원이 게임 파일 전체를 재다운로드하게 되므로, 설치 0명인
지금 확정한다.

컨테이너/비 Windows 에서는 APPDATA 가 없으므로 ~ 아래로 폴백 (테스트용).
"""

import json
import os

APP_DIR_NAME = "DonglelandLauncher"
DEFAULT_PROFILE = "dongleland"


def root_dir() -> str:
    """클라이언트 루트 (%APPDATA%/DonglelandClient)."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_DIR_NAME)


def instance_dir(profile_id: str = DEFAULT_PROFILE) -> str:
    """게임 인스턴스 디렉토리 = launcher-lib 의 minecraft_directory."""
    return os.path.join(root_dir(), "instances", profile_id)


def mods_dir() -> str:
    return os.path.join(instance_dir(), "mods")


def shaderpacks_dir() -> str:
    return os.path.join(instance_dir(), "shaderpacks")


def resourcepacks_dir() -> str:
    return os.path.join(instance_dir(), "resourcepacks")


def account_path() -> str:
    """[구] 단일 계정 파일 (마이그레이션 원본)."""
    return os.path.join(root_dir(), "account.dat")


def accounts_path() -> str:
    """[신] 다중 계정 저장 파일 (auth.py 가 사용)."""
    return os.path.join(root_dir(), "accounts.dat")


def state_path(profile_id: str = DEFAULT_PROFILE) -> str:
    """설치 상태는 프로필별 (인스턴스 폴더 안)."""
    return os.path.join(instance_dir(profile_id), "state.json")


def ensure_dirs() -> str:
    """루트/인스턴스/mods/shaderpacks/resourcepacks 디렉토리 생성. 인스턴스 경로 반환."""
    for d in (root_dir(), instance_dir(), mods_dir(), shaderpacks_dir(),
              resourcepacks_dir()):
        os.makedirs(d, exist_ok=True)
    return instance_dir()


# ── 설치 상태 (state.json) ────────────────────────────────────────────────

def load_state() -> dict:
    try:
        with open(state_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict):
    os.makedirs(root_dir(), exist_ok=True)
    tmp = state_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, state_path())


def installed_version_id() -> str | None:
    """설치 완료된 실행 대상 버전 id (예: 'fabric-loader-0.16.x-26.1.2').

    game_installer 가 설치 성공 시 기록. 실행(launcher.py)은 이 값을 쓴다.
    """
    return load_state().get("installed_version_id")


def set_installed_version_id(version_id: str, mc_version: str, loader_version: str):
    st = load_state()
    st["installed_version_id"] = version_id
    st["mc_version"] = mc_version
    st["fabric_loader_version"] = loader_version
    save_state(st)


def _version_json_path(vid: str) -> str:
    return os.path.join(instance_dir(), "versions", vid, f"{vid}.json")


def _version_jar_path(vid: str) -> str:
    return os.path.join(instance_dir(), "versions", vid, f"{vid}.jar")


def is_version_ready(version_id: str | None = None) -> bool:
    """실제로 실행 가능한 상태인지 구조적으로 확인.

    ⚠️ 이전 구현은 versions/<id>/<id>.json 존재만 봤다. 그러면 client.jar 나
    라이브러리가 하나도 없어도 '설치 완료' 로 판정된다.
    여기서는 최소한 다음을 확인한다:
      1) 버전 JSON 존재
      2) inheritsFrom 이 있으면 부모(바닐라) JSON 도 존재
      3) 실행에 쓰이는 client.jar 가 존재 (Fabric 은 부모 jar 를 상속)

    파일 하나하나의 sha1 무결성까지는 보지 않는다. 그건 비싸므로
    game_installer.verify_and_repair() (mll install_minecraft_version) 가 맡는다.
    """
    vid = version_id or installed_version_id()
    if not vid:
        return False
    j = _version_json_path(vid)
    if not os.path.isfile(j):
        return False

    try:
        with open(j, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False   # JSON 이 깨졌으면 준비 안 된 것

    # 상속 구조(Fabric): 부모 바닐라 버전이 있어야 한다
    parent = data.get("inheritsFrom")
    if parent:
        if not os.path.isfile(_version_json_path(parent)):
            return False
        # Fabric 버전 폴더엔 jar 가 없고 부모의 jar 를 쓴다
        if not os.path.isfile(_version_jar_path(parent)):
            return False
        return True

    # 바닐라 단독 버전이면 자기 jar 가 있어야 한다
    return os.path.isfile(_version_jar_path(vid))
