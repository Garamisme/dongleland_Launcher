const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const $=s=>d.querySelector(s);
const $$=s=>[...d.querySelectorAll(s)];
const click=el=>el.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let fails=0;
const ok=m=>console.log("[OK] "+m);
const fail=m=>{console.log("[FAIL] "+m);fails++;};

setTimeout(async()=>{
  $('[data-gate="begin"]').click(); await sleep(5300);
  $('[data-nav="mods"]').click(); await sleep(200);

  // 백엔드가 준 것처럼 상태+버전 주입
  const mods=w.eval('DATA').mods;
  const a=mods[0], b=mods.find(x=>x.id!==a.id);
  w.eval('applyStatuses')({[a.id]:"installed",[b.id]:"update"},
                  {[a.id]:{installed:"0.9.1",latest:"0.9.1"},
                   [b.id]:{installed:"0.8.9",latest:"0.9.1"}});
  w.eval('renderScreen')(false); await sleep(200);

  // 1) 카드에는 버전을 표시하지 않는다
  const html=$("#screen-holder").innerHTML;
  if(/badge[^>]*>v0\.9\.1/.test(html)) fail("카드에 버전 뱃지가 남아 있음");
  else ok("카드: 버전 미표시");

  // 2) 설치됨 모달: 제거 + ⋯ + 설치됨
  const cards=$$(".modcard");
  const cardA=cards.find(c=>c.textContent.includes(a.title));
  click(cardA); await sleep(300);
  let act=$("#modal-action");
  console.log("  [설치됨] 액션:", act.textContent.replace(/\s+/g," ").trim());
  if(!$('[data-modrm]')) fail("설치됨 모달에 제거 버튼 없음");
  else ok("설치됨: 제거 버튼");
  if(!$('[data-ver="menu"]')) fail("설치됨 모달에 ⋯ 없음");
  else ok("설치됨: ⋯ 존재");
  const body=$(".mbody").textContent;
  if(d.querySelector('[data-meta="author"]')) ok("모달: 제작자가 다운로드 행에 표시");
  else fail("제작자가 다운로드 행에 없음");
  if(/제작자/.test($(".metagrid").textContent)) fail("metagrid 에 제작자 칸이 남음");
  else ok("metagrid: 제작자 칸 삭제");
  const vb=$('[data-ver="menu"]');
  if(vb && /버전 선택/.test(vb.textContent)) ok("버튼 라벨: 버전 선택");
  else fail("버전 선택 라벨 아님: "+(vb?vb.textContent:"없음"));
  if(!body.includes("설치된 버전")) fail("모달에 '설치된 버전' 셀 없음");
  else ok("모달: 설치된 버전 표시");
  if(!body.includes("0.9.1")) fail("모달에 실제 버전 숫자 없음");
  else ok("모달: 버전 숫자 0.9.1");
  click($("[data-close-modal]")); await sleep(200);

  // 3) 업데이트 모달: 제거 버튼이 있어야 한다 (기존 버그)
  const cardB=cards.find(c=>c.textContent.includes(b.title)) || $$(".modcard").find(c=>c.textContent.includes(b.title));
  click(cardB); await sleep(300);
  act=$("#modal-action");
  console.log("  [업데이트] 액션:", act.textContent.replace(/\s+/g," ").trim());
  if(!$('[data-modrm]')) fail("업데이트 상태에서 제거 버튼 사라짐 (버그)");
  else ok("업데이트: 제거 버튼 유지");
  if(!act.textContent.includes("업데이트")) fail("업데이트 버튼 라벨 없음");
  else if(act.textContent.includes("지금 업데이트")) fail("라벨이 아직 '지금 업데이트'");
  else ok("업데이트 라벨 통일");
  const mb=$(".mbody").textContent;
  if(!mb.includes("구버전")) fail("업데이트 상태에 '구버전' 표시 없음");
  else ok("모달: 구버전 표시");

  // 4) ⋯ 순서: 제거 다음, 주버튼 앞
  const kids=[...act.children].map(el=>el.className||el.tagName);
  console.log("  액션 순서:", kids.join(" | "));
  const idx=(sel)=>[...act.children].findIndex(el=>el.matches(sel)||el.querySelector(sel));
  const iRm=idx("[data-modrm]"), iVer=idx('[data-ver="menu"]'), iMain=idx(".install");
  if(!(iRm<iVer && iVer<iMain)) fail(`순서 잘못됨 rm=${iRm} ver=${iVer} main=${iMain}`);
  else ok("순서: [제거][⋯][업데이트]");

  // 5) 미설치 모달: ⋯ 이 설치 버튼 옆에 있어야
  click($("[data-close-modal]")); await sleep(200);
  const c=mods.find(x=>stOfSafe(x)==="install");
  function stOfSafe(m){ try{return w.eval("stOf")(m);}catch(_){return "";} }
  if(c){
    const cardC=$$(".modcard").find(x=>x.textContent.includes(c.title));
    if(cardC){
      click(cardC); await sleep(300);
      const a2=$("#modal-action");
      console.log("  [미설치] 액션:", a2.textContent.replace(/\s+/g," ").trim());
      if(!$('[data-ver="menu"]')) fail("미설치 모달에 ⋯ 없음");
      else ok("미설치: ⋯ 존재 (설치 버튼 옆)");
      if($('[data-modrm]')) fail("미설치인데 제거 버튼 있음");
      else ok("미설치: 제거 버튼 없음");
    }
  }

  console.log(fails? "\n=== 실패 "+fails+"건 ===" : "\n=== 모드 UI 전체 통과 ===");
  process.exit(0);
},600);
