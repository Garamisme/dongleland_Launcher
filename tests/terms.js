const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
setTimeout(async()=>{
  // 약관 게이트 강제 표시
  w.eval('showGate')("terms"); await sleep(150);
  const cb=d.getElementById("terms-agree");
  const btn=d.querySelector('[data-gate="accept"]');
  console.log("체크박스:", cb?"✅":"❌", "| 동의 버튼:", btn?"✅":"❌");
  console.log("초기 버튼 비활성:", btn && btn.disabled ? "✅":"❌ 바로 눌림");
  cb.checked=true; cb.dispatchEvent(new w.Event("change")); await sleep(50);
  console.log("체크 후 활성화:", !btn.disabled ? "✅":"❌");
  const txt=d.querySelector(".gate-card").textContent;
  for(const k of ["공식 제품이 아닙니다","있는 그대로","백업","암호화"]){
    console.log(`문구 "${k}":`, txt.includes(k)?"✅":"❌");
  }
  console.log("라이선스 버튼:", d.querySelector('[data-gate="licenses"]')?"✅":"❌");
  process.exit(0);
},600);
