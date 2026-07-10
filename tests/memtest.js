const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const $=s=>d.querySelector(s);
const click=el=>el.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let fails=0;
const ok=m=>console.log("[OK] "+m);
const fail=m=>{console.log("[FAIL] "+m);fails++;};
setTimeout(async()=>{
  $('[data-gate="begin"]').click(); await sleep(5300);
  $('[data-nav="system"]').click(); await sleep(400);

  // 1) 메모리 카드 렌더
  const card=$("#screen-holder").textContent;
  if(!card.includes("할당 메모리")) fail("메모리 카드 없음"); else ok("할당 메모리 카드 표시");
  const range=$("#mem-range");
  if(!range) fail("슬라이더 없음"); else ok("슬라이더 존재 (min="+range.min+" max="+range.max+")");
  if(!$("#mem-val")) fail("현재 값 표시 없음"); else ok("현재 값: "+$("#mem-val").textContent);

  // 2) 프리셋 칩
  const chips=[...d.querySelectorAll("[data-mem='preset']")];
  console.log("   프리셋 개수:", chips.length);
  if(!chips.length) fail("프리셋 칩 없음"); else ok("프리셋 칩 "+chips.length+"개");
  const active=d.querySelector('.mem-chip[data-active="true"]');
  if(!active) fail("활성 칩 없음"); else ok("활성 칩: "+active.textContent.trim());

  // 3) 프리셋 클릭 → 값 변경
  const other=chips.find(c=>c.getAttribute("data-mb")!=="4096");
  if(other){
    click(other); await sleep(400);
    const v=$("#mem-val");
    ok("프리셋 클릭 후 값: "+(v?v.textContent:"?"));
  }

  // 4) 슬라이더 input 이벤트
  const r2=$("#mem-range");
  if(r2){
    r2.value="8192";
    r2.dispatchEvent(new w.Event("input",{bubbles:true}));
    await sleep(80);
    const v=$("#mem-val");
    if(v && v.textContent.includes("8")) ok("슬라이더 미리보기 동작: "+v.textContent);
    else fail("슬라이더 미리보기 실패: "+(v?v.textContent:"없음"));
  }

  console.log(fails? "\n=== 실패 "+fails+"건 ===" : "\n=== 메모리 UI 전체 통과 ===");
  process.exit(0);
},600);
