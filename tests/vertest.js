const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync("" + __dirname + "/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const $=s=>d.querySelector(s);
const click=el=>el.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
setTimeout(async()=>{
  $('[data-gate="begin"]').click(); await sleep(5300);
  $('[data-nav="mods"]').click(); await sleep(200);
  const cards=[...d.querySelectorAll(".modcard")];
  let opened=false;
  for(const c of cards){
    if(c.textContent.includes("설치됨")||c.textContent.includes("업데이트")){ click(c); opened=true; break; }
  }
  await sleep(300);
  console.log("모달 열림:", !!$("#modal-root .modal"));
  const verBtn=$('[data-ver="menu"]');
  console.log("버전 ⋯ 버튼 존재:", !!verBtn);
  if(!verBtn){ console.log("설치된 모드 카드 못찾음? opened=",opened); process.exit(0); }
  click(verBtn); await sleep(500);
  const menu=$(".ver-menu");
  console.log("드롭다운 열림:", !!menu);
  const items=[...d.querySelectorAll(".ver-menu-item")];
  console.log("버전 항목 수:", items.length);
  console.log("현재 버전 하이라이트:", !!$(".ver-menu-item--cur"));
  const pick=items.find(i=>!i.disabled);
  console.log("선택 가능한 이전 버전:", pick? pick.textContent.trim().slice(0,20) : "없음");
  if(pick){
    click(pick); await sleep(1200);
    console.log("변경 후 액션 영역:", $("#modal-action").textContent.trim().slice(0,24));
    console.log("드롭다운 닫힘:", !$(".ver-menu"));
  }
  process.exit(0);
},600);
