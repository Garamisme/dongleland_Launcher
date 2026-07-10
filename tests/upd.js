const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const H=()=>d.getElementById("screen-holder").innerHTML;
setTimeout(async()=>{
  d.querySelector('[data-gate="begin"]').click(); await sleep(5300);
  d.querySelector('[data-nav="system"]').click(); await sleep(300);
  const ap=w.eval('applyUpdateResult'), rs=w.eval('renderScreen');

  ap({app:{status:"rate_limited",current:"3.0.0",message:"GitHub 요청 한도를 초과했습니다."}});
  rs(false); await sleep(100);
  console.log("rate_limited →", /확인 불가/.test(H())?"✅ '확인 불가' 표시":"❌ 최신으로 표시됨");

  ap({app:{status:"update_available",current:"3.0.0",latest:"3.1.0"}});
  rs(false); await sleep(100);
  console.log("update_available →", /3\.1\.0/.test(H())?"✅ 업데이트 안내":"❌");
  console.log("  note 잔재:", /확인 불가/.test(H())?"❌ 남음":"✅ 해제됨");

  ap({app:{status:"up_to_date",current:"3.0.0"}});
  rs(false); await sleep(100);
  console.log("up_to_date →", /최신/.test(H())&&!/확인 불가/.test(H())?"✅ 최신":"❌");
  process.exit(0);
},600);
