const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const $=s=>d.querySelector(s);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
setTimeout(async()=>{
  $('[data-gate="begin"]').click(); await sleep(5300);
  d.querySelector('[data-nav="mods"]').click(); await sleep(300);
  const holder=$("#screen-holder");
  const before=holder.innerHTML.length;
  const nodeBefore=$(".screen");

  const mods=w.eval('DATA').mods, m=mods[2];
  w.eval('applyStatuses')({[m.id]:"installed"},{[m.id]:{installed:"0.9.1",latest:"0.9.1"}});
  w.eval('renderScreen')(false); await sleep(150);
  const screenNode=$(".screen");

  await w.eval('pickVersion')(m.id, "v2"); await sleep(900);

  const screenAfter=$(".screen");
  console.log("화면 노드 교체됨?", screenNode!==screenAfter ? "❌ 전체 재렌더(스크롤 초기화)" : "✅ 유지(스크롤 보존)");
  console.log("모드 상태:", m.state, "| 설치버전:", m._installedVersion);
  process.exit(0);
},600);
