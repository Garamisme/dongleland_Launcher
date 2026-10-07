// 새 스킨 창이 열릴 때 '한 번 껌벅' 하던 문제.
// 원인: 망토 목록이 오면 모달 전체를 innerHTML 로 다시 그려 등장 애니메이션이 재생됐고,
// 초기값 [] 때문에 미리 불러오기가 한 번도 안 돌아 매번 그 경로를 탔다.
const {JSDOM}=require("jsdom"),fs=require("fs");
const dom=new JSDOM(fs.readFileSync(__dirname+"/../frontend/nether-glass-launcher-standalone.html","utf-8"),{runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"});
const w=dom.window,d=w.document;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
setTimeout(async()=>{
  d.querySelector('[data-gate="begin"]').click(); await sleep(5300);
  const api=w.eval('V3')(), state=w.eval('state');
  let calls=0, capes=[];
  api.skin_capes=async()=>{ calls++; await sleep(80); return {ok:true,capes}; };

  // 1) 망토가 늦게 도착해도 모달 노드는 그대로, 망토 칸만 바뀐다
  state.skinCapes=null; capes=[{id:"c1",name:"테스트 망토",url:null,active:false}];
  const p=w.eval('skinModalOpen')("add");
  const before=d.querySelector("#skin-modal-root .modal");
  await p; await sleep(20);
  const after=d.querySelector("#skin-modal-root .modal");
  console.log("모달 노드 유지:", before && before===after ? "✅" : "❌ 다시 그려짐");
  console.log("망토 칸 갱신:", d.querySelectorAll('#skinm-capes [data-skinm="cape"]').length===2 ? "✅" : "❌");

  // 2) 망토 없는 계정: 빈 배열도 '로드 완료' — 두 번째 열 때 다시 받지 않는다
  state.skinModal=null; w.eval('renderSkinModal')();
  state.skinCapes=null; capes=[]; calls=0;
  await w.eval('skinModalOpen')("add");
  state.skinModal=null; w.eval('renderSkinModal')();
  await w.eval('skinModalOpen')("add");
  console.log("망토 없는 계정 재요청 없음:", calls===1 ? "✅" : "❌ "+calls+"회");

  // 3) 계정 전환 시 이전 계정 망토를 버린다
  state.skinCapes=[{id:"old"}];
  await w.eval('afterLogin')();
  console.log("계정 전환 시 망토 초기화:", state.skinCapes===null || (Array.isArray(state.skinCapes) && !state.skinCapes.some(c=>c.id==="old")) ? "✅" : "❌");
  process.exit(0);
},600);
