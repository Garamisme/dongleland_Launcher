const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
setTimeout(async()=>{
  d.querySelector('[data-gate="begin"]').click(); await sleep(5300);
  d.querySelector('[data-nav="system"]').click(); await sleep(400);
  const h=d.getElementById("screen-holder").innerHTML;
  console.log("BETA 칩:", /chan-chip">BETA/.test(h) ? "❌ 남아있음" : "✅ 제거됨");
  console.log("버전 3.0.0:", /3\.0\.0/.test(h) ? "✅ 표시" : "❌ 없음");
  process.exit(0);
},600);
