# 인수인계 — 동글랜드 런처 v3

> Claude Code로 이어받는 사람을 위한 문서.
> **코드를 읽으면 알 수 있는 것은 적지 않았다.** 읽어도 알 수 없는 것 —
> 왜 그렇게 짰는지, 어디를 밟으면 터지는지 — 만 담았다.
>
> 최종 상태: **v3.0.0 release 배포 완료** (2026-07)

---

## 0. 가장 먼저 할 일

```bash
python3 tests/run_all.py
```

전체 통과를 확인하고 시작하라. 이 한 줄이 다음을 검사한다.

| 검사 | 왜 필요한가 |
|---|---|
| 백엔드 컴파일 | 12개 모듈 |
| 프론트 ↔ `api.py` 계약 | 프론트가 부르는 67개 메서드가 실제로 있는지 |
| **함수 중복 정의** | 이 프로젝트를 한 번 크게 깨뜨렸다 (§4 참고) |
| JS 문법 | `<script>` 인라인 추출 후 `node --check` |
| jsdom 스위트 14개 | E2E 20단계 + UI 회귀 |

⚠️ **JS 문법 검사는 문법만 본다.** 선언 안 된 변수를 쓰는 실수는 못 잡는다.
실제로 `__cancelReq` 미선언을 놓친 적이 있다. 반드시 스위트까지 돌려라.

---

## 1. 무엇을 만드는가

사설 서버 `dongleland.com` 전용 **Minecraft: Java Edition 풀 클라이언트**.

- **스택**: Python + pywebview(WebView2) + 단일 파일 HTML 프론트
- **핵심 라이브러리**: `minecraft-launcher-lib` (이하 **mll**) v8
- **저장소**: https://github.com/Garamisme/dongleland_Launcher
- **게임**: 26.1.2 / Fabric

```
app.py               진입점 (pywebview 창)
api.py         2186줄 프론트 ↔ 백엔드 브릿지. 모든 public 메서드가 JS에 노출된다
auth.py         679줄 MS OAuth (authorization code + PKCE + 로컬 콜백)
game_installer.py     설치·검증복구·Java 런타임·Fabric 로더
modrinth_api.py 987줄 모드/셰이더 검색·설치·버전·레지스트리
preflight.py   1217줄 사전점검·설정저장·업데이트확인
instance.py           격리 인스턴스 경로
launcher.py           실행 커맨드 생성
frontend/nether-glass-launcher-standalone.html  3520줄, UI 전체
```

**프론트는 단일 파일이다.** 3500줄이 부담스럽겠지만 쪼개지 마라 —
pywebview가 로컬 파일을 로드하는 구조라 번들러가 없고, 분리하면 배포가 복잡해진다.

---

## 2. 확정된 설계 결정 (다시 논의하지 말 것)

### 인증
- MS OAuth **authorization code + PKCE + 로컬 콜백 서버**, 임베디드 pywebview 창(Lunar 스타일)
- 폴백: device code flow
- `auth.py`의 `_TENANT = "consumers"` — **`common`/`organizations`로 바꾸지 마라.**
  Minecraft는 개인 MS 계정으로만 소유한다. 회사 계정은 로그인은 성공한 뒤
  Xbox Live 단계에서 알 수 없는 오류가 난다.
- Ed25519 라이선스 키 방식은 **영구 폐기**. 런처 측 접근 제어와 코드 서명도 하지 않는다.
- 서버 측 접근 제어는 `whitelist.json` (SQLite `v_whitelist` 뷰에서 생성).
  **런처의 역할은 UUID 획득과 게임 실행뿐이다.**

### Java
- **"항상 최신 LTS"는 금지.** Java가 요구보다 높으면 Mixin/ASM이 새 클래스 파일을 못 읽는다
  (`Unsupported class file major version 64`).
- 정답지는 버전 JSON의 `javaVersion` 컴포넌트. Fabric JSON엔 없고 부모(바닐라)에 있으나
  mll의 `inherit_json`이 상속시킨다.
- Mojang 지정 런타임을 인스턴스 안에 격리 설치 (`install_jvm_runtime`). UAC 불필요.
- 관련 죽은 코드가 남아 있다: `download_java_installer`, `run_java_installer`,
  `get_latest_java_lts` (정의만 있고 호출부 0). 지워도 된다.

### 실행 전 검증
- mll 문서: `install_minecraft_version`은 설치를 검증·복구한다 → **실행 전 매번 호출한다.**
- `is_version_ready()`는 원래 `versions/<id>/<id>.json` 존재만 봤다.
  client.jar가 없어도 "설치 완료"로 판정하던 심각한 결함이었다.
  지금은 JSON 파싱 + `inheritsFrom` 부모 확인 + **실제 client.jar 존재**까지 검사한다.

---

## 3. 이 코드베이스의 반복되는 함정

### ⚠️ 함정 1 — 상태로 분기하는 버튼

`doInstall(title)`은 **모드의 현재 상태로 동작을 정한다.**

```js
if (s === "install")   install_mod()
else if (s === "update") update_mod()
else if (s === "installed") remove_mod()
```

그래서 **제거 버튼에 `data-install`을 달면 안 된다.**
`update` 상태에서 제거를 누르면 업데이트가 실행된다.
이 버그는 모달과 라이브러리 카드에서 **각각 따로** 발생했다.

제거는 반드시 `data-modrm` + `doRemove()`를 쓴다.

### ⚠️ 함정 2 — `textContent`로 덮으면 아이콘이 죽는다

`setCell(key, val)`이 `el.textContent = val`을 하면 **안에 있던 SVG가 삭제된다.**
제작자 아이콘이 "몇몇 모달에서만" 사라지던 원인이었다 (프로젝트 상세가 도착한 모달).
아이콘이 있는 셀은 SVG를 보존하고 텍스트 노드만 교체하라.

### ⚠️ 함정 3 — `renderScreen(false)`는 스크롤을 날린다

`#screen-holder`의 자식을 통째로 교체한다.
설치·롤백 후에는 `refreshItemInPlace(m, kind)`로 **해당 카드만** 갱신하라.

또한 `setNav`가 `renderScreen(true)`로 애니메이션을 켠 직후
비동기 로드 콜백이 `renderScreen(false)`를 부르면 **전환 효과가 사라진다.**
→ `renderScreenSoon()`을 쓴다 (`__animUntil`까지 대기).

### ⚠️ 함정 4 — 진행률 100%는 완료가 아니다

`_make_callback`이 주는 `pct`는 **현재 단계 안에서의** 퍼센트다.
4단계(라이브러리/리소스/Java/마무리)라 첫 단계 끝에서도 100에 도달한다.

**완료 판정은 오직 `detail.raw === "done"`으로 한다.**
백엔드가 `is_version_ready()` 통과 후에만 보낸다.
`if (pct >= 100)`으로 판정하는 코드를 다시 넣지 마라.

### ⚠️ 함정 5 — 프론트 최상위 `const`는 `window` 프로퍼티가 아니다

jsdom 테스트에서 `w.DATA`는 `undefined`다. `w.eval('DATA')`를 써라.

---

## 4. 무한 로딩을 일으킨 실수 (재발 방지)

부팅 뒷부분을 `continueBoot()`이라는 이름으로 분리했는데,
**같은 이름의 함수가 이미 1962줄에 있었다** (로그인 후 카탈로그 로딩 담당).

JS는 나중 함수 선언이 앞의 것을 덮어쓴다.
→ 로그인에 성공해도 카탈로그를 영영 못 불러와 **모든 사용자가 "불러오는 중"에 갇혔다.**

`tests/run_all.py`의 **함수 중복 검사**가 이걸 잡는다. 지우지 마라.

---

## 5. 미해결 — 다음 사람이 할 일

### 🔴 최우선: 모드 간 버전 충돌 (Fabric 크래시의 나머지 절반)

의존성 자동 설치는 끝났다 (`_install_modrinth_deps` — Modrinth 버전 JSON의
`dependencies(required)`를 따라간다. 카탈로그의 `dependencies`는 수기 관리라 전부 빈 배열이었다).

하지만 **모드끼리의 버전 제약**은 여전히 못 본다.

```
sodium 0.9.1  → 26.1.2 호환 ✅
iris 1.10.9   → 26.1.2 호환 ✅
그러나 iris 1.10.9 는 sodium 0.8.x 를 요구  ← 우리가 못 보는 제약
```

모드마다 독립적으로 "최신"을 고르므로 원리적으로 볼 수 없다.
Modrinth의 `dependencies`엔 보통 버전 범위가 없고,
**진짜 제약은 jar 안의 `fabric.mod.json`의 `depends` / `breaks`에 있다.**

**제안 (가벼운 쪽)**: 실행 전에 설치된 jar들의 `fabric.mod.json`을 읽어
조합 충돌을 검사하고, 한글로 안내한 뒤 버전 롤백을 유도한다.
(무거운 쪽 = 설치 시점의 제약 해석기. 오버킬로 보인다.)

임시 안내: sodium을 0.8.x로 되돌리면 실행된다.

### 🟡 exe 빌드 실기 검증
`build.bat` / `Dongleland_Launcher.spec`로 빌드는 되지만 다음이 미확인이다.
- 임베디드 로그인용 **두 번째 pywebview 창**이 패키징 후에도 뜨는가
- `frontend/vendor/skinview3d/skinview3d.bundle.js` (468KB)가 포함되는가
- SmartScreen "추가 정보 → 실행" 안내는 README에 있다

### 🟡 `LICENSE` 파일이 없다
`README.md`와 `THIRD_PARTY_NOTICES.md`가 둘 다 참조 중.
라이선스를 정하지 않으면 법적으로 "모든 권리 유보"라 포크·기여가 불가능하다.
참고: Prism Launcher = GPL-3, MultiMC = Apache-2.0.

### 🟢 정리하면 좋은 것
- 죽은 Java 설치 코드 3개 (§2)
- `requests.Session` 연결 재사용 (Modrinth 배치화로 우선순위는 낮아졌다)
- UX/시각 디자인 패스 (계속 미뤄왔다)

---

## 6. 성능 — 이미 한 것과 그 근거

**측정부터 했다.** 부팅 경로에서 `scan_mods`가 jar당 `get_version_from_hash`(N) +
모드당 `get_latest_compatible_version`(N) ≈ **25회 순차 호출**.
`urllib.urlopen`은 연결 재사용이 없어 매번 TCP+TLS → 약 3.75초.

→ Modrinth 배치 엔드포인트로 **25회 → 2회**.
- `POST /version_files` (`get_versions_from_hashes`)
- `POST /version_files/update` (`get_latest_versions_from_hashes`)
- `sha1_of_file_cached()` (키 = path + mtime_ns + size, 상한 256)

⚠️ **Modrinth는 대문자 해시를 거부한다** (modrinth/code#2707). 항상 `.lower()`.

skinview3d(468KB)는 `<head>` 동기 로드 → `ensureSkinView()` 지연 로드로 바꿨다.
부팅 시 외부 스크립트 0개.

**과잉 최적화는 기각했다.** 5초 게임 실행 폴링은 종료 시 1회만 재렌더하므로 문제없다.

---

## 7. 자잘하지만 알아야 할 것들

- `instance.py`의 `APP_DIR_NAME = "DonglelandLauncher"` — **바꾸지 마라.** 사용자 데이터 경로다.
  앱 이름을 바꿀 때도 이건 유지했다.
- `APP_CHANNEL` — `"beta"`로 바꾸면 UI에 BETA 칩이 자동으로 붙는다. 프론트 수정 불필요.
- `TERMS_VERSION` — 약관 내용이 실질적으로 바뀔 때만 올린다. 올리면 전원 재동의.
- `TERMS_URL`/`NOTICES_URL`은 `blob/HEAD`를 쓴다 → 기본 브랜치가 main이든 master든 안 깨진다.
- 의존 모드는 레지스트리에 `__dep__:<project_id>` 키로 기록된다.
  이래야 초기화 때 지워지고, 갱신 시 옛 jar가 안 남는다.
  `scan_mods`가 기존에 깔린 의존 모드도 **소급 등록**한다
  (판정 기준: "설치된 모드가 required로 요구하는 project_id" → 사용자가 직접 넣은 모드는 보존).
- `ModRegistry(mods_dir)` — json 경로가 아니라 **폴더 경로**다. 테스트에서 한 번 틀렸다.
- 셰이더 상태는 `_shader_by_slug` 맵이 진실의 원천이다.
  `install_version(kind="shader")`이 filename을 기록하지 않아 제거가 실패한 적 있다.
- 파일이 실제로 없는데 "제거 실패" 에러를 내면 UI가 영영 "설치됨"에 갇힌다.
  → `{"ok": True, "status": "not_installed"}`를 반환한다.

---

## 8. 작업 방식 (Garam의 선호)

- **한국어**로 소통한다.
- **표와 인과 설명** 중심의 간결한 출력을 선호한다. 장황한 서론은 싫어한다.
- **우선순위: 백엔드 안정화 → 최적화 → 프론트/디자인.** 셋 다 릴리스보다 우선한다.
- **객관적·측정 기반 평가를 명시적으로 요구한다.** "빨라졌을 것"이 아니라 숫자를 대라.
- 추측하지 말고 **재현하라.** 이 프로젝트에서 "버그인 줄 알았는데 정상이었던" 사례가 여럿이다
  (재설치 시 구버전 설치 의혹 → 백엔드는 정상, 버전이 화면에 없어서 그렇게 보인 것).
- Garam은 종종 결론을 먼저 맞힌다. 반박할 땐 **증거를 들어라**
  ("최신 LTS로 자동 교체" 제안을 Mixin 호환성 근거로 반박해 채택되지 않았다).

---

## 9. 참고 자료

- 의사결정 로그: `V3_BACKEND_NOTES.md` (35단계까지, 이 문서보다 훨씬 상세하다)
- Azure 앱 등록: `AZURE_SETUP.md`
- 다른 런처: Prism Launcher(GPL-3, 인스턴스 격리 + Java 관리 + 다중 계정),
  Modrinth App(<150MB RAM)
- https://ryanccn.dev/posts/inside-a-minecraft-launcher/
