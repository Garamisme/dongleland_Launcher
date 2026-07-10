const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let accepted=false, calls=[];
setTimeout(async()=>{
  w.pywebview={api:{
    get_terms_status:async()=>{calls.push("terms");return {ok:true,accepted,version:"1.0"};},
    accept_terms:async()=>{calls.push("accept");accepted=true;return {ok:true};},
    auth_status:async()=>{calls.push("auth");return {logged_in:false};},
  }};
  await w.eval('bootFromBackend')(); await sleep(300);
  console.log("호출:", calls.join(" → "));
  console.log("게이트:", w.eval('state').gate.mode);

  const cb=d.getElementById("terms-agree");
  cb.checked=true; cb.dispatchEvent(new w.Event("change")); await sleep(30);
  const btn=d.querySelector('[data-gate="accept"]');
  console.log("버튼 disabled:", btn.disabled);
  w.eval('flash = function(m){ console.log("   [flash]", m); }');
  btn.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));
  await sleep(600);
  console.log("클릭 후 호출:", calls.join(" → "));
  const st=w.eval('state');
  console.log("booting:", st.booting, "| gate:", st.gate.mode);
  try{ await w.eval('continueBoot')(); console.log("continueBoot 직접: 성공, booting=", w.eval('state').booting, "gate=", w.eval('state').gate.mode); }
  catch(e){ console.log("continueBoot 예외:", e && e.message); }
  process.exit(0);
},600);
