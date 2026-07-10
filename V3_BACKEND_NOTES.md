# v3 백엔드 1차 구현 노트 (Phase 1~3 코어)

이번 세션 결과: **HANDOFF_v3_CLIENT.md 의 신규 4모듈 + api.py 브릿지 완성.**
컨테이너에서 모의 검증(디바이스 플로우/리프레시/오류 매핑/설치 진행률/커맨드 조립) 전부 통과.
남은 것 = **UI(로그인 화면·설치 진행 화면) + 실제 PC 테스트.**

## 신규 파일
| 파일 | 내용 | 상태 |
|------|------|------|
| `instance.py` | `%APPDATA%/DonglelandClient/instance` 격리 인스턴스, state.json | ✅ 검증 |
| `auth.py` | 디바이스 코드 로그인 → XBL→XSTS→MC (mll 재사용), DPAPI 토큰 저장, 자동 리프레시, XErr 한글 매핑 | ✅ 모의 검증 |
| `game_installer.py` | `fabric.install_fabric` (바닐라 포함 설치), stable 로더 선택, 진행률 0~100 매핑 | ✅ 모의 검증 |
| `launcher.py` | mll `get_minecraft_command` + `quickPlayMultiplayer=dongleland.com` + javaw 직접 실행 | ✅ 커맨드 조립 검증 |

## api.py 신규 브릿지 (JS 계약)
```
auth_status()            → {logged_in, username?, uuid?, avatar_url?}
auth_begin()             → {ok, user_code, verification_uri, device_code, interval, expires_in}
auth_poll(device_code)   → {status: pending|slow_down|ok|error, ...}   ← interval 간격 폴링
auth_open_verification(url)  → 기본 브라우저로 microsoft.com/link 열기
auth_logout()

client_status()          → {installed, version_id, mc_version, loader_version, installing}
client_install_async()   → 진행률 push: window.onClientInstall(pct, msg)  (완료 100 / 실패 -1)
client_launch()          → 필수모드 게이팅 → 모드 동기화 → 로그인 갱신 → 실행+서버 자동입장
                           오류 코드: required_missing / relogin / not_installed / no_java / launch_failed
```
- 토큰은 JS 로 절대 안 나감 (public_view 만 전달, 검증 완료)
- `_sync_mods_to_instance()`: **임시**. v2.1 mods → 인스턴스 mods 미러링.
  Phase 4 에서 modrinth_api 설치 경로를 인스턴스로 옮기면 제거.

## 개발자 1회 작업 (코드 밖, 필수)
1. Azure Portal 앱 등록 — 지원 계정 유형: **개인 Microsoft 계정**
2. 인증 → 고급 설정 → **"공용 클라이언트 흐름 허용" = 예** (디바이스 코드 필수)
3. client ID 를 `app_meta.AZURE_CLIENT_ID` 에 기입 (비밀값 아님)
4. 런처에서 **로그인 1회 시도** (403 나는 게 정상 — 활동 기록 필요)
5. **Mojang 승인 폼 제출**: aka.ms/mce-reviewappid → 승인까지 대기(수 일), 승인 후 24h 반영
   - 미승인 상태의 403 은 auth.py 가 `app_not_permitted` 로 안내함

## PC 테스트 체크리스트 (컨테이너 불가 항목)
- [ ] auth_begin → 코드 표시 → microsoft.com/link 입력 → auth_poll ok
- [ ] account.dat 헤더가 `DPAPI` 인지 (컨테이너에선 PLAIN 폴백)
- [ ] client_install_async → 진행률 push → versions/fabric-loader-* 생성
- [ ] `app_meta.GAME_VERSION(26.1.2)` 이 Mojang 매니페스트/Fabric 메타에 실재하는지
- [ ] client_launch → javaw 로 게임 기동 → **동글랜드 서버 자동 입장** (quickPlay)
- [ ] 24h 뒤(또는 mc_expires_at 조작) 자동 리프레시 경로
- [ ] 미성년/Xbox 프로필 없음 계정 오류 문구

## 다음 세션
1. ~~UI~~ → **완료** (아래 'v3 UI 구현' 참조)
2. Phase 4: modrinth_api/셰이더 설치 경로 인스턴스 전환, `_sync_mods_to_instance` 제거
3. ~~license/인증 시스템~~ → **폐기 확정** (HANDOFF_AUTH_WHITELIST.md).
   최종 구조 = MS 정품 인증(런처, 완료) + 서버측 whitelist.json(운영자 도구, 완료).
   런처에는 어떤 접속 판단도 넣지 않는다.

## 인증/화이트리스트 트랙 (HANDOFF_AUTH_WHITELIST.md TODO 진행 상황)
- [x] MS OAuth 로그인 → 정품 UUID 획득 (`auth.py`)
- [x] UUID+토큰으로 마크 실행 (`launcher.py`)
- [x] DB → whitelist.json export (`server_tools/dongleland_members.py export`)
- [x] 멤버 관리 CLI (add / set-status / whitelist / list / info / sync-name — delete 없음)
- [ ] whitelist 반영 절차 확정 — CLI 는 두 방식 다 지원:
      수동(`export` 후 복사) / 반자동(`export --server-dir <서버폴더>` + `/whitelist reload`)
- [ ] 폐쇄형/개방형 정책 최종 확정 (운영 결정 사항)

## 멀티 프로필 확장 계획 (v3.x — UI 구상 완료, 백엔드는 준비만)
- 원칙: 동글랜드 = 삭제 불가 기본 프로필(큐레이션+게이팅), 사용자 프로필 = 자유(게이팅 없음)
- 계정(MS 로그인)은 전역 1개 — 프로필과 무관
- **디렉토리 구조는 선반영 완료**: `instances/dongleland/` + 프로필별 state.json
  (첫 실설치 후 변경 시 전 유저 재다운로드가 되므로 설치 0명인 지금 확정함)
- 나머지(profiles.json, 프로필 칩 UI, 추가 모달, installer/launcher 파라미터화)는
  v3.0 릴리스 후 v3.x 에서. v3.0 은 동글랜드 단일로 출시.
- 프로필 입력값은 4개로 제한: 이름 / 서버주소(선택) / 버전 / 로더(바닐라·Fabric)


## v3 UI 구현 (완료 — 더미 모드 E2E 9/9 통과)
브라우저에서 `frontend/nether-glass-launcher-standalone.html` 을 직접 열면
**더미 모드로 전체 플로우 시연 가능** (로그인 게이트 → 코드 → 폴링 성공 →
설치 진행률 → 실행). pywebview 안에서는 동일 코드가 실백엔드를 호출.

- 로그인 게이트: 전체 화면 오버레이(타이틀바 제외 — 창 조작 가능).
  상태 idle/busy/code/error, 코드 클릭 복사, 브라우저 열기, 남은 시간
  카운트다운, slow_down 간격 증가, 만료 시 재시도 화면
- 타이틀바 계정 뱃지(no-drag 영역): 이니셜→스킨헤드 폴백 아바타 + 닉네임.
  드롭다운: UUID 축약(클릭=전체 복사)/계정 관리/계정 전환(코드 발급 직행)/
  로그아웃(2단계 확인). 외부 클릭·Esc 닫힘
- 플레이 탭: 상태 배지 동적(준비 완료/설치 필요/설치 중/로그인 필요),
  실행 버튼 상태머신(설치→설치 중→실행→실행 중… 잠금→relogin 게이트 복귀),
  설치 카드(진행률 제자리 갱신 #ci-bar, 격리 인스턴스 안내 문구)
- 시스템 탭: 계정 카드(정품 배지+전체 UUID 복사+전환/로그아웃) +
  전용 인스턴스 카드(설치된 클라이언트/폴더 열기/재설치 2단계)
- 신규 백엔드 브릿지: open_instance_folder, client_reinstall_async
  (재설치 = 마커 제거 후 무결성 기반 재설치, 모드·월드 보존)
- JS↔백엔드 계약 교차검증: 프론트 호출 40개 메서드 전부 api.py 에 실재

남은 것: Azure 승인 후 실PC 테스트 (V3 체크리스트 그대로).

## Azure/Mojang 승인 완료 (실동작 단계 진입)
- Client ID `c34feb67-...` Mojang 승인 완료 → 인증/스킨/망토 API 실동작 가능
- 이제 `dev_login_test.py` 실행 시 403 대신 닉네임/UUID 출력되어야 정상
- 남은 것 = 실PC에서 로그인→설치→실행→서버 자동접속 실동작 검증

## 향후: 소셜 기능 (마인크래프트 친구 기능 기반)
계정 드롭다운의 "계정 관리"는 제거함. 향후 소셜 기능으로 대체 예정.
- 마인크래프트 공식 친구 API 활용 (계정별 친구 목록/온라인 상태)
- 구상: 친구 목록 보기, 온라인 여부, 같은 서버 접속 상태, 초대 등
- MC access_token 으로 접근 (auth.get_account 재사용). 승인된 Client ID 필요 — 이미 확보
- 별도 탭 또는 계정 드롭다운 하위 메뉴로 배치 검토
- ⚠️ 친구 API 는 공식 문서화가 제한적 → 착수 시 실제 엔드포인트/권한 재확인 필요

## 실PC 피드백 반영 (2차)
- 앱 폴더명: `DonglelandClient` → **`DonglelandLauncher`** 로 변경 (instance.py APP_DIR_NAME).
  ⚠️ 기존 사용자는 %APPDATA% 아래 구 폴더가 남으므로, 재로그인/재설치 필요.
  추후 "클라이언트"로 정식 전환 시 이름 다시 검토.
- Java 요구: 21 → **25** 로 상향 (preflight.REQUIRED_JAVA_MAJOR + Adoptium URL /25/).
  이유: MC 26.1.2 + 최신 Fabric API/모드들이 Java 25 요구 (실행 시 Incompatible mods 오류).
  Java 24만 있는 PC는 이제 자동으로 Adoptium 25 JRE 다운로드.
- "게임 폴더" 버튼: open_game_folder(.minecraft) → **open_instance_folder**(우리 인스턴스)로 교체.
- instances/dongleland/ 구조: 서버별 프로필화 대비한 의도된 설계. 유지.

## 스킨 3D 렌더 기술 검토 (향후)
현재 CSS 레이어 합성은 정면 단순 렌더만 안정적. 대각선/3D/애니메이션은 CSS 로는
찌그러짐 발생 → 정면으로 되돌림. 향후 옵션:
- **skinview3d** (three.js 기반, 오픈소스): 스킨 URL/텍스처로 3D 모델 + 회전·걷기
  애니메이션 지원. 라이브러리 카드/현재 스킨 모두 적용 가능. 가장 유력.
- three.js 직접 (블렌더 익스포트 glTF 모델 + 스킨 텍스처 매핑): 커스텀 애니메이션
  자유도 높으나 구현 비용 큼. 블렌더 애니메이션 계획과 부합.
- 로컬 PNG 는 data_url 로 three.js 텍스처에 바로 매핑 가능 (외부 서비스 불필요).
- 착수 시 pywebview WebGL 지원 확인 필요 (WebView2 는 지원).

## Java 업데이트 검사 로직 수정 (개념 오류 바로잡음)
문제: 기존 "Java 업데이트 검사"는 최신 버전을 안 봤음. "요구 버전 이상이면
무조건 ok(최신)" 로 표시 → Java 24 인데 "최신"이라 나오고, 정작 게임은
Java 25 요구라 실행 실패하는 모순.

수정 (preflight.check_java_status):
- Adoptium /v3/info/available_releases 의 most_recent_lts 로 실제 최신 LTS 조회
- 3상태로 구분:
  - ok       = 요구 충족 + 최신 LTS 이상
  - outdated = 요구는 충족(게임 실행 가능)하지만 최신 LTS 보다 낮음 → "선택적 업데이트"
  - needed   = 요구 미충족 → 게임 실행 불가, 설치 필요
- tip_version(26 등 비-LTS 개발 버전)은 기준으로 안 씀 — 게임/모드가 LTS 기준이라.
- 최신 조회 실패(오프라인) 시 요구 충족이면 ok 로 폴백 (안전)

## Java 버전 완전 자동화 (옵션 A + B 구현)
하드코딩(REQUIRED_JAVA_MAJOR=25, latest/25 URL) 제거. 이제 게임 버전/모드가
바뀌면 자동 대응.

### 옵션 A — 요구 버전 자동 판정 (preflight.required_java_major)
= max(게임 JSON javaVersion.majorVersion, 설치된 모드들의 fabric.mod.json depends.java)
- 게임 JSON: inheritsFrom(Fabric→바닐라) 따라가며 javaVersion 읽음
- 모드: 각 jar 의 fabric.mod.json 의 depends.java 범위(">=25" 등)에서 숫자 추출, 최댓값
- 이유: Garam 케이스처럼 "게임은 Java21 되는데 Fabric API/모드가 25 요구" 를 자동 포착
- REQUIRED_JAVA_MAJOR=21 은 이제 폴백 상수(JSON 못 읽을 때만)
- find_valid_java(required=...), check_java_status() 모두 이 동적 값 사용

### 옵션 B — outdated 교체 버튼
- check_java_status 3상태: ok / outdated(요구충족+최신LTS보다낮음) / needed(요구미충족)
- api.install_java_async(to_latest):
  - to_latest=False(needed): 요구버전(required_java_major) JRE 설치
  - to_latest=True(outdated): 최신 LTS(get_latest_java_lts) JRE 로 교체
- Adoptium URL 은 ADOPTIUM_API_URL_TEMPLATE.format(major=...) 로 동적 생성
- 진행상황 window.onJavaInstall(phase, payload) 로 push (progress/run/done/error)
- 설정탭 Java 버튼 라벨 상태별: needed="설치", outdated="최신 LTS로 교체"
- 설치 후 invalidate_java_cache + check_java_status 재실행 → 행 자동 갱신

### 요약: "다음 LTS/신버전 나오면?"
- 게임/모드가 새 Java 요구 → required_java_major 가 자동 반영 → needed 로 표시 + 그 버전 설치
- 최신 LTS 가 요구보다 높아짐 → outdated 로 표시 + 교체 버튼으로 최신 받기
- 코드 숫자 수정 불필요. 완전 자동.

## 스킨 3D 렌더: three.js 도입 (1단계 — 뷰어 + WebGL 검증)
결정: CSS 합성 → three.js 직접. 파이썬 백엔드는 그대로(3D 와 무관).
pywebview=WebView2=크로미움이라 WebGL 지원.

### 추가된 것
- frontend/vendor/three/ : three.js r160 코어 + OrbitControls + GLTFLoader
  (npm registry tarball 에서 추출. unpkg/cdn 은 네트워크 차단이라 로컬 번들.)
  → 오프라인 앱이므로 importmap 으로 "three" 를 로컬 파일에 매핑.
- frontend/vendor/skin3d.js : MC 스킨 3D 뷰어 모듈
  - 표준 박스 모델(머리·몸·팔·다리) + 오버레이 레이어 직접 조립
  - 슬림/와이드 팔(aw=3/4), NearestFilter(픽셀 아트), idle 자동회전 + 드래그
  - createSkinViewer(canvas, opts) → setSkin(url, variant)/resize/dispose
  - 향후 블렌더 glTF 로 교체 시 buildPlayer() 만 GLTFLoader 결과로 바꾸면 됨
- frontend/webgl_test.html : 독립 WebGL/three.js 동작 테스트 페이지
- app.py : DL_WEBGL_TEST=1 이면 테스트 페이지 로드
- .spec 은 frontend/ 통째로 번들 → vendor/ 자동 포함 (빌드 OK)

### ⚠️ 실PC 검증 필요 (다음 단계 전 필수)
importmap + ES module + WebGL 이 WebView2 에서 다 되는지 실기 확인:
  Windows: set DL_WEBGL_TEST=1 && py app.py
  → 큐브/스킨이 3D 로 회전하고 드래그되면 성공.
  실패 시: WebView2 런타임 최신화, 또는 importmap 미지원이면 번들러로 전환.
검증 성공하면 2단계에서 스킨 탭의 CSS 렌더를 skin3d 뷰어로 교체.

## 스킨 3D 렌더: three.js 통합 완료 (2단계)
실PC WebGL 검증 통과(스크린샷 확인) → 스킨 탭 현재 스킨 뷰에 실제 통합.
- bare 'three' import 문제 해결: vendor/three 의 jsm 파일들(OrbitControls,
  GLTFLoader, BufferGeometryUtils) + skin3d.js 의 import 를 상대경로로 수정.
  → importmap 불필요, file:// 에서 정상 로드.
- HTML <head> 에 module bridge: skin3d.js 를 import 해 window.__SkinViewer 노출.
  인라인(비모듈) 스크립트가 이걸 통해 뷰어 생성.
- 현재 스킨: <img> → <canvas id="skin3d-current"> 로 교체.
  renderScreen() 에서 syncSkin3D() 호출 → 스킨 탭이면 뷰어 생성/재사용,
  이탈하면 dispose. canvas 요소 교체(innerHTML) 감지해 재생성.
- 자동 회전 없음(요청): idleSpin 기본 off, 초기 3/4 각도, 드래그로만 회전.
- variant: refreshSkinLib 에서 skin_get 으로 현재 스킨 variant 받아 슬림/와이드 정확.
- 폴백: 모듈 로드 전/실패 시 mc-heads 이미지(skin3d-fallback) 표시.
- 라이브러리 카드: 성능상 3D 안 씀(정면 단순 렌더 유지). 카드가 여러 개라
  각각 WebGL 컨텍스트 띄우면 부담. 현재 스킨 대형 뷰만 3D.
- 향후 블렌더 애니메이션: buildPlayer() 를 GLTFLoader 결과로 교체하면 됨.

## 스킨 3D 렌더 수정 (3단계) + 파일 정리
- 렌더 잘림 수정: 모델을 원점 중심으로 재배치(root.position.y=-3 + pivot 그룹),
  카메라 fov 30 / z=52 / target 원점 → 전신이 프레임에 안정적으로 들어옴.
- 현재 스킨 canvas 200x280 로 확대.
- "현재 스킨" 라벨을 카드 밖 위쪽으로 이동 → 라이브러리("라이브러리" 라벨)와 통일감.
- 모달 미리보기: 박스(배경/테두리) 제거, 왼쪽 가운데 렌더만 표시.
- 카드 ⋯ 드롭다운 가림 수정: .tile 의 backdrop-filter 가 stacking context 를
  만들어 메뉴가 다음 카드에 가려짐 → 메뉴 열린 카드에 .skin-card--menuopen
  (position:relative; z-index:150) 부여 + 메뉴 z-index 200.
- 파일 정리: webgl_test.html 삭제, app.py 의 --webgl-test 토글 제거,
  구 스펙 문서 5개(SPEC/V2.1_SPEC/SHADER_SPEC/DEFERRED_NOTES/HANDOFF_v3_CLIENT) 삭제.
  유지: V3_BACKEND_NOTES.md(작업로그), HANDOFF_AUTH_WHITELIST.md(인증 아키텍처).
- vendor/three/utils/BufferGeometryUtils.js 는 GLTFLoader 의존이라 유지(블렌더용).

## 스킨 3D: 블렌더(Blockbench) glTF 모델 도입 (4단계)
사용자 제공 Garamisme.gltf (Blockbench 5.1.4 export) 를 vendor/models/player.gltf 로
번들. 직접 박스 조립 대신 이 모델을 GLTFLoader 로 로드하고 스킨 텍스처만 교체.
- UV 가 이미 MC 스킨 레이아웃으로 매핑돼 있어 텍스처 교체만으로 입혀짐.
- 텍스처: NearestFilter(픽셀), flipY=false(glTF 기준), SRGB, alphaTest 0.05.
- 카메라: Box3 로 모델 바운딩 계산해 자동 프레이밍(fillY 비율) → 잘림 없음.
- createSkinViewer: 현재 스킨 인터랙티브(드래그, idle 회전 off).
- renderSkinThumbnail: 라이브러리 카드용 정적 썸네일. 공유 오프스크린 렌더러로
  한 장씩 구워 dataURL 반환 → <img>. 카드마다 WebGL 컨텍스트 안 만들어 안전.
  __thumbCache 로 재렌더 방지, 큐로 순차 처리. 로딩 중엔 2D 폴백 표시.
- 슬림/와이드 두 모델 분기 완료: player_slim.gltf / player_wide.gltf.
  variant 에 따라 loadModelTemplate(variant) 가 해당 모델 로드. 뷰어 key 와
  썸네일 cache key 에 variant 포함 → 정확히 구분 렌더.
- 향후 애니메이션: 같은 gltf 에 Blockbench/블렌더 애니메이션 클립 넣어 export →
  gltf.animations 를 AnimationMixer 로 재생하면 됨(로더/씬 구성 재사용).

## 스킨 3D 렌더: skinview3d 로 전환 (5단계 — 원점 재검토 결론)
문제: 직접 만든 gltf/three 렌더가 UV 깨짐 반복 (슬림 모델 메시 구조가 와이드와
달라 일관 처리 어려움, flipY 추측 악순환). 원점 재검토 후 검증된 라이브러리 채택.

### 채택: skinview3d 3.4.2
- vendor/skinview3d/skinview3d.bundle.js — three 내장 UMD 단일 번들(477KB).
  일반 <script> 로 로드 → window.skinview3d 전역. importmap/별도 three 불필요.
- 현재 스킨: new SkinViewer({canvas,skin,model}) — UV/슬림·와이드/카메라 자동.
  autoRotate=false(드래그로만), zoom 0.9, fov 45, enableZoom off.
- 라이브러리 카드: 오프스크린 SkinViewer 1개 재사용 → loadSkin+render+toDataURL
  로 썸네일 구워 <img>. __thumbCache 로 재사용. WebGL 컨텍스트 1개만.
- model: variant "slim"→slim, 그 외 default(와이드). "auto-detect" 도 가능.
- crossOrigin: skinview3d 가 자체 설정. mc-heads.net(현재 스킨)은 CORS 허용 필요,
  로컬 data_url(라이브러리)은 무관.

### 삭제된 것 (더 이상 불필요)
- vendor/three/ (skinview3d 에 내장)
- vendor/models/player_slim.gltf, player_wide.gltf (자체 모델 안 씀)
- vendor/skin3d.js (직접 만든 뷰어)
- frontend/skin_diag.html + app.py --skin-diag 토글
- frontend/webgl_test.html (이전에 삭제됨)

### 향후 애니메이션
skinview3d 내장: WalkingAnimation/RunningAnimation/IdleAnimation/FlyingAnimation.
viewer.animation = new skinview3d.WalkingAnimation() 로 바로 적용 가능.
(블렌더 커스텀 대신 라이브러리 제공 애니메이션 사용 — 커스텀 필요 시 재검토)

## 스킨 탭 UX 수정 (6단계)
- 현재 스킨 스티브 문제: skinTextureURL 이 mc-heads(uuid) 만 쓰던 것 →
  skin_get 의 Mojang 공식 텍스처 URL(state.skin.url) 우선 사용. CORS 안전 + 실제 스킨.
- 라이브러리 썸네일 대각선(3/4) 뷰: __thumbViewer.playerObject.rotation.y=-0.55.
- 드롭다운 가림: .skin-card--menuopen 에 backdrop-filter:none 추가(스택 컨텍스트 해제)
  + z-index 999. .tile 의 backdrop-filter 가 메뉴를 가두던 문제 해결.
- 모달 껌벅 수정:
  · edit 열 때 renderScreen(false) 선호출 제거(전체 재렌더가 껌벅 원인).
  · capes 프리로드(refreshSkinLib) + skinModalOpen 은 capes 없거나 빈배열일 때만 로드.
  · 파일선택/variant 변경 시 전체 재렌더 대신 updateSkinModalPreview()로 부분 갱신
    (#skinm-preview / #skinm-filelabel / save 버튼만 교체).
- 찾아보기 버튼 줄바꿈 방지 + 긴 파일명 ellipsis(...) — 기존 text-overflow 패턴 재사용.
- 새 스킨 카드: arrow-up-circle(원+화살표) + skin-add-circle(원 배경) 이중 원 →
  plus 아이콘 + 원 제거. skin-add-circle CSS 삭제.

## 경로 인스턴스 통일 + 스킨 UX (7단계)
### 기본 런처(.minecraft) → 격리 인스턴스로 전면 전환
- preflight.find_minecraft_dir(): 격리 인스턴스(instance.instance_dir()) 최우선 반환.
  → mods/shaders/Fabric 체크 등 모든 경로가 자동으로 인스턴스를 가리킴.
- api.ensure_ready(): preflight.find_minecraft_dir 대신 instance.mods_dir()/
  shaderpacks_dir() 직접 사용. 폴더 자동 생성.
- open_mods_folder / open_shaderpacks_folder: 인스턴스 폴더 열기.
- shader_ready: shaderpacks 폴더는 우리가 생성하므로 "마크 1회 실행" 조건 제거,
  Iris 설치 여부만 확인. → 셰이더가 기본 런처가 아니라 인스턴스로 설치됨.

### 스킨 탭 UX
- ⋯ 드롭다운 가림: .screen(overflow-y:auto)가 메뉴를 자르던 근본 원인.
  메뉴 열린 동안 .screen 에 menu-open-noflow(overflow:visible) 토글 +
  카드 z-index 999 + backdrop-filter 해제. toggleSkinMenu 에서 제어.
- 이름 드래그 시 모달 닫힘 버그: mousedown 이 모달 내부(data-stop)에서 시작하면
  __mdInsideModal 플래그 → 드래그로 밖에서 mouseup 된 click 을 '닫기'로 안 봄.
- 복제: 맨 뒤 append → 원본 바로 뒤 insert (백엔드 skin.py + 더미 둘 다).
- 삭제: 2단계(firefly armed) 제거 → 한 번에 즉시 삭제.
- 모달 미리보기: skinBodyHTML(2D) → skinThumbHTML(3D 썸네일) 재사용, 라이브러리와 통일.
- 현재 스킨 뷰어: playerObject.rotation.y=0.55 (라이브러리 -0.55 와 반대 방향 대각선).

## 버그 수정 + 게임 실행 상태 (8단계)
### 근본 버그 수정 (대부분 버튼 작동 안함 + UI 춤춤)
- 원인: __ovBlock 에 __dragFromInside 를 무조건 섞어, 모달 내부 버튼 클릭도
  '닫기 차단'으로 처리 → 버튼 액션 실행 안 됨. + .screen overflow 토글이
  레이아웃 재계산 유발(카드 크기 변동).
- 수정: __ovBlock = 오버레이 배경(t.classList.contains("overlay")) 클릭일 때만.
  드래그 판정도 그 경우에만 적용. overflow 토글 완전 제거.
- 업데이트 창 닫기('나중에') 안 먹던 것도 위 __ovBlock 버그가 원인 → 해결.
- ⋯ 드롭다운: overflow 토글 대신 메뉴를 위로(bottom:100%+6px) 열어 스크롤
  컨테이너에 안 잘리게. 카드 z-index 60.

### 계정 추가 시 로그인 창 먼저
- auth.begin_device_login 이 verification_uri_complete(코드 포함 URL) 반환.
- gateBegin: 코드 화면 렌더 직후 auth_open_verification(complete URL) 자동 호출
  → 브라우저 로그인 창이 먼저 뜸. 수동 '열기' 버튼도 complete URL 사용.

### 게임 실행 중 버튼 (요청: '게임 실행 중' 비활성)
- launcher.py: _running_proc 에 프로세스 보관, is_game_running()=poll() 확인.
- api.game_running() → {"running":bool}. 프론트가 5초마다 폴링.
- doLaunch 성공 시 state.gameRunning=true → 버튼 '게임 실행 중'(pulse-dot, 비활성).
  startGameRunningPoll 이 프로세스 종료 감지하면 false 로 원복 + 플레이타임 갱신.
- 미리보기(Bridge.live=false)는 12초 후 종료 처리.

## 로그인: device code → authorization code flow 전환 (9단계)
요청: 계정 전환/추가 시 브라우저 로그인창(계정선택→비번)이 바로 떠야 함.
device code(코드 입력 방식) → authorization code flow(브라우저 바로 로그인)로 전환.

### auth.py
- begin_auth_code_login(): PKCE(S256) 생성 + 로컬 콜백 서버(127.0.0.1:임의포트,
  /callback)를 백그라운드 스레드로 띄우고, authorize URL(prompt=select_account)
  반환. 브라우저가 로그인 후 이 로컬 서버로 code 를 돌려줌.
- poll_auth_code(): 콜백 도착 확인 → code+PKCE verifier 로 토큰 교환 →
  기존 _complete_xbox_chain + _save_account 재사용. {status:pending|ok}.
- device code 함수(begin/poll_device_login)는 미사용이나 폴백용 보존.

### api.py
- auth_begin(): begin_auth_code_login 호출 + webbrowser.open(auth_url) 로 로그인창
  바로 띄움. {ok, flow:"authcode", auth_url} 반환.
- auth_poll(device_code=None): poll_auth_code 호출.
- auth_open_verification: login.live.com 도 허용 목록 추가.

### 프론트
- gate mode "code"(코드 표시) → "waiting"(브라우저 로그인 대기) 로 교체.
  스피너 + 5분 카운트다운 + "다시 열기"(data-gate=reopen) + 취소.
- gateBegin: auth_begin 후 waiting 모드, 2초 간격 폴링(auth_poll).
- reopen: 저장된 authUrl 을 auth_open_verification 으로 재오픈.

### ⚠️ 배포 필수: Azure 앱 등록에 redirect URI 추가
Azure Portal → 앱 등록 → 인증 → 플랫폼 추가 → "모바일 및 데스크톱 애플리케이션"
→ 리디렉션 URI 에 http://localhost 추가 (127.0.0.1 임의 포트 콜백 허용됨).
이거 없으면 authorization code flow 가 redirect_uri_mismatch 로 실패함.

## 로그인: WAM(네이티브 Windows 계정창) 전환 + 브라우저 폴백 (10단계)
Garam 확인: 공식 마인크래프트 런처의 계정 변경 화면은 브라우저가 아니라
Windows 네이티브 계정 선택창(WAM, Web Account Manager). 이걸 채택.

### auth.py
- wam_available(): win32 + pymsalruntime + msal 있으면 True.
- login_with_wam(): msal.PublicClientApplication(enable_broker_on_windows=True)
  → acquire_token_interactive(scopes=["XboxLive.signin"],
    parent_window_handle=GetForegroundWindow(), prompt="select_account")
  → 네이티브 계정창 표시, 브라우저 안 열림. 동기 완료.
  → 받은 access_token 을 기존 _complete_xbox_chain 에 연결(체인 재사용).
  → msal_home_account_id 저장.
- _refresh(): WAM 계정(msal_home_account_id 보유)은 refresh_token 이 없으므로
  app.acquire_token_silent(account=...) 로 갱신. 실패 시 기존 경로/재로그인.

### api.py auth_begin 우선순위
1. wam_available() → login_with_wam() → {"ok":True,"flow":"wam","account":{...}}
   (로그인 즉시 완료 — 폴링 불필요)
2. 실패/불가 → authorization code flow(브라우저) 폴백
   → {"ok":True,"flow":"authcode","auth_url":...} + webbrowser.open
즉 어떤 환경에서도 로그인은 된다. Windows 에선 네이티브 창, 그 외엔 브라우저.

### 프론트
- gateBegin: r.flow==="wam" 이면 account 를 바로 받아 로그인 완료 처리(대기화면 없음).
  r.flow==="authcode" 면 기존 waiting 모드 + 폴링.

### 빌드
- requirements.txt: msal[broker] (win32), msal (기타).
- .spec: collect_all('msal'), collect_all('pymsalruntime') — 네이티브 DLL 포함 필수.
  실패해도 try/except 로 넘어가며, 그 경우 런타임에 브라우저 폴백.

### ⚠️ Azure 앱 등록 (두 방식 모두 대비해 둘 다 등록 권장)
Azure Portal → 앱 등록 → 인증 → 플랫폼 추가 → "모바일 및 데스크톱 애플리케이션":
  - http://localhost                                  (authorization code 폴백용)
  - ms-appx-web://microsoft.aad.brokerplugin/<CLIENT_ID>   (WAM/broker 용)
둘 다 넣어두면 어느 경로로 가든 실패하지 않는다.

## 로그인 3단 폴백: WAM → 앱 내부 창 → 외부 브라우저 (11단계)
Garam 제시: Lunar Client 는 앱 안에 로그인 창을 띄움(외부 브라우저 아님).
(제시된 device code + QR 화면은 우리가 이미 버린 방식이라 채택 안 함)

### auth.py
- open_login_window(auth_url): webview.create_window 로 앱 내부 로그인 창.
  실패 시 False → 외부 브라우저 폴백. close_login_window(): 콜백 수신/취소 시 닫기.
- poll_auth_code(): 콜백 도착하면 close_login_window() 자동 호출.

### api.py auth_begin 우선순위 (최종)
1. WAM(네이티브 계정창) — Windows + pymsalruntime
2. 앱 내부 로그인 창(pywebview) — Lunar 방식, 추가 의존성 0
3. 외부 브라우저 — 최종 폴백
2/3 은 {"flow":"authcode","auth_url","embedded":bool} 반환.
- auth_cancel(): 취소 시 내부 창 닫기. auth_open_verification: 내부창 우선 재오픈.

### 프론트
- state.gate.embedded 로 안내 문구 분기("로그인 창"/"브라우저").
- 취소 시 auth_cancel 호출.

### 남은 검증 (실PC 필수)
- webview.start() 루프 중 create_window 로 2번째 창 추가가 정상 동작하는지.
  (js_api 브릿지는 별도 스레드에서 호출됨 → 실패 시 브라우저 폴백하도록 방어됨)

## 로그인 최종 확정: 임베디드 웹뷰 + 인증코드 (12단계)
[DECISION] WAM 폐기 — 서드파티(비 1st-party) 클라이언트는 WAM 사용 불가.
msal / pymsalruntime 의존성 전부 제거 (requirements + .spec). 추가 의존성 0.

### 최종 구조
- **기본**: 앱 내부 로그인 창(pywebview create_window) = authorization code flow.
  창 생성 실패 시 외부 브라우저로 자동 폴백. state.gate.embedded 로 문구 분기.
- **대체**: 인증 코드(device code). 로그인 버튼 아래 "인증 코드로 로그인" 버튼.
  gate mode "code" 복원(코드 표시 + 복사 + microsoft.com/link 열기).

### api.py
- auth_begin(): begin_auth_code_login + open_login_window (embedded 우선).
- auth_begin_devicecode(): begin_device_login, flow="devicecode".
- auth_poll(device_code=None): device_code 있으면 poll_device_login, 없으면 poll_auth_code.
- auth_cancel(): 내부 로그인 창 닫기.

### 프론트
- gateActive() = mode in (waiting, code). 카운트다운/폴링 공용.
- scheduleGatePoll: code 모드는 intervalMs, waiting 은 2초.
- slow_down 은 code 모드에서만 의미 (device code).

### Azure 설정 (단순해짐)
- `http://localhost` 하나만 등록 (모바일 및 데스크톱 플랫폼, 포트 없이).
- 퍼블릭 클라이언트 흐름 허용 = 예.
- device code 는 리디렉션 URI 불필요 → 최후 수단으로 항상 동작.

## 셰이더 탭 빈 목록 버그 (13단계)
증상: 계정 전환 등을 한 뒤 셰이더 탭이 "해당하는 셰이더팩이 없습니다" (카테고리
카운트는 정상 표시). 앱 재시작하면 정상.

원인: applyCatalog(부트 시 모드 카탈로그 적용)가 `DATA.shaders.length=0` 으로
셰이더를 비우면서 `state.shadersLoaded` 플래그는 true 로 남겨둠.
계정 전환 → afterLogin → bootMain 재실행 → 셰이더 데이터만 비워짐.
이후 loadShaders() 가 `if(state.shadersLoaded) return` 가드에 걸려 재로드 안 함
→ 빈 목록 영구 고착. (재시작하면 플래그가 false 로 초기화돼 정상)

수정:
1. DATA.shaders 를 비울 때 shadersLoaded=false + shaderCategories 도 함께 비움.
2. loadShaders(): 플래그가 true 여도 `DATA.shaders.length===0` 이면 재로드(방어).
3. setNav(): 같은 조건으로 진입 시 재로드.
데이터와 플래그가 어긋나지 않도록 3중으로 막음.

## 버전 롤백 (이전 버전으로 되돌리기) — 모드 + 셰이더팩 (14단계)
목적: 신버전 모드/셰이더 버그로 게임이 안 켜질 때 이전 버전으로 되돌리기.

### 설계 판단 (디자인 철학 유지)
- 위치: mfoot 오른쪽 `#modal-action` 안, 설치/제거 버튼 왼쪽.
  이유: mfoot 은 이미 [왼쪽=외부링크 / 오른쪽=설치액션] 으로 의미 분리됨.
  버전 롤백은 설치 액션이므로 오른쪽. `#modal-action` 은 설치 후 제자리 갱신
  되는 영역이라 상태 동기화가 공짜로 따라온다.
- 형태: `⋯` 버튼 → 드롭다운. 스킨 카드 ⋯ 메뉴와 동일한 시각 언어 재사용.
  split button(⌄)은 이 디자인 시스템에 없는 새 컴포넌트라 배제.
  "이전 버전" 텍스트 버튼은 주 액션(설치)과 시각 무게가 겹쳐 배제.
- 노출: 설치됨/업데이트 상태 + 번들 모드 아닌 항목만 (미설치 항목엔 무의미).

### 백엔드
- modrinth_api.get_version_by_id(version_id): 특정 버전 조회 (신규).
- install_mod_by_slug / install_shader_by_slug 에 `version_id=None` 인자 추가.
  주면 그 버전 설치, 없으면 기존대로 최신. 다운로드/검증 로직 전부 재사용.
- api.list_versions(item_id, kind): 최근 30개 버전 (id, version_number,
  version_type, date, is_current). 셰이더는 loader=None, 모드는 fabric.
  현재 버전은 _registry.get_installed_version / _shader_by_slug 로 판정.
- api.install_version(item_id, version_id, kind): 기존 파일 먼저 제거(중복 방지)
  → 지정 버전 설치 → 모드는 _registry.record_install 갱신.
- 번들 모드(slug=None)는 "버전 선택 미지원" 반환.

### 프론트
- state.verMenu / verList / verBusy. verMenuHTML + toggleVerMenu + pickVersion.
- .ver-menu CSS 는 .skin-menu 를 본떠 작성, 모달 하단이라 위로 열림(bottom:100%).
- 현재 버전은 ver-menu-item--cur(초록, disabled, "사용 중").
- beta/alpha 는 ver-chan 뱃지로 채널 표시.
- 외부 클릭/모달 닫기 시 메뉴 정리.
- 더미 DATA.mods/shaders 에 id 추가 (미리보기에서도 동작하도록).

## 리네이밍 + 폴더 통합 + 설치 진행률 + 메모리 설정 (15단계)

### 1) 앱 이름 변경
동글랜드 모드 런처 → 동글랜드 런처 / Dongleland_Mod_Launcher → Dongleland_Launcher
- app.py(창 제목), frontend(<title>, 타이틀바), build.bat(4곳), .spec(내부 name + 파일명)
- ⚠️ instance.APP_DIR_NAME = "DonglelandLauncher" 는 그대로 (사용자 데이터 폴더).

### 2) %APPDATA% 폴더 통합
- preflight 가 쓰던 %APPDATA%/dongleland_installer/ → %APPDATA%/DonglelandLauncher/ 로 통합.
- _app_dir() 은 instance.root_dir() 재사용 (instance 는 preflight 를 import 하지 않아 순환 없음).
- _migrate_legacy_once(): 구 폴더의 config.json / log.txt 를 최초 1회 복사 이전.
  (복사이므로 구 폴더는 보존 — 롤백 안전)

### 3) 게임 설치 진행률 버그 (핵심)
증상: 설치율이 100% 됐다가 0% 로 추락 반복. 다 안 받았는데 "설치 완료" 표시.
원인: mll 은 단계(라이브러리/에셋/Fabric)마다 setMax 를 새로 호출하고 setProgress 를
  0 부터 다시 올린다. 기존 _make_callback 은 단계별 cur/max 를 그대로 % 로 썼기 때문에
  단계가 바뀔 때마다 0% 로 추락하고, 각 단계 끝에서 100% 를 뿜었다.
  프론트는 pct>=100 을 완료로 처리 → 첫 단계 끝나자마자 "설치 완료".
수정:
  - _make_callback: 새 단계(setMax) 시작 시 지금까지의 표시값을 base 로 고정하고
    남은 구간(ceiling-base)의 60% 만 이번 단계에 할당 → 단조 증가, 추락 없음.
    표시값은 ceiling(99%) 을 절대 넘지 않음.
  - install(): is_version_ready() 검증을 통과한 뒤에만 on_progress(100).
  - api._worker: 중복 _push(100) 제거.
  - 프론트 onClientInstall: pct>=100 이어도 client_status() 로 실제 installed 재확인 후에만
    "설치 완료" 표시. 실패 시 "설치가 완료되지 않았습니다".
검증: 3단계 시뮬레이션에서 설치 중 최대 92%, 100 미출현, 단조증가 True.

### 4) 설치 후 Fabric '미설치' 표시 문제
- get_versions(): state.json 의 fabric_loader_version 을 우선 사용
  (is_version_ready() 통과 시). 캐시된 mc_dir 때문에 '미설치'로 오표시되던 것 해결.
- 프론트 reloadVersions(): 설치 완료 시 호출 → 설정탭 Fabric 행이 즉시 갱신.

### 5) 할당 메모리(Allocated memory) 설정
- api.memory_info(): 시스템 총 RAM 감지(Windows GlobalMemoryStatusEx / POSIX sysconf).
  범위 = 2GB ~ min(총RAM*0.75, 16GB). 권장값 = 총RAM 8/16GB 기준 2/4/6GB.
- api.set_memory(mb): 범위 클램프 후 config.json 의 max_mem_mb 에 저장.
- client_launch(): 저장된 값을 launcher.launch(max_mem_mb=...) 로 전달 → -Xmx 적용.
- 프론트: 설정탭에 메모리 카드. 슬라이더(input=미리보기 / change=저장) + 프리셋 칩
  (2/4/6/8GB, 권장 표시) + 총 RAM 55% 초과 시 경고. 아이콘은 sliders-horizontal.

## FileSystemException (jar 잠김) — 근본 원인은 v2.1 잔재 (16단계)
증상: java.nio.file.FileSystemException — .minecraft\versions\fabric-loader-...jar
      "다른 프로세스가 파일을 사용 중" (net.fabricmc.installer 스택)

### 진짜 원인 (두 겹)
1. **잘못된 경로**: quick_check() 가 'Fabric 미설치'를 사전점검 문제로 보고 →
   run_preflight_async() → v2.1 의 fabric-installer.exe 다운로드/실행 →
   이 설치기는 %APPDATA%\.minecraft 에 설치한다 (우리 격리 인스턴스가 아님).
   v3 는 Fabric 을 game_installer.install(mll) 이 인스턴스에 넣으므로 완전 불필요.
2. **파일 잠김**: 그 .minecraft 의 jar 를 실행 중인 마인크래프트(공식 런처 등)가
   잡고 있어 deleteIfExists 가 실패.

### 수정
- api.quick_check(): Fabric 미설치를 problems 에 넣지 않음
  (게임 미설치 상태일 뿐 → 플레이 탭 '게임 설치'로 해결).
- preflight.run_preflight(): Fabric 단계에서 fabric-installer.exe 실행 제거.
  상태만 on_status("fabric_skip") 로 알림. → .minecraft 를 건드리는 경로 소멸.
  (download_fabric_installer / run_fabric_installer 함수는 남아있으나 호출부 없음)
- 프론트: PF_STEP 에 fabric_skip → ["fabric","done"] 매핑 추가.

### 강제 종료는 하지 않는다 (의도적 결정)
잠근 프로세스가 플레이 중인 마인크래프트일 수 있고, taskkill 로 죽이면
월드 데이터가 손상될 수 있다. 대신 감지 + 안내:
- game_installer._assert_installable(): 설치 전 (1) launcher.is_game_running()
  (2) 인스턴스 versions/*.jar 잠김 여부(_is_file_locked: 쓰기 모드 open 시도)
  를 확인해 InstallError 로 차단 → "마인크래프트를 완전히 종료한 뒤 다시 시도".
  * is_game_running() 은 우리가 띄운 프로세스만 알기 때문에, 공식 런처로 켠
    경우까지 잡으려고 파일 잠김 검사를 함께 둔다.
- install() 예외 번역: FileSystemException / PermissionError / "다른 프로세스"
  → 사용자에게 뜻이 통하는 한글 메시지로 변환.

## Fabric 로더 업데이트 구현 (17단계)
mll 은 스스로 갱신하지 않는다. 검사 → 설치를 우리가 호출하는 구조.
필요한 부품은 mll 에 다 있음: get_all_loader_versions / install_fabric(loader_version=).

### 기존 구멍
설정탭 Fabric 업데이트 버튼이 "게임 실행 시 자동 설치됩니다" 안내만 띄웠는데,
client_launch 는 로더를 갱신하지 않으므로 사실이 아니었다. 즉 로더를 올릴 방법이
아예 없었다.

### 백엔드 (game_installer.py)
- check_loader_update(): state.json 의 fabric_loader_version vs _pick_stable_loader()
  → not_installed | up_to_date | update_available | check_failed
- update_loader(on_progress): _assert_installable()(잠김/실행 검사 재사용) →
  install_fabric(loader_version=새버전) → is_version_ready 검증 →
  set_installed_version_id(새 version_id) → _cleanup_old_version(옛 로더 폴더 제거)
  * 진행률은 install() 과 동일한 단조증가 콜백(0~99), 100 은 검증 후에만.
  * 파일 잠김 예외는 한글 메시지로 번역.
- _cleanup_old_version(): "fabric-loader-" 로 시작하는 폴더만 삭제.
  바닐라 버전 폴더(26.1.2)는 새 로더가 상속해 쓰므로 절대 삭제 금지 (안전장치).

### api.py
- check_updates(): fabric 판정을 game_installer.check_loader_update() 로 교체
  (mc_dir 캐시 영향 제거, 인스턴스 state.json 기준).
- update_fabric_async(): 백그라운드 + window.onFabricUpdate(pct,msg) push.
  게임 설치 중이면 거부. _fabric_updating 플래그로 중복 방지.

### 프론트
- doFabricUpdate(): 게임 미설치 → "게임 설치 먼저", 게임 실행 중 → "종료 후" 로 선차단.
- onFabricUpdate(): 진행률을 Fabric 행 뱃지에 표시, 완료 시 reloadVersions()+refreshClient().
- verBtnLabel("fabric"): 업데이트 중 / 게임 설치 필요 / 로더 업데이트 로 분기.

## 버전행 모순: "0.19.3 → 설치 필요" 인데 뱃지는 "최신" (18단계)
증상(스크린샷): 게임 설치 후 새로고침하면 Fabric 행이
  텍스트 "0.19.3 → 설치 필요" + 뱃지 "최신" 으로 서로 모순.

### 원인 (두 겹)
1. updateVerRowsInPlace() 가 오른쪽 .ver-status(뱃지/버튼)만 갈아끼우고
   왼쪽 "current → newest" 텍스트는 옛 DOM 그대로 뒀다. 두 곳이 독립 갱신됨.
2. applyVersions(): 설치 후 current 는 0.19.3 으로 갱신되지만,
   `if(latest!==false) newest=...` 가드 때문에 latest=false 시절의
   newest="설치 필요" 가 고착됐다.

### 수정
- verTextHTML(v) / verStatusHTML(v) 공용 렌더러로 추출.
  verRow(전체 렌더)와 updateVerRowsInPlace(제자리 갱신) 모두 이 둘만 사용
  → 구조적으로 어긋날 수 없게 만듦. 텍스트에 data-vertext="<id>" 식별자 부여.
- applyVersions(): current 가 실제 버전인데 newest 가 자리표시자
  (_VER_PLACEHOLDER: 설치 필요/미설치/확인 필요/확인 불가/"")면 newest=current,
  latest=true. 설치는 항상 최신 stable 로더를 쓰므로 정확함.
- applyUpdateResult(): up_to_date 시 newest=current 로 자리표시자 제거,
  installed 값으로 current 도 갱신. not_installed 시 current="미설치".
- verBtnLabel("fabric"): fab.current 가 실제 버전이면 게임 설치된 것으로 보고
  "로더 업데이트" (client 상태 갱신 전에 "게임 설치 필요"로 잘못 뜨던 것 수정).

### 리네이밍 잔재
- DATA.system 의 label:"모드 런처" → "런처"
- 개발자 알림 문구 "동글랜드 전용 모드 런처" → "동글랜드 전용 런처"

### E2E 강화
- 소스에서 btn--update 문자열 개수를 세던 검사(리팩터링으로 깨짐) →
  설정탭에서 실제 렌더 확인 + "화살표(→) 있는데 '최신' 뱃지" 모순 검사로 교체.
- /tmp/vertows.js: 미설치 → 설치 후 → 업데이트 가능 3단계 시나리오 재현 테스트.

## A-1/A-2: 실행 전 무결성 검증·복구 (19단계) — 안정화 1순위
근거: mll 공식 문서 — install_minecraft_version 은 설치를 검증하고 복구하므로
"실행 전에 매번" 호출해야 하며, 빠졌거나 손상된 파일만 다시 받는다.

### A-2. is_version_ready() 강화 (instance.py)
[문제] 이전 구현은 versions/<id>/<id>.json 존재만 확인.
  → client.jar, 라이브러리, 에셋이 하나도 없어도 '설치 완료' 로 판정.
  → 진행률 100% 를 "검증 후에만" 내보내도록 고쳤는데, 그 검증 자체가 빈껍데기였음.
[수정] 구조적 확인:
  1) 버전 JSON 존재 + 파싱 가능 (깨진 JSON 이면 False)
  2) inheritsFrom 있으면 부모(바닐라) JSON 존재
  3) 실행에 쓰는 client.jar 존재 (Fabric 은 부모 jar 상속 → 부모 jar 확인)
  * 파일별 sha1 무결성은 비싸므로 verify_and_repair 가 담당.

### A-1. verify_and_repair() (game_installer.py)
- _assert_installable()(게임 실행중/파일잠김 검사) 재사용 후
  _install.install_minecraft_version(version_id, mc_dir, callback) 호출.
- mll 의 do_version_install 이 하는 일 (소스 확인):
    inheritsFrom → 바닐라 재귀 검증 / install_libraries(sha1) /
    install_assets(sha1) / client.jar(sha1) /
    javaVersion 있으면 install_jvm_runtime 까지 자동
  → 로컬 JSON 이 있으면 그걸 읽으므로 Fabric 버전 id 를 그대로 넘기면 된다.
- setStatus("Download ...") 횟수를 세어 repaired/files 를 반환(복구 발생 여부).
- 파일 잠김 예외는 한글 메시지로 번역.

### api.client_launch
- 실행 직전 verify_and_repair(on_progress=_prep) 호출.
  진행률은 window.onLaunchPrep(pct,msg) 로 push. 실패 시 error="verify_failed".
- 정상 설치 상태면 파일 존재+sha1 확인만 하므로 수 초 내 종료.

### 프론트
- state.launchPrep {pct,msg}. 실행 버튼에 현재 단계 표시
  (NN/g: 긴 대기에는 현재 단계를 사용자 언어로 노출).
- prepMsgKo(): mll 의 영어 상태 문자열 → "라이브러리 확인 중/리소스 확인 중/
  파일 내려받는 중/Java 런타임 준비 중" 등 한글로 번역.
- **성능**: 검증 진행률은 수백 번 발생 → renderScreen() 전체 재렌더 금지.
  #launch-btn-holder 를 두고 refreshLaunchBtn() 으로 버튼만 교체.
- verify_failed 시 refreshClient() 로 설치 상태 재확인.

### 부수 효과
do_version_install 이 javaVersion 을 보고 install_jvm_runtime 을 부르므로,
A-3(Java를 mll runtime 으로 교체)의 상당 부분이 여기서 자동 해결된다.

### 검증
- json 만 존재 → False / 부모 json 만 → False / 부모 jar 까지 → True / 깨진 json → False
- client.jar 삭제 후 is_version_ready()=False (예전엔 True 였음)
- 미설치 상태에서 verify_and_repair → InstallError 차단

## A-3: Java 를 Mojang 공식 런타임으로 전환 (20단계)

### [DECISION] '최신 LTS 로 통일' 은 채택하지 않음 (위험)
근거: Java 가 요구보다 높으면 Fabric 의 Mixin/ASM 이 새 클래스 파일을 읽지 못해
  `IllegalArgumentException: Unsupported class file major version 64` (=Java 20)
  같은 오류로 게임이 깨진다. 실제 사례: 1.18.2(Java 17 요구)를 Java 19 로 돌려 크래시.
Minecraft 는 Mojang 이 특정 JVM 으로 테스트해 출시하고, 모드도 그 Java 에 맞춰
컴파일된다. 최신 LTS 는 '더 좋은 것'이 아니라 '테스트되지 않은 것'.

### 정답지 = 버전 JSON 의 javaVersion 컴포넌트
- fabric 버전 json 엔 javaVersion 이 없고 부모(바닐라)에 있다.
  mll 의 get_client_json → inherit_json 이 부모에서 시작해 자식을 덮으므로
  javaVersion 이 그대로 상속된다. (테스트로 확인)

### game_installer 신규
- runtime_info(): get_version_runtime_information → {name, major, installed, path}
- java_executable(): 인스턴스 런타임 경로. Windows 는 javaw.exe 우선(콘솔창 없음).
- ensure_runtime(): install_jvm_runtime — sha1 검증 + 병렬 다운로드,
  인스턴스 안(runtime/<name>/<platform>/...)에 격리 설치. 관리자 권한 불필요.

### launcher._java_executable() 우선순위
1) 인스턴스의 Mojang 런타임  2) 시스템 Java 폴백(javaVersion 없는 구버전용)

### 제거된 위험 경로
- preflight.check_java_status(): status 에서 "outdated" 개념 삭제.
  → "ok | managed | needed | check_failed". managed = 런처 관리 런타임 사용 중.
- api.install_java_async(): Adoptium MSI 다운로드 + run_java_installer(UAC 마법사)
  → game_installer.ensure_runtime() 으로 교체. to_latest 인자는 무시(하위호환).
- preflight.run_preflight(): Java 단계에서 MSI 설치 마법사 실행 제거 → 상태 안내만.
- 프론트: "최신 LTS로 교체" 버튼 삭제, onJavaInstall 의 "run"(설치 마법사) phase 제거,
  pf.needsInstaller = false 고정.
- download_java_installer / run_java_installer / get_latest_java_lts 는 정의만 남고
  호출부 0 (릴리스 후 정리 가능).

### 부수 효과
verify_and_repair(=install_minecraft_version) 의 do_version_install 이
javaVersion 을 보고 install_jvm_runtime 을 이미 부른다.
→ 게임 설치/실행만 하면 정확한 Java 가 자동으로 준비된다. 사용자 조작 0.

### 검증
- 부모 상속으로 java-runtime-delta(21) 식별 ✅
- 미설치 → java_executable() None → 시스템 폴백 ✅
- 설치 후 → status="managed", 경로 반환 ✅

## B: 백엔드/프론트 최적화 — 측정 기반 (21단계)

### 측정: 부팅 경로의 실제 비용
부팅 호출 순서: quick_check → ensure_ready → get_catalog → get_versions → scan_mods

scan_mods 가 병목. 모드 12개 설치 기준:
  Step2 get_projects_batch     1회 (이미 배치+캐시 — 잘 돼 있었음)
  Step3 get_version_from_hash  jar 개수만큼 = 12회  ← jar 하나당 1요청
  Step4 get_latest_compatible  모드 수만큼   = 12회  ← 모드 하나당 1요청
  합계 약 25회, 전부 순차.
게다가 urllib.request.urlopen 은 연결 재사용을 하지 않아 매 요청마다 TCP+TLS
핸드셰이크. 1회 ~150ms 가정 시 약 3.75초.

### 수정: Modrinth 배치 엔드포인트 사용 (25회 → 2회)
- modrinth_api._post_json() 추가.
- get_versions_from_hashes(hashes)        → POST /version_files
- get_latest_versions_from_hashes(...)    → POST /version_files/update
- ⚠️ Modrinth 는 대문자 해시를 거부한다 (modrinth/code#2707) → 항상 .lower().
- sha1_of_file_cached(): (경로, mtime_ns, size) 키 캐시. 상한 256.
- api.scan_mods Step3/4 를 배치로 재작성.
- USER_AGENT: "dongleland-mod-installer/2.0" → "grkim1519/dongleland-launcher/3.0"
  (Modrinth 는 고유 UA 요구, 일반적 UA 는 차단될 수 있음)

검증(모의 서버): 네트워크 2회, sodium=update / fabric_api=installed 로
이전과 동일한 상태 판정. 대문자 해시 전송 시 assert 로 검출되도록 테스트.

### 프론트: skinview3d 지연 로드 (468KB)
- <head> 에서 동기 <script src> 로 항상 로드 → 스킨 탭에 가지 않아도 파싱 비용.
- ensureSkinView(): 필요 시 한 번만 동적 삽입, Promise 반환.
  syncSkin3D() / drainThumbQueue() 에서 await 후 재시도, 실패하면 기존 폴백.
- 검증: 부팅 시 외부 스크립트 0개, 스킨 탭 진입 시 삽입 확인.

### 과잉 우려였던 것 (측정으로 기각)
- "5초 게임 실행 폴링이 renderScreen 전체 재렌더" → 실제로는 게임 종료 시 1회만.
  그래도 버튼만 갱신하면 되므로 refreshLaunchBtn() 으로 교체.
- get_projects_batch 는 이미 배치 + config 캐시로 잘 구현돼 있었다.

### 남은 최적화 후보 (미착수)
- renderScreen() 의 innerHTML 통째 교체 (모드/셰이더 카드 다수 시 DOM 재구축)
- HTTP 연결 재사용 (urllib → requests.Session). mll 이 requests 를 이미 의존하므로
  추가 비용 없음. 배치화로 요청 수가 2회로 줄어 우선순위는 낮아짐.

## 다운그레이드 후 '업데이트' 미표시 버그 (22단계)
[원인] 프론트 pickVersion() 이 설치 성공 시 m.state="installed" 를 무조건 대입.
  백엔드 install_version() 도 상태를 돌려주지 않았다.
  → 구버전으로 되돌려도 '설치됨' 으로 보임. scan_mods 는 부팅 때만 도니 재시작 전까지 유지.
[수정]
- api._status_after_install(): 설치된 파일의 sha1 을
  get_latest_versions_from_hashes 로 최신 sha1 과 비교 → "installed" | "update".
  확인 실패 시 보수적으로 "installed" (잘못된 업데이트 유도 방지).
- install_version() 이 {"ok":True,"version":...,"status":...} 반환.
  모드는 _mod_statuses 도 즉시 갱신.
- 프론트: m.state = (r.status==="update") ? "update" : "installed".
  되돌린 경우 "버전 X (으)로 되돌렸습니다 — 최신 버전이 있습니다" 안내.
- 모드/셰이더 모두 동일 경로.

## C: 진행률 단계표시 + 취소 (23단계)
### C-1. 정직한 진행률 (점근 곡선 폐기)
[문제] 21단계에서 넣은 '남은 구간의 60% 소비' 방식은 단조 증가는 되지만
  끝에서 92% 근처에 오래 머문다. NN/g 가 지적하는 대표적 안티패턴
  ("마지막 몇 %에서 멈추면 진행률 표시의 이점이 상쇄된다").
[해결] mll 이 실제로 주는 단계를 그대로 노출한다. mll 소스 확인 결과:
    setStatus("Download Libraries") + setMax(len(libraries)-1)
    setStatus("Download Assets")    + setMax(len(assets)-1)
    setStatus("Install java runtime")
    setStatus("Installation complete")
    setStatus("Download <파일명>")   ← _helper.download_file
  → _STAGES 매핑으로 단계명/번호를 만들고, on_progress(pct, msg, detail) 로
    detail={stage, stage_no, stage_total, cur, max, raw} 전달.
    pct 는 '현재 단계 내' 퍼센트. 전체 %를 억지로 추정하지 않는다.
  UI: "라이브러리 (1/4 단계)" + "342 / 1,200 파일" + 진행바.

⚠️ 함정: pct 가 단계마다 100 에 도달한다. 프론트의 pct>=100 완료 판정이
  그대로 있으면 첫 단계 끝에 '설치 완료'가 뜬다(3단계에서 고쳤던 버그의 재발).
  → 완료 신호를 detail.raw==="done" 으로 변경. onClientInstall / onFabricUpdate 모두.
  백엔드의 완료 push 4곳(설치/검증/Java/업데이트)에 done detail 을 붙였다.

### C-2. 취소 버튼
mll 에는 취소 API 가 없다. → 진행률 콜백 안에서 InstallCancelled 예외를 던져 중단.
- game_installer: _cancel(threading.Event), request_cancel/clear_cancel/is_cancelled.
  _make_callback._emit() 이 매 이벤트마다 취소를 확인.
  install/verify_and_repair/update_loader 진입 시 clear_cancel(),
  except InstallCancelled: raise 로 잠김-에러 번역 로직을 우회.
- api.cancel_install(): 진행 중일 때만 취소 요청. 진행률 -2 로 취소를 신호.
- 프론트: 설치 카드에 취소 버튼(.ci-foot), state.clientCancelling,
  onClientInstall(-2) 시 카드 정리 + refreshClient().
- 이미 받은 파일은 남지만 다음 설치/검증에서 재사용되고 빠진 것만 받으므로 손해 없음.

### 검증
- 단계 시뮬: 라이브러리 0→50/50, 리소스 0→1200/1200, Java, 마무리 (정체 없음)
- 취소: 콜백에서 InstallCancelled 발생 확인, clear_cancel 후 복구
- /tmp/canceltest.js: 단계/파일수/취소버튼 표시, 취소 후 설치버튼 복귀
- E2E 에 단계·파일수·취소버튼 검사 추가 (더미 설치 5.3초로 늘어나 대기 조정)

## 모드 관리 개선 + 의존성 자동 설치 (24단계)

### 크래시 원인 (Fabric "Incompatible mods found!")
두 종류가 섞여 있었다.
1) **필수 의존 모드 누락** — chatpatches→yet_another_config_lib, subtle_effects→fzzy_config,
   litematica→malilib. 이 모드들은 mod_catalog.py 에 아예 없고,
   카탈로그의 "dependencies" 는 손으로 채우는 구조라 전부 빈 배열이었다.
   → Modrinth 버전 JSON 의 dependencies(required) 를 읽어 자동 설치하도록 수정.
2) **모드 간 버전 제약** — sodium 0.9.1 과 iris 1.10.9 는 각각 26.1.2 호환이지만
   iris 1.10.9 는 sodium 0.8.x 를 요구한다. 우리는 모드마다 독립적으로
   '게임 버전 호환 최신' 을 고르므로 이 제약을 볼 수 없다. (미해결 — 아래 참고)

### 의존성 자동 설치 (modrinth_api / api)
- required_dependency_project_ids(version): dependency_type=="required" 만 추출
  (optional/embedded/incompatible 제외).
- get_projects_meta(ids): GET /projects?ids=[...] 배치 1회로 project_id→slug/title.
- install_mod_by_slug 가 "requires": [project_id...] 를 함께 반환.
- api._install_modrinth_deps(): 카탈로그에 없는 모드도 설치. 의존의 의존까지
  (depth<=3), 이미 설치된 project_id 는 건너뜀(self._installed_pids).
- install_mod / install_version 이 deps(설치된 이름 목록), dep_failed 반환.
검증: chatpatches → YACL → Fabric API 연쇄 설치, optional 은 미설치.

### 설치된 버전을 어디서도 볼 수 없던 문제
- scan_mods 가 versions: {mod_id: {installed, latest}} 를 함께 반환.
- _status_after_install() 이 (status, 최신버전번호) 튜플 반환 → 조회 1회로 통합.
- install_mod/update_mod/install_version 이 version(+latest) 반환.
- 프론트: applyStatuses(statuses, versions) → m._installedVersion / m._latest.
  · 모달 metagrid 에 "설치된 버전" 셀 추가 (update 상태면 "0.8.9 (구버전)")
  · 카드 badge-row 에 v0.9.1 뱃지 (최신=emerald, 구버전=gold)
- 재설치 시 구버전이 깔린다는 의심 → 시뮬레이션 결과 백엔드는 정상
  (설치→롤백→제거→재설치 = 최신). 버전이 화면에 없어서 그렇게 보였던 것.

### 모달 액션 재설계
- ⋯(버전 선택)은 **항상** 주 버튼 바로 왼쪽:
    미설치  [⋯][설치]
    설치됨  [제거][⋯][설치됨]
    업데이트[제거][⋯][업데이트]
  제거 버튼이 생기면 ⋯ 가 밀리고, 제거하면 되돌아온다.
- ⚠️ update 상태에 제거 버튼이 없던 버그 수정.
- ⚠️ 제거 버튼이 data-install 을 쓰고 있어서, doInstall 이 상태로 분기하는 탓에
  update 상태에서 '제거'를 누르면 업데이트가 실행됐다.
  → data-modrm + doRemove() 로 명시적 분리.
- 드롭다운: .ver-anchor 기준 오른쪽 정렬 + 위로 열림.
  placeVerMenu(): 버튼 위 공간이 부족하면 data-place="down" 으로 아래로 연다.
- 라벨 통일: "지금 업데이트" → "업데이트", "로더 업데이트" → "업데이트".

### 남은 문제 (미해결)
모드 간 버전 제약(sodium/iris)은 per-mod 최신 선택으로는 풀 수 없다.
해결하려면 jar 안의 fabric.mod.json 의 depends/breaks 범위를 읽어
조합을 검사하거나(설치 전 검증), 실행 전 사전 점검으로 막아야 한다.

## 모드 UI 정밀 조정 + 3.0.0 베타 (25단계)
- 모드/셰이더 **카드**의 설치 버전 뱃지 제거 (cardVerBadge 삭제). 버전은 모달에서만.
- 모달 metagrid: "제작자" 칸 삭제 → 3칸(설치된 버전 / 최신 버전 / 호환성)으로 정렬.
  제작자는 다운로드·종류 행 오른쪽에 아이콘과 함께 표시 (data-meta="author").
- 버전 선택 버튼: "⋯" → git-branch 아이콘 + "버전 선택" (btn--ghost).
- 드롭다운: width 264→320px, max-height 240→260px.
  .ver-menu-item 을 flex-direction:column 으로 바꿔 버전 번호가 한 줄을 온전히 쓰고,
  날짜/채널은 아랫줄(.ver-meta)로. .ver-num 은 white-space:nowrap+ellipsis 대신
  overflow-wrap:anywhere → "fabric-0.100.1+1.21.4"(21자)도 잘리지 않는다.
- app_meta: APP_VERSION "2.1.1" → "3.0.0", APP_CHANNEL = "beta" 신설.
  api.get_versions() 가 app_channel 반환.
  프론트: DATA.account.appChannel, verTextHTML() 의 런처 행과 하단 크레딧에
  .chan-chip(BETA) 표시. 정식 배포 시 APP_CHANNEL="release" 로만 바꾸면 사라짐.

### 검증
- /tmp/modui.js: 카드 버전 미표시, 제작자 위치, metagrid 3칸, "버전 선택" 라벨,
  [제거][버전 선택][업데이트] 순서, update 상태 제거 버튼 유지.
- /tmp/vermenu.js: BETA 칩, 폭 320px, ver-num 줄바꿈, 항목 2줄 구조.

## 모달/탭 버그 수정 (26단계)
1. 설치 후 '설치된 버전' 이 모달을 다시 열어야 갱신되던 문제
   → refreshModalAction() 이 액션 행뿐 아니라 [data-meta="installed-version"] /
     [data-meta="version"] 셀도 제자리 갱신. 설치/업데이트/제거/롤백 모든 경로 커버.
2. 모달 하단 버튼 글자가 세로로 접히던 문제
   → .btn / .install 에 white-space:nowrap; flex:0 0 auto.
     .mfoot 에 flex-wrap:wrap. "프로젝트 페이지" → "프로젝트" 로 축약.
3. 일부 모달에서 제작자 아이콘이 사라지던 문제 (원인)
   → 프로젝트 상세 도착 시 setCell() 이 el.textContent=val 로 덮어써 내부 SVG 를 삭제.
     아이콘이 있으면 SVG 를 보존하고 텍스트 노드만 교체하도록 수정.
4. 셰이더 탭 전환 애니메이션이 사라지던 문제 (원인)
   → setNav 가 renderScreen(true) 로 애니메이션을 시작한 직후,
     loadShaders()/loadShaderReady() 완료 콜백이 renderScreen(false) 로 노드를 교체.
     __animUntil + renderScreenSoon() 으로 애니메이션이 끝난 뒤 다시 그린다.
5. BETA 등 영어 라벨 글꼴
   → --font-mono 의 'Space Mono' 제거, 기본 UI 글꼴(Pretendard) 사용.
     .mono 는 font-variant-numeric:tabular-nums 로 숫자 정렬만 유지.
     SpaceMono woff2 @font-face 2개 삭제 → 부팅 시 폰트 다운로드도 감소.

## 제거/초기화 정합성 (27단계)
1. 라이브러리 카드의 '제거' 버튼이 data-install 을 써서, update 상태에서 누르면
   doInstall 이 update_mod 를 호출했다(모달과 동일한 버그).
   → data-modrm + doRemove(). 브라우저 폴백에서도 m.state 를 갱신하도록 수정.
2. 롤백 안내 문구를 "(으)로 변경했습니다" 로 통일.
3. **의존 모드가 초기화 후에도 남던 문제**
   원인: _install_modrinth_deps 가 설치한 모드를 레지스트리에 기록하지 않아
   reset_instance(레지스트리 기반)가 찾지 못했다. 갱신 시 옛 jar 도 남았다.
   수정:
   - DEP_PREFIX("__dep__:") + _dep_key(project_id) 로 의존 모드를 레지스트리에 기록.
   - 의존 모드 재설치 시 파일명이 바뀌면 이전 jar 를 삭제 → 중복 방지.
   - scan_mods 가 설치된 jar 들의 dependencies(required)를 모아 required_pids 를 만들고,
     카탈로그에 없으면서 required_pids 에 속하는 jar 를 __dep__ 로 소급 등록.
     → 이 변경 이전에 설치된 의존 모드도 초기화 대상이 된다.
     사용자가 직접 넣은 무관한 모드는 required_pids 에 없으므로 보존된다.
   - reset_instance 가 _installed_pids / _mod_versions 도 비운다.
   검증: chatpatches + yacl(의존) + mine(사용자) → 초기화 후 mine.jar 만 잔존.
        의존 갱신 시 yacl-3.6.jar 삭제 후 yacl-3.7.jar 만 남음.

## 버전 선택 후 스크롤이 맨 위로 튀는 버그 (28단계)
pickVersion() 끝에서 renderScreen(false) 로 화면을 통째로 다시 그려
#screen-holder 의 자식이 교체되면서 스크롤 위치가 초기화됐다.
→ refreshItemInPlace(m, kind) + renderSidebar() 로 해당 카드/행만 제자리 갱신.
검증: pickVersion 전후 .screen 노드 동일성 확인 (/tmp/scroll.js)

## 3.0.0 정식 릴리스 전환 (29단계)
- app_meta.APP_CHANNEL: "beta" → "release" (한 줄).
  프론트는 DATA.account.appChannel 로만 판단하므로 BETA 칩이 자동으로 사라진다.
- 미리보기 더미의 하드코딩된 appChannel 도 "release" 로 동기화.
- build.bat / .spec 에는 버전 하드코딩이 없어 추가 수정 불필요.
검증: 설정 탭에서 BETA 칩 없음 + "3.0.0" 표시 유지.

## 런처 업데이트 검사 점검 (30단계)
실기 확인 중 GitHub API 가 403 을 반환 → rate_limit 조회 결과 remaining=0.
저장소 문제가 아니라 시간당 60회(비인증 IP) 한도 소진. 공유 IP 환경의 사용자도 겪는다.

### 발견된 결함
1. _version_tuple 이 자릿수를 맞추지 않아 (3,0) < (3,0,0) → "3.0" 사용자에게
   "3.0.0 업데이트 있음" 오탐. → 3자리 패딩.
2. 프리릴리스를 구분하지 못해 3.0.0-beta == 3.0.0 → 베타에서 정식판으로 못 넘어감.
   → (major, minor, patch, pre) 튜플. pre: 정식 1 / 프리릴리스 0.
   ('+build.7' 같은 빌드 메타데이터는 semver 대로 비교에서 무시)
3. 모든 실패를 check_failed 로 뭉뚱그려 원인을 알 수 없었고,
   프론트에는 실패 분기 자체가 없어 직전 상태('최신')가 그대로 남았다.
   → status 를 rate_limited / no_release / check_failed 로 구분 + message 필드.
   → 프론트: by.app.note 설정, verStatusHTML 이 "확인 불가" 뱃지(툴팁=사유) 표시.
     성공 시 note 해제.
4. preflight.USER_AGENT 가 "dongleland-mod-installer/2.0" 이라 최신화.

### 검증
- 버전 비교 11케이스 통과 (자릿수/프리릴리스/v접두어/빌드메타)
- HTTPError 403+remaining=0 → rate_limited, 404 → no_release, 500/타임아웃 → check_failed
- 프론트: rate_limited 시 '확인 불가', 이후 성공하면 note 해제 확인

## 셰이더 설치/제거 정합성 (31단계)
증상 3가지, 원인 2가지.

1) "설치됨인데 폴더에 파일이 없음"
   원인: 셰이더 목록은 state.shadersLoaded 가드로 한 번만 로드된다.
   사용자가 탐색기에서 직접 지워도 런처는 모른 채 '설치됨' 을 유지.
   → api.shader_statuses(): shaderpacks 폴더만 스캔(네트워크 없음)해
     {slug: installed|not_installed} 반환. _shader_by_slug 의 filename 도 갱신.
   → 프론트 setNav("shaders"): 목록이 이미 있으면 refreshShaderStatuses() 호출.

2) "버전 선택으로 설치한 뒤 제거하면 '설치된 셰이더 파일을 찾을 수 없습니다'"
   원인: install_shader() 는 _shader_by_slug[slug]["filename"] 을 기록하지만
   install_version(kind="shader") 은 기록하지 않았다. remove_shader 는 그 맵을 본다.
   → install_version 의 셰이더 분기에서 filename/project_id/version 을 기록하고
     반환값에도 filename 을 포함. 프론트 pickVersion 이 m._filename 갱신.

3) "제거가 아예 안 됨"
   원인: 맵이 비면(런처 재시작 후 셰이더 탭 미방문) 복구 로직이 info["project_id"]
   에만 의존해 실패 → not_found 에러.
   → slug → project_id 를 get_projects_batch 로 직접 조회해 복구.
   → 그래도 파일이 없으면 에러 대신 {"ok":True,"status":"not_installed"} 를 반환한다.
     실제로 없는 것을 '제거 실패' 라고 하면 UI 가 영영 정상화되지 않는다.

검증(시뮬): 버전 선택 설치 → 파일명 기록 → 제거 성공 → 직접 삭제 후
shader_statuses 가 not_installed 로 정정 → 재제거 시도도 정상 처리.

## 제3자 라이선스 고지 + 사용자 동의 (32단계)
⚠️ 변호사 검토를 받은 문서가 아니다. 실무용 초안.

### 실제 의존성 조사 결과 (추측이 아니라 확인)
- minecraft-launcher-lib (JakobDev) — BSD-2-Clause
- pywebview (Roman Sirokov) — BSD-3-Clause
- requests — Apache-2.0 / certifi — MPL-2.0
- skinview3d — MIT (Kent Rasmussen 2014-2018, Haowei Wen·Sean Boult 2017-2022)
  · 번들 안에 three.js(MIT, © 2010-2026 three.js authors)가 포함되어 있어 별도 표기 필요
- 아이콘 — Lucide (ISC). 일부는 Feather(MIT, Cole Bemis)에서 유래
- Pretendard — SIL OFL 1.1 (Kil Hyung-jin) / Pixelify Sans — SIL OFL 1.1
- PyInstaller — GPL-2.0 with bootloader exception (빌드 도구, 결과물에 전파 안 됨)

### 정리한 것
- SpaceMono woff2 2개 삭제 (더 이상 참조되지 않음 → 재배포 의무·용량 감소)
- THIRD_PARTY_NOTICES.md 작성 (구성요소·라이선스·용도·외부 서비스·비제휴 고지)
- TERMS.md 작성 (하는 일/안 하는 일, 저장 정보, 보증 부인, 책임 제한, 사용자 책임)
- .spec datas 에 두 문서 포함 → 오프라인에서도 확인 가능

### 동의 게이트
- app_meta.TERMS_VERSION="1.0" + TERMS_URL / NOTICES_URL
- api.get_terms_status() / accept_terms() / open_terms_page() / open_licenses_page()
  · config 에 terms_accepted_version 저장 → 약관 개정 시 버전을 올리면 자동 재동의
- 프론트: renderGate 에 mode="terms" 추가. **auth_status 조회보다 먼저** 검사한다.
  체크박스를 켜야 '동의하고 시작' 이 활성화된다(형식적 클릭 방지).
  동의 후 bootFromBackend() 를 다시 호출해 원래 흐름을 잇는다.
- 설정 탭 하단에 '이용 약관' / '오픈소스 라이선스' / 'Mojang·Microsoft 비제휴' 상시 노출.

검증: 최초 실행 미동의 → 게이트, 동의 저장 → 통과, TERMS_VERSION 1.1 로 올리면 재동의 요구.
프론트: 체크 전 버튼 비활성, 필수 문구 4종 렌더 확인 (/tmp/terms.js)

## 부팅이 '불러오는 중' 에서 멈추던 버그 (33단계)
원인: 약관 게이트를 넣으면서 부팅의 뒷부분을 continueBoot() 라는 이름으로 분리했는데,
**같은 이름의 함수가 이미 존재했다**(로그인 이후 카탈로그/버전을 불러오는 함수, 1962줄).
함수 선언은 나중 것이 앞의 것을 덮어쓰므로, bootMain() 이 부르던 진짜 continueBoot() 가
사라지고 내 함수가 실행됐다. → 카탈로그를 못 불러와 state.booting 이 계속 true.
약관과 무관하게 모든 사용자가 겪는 버그였다.

수정: 새 함수를 bootAfterTerms() 로 개명. 호출부 2곳 반영.
재발 방지: 프론트 함수 선언 중복 검사 추가 (145개, 중복 0).
   python: re.findall(r'^\s*(?:async\s+)?function\s+(\w+)\s*\(', js, re.M) → Counter

교훈: 큰 파일에 새 최상위 함수를 추가할 때는 이름 충돌을 먼저 확인할 것.

## 부팅이 '불러오는 중' 에서 멈추던 버그 (33단계)
원인: 약관 게이트를 붙이면서 부팅 뒷부분을 continueBoot() 라는 이름으로 분리했는데,
**이미 같은 이름의 함수가 1962줄에 존재**했다(로그인 이후 카탈로그 로딩 담당).
함수 선언은 나중 것이 앞의 것을 덮어쓰므로, 로그인 성공 후 카탈로그를 영영 못 불러왔다.
→ 약관과 무관하게 모든 사용자가 겪는 회귀였다.

수정: 내가 추가한 함수를 bootAfterTerms() 로 개명. 기존 continueBoot() 는 그대로.
안전망: bootFromBackend / acceptTerms 가 예외 시 booting=false + showGate("idle").
재발 방지: 프론트 함수 중복 정의 검사 추가 (현재 145개, 중복 0).

## 게이트 로고의 글래스 박스 제거 (34단계)
.logo:has(img) 규칙으로 타이틀바·사이드바는 이미 배경/테두리를 지웠으나
.gate-logo 에만 border 가 남아 있었다 → 로그인/약관 화면에서 아이콘 뒤 유리 박스.
.gate-logo 에서 border 제거. (app_icon.png 는 128x128 정사각이라 cover 로도 안 잘림)

## 저장소 주소 확정 (35단계)
실제 저장소: https://github.com/Garamisme/dongleland_Launcher
(코드에는 grkim1519/dongleland-installer 로 되어 있어 업데이트 검사가 404 날 뻔했다)

- preflight.GITHUB_OWNER/GITHUB_REPO → Garamisme / dongleland_Launcher
- app_meta._REPO 갱신. TERMS_URL/NOTICES_URL 은 blob/main 대신 **blob/HEAD** 사용
  → 기본 브랜치가 main 이든 master 든 GitHub 가 알아서 해석하므로 링크가 안 깨진다.
- USER_AGENT (preflight, modrinth_api 양쪽) 를 실제 저장소 이름으로 통일.
- TERMS.md / PROJECT_STATUS.md 의 저장소 표기도 수정.
- README.md 신규 작성 (사용자용 설치·문제해결 + 개발자용 빌드·구조 + 비제휴 고지).
  ⚠️ LICENSE 파일은 아직 없음 — README 와 THIRD_PARTY_NOTICES 가 참조 중.

## Claude Code 인수인계 (36단계)
- tests/ 를 저장소로 옮김 (그동안 /tmp 에 있어 세션 종료 시 소실 위험).
  경로를 __dirname 기준으로 바꿔 어디서 실행해도 동작.
- tests/run_all.py: 컴파일 + 프론트↔api 계약(67) + **함수 중복 정의** + JS 문법 +
  jsdom 스위트 14개를 한 번에. jsdom 미설치 시 14개 실패 대신 안내 1줄.
- vermenu.js 의 낡은 BETA 검사 제거 (채널 검증은 beta.js 담당).
- HANDOFF_CLAUDE_CODE.md: 코드를 읽어도 알 수 없는 것만 기록
  (확정 설계, 반복 함정 5개, 무한로딩 실수, 미해결 과제, 작업 방식).
- CLAUDE.md: Claude Code 가 자동 로드하는 짧은 진입점.
- 문서 검증 중 오류 1건 발견: APP_DIR_NAME 은 app_meta 가 아니라 instance.py 에 있다 → 정정.

### Entra ID 관련 메모
auth.py 의 _TENANT 는 이미 "consumers" (개인 MS 계정 전용).
Azure 앱 등록이 "모든 Entra ID 테넌트 + 개인 계정" 으로 되어 있어도 동작에는 문제없지만,
Minecraft 는 개인 계정으로만 소유하므로 Azure 쪽도 개인 계정 전용으로 좁히는 편이 안전하다.
(_TENANT 를 common 으로 바꾸면 회사 계정 사용자가 로그인 성공 후 Xbox 단계에서 실패한다)
