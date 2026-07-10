const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const $=s=>d.querySelector(s), $$=s=>[...d.querySelectorAll(s)];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
setTimeout(async()=>{
  $('[data-gate="begin"]').click(); await sleep(5300);
  const mods=w.eval('DATA').mods, m=mods[0];
  // update 상태로 만들고 라이브러리 진입
  w.eval('applyStatuses')({[m.id]:"update"},{[m.id]:{installed:"0.8.9",latest:"0.9.1"}});
  d.querySelector('[data-nav="library"]').click(); await sleep(500);
  const rm=$$('[data-modrm]')[0];
  console.log("라이브러리 제거 버튼:", rm? "✅ data-modrm 사용" : "❌ 없음");
  const legacy=$$('.btn--danger[data-install]');
  console.log("data-install 쓰는 제거 버튼:", legacy.length, legacy.length? "❌":"✅");
  if(rm){
    rm.dispatchEvent(new w.MouseEvent("click",{bubbles:true})); await sleep(400);
    console.log("클릭 후 상태:", m.state, m.state==="install"? "✅ 제거됨":"❌ 업데이트됨");
  }
  process.exit(0);
},600);
