"""앱 메타 정보 — 버전, 작성자, 게임 버전 등 공용 상수.

앱 전역에서 공유하는 상수를
tkinter 파일을 쓰지 않으므로 여기로 분리해 백엔드/브릿지가 공유한다.
"""

APP_VERSION = "3.1.2"
# 릴리스 채널: "beta" 면 UI 에 베타 표식을 붙인다. 정식 배포 시 "release" 로.
APP_CHANNEL = "release"

# 약관 버전. 내용이 실질적으로 바뀌면 올린다 → 사용자에게 재동의를 받는다.
TERMS_VERSION = "1.0"
_REPO = "https://github.com/Garamisme/dongleland_Launcher"
# blob/HEAD 는 GitHub 가 기본 브랜치(main/master)로 알아서 해석한다.
TERMS_URL = f"{_REPO}/blob/HEAD/TERMS.md"
NOTICES_URL = f"{_REPO}/blob/HEAD/THIRD_PARTY_NOTICES.md"
APP_AUTHOR = "Garamisme"
GAME_VERSION = "26.1.2"
LOADER = "fabric"

# 동글랜드 서버 (플레이 탭 상태 표시용 + v3 자동 접속 대상)
SERVER_HOST = "dongleland.com"
SERVER_PORT = 25565

# v3: Microsoft 로그인용 Azure 앱 Application(client) ID.
# 비밀값 아님(공개 가능). Azure Portal 등록 + Mojang 승인 폼
# (aka.ms/mce-reviewappid) 완료 후 실제 값으로 교체할 것. — auth.py 참고
AZURE_CLIENT_ID = "c34feb67-8219-4662-abfc-29b1c8045953"
