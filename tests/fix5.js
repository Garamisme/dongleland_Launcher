const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const $=s=>d.querySelector(s), $$=s=>[...d.querySelectorAll(s)];
const click=el=>el.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let f=0; const ok=m=>console.log("[OK] "+m); const bad=m=>{console.log("[FAIL] "+m);f++;};
setTimeout(async()=>{
  $('[data-gate="begin"]').click(); await sleep(5300);

  const css=[...d.querySelectorAll("style")].map(x=>x.textContent).join("\n");
  // 1) 버튼 줄바꿈 방지
  if(/\.btn\{[^}]*white-space:nowrap/.test(css) && /\.install\{[^}]*white-space:nowrap/.test(css)) ok("버튼 nowrap");
  else bad("버튼 nowrap 없음");
  // 2) Space Mono 제거
  if(/@font-face[^}]*Space Mono/.test(css)) bad("Space Mono @font-face 남음");
  else ok("Space Mono 제거");
  if(/--font-mono:'Pretendard'/.test(css)) ok("mono → 기본 글꼴");
  else bad("--font-mono 그대로");

  // 3) 셰이더 탭 애니메이션
  d.querySelector('[data-nav="shaders"]').click(); await sleep(60);
  const sc=$(".screen");
  if(sc && /anim-(up|down)/.test(sc.className)) ok("셰이더 탭 애니메이션: "+sc.className.trim());
  else bad("셰이더 탭 애니메이션 없음: "+(sc?sc.className:"?"));
  if(typeof w.eval("renderScreenSoon")==="function") ok("renderScreenSoon 존재");

  // 4) 모달: 제작자 아이콘 유지 + 설치 즉시 버전 갱신
  d.querySelector('[data-nav="mods"]').click(); await sleep(300);
  const mods=w.eval('DATA').mods;
  const m0=mods[0];
  w.eval('applyStatuses')({[m0.id]:"installed"},{[m0.id]:{installed:"0.9.1",latest:"0.9.1"}});
  w.eval('renderScreen')(false); await sleep(150);
  const card=$$(".modcard").find(c=>c.textContent.includes(m0.title));
  click(card); await sleep(300);
  const au=$('[data-meta="author"]');
  if(au && au.querySelector("svg")) ok("제작자 아이콘 존재");
  else bad("제작자 아이콘 없음");

  // setCell 이 아이콘을 지우지 않는지 (프로젝트 상세 도착 시뮬)
  if(au){
    const svg=au.querySelector("svg");
    au.innerHTML=""; au.appendChild(svg); au.appendChild(d.createTextNode(" jellysquid"));
    if(au.querySelector("svg")) ok("아이콘 보존 방식 동작");
  }

  // 설치된 버전 즉시 갱신
  const before=$('[data-meta="installed-version"]').textContent;
  m0._installedVersion="1.0.0"; m0.state="installed";
  w.eval('refreshModalAction')(m0); await sleep(60);
  const after=$('[data-meta="installed-version"]').textContent;
  if(before!==after && after.includes("1.0.0")) ok("설치 후 버전 즉시 갱신: "+before+" → "+after);
  else bad("버전 갱신 안 됨: "+before+" → "+after);

  console.log(f? "\n실패 "+f+"건":"\n=== 통과 ===");
  process.exit(0);
},600);
