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
  // 카탈로그 밖에서 직접 넣은 jar 도 라이브러리에 보여야 한다
  w.eval('state').extraMods=[{filename:"my-mod.jar",size:2048}];
  w.eval('renderScreen')(false); await sleep(200);
  const ext=$$('[data-extrarm]');
  console.log("직접 추가한 모드 행:", ext.length===1 && ext[0].getAttribute("data-extrarm")==="my-mod.jar" ? "✅" : "❌ "+ext.length);
  console.log("섹션 제목:", d.body.textContent.includes("직접 추가한 모드") ? "✅" : "❌ 없음");
  // 서버가 금지한 모드가 설치돼 있으면 경고 (경고만)
  const bm=mods[1]; bm._banned=true; w.eval('applyStatuses')({[bm.id]:"installed"},{});
  w.eval('warnBannedMods')(); await sleep(50);
  const fx=d.body.textContent;
  console.log("금지 모드 경고:", fx.includes("서버에서 금지한 모드") && fx.includes(bm.title) ? "✅" : "❌");
  process.exit(0);
},600);
