const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
setTimeout(async()=>{
  const css=[...d.querySelectorAll("style")].map(x=>x.textContent).join("\n");
  const m=css.match(/\.gate-logo\{([^}]*)\}/);
  console.log(".gate-logo:", m?m[1]:"?");
  console.log("  border 제거:", m && !/border:/.test(m[1]) ? "✅" : "❌ 남음");
  console.log("  background 없음:", m && !/background:/.test(m[1]) ? "✅" : "❌");
  console.log(".logo:has(img) 규칙:", /\.logo:has\(img\)/.test(css) ? "✅ (타이틀바·사이드바)" : "❌");
  // 게이트 두 화면 모두 확인
  for(const mode of ["idle","terms"]){
    w.eval('showGate')(mode); await sleep(80);
    const el=d.querySelector(".gate-logo");
    console.log(`  ${mode} 화면 로고:`, el?"있음 ✅":"❌");
  }
  process.exit(0);
},600);
