const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const $=s=>d.querySelector(s);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let fails=0; const ok=m=>console.log("[OK] "+m); const fail=m=>{console.log("[FAIL] "+m);fails++;};
setTimeout(async()=>{
  $('[data-gate="begin"]').click(); await sleep(5300);

  // 버전 표시 (BETA 칩 자체는 beta.js 가 채널별로 검증한다)
  d.querySelector('[data-nav="system"]').click(); await sleep(300);
  const sys=$("#screen-holder").innerHTML;
  if(!/3\.0\.0/.test(sys)) fail("3.0.0 표시 없음");
  else ok("버전 3.0.0");

  // 긴 버전 문자열이 줄바꿈 되는지 (CSS 확인)
  const css=[...d.querySelectorAll("style")].map(s=>s.textContent).join("\n");
  if(/\.ver-num\{[^}]*overflow-wrap:anywhere/.test(css)) ok("긴 버전: 줄바꿈 허용(overflow-wrap)");
  else fail("ver-num 이 여전히 ellipsis/nowrap");
  if(/\.ver-num\{[^}]*white-space:nowrap/.test(css)) fail("ver-num 에 nowrap 남음");
  const wm=css.match(/\.ver-menu\{[^}]*width:(\d+)px/);
  console.log("  드롭다운 폭:", wm?wm[1]+"px":"?");
  if(wm && +wm[1]>=300 && +wm[1]<=340) ok("폭 적정 (300~340px)");
  else fail("폭 부적정");
  if(/\.ver-menu-item\{[^}]*flex-direction:column/.test(css)) ok("항목 2줄 구조 (버전 / 날짜)");
  else fail("항목이 아직 한 줄");

  console.log(fails? "\n=== 실패 "+fails+"건 ===":"\n=== 통과 ===");
  process.exit(0);
},600);
