# 제3자 소프트웨어 고지 (Third-Party Notices)

동글랜드 런처(Dongleland Launcher)는 아래의 오픈소스 소프트웨어와 글꼴을 사용하거나
함께 배포합니다. 각 구성요소는 원저작자가 정한 라이선스 조건에 따릅니다.

이 문서는 배포물(예: `Dongleland_Launcher.exe`)과 함께 제공되며,
런처의 **설정 → 라이선스** 화면에서도 확인할 수 있습니다.

> 이 목록에 누락이나 오류가 있다면 이슈로 알려주세요. 즉시 수정하겠습니다.

---

## 1. 런처와 함께 배포되는 구성요소

### minecraft-launcher-lib
- 저작자: JakobDev
- 라이선스: **BSD 2-Clause "Simplified" License**
- 출처: https://codeberg.org/JakobDev/minecraft-launcher-lib
- 용도: Minecraft 버전/Fabric 설치, Microsoft 계정 인증 체인, 실행 커맨드 생성

### pywebview
- 저작자: Roman Sirokov
- 라이선스: **BSD 3-Clause License**
- 출처: https://github.com/r0x0r/pywebview
- 용도: 런처 UI(WebView2) 창

### Requests
- 저작자: Kenneth Reitz 및 기여자
- 라이선스: **Apache License 2.0**
- 출처: https://github.com/psf/requests
- 용도: HTTP 통신 (minecraft-launcher-lib 의존성)

### certifi
- 저작자: Kenneth Reitz 및 기여자
- 라이선스: **Mozilla Public License 2.0 (MPL-2.0)**
- 출처: https://github.com/certifi/python-certifi
- 용도: TLS 인증서 번들 (exe 배포 시 SSL 검증)

### skinview3d
- Copyright (c) 2014-2018 Kent Rasmussen
- Copyright (c) 2017-2022 Haowei Wen, Sean Boult and contributors
- 라이선스: **MIT License**
- 출처: https://github.com/bs-community/skinview3d
- 용도: 스킨 3D 미리보기
- 위치: `frontend/vendor/skinview3d/skinview3d.bundle.js`

### three.js
- Copyright © 2010-2026 three.js authors
- 라이선스: **MIT License**
- 출처: https://github.com/mrdoob/three.js
- 비고: 위 `skinview3d.bundle.js` 안에 **번들로 포함**되어 있습니다.

### Lucide (아이콘)
- ISC License. Lucide의 일부 저작권은 Feather(MIT)의 일부로서
  Cole Bemis(2013–2022)에게 있으며, 그 외 저작권은 Lucide Contributors(2022)에게 있습니다.
- 라이선스: **ISC License**
- 출처: https://lucide.dev/license
- 용도: UI 아이콘 (SVG path 를 `frontend/` 에 인라인 포함)

### Pretendard
- Copyright (c) 2021, Kil Hyung-jin, with Reserved Font Name Pretendard.
- 라이선스: **SIL Open Font License 1.1**
- 출처: https://github.com/orioncactus/pretendard
- 위치: `frontend/fonts/Pretendard-*.woff2`

### Pixelify Sans
- 라이선스: **SIL Open Font License 1.1**
- 출처: https://fonts.google.com/specimen/Pixelify+Sans
- 위치: `frontend/fonts/PixelifySans.woff2`

---

## 2. 빌드 도구 (배포물에 포함되지 않음)

### PyInstaller
- 라이선스: **GPL 2.0 with a special exception** (부트로더 예외 조항)
- 출처: https://github.com/pyinstaller/pyinstaller
- 비고: 이 예외 조항에 따라, PyInstaller 로 패키징한 결과물에는
  GPL 이 전파되지 않습니다.

---

## 3. 런처가 이용하는 외부 서비스

이 소프트웨어는 아래 서비스의 공개 API/엔드포인트를 이용합니다.
해당 콘텐츠의 저작권은 각 서비스와 원저작자에게 있으며,
런처는 그 콘텐츠를 재배포하지 않고 사용자의 요청에 따라 내려받을 뿐입니다.

| 서비스 | 용도 |
|---|---|
| Microsoft / Xbox Live 인증 | 계정 로그인 (사용자 본인 인증) |
| Mojang / Minecraft API | 게임 파일·에셋·Java 런타임 다운로드, 프로필 조회 |
| Modrinth API | 모드·셰이더팩 검색 및 다운로드 |
| Fabric | 모드 로더 설치 |

- 모드와 셰이더팩의 저작권은 **각 제작자**에게 있습니다. 런처는 Modrinth를 통해
  원본 파일을 그대로 내려받으며, 재배포하거나 수정하지 않습니다.

---

## 4. 상표 및 비제휴 고지 (Trademark / Non-affiliation)

- **동글랜드 런처는 Mojang Studios 또는 Microsoft 의 공식 제품이 아니며,
  이들로부터 승인·후원·제휴받지 않았습니다.**
  NOT AN OFFICIAL MINECRAFT PRODUCT.
  NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.
- Minecraft 는 Mojang Synergies AB 의 상표입니다.
- 이 런처를 사용하려면 **정품 Minecraft: Java Edition 계정이 필요합니다.**
  런처는 게임을 판매하거나 제공하지 않으며, 계정 우회 수단을 제공하지 않습니다.
- Modrinth, Fabric 등 언급된 상표는 각 소유자의 자산입니다.

---

## 5. 이 소프트웨어의 라이선스

동글랜드 런처 자체의 라이선스는 저장소 루트의 `LICENSE` 파일을 참고하세요.
