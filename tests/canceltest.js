const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const $=s=>d.querySelector(s);
const click=el=>el.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let fails=0;
const ok=m=>console.log("[OK] "+m);
const fail=m=>{console.log("[FAIL] "+m);fails++;};
w.onerror=e=>console.log("[JS ERROR]",e);

setTimeout(async()=>{
  $('[data-gate="begin"]').click(); await sleep(5300);
  // 게임 미설치 → 설치 버튼
  const inst=$('[data-client="install"]');
  if(!inst){ fail("설치 버튼 없음"); process.exit(0); }
  click(inst); await sleep(400);

  const msg=$("#ci-msg"), sub=$("#ci-sub"), cancel=$('[data-client="cancel"]');
  console.log("  단계:", msg?msg.textContent:"(없음)");
  console.log("  파일수:", sub?sub.textContent:"(없음)");

  if(!msg || !/단계/.test(msg.textContent)) fail("단계 표시 없음");
  else ok("단계 표시: "+msg.textContent);
  if(!sub || !/파일/.test(sub.textContent)) fail("파일 수 표시 없음");
  else ok("파일 수 표시: "+sub.textContent);
  if(!cancel) fail("취소 버튼 없음");
  else ok("취소 버튼 존재");

  // 진행률이 끝에서 멈추지 않는지: 몇 번 샘플링
  const pcts=[];
  for(let i=0;i<5;i++){ await sleep(200); const p=$("#ci-pct"); if(p) pcts.push(p.textContent); }
  console.log("  퍼센트 추이:", pcts.join(" → "));

  // 취소 (진행 중 재렌더로 노드가 바뀌므로 다시 찾는다)
  const cb=$('[data-client="cancel"]');
  if(!cb){ fail("취소 버튼 사라짐"); process.exit(1); }
  click(cb); await sleep(600);
  const stillInstalling = !!$("#ci-bar");
  if(stillInstalling) fail("취소 후에도 설치 카드 표시");
  else ok("취소 후 설치 카드 사라짐");

  const again=$('[data-client="install"]');
  if(!again) fail("취소 후 설치 버튼 복귀 안 됨");
  else ok("취소 후 설치 버튼 복귀");

  console.log(fails? "\n=== 실패 "+fails+"건 ===" : "\n=== 설치 UX 전체 통과 ===");
  process.exit(0);
},600);
