// 설정 화면 Fabric 업데이트 · Java 설치: 진행바·단계·취소.
// 예전엔 Fabric 은 행 뱃지 글자만, Java 는 토스트 % 만 있었고 둘 다 취소가 없었다.
const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync(__dirname+"/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const $=s=>d.querySelector(s);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const ok=(name,c,extra)=>console.log(name+":", c?"✅":"❌ "+(extra||""));
setTimeout(async()=>{
  $('[data-gate="begin"]').click(); await sleep(5300);
  const api=w.eval('V3')(), state=w.eval('state');
  let cancelCalls=0;
  api.update_fabric_async=async()=>({started:true});          // 자동 완료하지 않는 가짜
  api.cancel_install=async()=>{ cancelCalls++; setTimeout(()=>w.onFabricUpdate(-2,"Fabric 업데이트를 취소했습니다"),30); return {ok:true}; };
  state.client={installed:true}; state.gameRunning=false;
  w.eval('setNav')("system"); await sleep(500);

  // 1) 시작 → Fabric 행 아래 진행 패널
  await w.eval('doFabricUpdate')(); await sleep(50);
  ok("Fabric 시작: 진행바 표시", !!$("#tk-bar"));
  ok("Fabric 시작: 취소 버튼", !!$('[data-task="cancel"]'));

  // 2) 진행 이벤트는 화면을 다시 그리지 않고 값만 바꾼다
  const scr=$(".screen");
  await w.onFabricUpdate(42,"x",{stage:"라이브러리",stage_no:1,stage_total:4,cur:5,max:10,raw:"Download Libraries"});
  ok("진행: 화면 노드 유지(제자리 갱신)", $(".screen")===scr);
  ok("진행: 퍼센트", $("#tk-pct").textContent==="42%", $("#tk-pct").textContent);
  ok("진행: 단계", $("#tk-msg").textContent.includes("라이브러리 (1/4 단계)"), $("#tk-msg").textContent);
  ok("진행: 파일 수", $("#tk-sub").textContent==="5 / 10 파일", $("#tk-sub").textContent);

  // 3) 취소
  $('[data-task="cancel"]').dispatchEvent(new w.MouseEvent("click",{bubbles:true})); await sleep(10);
  ok("취소 클릭: 버튼 잠김", $('[data-task="cancel"]') && $('[data-task="cancel"]').disabled);
  await sleep(100);
  ok("취소 요청 1회", cancelCalls===1, cancelCalls+"회");
  ok("취소 완료: 패널 사라짐", !$("#tk-bar"));
  ok("취소 완료: 업데이트 상태 해제", state.fabricUpdating===false);

  // 4) Java — 진행·취소 이벤트
  w.eval('taskStart')("java"); await sleep(20);
  w.onJavaInstall("progress",{pct:30,detail:{stage:"준비",stage_no:0,cur:3,max:120}});
  ok("Java 진행: 퍼센트", $("#tk-pct") && $("#tk-pct").textContent==="30%");
  ok("Java 진행: 문구", $("#tk-msg") && $("#tk-msg").textContent==="Java 런타임 내려받는 중…", $("#tk-msg")&&$("#tk-msg").textContent);
  w.onJavaInstall("cancelled",{message:"Java 설치를 취소했습니다."}); await sleep(20);
  ok("Java 취소: 패널 사라짐", !$("#tk-bar"));

  // 5) 게임 설치 카드 문구는 그대로
  state.clientDetail=null;
  ok("게임 설치 카드 기본 문구 유지", w.eval('ciStageText')()==="게임 파일 준비 중…");
  process.exit(0);
},600);
