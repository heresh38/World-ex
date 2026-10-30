
/* ---------- v90 wiring: the new human replaces the MakeHuman/classic models for the player, NPCs and the editor ---------- */
function h90Pack(){if(!CHARPK.mh||!CHARPK.mh.h90)CHARPK.mh={h90:1,meta:{skel:{male:H90.K.male.S,female:H90.K.female.S},items:[],mats:[],tex:[]},buf:null,base:0};return CHARPK.mh}
mhPack=function(){return h90Pack()};
{const oR=rest89;rest89=function(C){if(C&&C.h90){if(C._r89)return C._r89;const P={};for(const k in C.K.W)P[k]=C.K.W[k].clone();return C._r89=P}return oR.apply(this,arguments)}}
function h90App(){const sex=(OUT.model==='mh_female'||OUT.model==='female')?'female':'male';if(!OUT.h90||typeof OUT.h90!=='object'){OUT.h90=h90Def(sex);if(OUT.skin)OUT.h90.skin=OUT.skin;if(OUT.hair)OUT.h90.hairC=OUT.hair}OUT.h90=Object.assign(h90Def(sex),OUT.h90,{sex});return OUT.h90}
buildCharMH=function(sex){h90Pack();return buildHuman90(sex,h90App())};
/* player */
applyCharModel=function(){h90Pack();const app=h90App(),want='mh_'+app.sex;OUT.model=want;
 if(CHAR&&(CHAR.name!==want||!CHAR.h90)){if(CHAR.grp.parent)CHAR.grp.parent.remove(CHAR.grp);CHAR=null;ANM=null}
 if(!CHAR){CHAR=buildHuman90(app.sex,app);CHAR.name=want;CHAR.app=OUT.h90}
 if(CHAR.grp.parent!==pl.m)pl.m.add(CHAR.grp);mhApplyOutfit(CHAR);for(const c of pl.m.children){if(c===CHAR.grp)continue;c.traverse(o=>{if(o.isMesh&&!isGear(o))o.visible=false})}};
mhApplyOutfit=function(C){if(!C||!C.h90)return;if(C===CHAR)C.app=h90App();const sh=C===CHAR?shader89():(C.sh90||shader89());apply90(C,sh);try{buildArmor89(C)}catch(e){console.warn('arm90',e)}vis90(C)};
/* female locomotion style for the new body */
{const oS=anmSetup;anmSetup=function(C){const A=oS.apply(this,arguments);if(A&&C&&C.h90&&C.sex==='female'){A.fem=true;A.sty={w:.08,cross:.015,sway:.032,pYaw:.11,pRoll:.06,abd:.07,swW:.24,swR:.62,elR:1.32,elW:.32,cad:1.08,lean:.06,shY:.9,inw:.32,bob:.8}}return A}}
/* armor is baked into one skinned mesh per material (helmet kept separate so the creator can lift it) */
function unbake90(C){for(const m of C._bake90||[]){if(m.parent)m.parent.remove(m);m.geometry.dispose()}C._bake90=[];C._bakeH=[]}
function bake90(C){unbake90(C);const P=rest89(C),skip=new Set();for(const c of C._cloth89||[])c.m.traverse(o=>skip.add(o));C.grp.updateMatrixWorld(true);const by=new Map();
 for(const [bn,g] of Object.entries(C._m89||{})){const bi=C.bones.indexOf(C.B[bn]);if(bi<0)continue;const gi=new T.Matrix4().copy(g.matrixWorld).invert(),TP=new T.Matrix4().makeTranslation(P[bn].x,P[bn].y,P[bn].z),dead=[];
  g.traverse(o=>{if(!o.isMesh||skip.has(o)||Array.isArray(o.material))return;const M4=TP.clone().multiply(new T.Matrix4().multiplyMatrices(gi,o.matrixWorld));const geo=o.geometry.index?o.geometry.toNonIndexed():o.geometry.clone();geo.applyMatrix4(M4);const key=o.material.uuid+(bn==='Head'?'|H':'');if(!by.has(key))by.set(key,{m:o.material,h:bn==='Head',L:[]});by.get(key).L.push([geo,bi]);dead.push(o)});
  for(const o of dead){o.parent.remove(o);o.geometry.dispose()}}
 for(const {m,h,L} of by.values()){let n=0;for(const [g] of L)n+=g.attributes.position.count;const Pa=new Float32Array(n*3),Na=new Float32Array(n*3),Ua=new Float32Array(n*2),SI=new Uint16Array(n*4),SW=new Float32Array(n*4);let k=0;
  for(const [g,bi] of L){const c=g.attributes.position.count;Pa.set(g.attributes.position.array.subarray(0,c*3),k*3);if(g.attributes.normal)Na.set(g.attributes.normal.array.subarray(0,c*3),k*3);if(g.attributes.uv)Ua.set(g.attributes.uv.array.subarray(0,c*2),k*2);for(let i=0;i<c;i++){SI[(k+i)*4]=bi;SW[(k+i)*4]=1}k+=c;g.dispose()}
  const G=new T.BufferGeometry();G.setAttribute('position',new T.BufferAttribute(Pa,3));G.setAttribute('normal',new T.BufferAttribute(Na,3));G.setAttribute('uv',new T.BufferAttribute(Ua,2));G.setAttribute('skinIndex',new T.BufferAttribute(SI,4));G.setAttribute('skinWeight',new T.BufferAttribute(SW,4));G.computeBoundingSphere();
  const me=new T.SkinnedMesh(G,m);me.bind(C.skel,new T.Matrix4());me.frustumCulled=false;me.castShadow=!C.npc&&!m.transparent;me.receiveShadow=true;me.userData.bake90=1;C.grp.add(me);C._bake90.push(me);if(h)C._bakeH.push(me)}}
{const oC=clearArmor89;clearArmor89=function(C){if(C&&C.h90)unbake90(C);return oC.apply(this,arguments)}}
{const oB=buildArmor89;buildArmor89=function(C){if(!C||!C.h90)return oB.apply(this,arguments);const s0=C._sig89;const r=oB.apply(this,arguments);if(C._sig89!==s0||!C._bake90||!C._bake90.length){try{bake90(C)}catch(e){console.warn('bake90',e)}}vis90(C);return r}}
/* NPCs: unique humans in random armor; every pedestrian's old model is hidden */
NPCMH.max=16;NPCMH.armA=-.62;
function npcArmor90(){const r=a=>a[Math.floor(Math.random()*a.length)],pick=(s,none)=>Math.random()<none?'none':r(ARM89[s].filter(d=>d[0]!=='none'))[0];return{ahelmet:Math.random()<.45?'none':pick('helmet',0),aarms:pick('arms',.15),achest:pick('chest',.1),alegs:pick('legs',.15),acls:pick('cls',.6),ashader:r(SHD89)[0],apri:null,asec:null,aglow:null}}
function npcDress90(C,cfg){const keys=['ahelmet','aarms','achest','alegs','acls','ashader','apri','asec','aglow'],save={};for(const k of keys){save[k]=OUT[k];OUT[k]=cfg[k]===undefined?null:cfg[k]}
 try{C.cfg90=cfg;C.sh90=shader89();apply90(C,C.sh90);C._sig89=null;buildArmor89(C)}catch(e){console.warn('npc90',e)}finally{Object.assign(OUT,save)}vis90(C)}
npcBuild=function(sex){h90Pack();sex=sex==='female'||sex==='male'?sex:undefined;const r=h90Recipe('civilian',sex);const C=buildHuman90(r.sex,r.app,{npc:true,outfit:r.outfit,hat:r.hat,hatC:r.hatC});C.recipe=r;
 for(const m of C.grp.children)if(m.isMesh)m.castShadow=false;const rest={};for(const b of C.bones)rest[b.name]=b.quaternion.clone();C.rest=rest;C.prel={};for(const b of C.bones){if(b.parent&&b.parent.isBone)C.prel[b.name]=new T.Quaternion()}return C};
npcStep=function(dt){if(!started)return;NPCMH.t+=dt;const peds=allPeds(),cx=cam.position.x,cz=cam.position.z;
 for(const p of peds){if(p.g&&!p._h90h){p._h90h=1;p.g.traverse(o=>{if(o.isMesh&&!(p._mh&&p._mh.grp.getObjectById(o.id)))o.visible=false})}}
 if((NPCMH.sel=(NPCMH.sel||0)-dt)<=0){NPCMH.sel=.5;const near=peds.filter(p=>p.g&&p.g.parent).map(p=>[p,(p.g.position.x-cx)**2+(p.g.position.z-cz)**2]).filter(q=>q[1]<(q[0].dead?45*45:120*120)).sort((a,b)=>a[1]-b[1]).slice(0,NPCMH.max).map(q=>q[0]);const want=new Set(near);
  for(const C of NPCMH.pool){if(C.ped&&!want.has(C.ped))npcDetach(C)}let built=0;for(const p of near){if(p._mh)continue;let C=NPCMH.pool.find(c=>!c.ped);if(!C&&NPCMH.pool.length<NPCMH.max&&built<1){C=npcBuild();built++;if(C)NPCMH.pool.push(C)}if(!C)break;npcAttach(C,p)}}
 for(const C of NPCMH.pool)if(C.ped)npcAnim(C,C.ped,NPCMH.t)};
