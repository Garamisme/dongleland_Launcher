<div align="center">

<img src="frontend/app_icon.png" width="96" alt="" />

# 동글랜드 런처

**동글랜드 서버 전용 Minecraft: Java Edition 클라이언트**

설치부터 접속까지, 클릭 한 번으로.

<img src="https://img.shields.io/badge/version-3.0.0-6c8cff" alt="version" />
<img src="https://img.shields.io/badge/Minecraft-26.1.2-3ea36a" alt="minecraft" />
<img src="https://img.shields.io/badge/loader-Fabric-d8a531" alt="fabric" />
<img src="https://img.shields.io/badge/platform-Windows-888" alt="platform" />

</div>

---

## 이게 뭔가요

동글랜드 런처는 사설 서버 **dongleland.com** 에 접속하기 위한 마인크래프트 클라이언트입니다.

게임을 따로 설치하거나, Fabric을 깔거나, 모드를 하나씩 받을 필요가 없습니다.
런처가 알아서 준비하고, 실행하면 곧바로 서버로 들어갑니다.

> **정품 Minecraft: Java Edition 계정이 필요합니다.**
> 런처는 게임이나 계정을 제공하지 않으며, 정품 인증을 우회하지 않습니다.

---

## 주요 기능

| | |
|---|---|
| 🔑 **Microsoft 계정 로그인** | 여러 계정을 저장해두고 바꿔가며 사용 |
| 📦 **게임 자동 설치** | 버전·Fabric·에셋을 알아서 내려받고, 실행 시 서버 자동 접속 |
| ☕ **Java 자동 준비** | Mojang 공식 런타임을 게임에 맞춰 설치 (관리자 권한 불필요) |
| 🧩 **모드 & 셰이더팩** | 큐레이션된 45개 모드, 필수 종속 모드 자동 설치, 버전 되돌리기 |
| 🛠 **파일 자동 복구** | 실행 전 손상·누락된 파일을 검증하고 다시 받음 |
| 🎨 **스킨 관리** | 스킨을 저장하고 3D로 미리보며 전환 |
| ⚙️ **메모리 설정** | 시스템 RAM에 맞춘 권장값과 과다 할당 경고 |

게임은 **격리된 인스턴스**(`%APPDATA%\DonglelandLauncher\instances\dongleland`)에 설치됩니다.
기존 `.minecraft` 폴더와 월드는 건드리지 않습니다.

---

## 설치

1. [Releases](https://github.com/Garamisme/dongleland_Launcher/releases/latest) 에서 최신 `.exe` 를 내려받습니다.
2. 실행합니다. 설치 과정은 없습니다.

Windows 10/11 이라면 대부분 그대로 실행됩니다.

<details>
<summary><b>"Windows의 PC 보호" 창이 뜬다면</b></summary>

코드 서명 인증서가 없어서 나오는 경고입니다. 악성코드라는 뜻이 아닙니다.

**추가 정보** → **실행** 을 누르면 됩니다.

</details>

<details>
<summary><b>실행이 안 될 때</b></summary>

**WebView2 런타임**이 필요합니다. Windows 10/11 에는 보통 기본 포함되어 있지만,
없다면 [Microsoft 공식 페이지](https://developer.microsoft.com/microsoft-edge/webview2/)에서 설치하세요.

그래도 안 되면 `%APPDATA%\DonglelandLauncher\launcher.log` 를 첨부해 이슈를 남겨주세요.

</details>

---

## 소스에서 실행하기

Python 3.10 이상이 필요합니다.

```bash
git clone https://github.com/Garamisme/dongleland_Launcher.git
cd dongleland_Launcher

pip install -r requirements.txt
python app.py
```

### exe 빌드

```bash
build.bat
```

PyInstaller로 `dist/` 에 단일 실행 파일이 생성됩니다.

---

## 프로젝트 구조

```
app.py               진입점 (pywebview 창 생성)
api.py               프론트엔드 ↔ 백엔드 브릿지
auth.py              Microsoft OAuth (authorization code + PKCE)
game_installer.py    게임/Fabric 설치, 검증·복구, Java 런타임
launcher.py          실행 커맨드 생성 및 프로세스 관리
instance.py          격리된 게임 인스턴스 경로 관리
modrinth_api.py      모드·셰이더 검색/설치/버전 관리
mod_catalog.py       큐레이션된 모드 목록
preflight.py         사전 점검, 설정 저장, 업데이트 확인
frontend/            단일 파일 HTML UI ("Nether Glass" 테마)
```

---

## 문서

- [이용 약관 및 면책 고지](TERMS.md)
- [제3자 라이선스 고지](THIRD_PARTY_NOTICES.md)
- [Azure 앱 등록 설정](AZURE_SETUP.md) — 직접 빌드할 때만 필요

---

## 비제휴 고지

**동글랜드 런처는 Mojang Studios 또는 Microsoft 의 공식 제품이 아니며,
이들로부터 승인·후원·제휴받지 않았습니다.**

NOT AN OFFICIAL MINECRAFT PRODUCT.
NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.

Minecraft 는 Mojang Synergies AB 의 상표입니다.
모드와 셰이더팩의 저작권은 각 제작자에게 있으며, 런처는 [Modrinth](https://modrinth.com) 를 통해
원본을 그대로 내려받을 뿐 재배포하지 않습니다.

---

## 라이선스

이 저장소의 라이선스는 [`LICENSE`](LICENSE) 를 참고하세요.
사용된 오픈소스 구성요소는 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 에 정리되어 있습니다.

---

<div align="center">
<sub>만든 사람 · <b>가람</b> (Garamisme)</sub>
</div>
