# CLAUDE.md

동글랜드 런처 v3 — 사설 서버 전용 Minecraft: Java Edition 클라이언트.
Python + pywebview + `minecraft-launcher-lib`(mll) v8 + 단일 파일 HTML 프론트.

## 시작하기 전에

**`HANDOFF_CLAUDE_CODE.md`를 먼저 읽어라.** 확정된 설계 결정, 반복되는 함정,
미해결 과제가 정리되어 있다. 상세한 의사결정 로그는 `V3_BACKEND_NOTES.md`.

## 검증

변경 후에는 반드시:

```bash
python3 tests/run_all.py
```

컴파일 + 프론트↔api 계약 + **함수 중복 정의** + JS 문법 + jsdom 스위트 14개.
`node --check`는 문법만 본다. 스위트까지 돌려야 미선언 변수를 잡는다.

## 절대 하지 말 것

- `auth.py`의 `_TENANT = "consumers"`를 `common`/`organizations`로 바꾸기
  (Minecraft는 개인 MS 계정 전용. 회사 계정은 Xbox 단계에서 터진다)
- `instance.APP_DIR_NAME = "DonglelandLauncher"` 변경 (사용자 데이터 경로)
- 제거 버튼에 `data-install` 달기 (`doInstall`이 상태로 분기 → update 상태에서 업데이트 실행됨)
- 설치 완료를 `pct >= 100`으로 판정 (pct는 단계 내 퍼센트. 완료는 `detail.raw === "done"`)
- "항상 최신 LTS Java" 도입 (Java가 요구보다 높으면 Mixin이 깨진다)
- 프론트 단일 파일 쪼개기 (번들러가 없다)

## 자주 밟는 지뢰

- `el.textContent = val`은 안에 있던 SVG 아이콘을 지운다
- `renderScreen(false)`는 스크롤을 맨 위로 날린다 → `refreshItemInPlace()`
- 프론트 최상위 `const`는 `window` 프로퍼티가 아니다 → 테스트에서 `w.eval('DATA')`
- `ModRegistry(mods_dir)` — json 경로가 아니라 폴더 경로
- Modrinth는 대문자 sha1을 거부한다 → 항상 `.lower()`

## 작업 방식

한국어. 표와 인과 설명 중심의 간결한 출력.
우선순위: **백엔드 안정화 → 최적화 → 프론트/디자인** (셋 다 릴리스보다 우선).
추측하지 말고 **재현하라.** 성능 주장은 측정으로 뒷받침하라.
