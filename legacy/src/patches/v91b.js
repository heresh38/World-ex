
/* ---------- modular clothing: every garment is data (which body regions, how loose, which fabric); colours/patterns per instance ---------- */
const GARM90={
 briefs:{mat:'knit',layer:0,torso:{y0:.8,y1:.95,off:.002,capBot:1},legs:{u0:.08,u1:.22,off:.002}},
 tshirt:{mat:'knit',layer:2,torso:{y0:.86,y1:1.487,off:.006,loose:.6,flare:.008},arms:{u0:0,u1:.34,off:.006,loose:1,flare:.006}},
 longtee:{mat:'knit',layer:2,torso:{y0:.86,y1:1.487,off:.006,loose:.6,flare:.006},arms:{u0:0,u1:.965,off:.005,loose:.6}},
 tank:{mat:'knit',layer:2,torso:{y0:.87,y1:1.445,off:.005,loose:.5}},
 shirt:{mat:'knit',layer:2,torso:{y0:.84,y1:1.49,off:.008,loose:.8,flare:.01},arms:{u0:0,u1:.965,off:.008,loose:1},collar:1,placket:1},
 hoodie:{mat:'knit',layer:3,torso:{y0:.84,y1:1.487,off:.016,loose:1,flare:.004},arms:{u0:0,u1:.965,off:.014,loose:1},hood:1,cuff:1,band:1,pocket:1},
 sweater:{mat:'knit',layer:3,torso:{y0:.86,y1:1.49,off:.012,loose:1},arms:{u0:0,u1:.965,off:.011,loose:1},cuff:1,band:1},
 jacket:{mat:'leather',layer:4,torso:{y0:.86,y1:1.487,off:.021,loose:1,flare:.006},arms:{u0:0,u1:.96,off:.018,loose:1},collar:1,zip:1},
 jeans:{mat:'denim',layer:1,torso:{y0:.8,capBot:1,y1:1.065,off:.006,loose:.3},legs:{u0:.1,u1:.985,off:.006,loose:.4,flare:.004}},
 chinos:{mat:'denim',layer:1,torso:{y0:.8,capBot:1,y1:1.065,off:.007,loose:.5},legs:{u0:.1,u1:.985,off:.008,loose:.7,flare:.002}},
 joggers:{mat:'knit',layer:1,torso:{y0:.8,capBot:1,y1:1.07,off:.009,loose:.6},legs:{u0:.1,u1:.975,off:.011,loose:.9},legCuff:1},
 shorts:{mat:'denim',layer:1,torso:{y0:.8,capBot:1,y1:1.06,off:.008,loose:.4},legs:{u0:.1,u1:.43,off:.013,loose:.6,flare:.01}},
 skirt:{mat:'knit',layer:1,torso:{y0:.96,y1:1.065,off:.006},skirt:{y0:.98,hem:.6,flare:.02}},
 dress:{mat:'knit',layer:2,torso:{y0:.96,y1:1.487,off:.006,loose:.4},arms:{u0:0,u1:.22,off:.006,loose:.8},skirt:{y0:.985,hem:.52,flare:.04}},
 sneakers:{mat:'leather',layer:1,feet:{style:'sneaker',off:.01},sole:0xf2f2f0},
 boots:{mat:'leather',layer:1,feet:{style:'boot',off:.008},legs:{u0:.86,u1:1,off:.013},sole:0x2a1e16},
 dressShoes:{mat:'leather',layer:1,feet:{style:'dress',off:.004},sole:0x1a1410},
 suit:{mat:'suit',layer:1,torso:{y0:.8,y1:1.503,off:.003,capBot:1,capTop:1},arms:{u0:0,u1:1,off:.003},legs:{u0:0,u1:1,off:.003},hands:{off:.0022},feet:{style:'boot',off:.006},collar:1}
};
const H90_PAL={tee:[0xf0f0ec,0x1c1c1e,0x22304f,0x8e9095,0x5a6340,0x6e2630,0xc9a03a,0x2f6f73,0x8fb6d8,0xe07a63,0x2e4a35,0x3a3c42,0xb8b2a4],
 bright:[0xd8483c,0x3e7cc8,0xf0c240,0x48a878,0xe87a9a,0x7a58b8,0xf08a3a,0x40b0c0],shirt:[0xf4f4f0,0xc8d8ea,0xe8d8c8,0x9ab8d8,0x2a3040,0xd8c8e0],
 denim:[0x2a3a5c,0x3b5276,0x6b84a8,0x1e1f24,0x4a4c52,0x31405e],khaki:[0xb8a47a,0x8a7a5a,0x5a5a48,0xc8b898,0x3a3a40],dark:[0x1e1f24,0x2a2c34,0x3a3c44,0x262a3a,0x3a3028],
 jacket:[0x1a1a1c,0x4a3022,0x3e4630,0x1f2a40,0x6a4a30],shoe:[0xf2f2f0,0x1c1c1e,0x8a8e94,0x24304a,0xb03030,0x3a5a3a],leather:[0x3a2416,0x1a1412,0x6a4a2e,0x2a2422]};
/* outfit recipes: add a row here to give the city a new look — no code changes needed */
const H90_OUTFITS=[
 {id:'casual',w:4,items:[{g:'tshirt',c:'tee'},{g:'jeans',c:'denim'},{g:'sneakers',c:'shoe'}]},
 {id:'stripes',w:1.2,items:[{g:'tshirt',c:'tee',c2:'tee',pat:'stripes'},{g:'chinos',c:'khaki'},{g:'sneakers',c:'shoe'}]},
 {id:'hoodie',w:2.5,items:[{g:'hoodie',c:'tee',c2:'tee'},{g:'joggers',c:'dark'},{g:'sneakers',c:'shoe'}]},
 {id:'biker',w:1.4,items:[{g:'longtee',c:'tee'},{g:'jacket',c:'jacket'},{g:'jeans',c:'denim'},{g:'boots',c:'leather'}]},
 {id:'summer',w:2,items:[{g:'tshirt',c:'bright'},{g:'shorts',c:'khaki'},{g:'sneakers',c:'shoe'}]},
 {id:'office',w:1.5,items:[{g:'shirt',c:'shirt'},{g:'chinos',c:'dark'},{g:'dressShoes',c:'leather'}]},
 {id:'knit',w:1.4,items:[{g:'sweater',c:'tee'},{g:'jeans',c:'denim'},{g:'boots',c:'leather'}]},
 {id:'sport',w:1.4,items:[{g:'tshirt',c:'bright',c2:'tee',pat:'raglan'},{g:'joggers',c:'dark',c2:'tee',pat:'side'},{g:'sneakers',c:'shoe'}]},
 {id:'layered',w:1.2,items:[{g:'longtee',c:'tee'},{g:'jeans',c:'denim'},{g:'sneakers',c:'shoe'}]},
 {id:'dress',w:2,sex:'female',items:[{g:'dress',c:'bright'},{g:'dressShoes',c:'leather'}]},
 {id:'skirt',w:2,sex:'female',items:[{g:'tank',c:'tee'},{g:'skirt',c:'dark'},{g:'sneakers',c:'shoe'}]},
 {id:'skirtTee',w:1.4,sex:'female',items:[{g:'tshirt',c:'tee'},{g:'skirt',c:'denim'},{g:'boots',c:'leather'}]}];
/* character archetypes (civilians now; police, workers, enemies can be added the same way) */
const H90_ARCH={civilian:{armor:false,hat:.12,pack:.1},player:{armor:true,outfit:[{g:'suit'}]}};
function h90Outfit(sex,id){const r=a=>a[Math.floor(Math.random()*a.length)],L=H90_OUTFITS.filter(o=>!o.sex||o.sex===sex);let o=id?L.find(q=>q.id===id):null;if(!o){let t=Math.random()*L.reduce((s,q)=>s+q.w,0);for(const q of L){t-=q.w;if(t<=0){o=q;break}}o=o||L[0]}
 return o.items.map(it=>{let c1=r(H90_PAL[it.c]||H90_PAL.tee),c2=it.c2?r(H90_PAL[it.c2]):null;if(c2===c1)c2=null;return{g:it.g,c1,c2:c2==null?(GARM90[it.g].sole||c1):c2,pat:it.pat||'solid'}})}
function h90Recipe(arch,sex){const A=H90_ARCH[arch]||H90_ARCH.civilian;sex=sex||(Math.random()<.5?'male':'female');const app=h90Rand(sex);const hat=Math.random()<(A.hat||0)?(Math.random()<.6?'cap':'beanie'):'none';
 return{arch,sex,app,outfit:A.outfit?A.outfit.map(q=>Object.assign({},q)):h90Outfit(sex),hat,hatC:[0x1c1c1e,0x22304f,0x6e2630,0xb8b2a4,0x2e4a35][Math.floor(Math.random()*5)],armor:!!A.armor}}
const _lin90=h=>{const c=new T.Color(h);return[c.r,c.g,c.b]};
/* build one garment instance into the per-fabric mesh builders */
function garment90(mbs,C,inst){let G=GARM90[inst.g];if(G&&G.torso&&!G.skirt&&C._skirt&&G.layer>=2)G=Object.assign({},G,{torso:Object.assign({},G.torso,{y0:Math.max(G.torso.y0,.975)})});if(!G)return;const mb=mbs[G.mat]||(mbs[G.mat]=new MB90()),lay=(G.layer||0)*.0022,c1=_lin90(inst.c1==null?0x888888:inst.c1),c2=_lin90(inst.c2==null?inst.c1||0x888888:inst.c2),pat=inst.pat||'solid',dk=c1.map(v=>v*.72);
 const col=part=>(p,a,r,ri)=>{if(G.mat==='suit')return null;const ca=Math.cos(a),sa=Math.sin(a);
  if(part==='foot')return p.y<.024?_lin90(G.sole||inst.c2||0xeeeeee):c1;
  if(pat==='stripes'&&(part==='torso'||part==='arm'))return((p.y*15)|0)%2?c2:c1;if(pat==='raglan'&&part==='arm')return c2;if(pat==='side'&&part==='leg'&&Math.abs(sa)>.965)return c2;
  if(G.zip&&part==='torso'&&sa>0&&Math.abs(ca)<.03)return dk;if(G.placket&&part==='torso'&&sa>0&&Math.abs(ca)<.045&&p.y>1.0)return c1.map(v=>v*.9);
  if(G.pocket&&part==='torso'&&sa>.5&&p.y>.9&&p.y<1.02&&Math.abs(p.x)<.1)return c1.map(v=>v*.86);
  if(G.band&&part==='torso'&&p.y<G.torso.y0+.045)return c1.map(v=>v*.88);if(G.cuff&&part==='arm'&&r&&r.v!==undefined&&r._u>G.arms.u1-.05)return c1.map(v=>v*.88);if(G.legCuff&&part==='leg'&&r._u>G.legs.u1-.05)return c1.map(v=>v*.85);return c1};
 const wrapU=(fn,part)=>{const f=col(part);return(p,a,r,ri)=>f(p,a,r,ri)};
 if(G.torso)torso90(mb,C,Object.assign({},G.torso,{off:(G.torso.off||0)+lay,rim:!G.torso.capBot,rimTop:!G.torso.capTop,col:col('torso')}));
 for(const S of['Left','Right']){if(G.arms)limb90(mb,C,'arm',S,Object.assign({},G.arms,{off:(G.arms.off||0)+lay,rim:true,col:col('arm')}));if(G.legs)limb90(mb,C,'leg',S,Object.assign({},G.legs,{off:(G.legs.off||0)+lay*.6,rim:true,col:col('leg')}));
  if(G.hands)hand90(mb,C,S,{off:G.hands.off,col:col('hand')});if(G.feet)foot90(mb,C,S,{style:G.feet.style,off:G.feet.off,col:col('foot')})}
 if(G.skirt)skirt90(mb,C,Object.assign({},G.skirt,{off:.008+lay,col:col('skirt')}));
 if(G.collar&&G.mat==='suit')headLoft90(mb,headP90(C.app),C.K,C.det*.6,{y0:H90_Y0,y1:-.123,off:.0035});
 else if(G.collar)collar90(mb,C,(G.torso.off||0)+lay+.004,c1);
 if(G.hood)hood90(mb,C,(G.torso.off||0)+lay,c1)}
function collar90(mb,C,off,col){const I=n=>C.K.names.indexOf(n),rows=[];for(let i=0;i<=3;i++){const y=1.487+i*.008,[w,df,db,zc]=torsoProf90(C.sex,1.487,C.wt,0),k=1-.12*i/3;rows.push({v:i*.1,sk:[[I('Spine2'),.5],[I('Neck'),.5]],pt:a=>{const ca=Math.cos(a),sa=Math.sin(a);return new T.Vector3((w*.95+off)*k*ca,y,zc+((sa>0?df*.92:db)+off)*k*sa)}})}mb.loft(rows,Math.max(24,Math.round(64*C.det)),0,0,()=>col)}
function hood90(mb,C,off,col){const I=n=>C.K.names.indexOf(n),pts=[],rad=[];for(let i=0;i<=14;i++){const t=i/14,a=Math.PI*(.15+.7*t),r=.1+off;pts.push(new T.Vector3(Math.cos(a)*r*1.15,1.475+.012*Math.sin(Math.PI*t),-.035-Math.sin(a)*r*.95));rad.push(.024*(.6+.4*Math.sin(Math.PI*t)))}
 const rows=pts.map((c,i)=>{const Y=pts[Math.min(i+1,14)].clone().sub(pts[Math.max(i-1,0)]).normalize();const X=new T.Vector3(0,1,0).addScaledVector(Y,-Y.y).normalize();return{c,X,Y,ra:rad[i],rb:rad[i]*1.3,e:2,v:i*.1,sk:[[I('Spine2'),.55],[I('Neck'),.45]]}});mb.loft(rows,Math.max(10,Math.round(18*C.det)),1,1,()=>col)}
/* the bare body (skin): torso, limbs, hands, feet */
function skin90(C){const mb=new MB90();torso90(mb,C,{y0:.8,y1:1.503,capBot:1,capTop:1});for(const S of['Left','Right']){limb90(mb,C,'arm',S,{});limb90(mb,C,'leg',S,{});hand90(mb,C,S,{});foot90(mb,C,S,{style:'skin'})}return mb}

/* ---------- character object (interface the animator, armor and menus use) ---------- */
function buildHuman90(sex,app,opt){opt=opt||{};sex=sex==='female'?'female':'male';const K=H90.K[sex],S=K.S,bones=S.map(b=>{const o=new T.Bone();o.name=b.n;o.position.fromArray(b.t);return o});S.forEach((b,i)=>{if(b.p>=0)bones[b.p].add(bones[i])});
 const grp=new T.Group();grp.add(bones[0]);grp.updateMatrixWorld(true);const skel=new T.Skeleton(bones),B={};for(const b of bones)B[b.name]=b;const restCS={};for(const b of bones)restCS[b.name]=new T.Quaternion();
 const mount=(bn,name)=>{const g2=new T.Group();g2.name=name;B[bn].add(g2);return g2};const npc=!!opt.npc;
 const C={grp,B,bones,restCS,skel,K,meshes:[],byItem:{},mixer:null,act:{},clips:{},ph:0,wA:0,wL:0,wAir:0,v2:1,mh:1,h90:1,sex,npc,det:opt.det||(npc?.5:1),app:Object.assign(h90Def(sex),app||{},{sex}),outfit:opt.outfit||(npc?h90Outfit(sex):[{g:'suit'}]),hat:opt.hat||'none',hatC:opt.hatC||0x1c1c1e,hatMount:mount('Head','hatMount'),packMount:mount('Spine2','packMount'),_bake90:[],_bakeH:[]};
 if(typeof CHARPK!=='undefined')CHARPK['mh_'+sex]={meta:{skel:S,v:2},buf:null,base:0};apply90(C,opt.sh);if(C.hat!=='none'&&typeof mhHat==='function')try{mhHat(C,C.hat,C.hatC)}catch(e){}return C}
function smesh90(C,geo,mat,item){const m=new T.SkinnedMesh(geo,mat);m.bind(C.skel,new T.Matrix4());m.frustumCulled=false;m.castShadow=!C.npc;m.receiveShadow=true;m.userData.item=item;C.grp.add(m);C.meshes.push(m);(C.byItem[item]=C.byItem[item]||[]).push(m);return m}
function drop90(C,item){for(const m of C.byItem[item]||[]){C.grp.remove(m);m.geometry.dispose();const i=C.meshes.indexOf(m);if(i>=0)C.meshes.splice(i,1);const M=m.material;if(M&&!M.userData.shared){for(const k of['map','emissiveMap'])if(M[k]&&M[k].userData&&M[k].userData.own90)M[k].dispose();M.dispose()}}delete C.byItem[item]}
function apply90(C,sh){const a=C.app,K=C.K;C.wt=Math.max(-1,Math.min(1,a.weight||0));if(!sh)sh=C.sh90||((!C.npc&&typeof shader89==='function')?shader89():{pri:0xe9e4d6,sec:0x2a2c31,glow:0xffe2a6,metal:0xc9a24c});
 const bk=a.sex+'|'+C.wt.toFixed(3)+'|'+C.det;if(C._bk!==bk){drop90(C,'body');const mat=new T.MeshStandardMaterial({map:skinTex90(),roughness:.62,metalness:0});smesh90(C,skin90(C).geo(K.K),mat,'body');C._bk=bk;C._ok=null;C._sig89=null;C._pol89=null;C._r89=null;C._fc89=null}
 C.byItem.body[0].material.color.setHex(a.skin);
 const ok=bk+JSON.stringify(C.outfit);if(C._ok!==ok){for(const it of['cloth_knit','cloth_denim','cloth_leather','suit'])drop90(C,it);const mbs={};C._skirt=C.outfit.some(q=>GARM90[q.g]&&GARM90[q.g].skirt);for(const inst of C.outfit)garment90(mbs,C,inst);
  for(const [k,mb] of Object.entries(mbs)){if(!mb.p.length)continue;if(k==='suit'){const T0=suitTex90(),m=new T.MeshStandardMaterial({map:T0.map,normalMap:T0.nrm,emissiveMap:T0.em,roughness:.5,metalness:.28,emissiveIntensity:.9});m.normalScale.set(.9,.9);smesh90(C,mb.geo(K.K),m,'suit')}else smesh90(C,mb.geo(K.K,true),fabric90(k),'cloth_'+k)}C._ok=ok;C._sig89=null;C._pol89=null;C._fc89=null}
 if(C.byItem.suit){const m=C.byItem.suit[0].material;m.color.copy(new T.Color(sh.sec).multiplyScalar(.62));m.emissive.setHex(sh.glow)}
 const hk=JSON.stringify(Object.assign({},a,{height:0,weight:0}))+C.det;if(C._hk!==hk){for(const it of['head','eyes','hair','brows','fhair','lash'])drop90(C,it);const H=headGeos90(a,K,C),ts=C.npc?512:1024,ft=faceTex90(H.P,a,ts);ft.map.userData.own90=1;if(ft.em)ft.em.userData.own90=1;
  const sc0=new T.Color(a.skin),hm=new T.MeshPhysicalMaterial({map:ft.map,roughness:.52,metalness:0,sheen:.45,sheenRoughness:.65,sheenColor:sc0.clone().lerp(new T.Color(1,.75,.7),.5),normalMap:poreTex90(),specularIntensity:.55});hm.normalScale.set(.08,.08);if(ft.em){hm.emissiveMap=ft.em;hm.emissive=new T.Color(a.markC);hm.emissiveIntensity=1.6}const hm90=smesh90(C,H.head,hm,'head');C._face=[hm90];face90Reg(C);
  const et=eyeTex90(a.eyeC,a.glow);et.map.userData.own90=1;const em=new T.MeshStandardMaterial({map:et.map,roughness:.06,metalness:0});if(et.em){et.em.userData.own90=1;em.emissiveMap=et.em;em.emissive=new T.Color(a.eyeC).lerp(new T.Color(1,1,1),.3);em.emissiveIntensity=2.2}smesh90(C,H.eyes,em,'eyes');
  const hairMat=c=>new T.MeshStandardMaterial({color:c,map:strandTex90(),roughness:.72,metalness:0,side:T.DoubleSide});if(H.hair)smesh90(C,H.hair,hairMat(a.hairC),'hair');if(H.brows)smesh90(C,H.brows,hairMat(a.browC==null?a.hairC:a.browC),'brows');if(H.fhair)smesh90(C,H.fhair,hairMat(a.fhairC==null?a.hairC:a.fhairC),'fhair');if(H.lash)smesh90(C,H.lash,new T.MeshStandardMaterial({color:new T.Color(a.browC==null?a.hairC:a.browC).multiplyScalar(.45),alphaMap:lashTex90(),alphaTest:.25,side:T.DoubleSide,roughness:.8}),'lash');if(C.byItem.lash)C._face.push(C.byItem.lash[0]);C._hk=hk;C._HP=H.P}
 C.grp.scale.setScalar(1+.04*Math.max(-1,Math.min(1,a.height||0)));vis90(C)}
/* hair is hidden under closed helmets and hats (the creator lifts the helmet to preview) */
function vis90(C){const h=C.npc?(C.cfg90&&C.cfg90.ahelmet):(typeof OUT!=='undefined'?OUT.ahelmet:'none'),closed=h&&h!=='none'&&h!=='cap'&&h!=='beanie',hat=C.hat&&C.hat!=='none',pv=!!C.preview90;for(const m of C.byItem.hair||[])m.visible=pv||!(closed||hat);for(const m of C._bakeH||[])m.visible=!pv;if(C.hatMount)C.hatMount.visible=!pv}

/* living faces: blinks, small saccade-free mood drift between neutral and a warm smile */
function face90Reg(C){H90.faceL=H90.faceL||[];if(H90.faceL.indexOf(C)<0)H90.faceL.push(C);if(!H90._ft){H90._ft=1;const L=t=>{requestAnimationFrame(L);try{face90Tick(t/1000)}catch(e){}};requestAnimationFrame(L)}}
function face90Tick(now){const L=H90.faceL;for(let i=L.length-1;i>=0;i--){const C=L[i];if(!C.npc&&typeof CHAR!=='undefined'&&CHAR&&C!==CHAR&&C.grp&&!C.grp.parent){L.splice(i,1);continue}if(!C._face||!C.grp||!C.grp.parent)continue;
 const f=C._fx||(C._fx={nb:now+.5+Math.random()*3,bs:-9,st:.15,sv:0,ns:now+1+Math.random()*4,lt:now});const dt=Math.min(.1,Math.max(0,now-f.lt));f.lt=now;
 if(now>f.nb){f.bs=now;f.nb=now+(Math.random()<.18?.32:2+Math.random()*4.5)}const e=now-f.bs,b=e<.06?e/.06:e<.1?1:e<.24?1-(e-.1)/.14:0;
 if(now>f.ns){f.st=Math.random()<.5?Math.random()*.25:.35+Math.random()*.65;f.ns=now+2.5+Math.random()*6}f.sv+=(f.st-f.sv)*Math.min(1,dt*2.2);
 for(const m of C._face){const I=m.morphTargetInfluences;if(!I)continue;I[0]=b;if(I.length>1)I[1]=f.sv}}}
