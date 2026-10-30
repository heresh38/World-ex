
/* ===== v96e: stability — no stalls on start, on entering/leaving vehicles, or from background bookkeeping ===== */
var PF96={warm:0,bq:[],bi:0,seen:new WeakSet(),budget:4,scanAt:0,seatQ:[]};
/* 1. the vehicle headlight never leaves the scene: the light count stays constant, so no material has to switch programs on enter/exit */
try{if(spot.parent!==scene){scene.add(spot);scene.add(spot.target)}}catch(e){}
function spotHome96(){try{if(!cur&&spot.parent!==scene){scene.add(spot);scene.add(spot.target);spot.position.set(0,-500,0);spot.target.position.set(0,-501,0)}}catch(e){}}
{const oT=toggleCar;toggleCar=function(){const r=oT.apply(this,arguments);spotHome96();return r}}
if(typeof genForceExit==='function'){const oG=genForceExit;genForceExit=function(){const r=oG.apply(this,arguments);spotHome96();return r}}
/* 2. shaders compile in the background while the title screen is up (parallel compile), never as one blocking pass on the first gameplay frame */
{const oM=menuFrame;menuFrame=function(){const r=oM.apply(this,arguments);try{if(!PF96.warm&&R.compileAsync&&scene.children.length>40){PF96.warm=1;_cmp=1;const t=performance.now();R.compileAsync(scene,cam).then(()=>{PF96.warmMs=performance.now()-t}).catch(()=>{})}}catch(e){}return r}}
{const oR=rnd;rnd=function(){if(started&&!_cmp&&R.compileAsync){_cmp=1;try{buildMini()}catch(e){}R.compileAsync(scene,cam).catch(()=>{})}return oR.apply(this,arguments)}}
/* 3. exact-raycast acceleration structures are built a few milliseconds per frame instead of all at once */
function bvhCand96(){const skip=bvhSkip(),out=[];scene.traverse(o=>{if(!o.isMesh||o.isInstancedMesh||o.isSkinnedMesh||skip.has(o)||BVH.dyn.has(o)||o.userData.isWater||!o.geometry||!o.geometry.attributes.position)return;const m=Array.isArray(o.material)?o.material[0]:o.material;if(m&&m.transparent&&m.opacity<.5)return;if(o.geometry.attributes.position.count<24)return;out.push(o)});return out}
bvhSetup=function(){if(BVH.ready||!window.MESHBVH)return;const L=window.MESHBVH;try{T.BufferGeometry.prototype.computeBoundsTree=L.computeBoundsTree;T.BufferGeometry.prototype.disposeBoundsTree=L.disposeBoundsTree;T.Mesh.prototype.raycast=L.acceleratedRaycast;BVH.rc=new T.Raycaster();BVH.rc.firstHitOnly=true;BVH.list=BVH.list||[];BVH.ready=true;PF96.bq=bvhCand96();PF96.bi=0;PF96.init=true}catch(e){console.warn('bvh',e)}};
bvhScan=function(){if(PF96.bi<PF96.bq.length)return 0;const n=performance.now();if(n<PF96.scanAt)return 0;PF96.scanAt=n+12000;PF96.bq=bvhCand96();PF96.bi=0;PF96.next=[];return 0};
function bvhStep96(){if(!BVH.ready||PF96.bi>=PF96.bq.length)return;const t0=performance.now(),nl=PF96.next||(PF96.next=[]);while(PF96.bi<PF96.bq.length&&performance.now()-t0<PF96.budget){const o=PF96.bq[PF96.bi++];const e=o.matrixWorld.elements,sn=BVH.snap.get(o);if(sn){let mv=false;for(let i=12;i<15;i++)if(Math.abs(sn[i]-e[i])>.01){mv=true;break}if(mv){BVH.dyn.add(o);continue}}else BVH.snap.set(o,e.slice());if(!o.geometry.boundsTree){try{o.geometry.computeBoundsTree({targetLeafSize:12})}catch(err){continue}}if(PF96.init)BVH.list.push(o);else nl.push(o)}
 if(PF96.bi>=PF96.bq.length){if(!PF96.init&&!(typeof GEN!=='undefined'&&GEN.on&&COL96&&COL96.saved))BVH.list=nl;PF96.init=false;PF96.next=null}}
/* 4. car seat geometry is analysed ahead of time (one car per idle slot, while you walk up to it) */
function seatPre96(){if(cur||!started||paused)return;const now=performance.now();if(now<(PF96.seatT||0))return;PF96.seatT=now+700;try{let best=null,bd=40*40;for(const c of cars){if(c._seat||c.air||c.kart||!c.m)continue;const d=(c.x-pl.x)**2+(c.z-pl.z)**2;if(d<bd){bd=d;best=c}}if(best){const go=()=>{try{if(!best._seat)best._seat=seatCompute(best)}catch(e){}};(window.requestIdleCallback||setTimeout)(go,{timeout:400})}}catch(e){}}
/* 5. everything above runs from the one frame hook */
{const oP=preRender;preRender=function(){oP.apply(this,arguments);try{bvhStep96();seatPre96()}catch(e){}}}
