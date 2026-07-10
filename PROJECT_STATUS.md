# 동글랜드 런처 v3 — 전체 명세 및 점검 (2026-07-08)

프로젝트: Python + pywebview(WebView2) 기반 마인크래프트: Java Edition 전용 클라이언트
저장소: Garamisme/dongleland_Launcher · 작성자: 가람 (Garamisme)
목표: 모드 인스톨러(v2.1) → 풀 게임 클라이언트(v3)로 전환

---

## 1. 전체 아키텍처 흐름

```
[사용자]
   │  ① MS 계정 로그인 (device-code)
   ▼
[auth.py] ─── UUID + access_token 획득 ──→ [accounts.dat (DPAPI 암호화)]
   │
   │  ② 게임 설치 (없으면)
   ▼
[game_installer.py] ─ 바닐라+Fabric 다운로드 ─→ [instances/dongleland/ 격리 폴더]
   │
   │  ③ 사전 점검
   ▼
[preflight.py] ─ Java 버전 판정/설치 ─→ [Adoptium JRE 자동 다운로드]
   │
   │  ④ 실행
   ▼
[launcher.py] ─ JVM 직접 실행 + --quickPlayMultiplayer ─→ [dongleland.com 자동 접속]
   │
   ▼
[서버] ─ whitelist.json (SQLite v_whitelist 뷰) ─→ 접근 제어
```

**설계 원칙(확정, 재론의 불가)**:
- 인증 = MS 계정으로 UUID 획득 + 실행만. 접근 제어는 서버측 whitelist.
- 온라인 모드 서버가 Mojang 세션서버로 재검증 → 런처측 검사는 UX용, 보안 아님.
- 라이선스 키/코드 서명 방식은 영구 폐기.

---

## 2. 구현 완료 (검증됨)

### 백엔드
| 모듈 | 기능 | 상태 |
|------|------|------|
| auth.py | MS device-code 로그인, 멀티계정 저장(DPAPI), 자동 리프레시, 계정 전환/제거 | ✅ 실PC 로그인 확인 |
| instance.py | 격리 인스턴스 경로(DonglelandLauncher), 서버별 프로필 대비 구조 | ✅ |
| game_installer.py | 바닐라+Fabric 설치, 설치 여부 확인 | ✅ |
| launcher.py | JVM 직접 실행, quickPlay 자동접속, javaw(콘솔숨김) | ✅ dict버그 수정됨 |
| preflight.py | Java 요구버전 자동판정(게임+모드 JSON), 3상태 검사, Adoptium 동적 다운로드 | ✅ 로직 검증 |
| skin.py | 스킨 조회/변경/초기화, 로컬 라이브러리, 망토 | ✅ |
| app_meta.py | 서버/버전 상수 | ✅ |
| server_tools/dongleland_members.py | 서버 운영 CLI(whitelist export) | ✅ |

### 프론트 (6개 탭)
| 탭 | 기능 | 상태 |
|----|------|------|
| play | 설치/실행, 서버 상태, 접속자 수, 공지 | ✅ |
| mods | 모드 카탈로그, 설치/삭제/업데이트, 필수모드 게이팅 | ✅ |
| shaders | Iris 셰이더팩 큐레이션 | ✅ |
| skin | 3D 뷰어(skinview3d), 라이브러리, 망토 | 🔶 방금 전환, 확인 대기 |
| library | 계정/플레이타임 | ✅ |
| system | 설정, 업데이트 검사, 폴더 열기, 로그아웃 | ✅ |

### 인증/배포 인프라
- Azure Client ID 발급 + Mojang API 승인 완료 ✅
- 멀티계정 UI(피커/전환/추가/제거) ✅
- "다른 계정 사용" 안내 ✅
- three.js/WebGL 실PC 동작 검증 ✅

---

## 3. 구현 중 / 확인 대기

| 항목 | 상태 | 다음 액션 |
|------|------|-----------|
| 스킨 3D 렌더(skinview3d) | 🔶 코드 완료, 실PC 미확인 | 현재스킨/카드/슬림·와이드 렌더 확인, mc-heads CORS 확인 |
| Java 25 자동설치 → 실행 | 🔶 로직완료, E2E통과, 실PC 전체흐름 미확인 | Java24 PC에서 25 자동설치→게임 실행→서버 접속 확인 |
| 멀티계정 추가(다른 사람) | 🔶 안내 추가됨 | "다른 계정 사용"으로 2번째 계정 실제 추가 확인 |

---

## 4. 검증 현황 (핵심 완료, 마무리 남음)

### A. 실PC 전체 플로우 — ✅ 검증됨 (2026-07-08)
- [x] **로그인 → 게임 다운로드 → Java → 실행 → dongleland.com 자동접속: 전체 체인 실동작 확인.**
      (개별 단계뿐 아니라 end-to-end 가 한 번에 도는 것을 실PC 에서 확인)
- [ ] 폴더명 DonglelandLauncher 변경 후 기존 사용자 재로그인 흐름 (신규만 확인됨)

### B. 서버 셋업 (서버 운영자 담당 — 런처 개발 범위 밖)
- 서버가 Garam 소유가 아니므로 whitelist 셋업은 서버 운영자 몫.
- 런처는 이미 MS 계정 UUID 를 정확히 넘기므로, 운영자가 whitelist.json 에
  해당 UUID 를 넣으면 접근제어가 동작함. (런처측 할 일은 없음)
- server_tools/dongleland_members.py 는 운영자용 도구로 제공(선택).
- ✅ 현재 접속이 되는 것으로 보아 서버는 온라인모드로 정상 동작 중.

### C. 배포
- [ ] PyInstaller 빌드 → exe 정상 동작 (skinview3d 번들 포함 확인)
- [ ] 코드 서명 없음 → SmartScreen "추가정보→실행" 안내 문서화
- [ ] GitHub 릴리스 + 앱 자동 업데이트 흐름 실동작

### D. 향후 기능 (선택)
- [ ] 스킨 애니메이션 (skinview3d 내장 Walking/Idle 등)
- [ ] 소셜 기능 (MC 친구 API)
- [ ] 서버별 프로필 (인스턴스 구조는 이미 대비됨)

---

## 5. 점검 결과 — 리스크 및 확인 필요 사항

### ✅ 해결됨 (이전 최대 리스크였으나 실PC 확인)
1. ~~end-to-end 미검증~~ → **로그인→서버접속 전체 체인 실동작 확인.**
2. ~~서버 whitelist~~ → 서버 운영자 담당(Garam 소유 아님). 런처는 UUID 정확히 전달,
   현재 접속되므로 서버측 정상 동작 중.

### 🟡 남은 확인 사항 (중간)
3. **스킨 3D 렌더**: skinview3d 전환 후 실PC 미확인. 현재스킨/카드/슬림·와이드 + mc-heads CORS.
4. **exe 빌드**: skinview3d 번들이 PyInstaller 에 포함되는지 실빌드 확인
   (.spec 은 frontend/ 통째 번들이라 이론상 OK).

### 🟢 낮음
5. 코드 서명 부재 → SmartScreen 경고 (워크어라운드 있음, 배포 시 안내).
6. 기존 사용자 폴더명 변경 후 재로그인 (신규는 확인됨).

---

## 6. 계약 무결성 (자동 검증됨)
- 프론트 JS → 백엔드 API 호출 53개 전부 매핑됨 (누락 0).
- E2E 20단계 전부 통과.
- 전체 파이썬 모듈 컴파일 OK.

---

## 7. 자동 점검 실행 결과 (2026-07-08)

| 점검 | 결과 |
|------|------|
| 전체 파이썬 모듈 컴파일 | ✅ 통과 |
| 계약 무결성 (JS 53호출 → API 매핑) | ✅ 누락 0 |
| 핵심 상수 일관성 (서버/Azure/폴더명/Java) | ✅ 일치 |
| skinview3d 번들 통합 | ✅ 포함 |
| PyInstaller .spec 번들 (frontend 통째) | ✅ skinview3d 자동 포함 |
| E2E 20단계 | ✅ 전부 통과 |

### 코드 정리 완료 (2026-07-08)
- 삭제: mod_installer.py(1770줄, v2.1 tkinter 진입점, 미사용),
  dev_login_test.py(개발자 테스트, 미사용).
- mod_installer 를 가리키던 주석 4곳 갱신 (존재하지 않는 파일 참조 제거).
- app.py docstring v2.1→v3 최신화.
- 파일명은 전부 명확해 유지(과한 리네이밍은 git 히스토리 단절 → 안 함).
- 남은 죽은 API 4개(open_game_folder/launch_game/can_launch/update_all)는
  참조 없어 안전하나 배포 후 정리 권장(지금 지우면 회귀 리스크).

---

## 8. 다음 액션 (우선순위)

핵심 기능(로그인→실행→서버접속)은 실동작 확인됨. 남은 건 스킨 마무리와 배포.

1. 🟡 **스킨 3D 실PC 확인** — skinview3d 렌더(현재스킨/카드/슬림·와이드), mc-heads CORS
2. 🟡 **exe 빌드 테스트** — PyInstaller 실행, skinview3d 포함 확인
3. 🟢 **배포** — GitHub 릴리스 + SmartScreen 안내 문서
4. 🟢 (선택) 스킨 애니메이션, 소셜 기능, 서버별 프로필
5. 🟢 (배포 후) 죽은 코드 4개 정리
