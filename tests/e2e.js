/* v3 프론트엔드 E2E (jsdom, 브라우저 미리보기=더미 모드) */
const { JSDOM } = require("jsdom");
const fs = require("fs");
const html = fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html", "utf-8");

const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/" });
const { window } = dom;
const { document } = window;
window.matchMedia = window.matchMedia || (() => ({ matches: true, addEventListener(){}, }));
// clipboard stub
Object.defineProperty(window.navigator, "clipboard", { value: { writeText: async () => {} } });

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const $ = (sel) => document.querySelector(sel);
const click = (el) => el.dispatchEvent(new window.Event("click", { bubbles: true, cancelable: true }));
const fail = (m) => { console.error("[FAIL]", m); process.exit(1); };
const ok = (m) => console.log("[OK]", m);

(async () => {
  // 1) 부팅: 500ms 브라우저 폴백 → 더미 렌더 + 게이트
  await sleep(900);
  if (!$("#gate-root .gate")) fail("게이트가 표시되지 않음");
  if (!$('[data-gate="begin"]')) fail("로그인 시작 버튼 없음");
  if (!$('[data-gate="begincode"]')) fail("인증 코드 로그인 버튼 없음");
  if ($("#acct-holder").innerHTML.trim() !== "") fail("미로그인인데 계정 뱃지가 보임");
  ok("부팅 → 로그인 게이트(상태 A) 표시, 계정 뱃지 숨김");

  // 2) 로그인 시작 → 브라우저 로그인 대기 화면 (authorization code flow)
  click($('[data-gate="begin"]'));
  await sleep(80);
  const gsub = $("#gate-root").textContent;
  if (!gsub.includes("Microsoft 로그인")) fail("브라우저 로그인 대기 화면 미표시");
  if (!$("#gate-remain")) fail("남은 시간 카운트다운 없음");
  if (!$('[data-gate="reopen"]')) fail("다시 열기 버튼 없음");
  if (!$("#gate-root").textContent.includes("로그인 창")) fail("임베디드 창 안내 문구 없음");
  ok("앱 내부 로그인 창 대기 화면(상태 B)");

  // 3) 더미 폴링(2초 간격, 2번째에 성공) → 로그인 완료
  await sleep(5200);
  if ($("#gate-root .gate")) fail("로그인 후에도 게이트가 남아있음");
  const badge = $(".acct-badge");
  if (!badge || !badge.textContent.includes("Garamisme")) fail("계정 뱃지 미표시");
  ok("로그인 완료 → 게이트 해제 + 타이틀바 뱃지: Garamisme");

  // 4) 플레이 탭: 미설치 카드 + '게임 설치' 버튼 상태
  await sleep(300);
  const body = $("#screen-holder").innerHTML;
  if (!body.includes("게임이 아직 설치되지 않았어요")) fail("미설치 카드 없음");
  if (!$('[data-client="install"]')) fail("게임 설치 버튼 없음");
  if (!body.includes("게임 설치 필요")) fail("히어로 상태 배지가 '게임 설치 필요'가 아님");
  ok("플레이 탭: 미설치 카드 + 설치 버튼 + 상태 배지");

  // 5) 설치 시작 → 진행률 → 완료
  click($('[data-client="install"]'));
  await sleep(400);
  if (!$("#ci-bar")) fail("진행률 바 없음");
  const midPct = $("#ci-pct") && $("#ci-pct").textContent;
  // 진행 중에는 단계 + 파일 수 + 취소 버튼이 보여야 한다 (NN/g)
  const stageEl=$("#ci-msg");
  if (!stageEl || !/단계/.test(stageEl.textContent)) fail("설치 단계 표시 없음");
  if (!$("#ci-sub") || !/파일/.test($("#ci-sub").textContent)) fail("파일 수 표시 없음");
  if (!$('[data-client="cancel"]')) fail("설치 취소 버튼 없음");
  await sleep(6200); // 더미: 4단계 × 12틱 × 110ms ≈ 5.3s
  const after = $("#screen-holder").innerHTML;
  if (after.includes("게임이 아직 설치되지 않았어요")) fail("설치 완료 후에도 미설치 카드");
  if (!$('[data-client="launch"]')) fail("설치 완료 후 실행 버튼이 안 나옴");
  ok("설치 진행(" + midPct + " 경유) → 완료 → 실행 버튼 활성");

  // 6) 드롭다운: 열기 → UUID/메뉴 → 외부 클릭 닫기
  click($('[data-acct="toggle"]'));
  await sleep(50);
  if (!$(".acct-menu")) fail("드롭다운이 안 열림");
  const tbz = window.getComputedStyle(document.querySelector(".titlebar")).zIndex;
  if (tbz !== "40") fail("타이틀바 z-index 미적용: " + tbz);
  const av = $(".acct-badge .acct-ava img");
  if (!av || !av.src.includes("mc-heads")) fail("스킨 헤드 아바타 이미지 없음");
  const menuTxt = $(".acct-menu").textContent;
  ["계정 전환", "로그아웃", "a1b2c3d4"].forEach(t => {
    if (!menuTxt.includes(t)) fail("드롭다운 항목 누락: " + t);
  });
  click(document.body);
  await sleep(50);
  if ($(".acct-menu")) fail("외부 클릭에도 드롭다운이 안 닫힘");
  ok("드롭다운 열림/항목/외부클릭 닫힘");

  // 7) 시스템 탭: 계정 카드 + 인스턴스 카드 + 로그아웃 2단계
  click($('[data-nav="system"]'));
  await sleep(150);
  const sys = $("#screen-holder").innerHTML;
  ["a1b2c3d4-e5f6-0718-293a-4b5c6d7e8f90", "게임 재설치", "인스턴스 초기화", "계정 전환"]
    .forEach(t => { if (!sys.includes(t)) fail("시스템 탭 누락: " + t); });
  ["설치된 클라이언트", "인스턴스 폴더 열기", "전용 인스턴스"].forEach(t => {
    if (sys.includes(t)) fail("삭제됐어야 할 항목 잔존: " + t); });
  const lg = [...document.querySelectorAll('[data-acct="logout"]')].find(b => b.closest("#screen-holder"));
  click(lg); await sleep(50);
  if (lg.getAttribute("data-armed") !== "1") fail("로그아웃 반딧불 무장 미동작");
  if (lg.textContent.includes("정말")) fail("로그아웃 라벨이 변함 (고정이어야 함)");
  ok("시스템 탭: 카드 + 로그아웃 반딧불 무장(라벨 고정)");

  // 8) 실제 로그아웃 → 게이트 복귀
  const lg2 = [...document.querySelectorAll('[data-acct="logout"]')].find(b => b.closest("#screen-holder"));
  click(lg2); await sleep(150);
  if (!$("#gate-root .gate")) fail("로그아웃 후 게이트 미복귀");
  if ($("#acct-holder").innerHTML.trim() !== "") fail("로그아웃 후에도 뱃지 잔존");
  ok("로그아웃 → 게이트 복귀 + 뱃지 제거");

  // 9) 재로그인 → 실행 버튼 → 더미 launch 성공 플로우
  click($('[data-gate="begin"]')); await sleep(5300);
  click($('[data-nav="play"]')); await sleep(150);
  const launch = $('[data-client="launch"]');
  if (!launch) fail("재로그인 후 실행 버튼 없음(설치 상태 유지 실패)");
  click(launch); await sleep(400);
  // 실행 전 파일 검증 단계가 버튼에 표시돼야 한다 (NN/g: 현재 단계 노출)
  let h = $("#screen-holder").innerHTML;
  if (!/검증|확인 중|내려받는|준비 중|실행 중/.test(h)) fail("검증 단계 표시 없음: "+h.slice(0,80));
  ok("실행 전 파일 검증 단계 표시");
  await sleep(1400);
  h = $("#screen-holder").innerHTML;
  if (!h.includes("실행 중…") && !h.includes("게임 실행 중")) fail("실행 중/게임 실행 중 잠금 버튼 미표시");
  ok("검증 완료 → 실행 잠금 버튼");

  // 10) 스킨 탭: 전신 렌더 카드 + 새 스킨 카드 + ⋯ 메뉴
  click($('[data-nav="skin"]')); await sleep(200);
  let sk = $("#screen-holder").innerHTML;
  ["현재 스킨", "라이브러리", "새 스킨", "기본 초록 스킨", "사용 중", "와이드"].forEach(t => {
    if (!sk.includes(t)) fail("스킨 탭 누락: " + t); });
  const resetBtn = $('[data-skin="reset"]');
  if (!resetBtn || resetBtn.previousElementSibling !== $('[data-skin="refresh"]')) fail("초기화 버튼이 새로고침 옆이 아님");
  // 전신 합성: 카드 안에 스킨 레이어 12장(기본6+오버레이6)
  const firstCard = [...document.querySelectorAll(".skin-card")].find(c => c.textContent.includes("기본 초록 스킨"));
  // 카드 렌더: 3D 썸네일 자리표시(로딩 중 2D 폴백) 또는 완성 img
  const ph = firstCard.querySelector('.skin-thumb-ph, .skin-card-body img');
  if (!ph) fail("카드 스킨 렌더(썸네일/폴백) 없음");
  ok("스킨 탭: 라이브러리 카드 3D 썸네일(폴백 포함) + 새 스킨 카드");

  // 10-1) ⋯ 메뉴: 수정/복제/삭제 + 외부 클릭 닫기
  click(firstCard.querySelector('[data-skin="menu"]')); await sleep(60);
  let menu = $(".skin-menu");
  if (!menu) fail("⋯ 메뉴 안 열림");
  ["수정","복제","삭제"].forEach(t => { if (!menu.textContent.includes(t)) fail("메뉴 항목 누락: "+t); });
  click(document.body); await sleep(60);
  if ($(".skin-menu")) fail("메뉴 외부 클릭 닫기 실패");
  ok("⋯ 메뉴: 수정/복제/삭제 + 외부 클릭 닫힘");

  // 10-2) 복제 (리렌더 후 stale 참조 방지 — 재조회)
  const greenCard = () => [...document.querySelectorAll(".skin-card")].find(c => c.textContent.includes("기본 초록 스킨") && !c.textContent.includes("사본"));
  click(greenCard().querySelector('[data-skin="menu"]')); await sleep(60);
  click($('[data-skin="dup"]')); await sleep(200);
  if (!$("#screen-holder").innerHTML.includes("기본 초록 스킨 사본")) fail("복제 실패");
  ok("복제 → '사본' 카드 생성");

  // 10-3) 추가 모달: 오버레이 가드 → 파일 → 슬림 → 망토 그리드 선택 → 저장하고 사용
  click($('[data-skin="add"]')); await sleep(200);
  if (!$("#skin-modal-root .modal")) fail("추가 모달 안 열림");
  let mtxt = $("#skin-modal-root").textContent;
  ["새 스킨 추가","이름","플레이어 모델","와이드","슬림","스킨 파일","찾아보기","망토"].forEach(t => {
    if (!mtxt.includes(t)) fail("모달 항목 누락: " + t); });
  if (!$('.cape-opt[title="망토 없음"]') || !$('.cape-opt[title="이주자 망토"]')) fail("망토 카드(title) 누락");
  if ($("#skin-modal-root .cape-opt").textContent.includes("망토")) fail("망토 카드에 이름 텍스트 잔존");
  if (!$("#skin-modal-root .modal > .closex")) fail("기존 closex(모달 직속) 미사용");
  click(document.getElementById("skinm-name")); await sleep(50);
  if (!$("#skin-modal-root .modal")) fail("모달 내부 클릭에 닫힘");
  if (!$('[data-skinm="saveuse"]').hasAttribute("disabled")) fail("파일 미선택인데 저장 활성");
  click($('[data-skinm="pick"]')); await sleep(120);
  if (!$("#skin-modal-root").textContent.includes("skin.png")) fail("파일명 미표시");
  if (!$("#skin-modal-root #skinm-preview")) fail("모달 미리보기 영역 없음");
  { const pv=$("#skin-modal-root #skinm-preview"); if(!pv.querySelector(".skin-thumb-ph, img, span span")) fail("모달 미리보기 렌더 없음"); }
  document.getElementById("skinm-name").value = "보라 스킨";
  click($('[data-skinm="variant-slim"]')); await sleep(60);
  const capeBtn = $('.cape-opt[title="이주자 망토"]');
  click(capeBtn); await sleep(60);
  if (!capeBtn.classList.contains("cape-opt--sel")) fail("망토 선택 미반영(제자리 갱신)");
  if (document.getElementById("skinm-name").value !== "보라 스킨") fail("망토 선택 시 이름 입력 유실");
  click($('[data-skinm="saveuse"]')); await sleep(1000);
  if ($("#skin-modal-root .modal")) fail("저장 후 모달 안 닫힘");
  sk = $("#screen-holder").innerHTML;
  if (!sk.includes("보라 스킨")) fail("새 스킨 카드 없음");
  if (!sk.includes("슬림 · 이주자 망토")) fail("모델/망토 메타 미표시");
  const purple = [...document.querySelectorAll(".skin-card")].find(c => c.textContent.includes("보라 스킨") && !c.textContent.includes("사본"));
  if (!purple.textContent.includes("사용 중")) fail("사용 중 배지 미이동");
  ok("추가 모달: 파일 → 슬림+망토 그리드 → 저장하고 사용 → 사용 중 이동");

  // 10-4) 수정 프리필 (망토 카드 선택 상태 포함)
  click(purple.querySelector('[data-skin="menu"]')); await sleep(60);
  click($('[data-skin="edit"]')); await sleep(150);
  if (!$("#skin-modal-root").textContent.includes("스킨 수정")) fail("수정 타이틀 아님");
  if (document.getElementById("skinm-name").value !== "보라 스킨") fail("이름 프리필 실패");
  if (!$('[data-skinm="variant-slim"][data-active="true"]')) fail("모델 프리필 실패");
  if (!$('.cape-opt[title="이주자 망토"]').classList.contains("cape-opt--sel")) fail("망토 프리필 실패");
  document.getElementById("skinm-name").value = "보라 스킨 v2";
  click($('[data-skinm="save"]')); await sleep(300);
  if (!$("#screen-holder").innerHTML.includes("보라 스킨 v2")) fail("수정 반영 실패");
  ok("수정 모달: 이름/모델/망토 프리필 + 저장");

  // 10-5) 삭제 (즉시 삭제 — 2단계 확인 제거됨)
  const v2card = [...document.querySelectorAll(".skin-card")].find(c => c.textContent.includes("보라 스킨 v2"));
  const menuBtnEl = v2card.querySelector('[data-skin="menu"]');
  click(menuBtnEl); await sleep(60);
  click($('.skin-menu [data-skin="del"]')); await sleep(250);
  if ($("#screen-holder").innerHTML.includes("보라 스킨 v2")) fail("삭제 후 카드 잔존");
  ok("⋯ 메뉴 내 삭제: 한 번에 즉시 제거");

  // 11) 드롭다운 = 모달 디자인 토큰 확인
  click($('[data-acct="toggle"]')); await sleep(50);
  /* jsdom 은 var() 포함 animation 단축을 computed 로 못 풀므로 소스 규칙으로 검증 */
  const cssSrc = require("fs").readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8");
  const accRule = cssSrc.slice(cssSrc.indexOf(".acct-menu{"), cssSrc.indexOf("}", cssSrc.indexOf(".acct-menu{")));
  ["animation:rise", "var(--glass-fill)", "var(--blur-xl)", "var(--shadow-lg)"].forEach(t => {
    if (!accRule.includes(t)) fail("드롭다운 모달 토큰 누락: " + t); });
  click(document.body); await sleep(50);
  ok("드롭다운: 모달 토큰(rise) 적용");

  // 15b) 다중 계정: 전환 화면 → 추가 → 목록 → 전환 → 제거
  // 두 번째 계정 로그인 (더미는 같은 UUID라, 목록 다중을 위해 더미에 강제 주입)
  window.eval('DummyV3.__accts.push({username:"Friend",uuid:"ffffffffffffffffffffffffffffffff",avatar_url:null,active:false})');
  click($('[data-acct="toggle"]')); await sleep(50);
  const switchBtn = $('[data-acct="switch"]');
  if (!switchBtn) fail("드롭다운에 계정 전환 없음");
  click(switchBtn); await sleep(150);
  if (!$("#gate-root .gate")) fail("계정 선택 화면이 안 열림");
  let gtxt = $("#gate-root").textContent;
  if (!gtxt.includes("계정 선택") || !gtxt.includes("계정 추가")) fail("선택 화면 구성 누락");
  const picks = [...document.querySelectorAll(".acct-pick")];
  if (picks.length !== 2) fail("계정 목록 수 이상: " + picks.length);
  if (!$("#gate-root").innerHTML.includes("사용 중")) fail("활성 계정 표시 없음");
  ok("계정 선택 화면: 목록 2개 + 사용 중 표시 + 계정 추가 버튼");

  // 전환: Friend 로
  const friendPick = picks.find(p => p.textContent.includes("Friend"));
  click(friendPick); await sleep(400);
  if ($("#gate-root .gate")) fail("전환 후 게이트 안 닫힘");
  const badgeAfter = $(".acct-badge");
  if (!badgeAfter || !badgeAfter.textContent.includes("Friend")) fail("전환 후 뱃지 미갱신: " + (badgeAfter?badgeAfter.textContent:"없음"));
  ok("계정 전환: Friend 로 활성 변경 + 뱃지 갱신");

  // 계정 추가: 전환 화면 → 추가 → 브라우저 로그인 대기 → 로그인 (더미는 Garamisme 재로그인)
  click($('[data-acct="toggle"]')); await sleep(50);
  click($('[data-acct="switch"]')); await sleep(120);
  click($('[data-gate="add"]')); await sleep(120);
  if (!$("#gate-root").textContent.includes("Microsoft 로그인")) fail("계정 추가가 브라우저 로그인 화면으로 안 감");
  if (!$("#gate-root").textContent.includes("다른 계정 사용")) fail("계정 추가 시 '다른 계정 사용' 안내 없음");
  await sleep(5200);
  if ($("#gate-root .gate")) fail("추가 로그인 후 게이트 잔존");
  if (!$(".acct-badge").textContent.includes("Garamisme")) fail("추가된 계정으로 활성화 안 됨");
  ok("계정 추가: 브라우저 로그인 → 새 계정 활성");

  // 제거: 전환 화면에서 비활성 계정 제거
  click($('[data-acct="toggle"]')); await sleep(50);
  click($('[data-acct="switch"]')); await sleep(120);
  const beforeN = document.querySelectorAll(".acct-pick").length;
  const inactive = [...document.querySelectorAll(".acct-pick")].find(p => !p.classList.contains("acct-pick--active"));
  click(inactive.querySelector('[data-gate="remove"]')); await sleep(200);
  const afterN = document.querySelectorAll(".acct-pick").length;
  if (afterN !== beforeN - 1) fail("계정 제거 미반영: " + beforeN + "→" + afterN);
  ok("계정 제거: 비활성 계정 목록에서 제거");
  // 정리: 선택 화면 닫기
  click($('[data-gate="cancel-select"]')); await sleep(80);

  // 16) 디자인 통합 검증 (소스 규칙)
  const src = require("fs").readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8");
  if (src.includes("alertglow") || src.includes("armedpulse")) fail("임의 글로우 잔존");
  if (!src.includes('.install[data-state="update"],.btn--update{background:var(--tint-lava);border:1px solid var(--tint-lava-edge);color:var(--tint-lava-text);animation:attention 2.6s')) fail("업데이트 룩 공유 규칙(attention) 없음");
  if (!src.includes('[data-armed="1"]{animation:attention')) fail("무장 버튼이 attention 패턴 재사용 안 함");
  if ((src.match(/@keyframes attention/g)||[]).length !== 1) fail("attention 키프레임 수 이상");
  const cardRule = src.slice(src.indexOf(".skin-card{"), src.indexOf("}", src.indexOf(".skin-card{")));
  if (!cardRule.includes("border:1px solid transparent")) fail("스킨 카드 투명 테두리 기준선 없음");
  const addRule = src.slice(src.indexOf(".skin-card--add{"), src.indexOf("}", src.indexOf(".skin-card--add{")));
  if (!addRule.includes("appearance:none") || !addRule.includes("border:1px solid transparent")) fail("새 스킨 버튼 리셋 누락");
  if (src.indexOf(".acct-badge:hover,.acct-item:hover,.skin-menu-item:hover,.cape-opt:hover") < 0) fail("상호작용 통합 레이어 누락");
  // 업데이트 버튼 통합: ↻ 제거 + 라이브러리/설정 공유 룩 + 아이콘 통일
  if (src.includes("↻")) fail("↻ 특수문자 잔존");
  if (!src.includes('.install[data-state="update"],.btn--update{background:var(--tint-lava)')) fail("업데이트 룩 공유 규칙 없음");
  if (src.includes('btn btn--primary btn--sm" data-update=')) fail("설정탭 업데이트 버튼이 아직 primary");
  if ((src.match(/btn--update/g)||[]).length < 2) fail("btn--update 적용 부족");
  ok("업데이트 버튼 통합: ↻ 제거 + 라이브러리 색 + 설정탭 아이콘/글자 공유");

  // 설정탭: 버전행 텍스트("0.19.3 → 설치 필요")와 뱃지("최신")가 어긋나면 안 됨
  click($('[data-nav="system"]')); await sleep(300);
  if (!$('[data-vertext]')) fail("버전행 텍스트 식별자 없음");
  for (const t of document.querySelectorAll("[data-vertext]")) {
    const id=t.getAttribute("data-vertext");
    const st=document.querySelector('.ver-status[data-verid="'+id+'"]');
    if(!st) continue;
    if (t.textContent.includes("→") && st.textContent.includes("최신"))
      fail("버전행 모순("+id+"): 화살표 있는데 '최신' 뱃지");
  }
  ok("버전행 텍스트/뱃지 일치 (모순 없음)");

  console.log("\n=== 프론트엔드 E2E 전체 통과 (20단계) ===");
  process.exit(0);
})().catch(e => { console.error("[ERROR]", e); process.exit(1); });
