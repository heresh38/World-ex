
/* ---------- armor polish: the arsenal's art style on every piece (ivory plates over graphite chassis, gold trim, glow seams, rings, panel lines) ---------- */
function det89(src,geo,mat,dy){const m=new T.Mesh(geo,mat);m.position.copy(src.position);m.quaternion.copy(src.quaternion);m.scale.copy(src.scale);if(dy)m.translateY(dy);m.castShadow=false;m.receiveShadow=true;m.userData.det89=1;src.parent.add(m);return m}
function polish89(root,M){const list=[];root.traverse(o=>{if(o.isMesh&&o.userData.d89&&!o.userData.det89)list.push(o)});
 for(const o of list){const d=o.userData.d89,isP=o.material===M.pri,isS=o.material===M.sec;if(!isP&&!isS&&o.material!==M.metal)continue;
  if(d.k==='limb'&&d.L>.05){const full=d.thL>6.2,mid=full?0:d.th0+d.thL/2,L=d.L,rAt=t=>d.r1+(d.r2-d.r1)*t;
   if(isP){/* gold trim bands at both ends */for(const t of[.06,.94]){const r=rAt(t)*1.045;det89(o,new T.CylinderGeometry(r,r,.008,18,1,true,d.th0,d.thL),M.metal,(t-.5)*L)}
    /* glow seam down the front */det89(o,new T.CylinderGeometry(d.r2*1.03,d.r1*1.03,L*.62,2,1,true,mid-.045,.09),M.glow);
    /* panel groove */const r=rAt(.5)*1.03;det89(o,new T.CylinderGeometry(r,r,.004,18,1,true,d.th0,d.thL),M.dark,L*.18);
    /* barrel rings (the rifles' signature) near the lower end of full tubes */if(full&&L>.12)for(const t of[.22,.3])det89(o,new T.TorusGeometry(rAt(t)*1.06,.0028,6,28).rotateX(Math.PI/2),M.glow,(t-.5)*L)}
   else if(isS&&full){/* graphite chassis: ribbing */for(let i=1;i<4;i++){const t=i/4,r=rAt(t)*1.025;det89(o,new T.CylinderGeometry(r,r,.006,16,1,true),M.dark,(t-.5)*L)}}}
  else if(d.k==='ell'&&isP){const part=d.thL<Math.PI*.95;
   if(part&&d.phL>6.2){const T1=d.th0+d.thL,g=new T.TorusGeometry(Math.sin(T1),.05,6,40);g.rotateX(Math.PI/2);g.translate(0,Math.cos(T1),0);g.scale(d.rx,d.ry,d.rz);det89(o,g,M.metal);
    const s2=new T.SphereGeometry(1.012,3,10,Math.PI/2-.05,.1,d.th0+.15,d.thL*.8);s2.scale(d.rx,d.ry,d.rz);det89(o,s2,M.glow)}
   else if(!part&&d.phL>6.2){/* helmet dome: centre crest, brow groove and temple seams */const cr=new T.SphereGeometry(1.02,4,16,Math.PI/2-.07,.14,.02,Math.PI*.62);cr.scale(d.rx,d.ry,d.rz);det89(o,cr,M.metal);
    const br=new T.TorusGeometry(Math.sin(Math.PI*.38),.012,5,48);br.rotateX(Math.PI/2);br.translate(0,Math.cos(Math.PI*.38),0);br.scale(d.rx*1.01,d.ry,d.rz*1.01);det89(o,br,M.dark);
    for(const s of[-1,1]){const sm=new T.SphereGeometry(1.015,3,8,(s>0?0:Math.PI)-.04,.08,Math.PI*.3,Math.PI*.3);sm.scale(d.rx,d.ry,d.rz);det89(o,sm,M.glow)}}}
  else if(d.k==='box'&&(isP||isS)&&Math.min(d.w,d.h)>.03){const gw=d.w*.74,gh=d.h*.64,t=.0032,gm=isP?M.dark:M.metal;for(const z of[1,-1]){for(const sy of[-1,1]){const m=det89(o,new T.BoxGeometry(gw,t,.003),gm);m.translateZ(z*(d.d/2+.0012));m.translateY(sy*gh/2)}for(const sx of[-1,1]){const m=det89(o,new T.BoxGeometry(t,gh,.003),gm);m.translateZ(z*(d.d/2+.0012));m.translateX(sx*gw/2)}}
   if(d.w>.06){const tr=new T.BoxGeometry(d.w*.86,.0045,.004);for(const z of[1,-1]){const m=det89(o,tr,M.metal);m.translateZ(z*(d.d/2+.003));m.translateY(-d.h/2+.012)}}
   if(isP&&d.w*d.h>.004){const gl=new T.BoxGeometry(.006,d.h*.42,.004);for(const z of[1,-1]){const m=det89(o,gl,M.glow);m.translateZ(z*(d.d/2+.0035))}}}}}
/* helmet hardware shared by every closed helmet: neck guard + ear modules with glow rings */
function helmetHW89(id,C,M,P,G){if(id==='none'||id==='cap'||id==='beanie'||id==='hood')return;const g=G('Head'),P0=P.Head,f=C.sex==='female'?.93:1,hc=V89(0,P0.y+.078*f,P0.z-.004),R=.128*f;
 for(let i=0;i<2;i++){const sh=new T.CylinderGeometry(R*(1-.08*i),R*(1.05-.08*i),.03,24,1,true,Math.PI*.55,Math.PI*.9);const m=new T.Mesh(sh,i?M.sec:M.pri);m.position.copy(hc.clone().add(V89(0,-.095*f-i*.026,-.012)).sub(P0));m.castShadow=true;g.add(m)}
 if(id!=='warden')for(const s of[-1,1]){const e=new T.Mesh(new T.CylinderGeometry(.026*f,.03*f,.022,20),M.sec);e.rotation.z=Math.PI/2;e.position.copy(hc.clone().add(V89(s*R*1.03,-.02*f,-.008)).sub(P0));g.add(e);const r=new T.Mesh(new T.TorusGeometry(.021*f,.0028,6,28),M.glow);r.rotation.y=Math.PI/2;r.position.copy(e.position).add(V89(s*.012,0,0));g.add(r);const c=new T.Mesh(new T.CylinderGeometry(.011*f,.011*f,.026,12),M.metal);c.rotation.z=Math.PI/2;c.position.copy(e.position);g.add(c)}}
/* chest emblem + shoulder yokes in gold, abdomen glow seam */
function chestHW89(id,C,M,P,G){if(id==='none')return;const g=G('Spine2'),P0=P.Spine2,shX=Math.abs(P.LeftArm.x),f=C.sex==='female',rz=(f?.152:.138)*(C._kT89||1),cz=C._cz89||P0.z+(f?.03:.025),y1=P.LeftArm.y+.025;
 const hex=new T.Mesh(new T.CylinderGeometry(.022,.022,.006,6),M.metal);hex.rotation.x=Math.PI/2;hex.position.set(-shX*.4,y1-.07-P0.y,cz+rz*1.24+.006-P0.z);g.add(hex);const hx2=new T.Mesh(new T.CylinderGeometry(.012,.012,.008,6),M.glow);hx2.rotation.x=Math.PI/2;hx2.position.copy(hex.position).add(V89(0,0,.003));g.add(hx2);
 for(const s of[-1,1]){const y=new T.Mesh(new T.BoxGeometry(.01,.006,rz*1.9),M.metal);y.position.set(s*shX*.62,y1+.004-P0.y,cz-P0.z);y.rotation.z=s*.28;g.add(y)}}
/* cloak: woven graphite cloth with an ivory hem, gold piping and a glowing sigil, all from the shader colours */
function capeMat89(M){const W=256,H=512,cv=document.createElement('canvas');cv.width=W;cv.height=H;const x=cv.getContext('2d'),ev=document.createElement('canvas');ev.width=W;ev.height=H;const e=ev.getContext('2d');e.fillStyle='#000';e.fillRect(0,0,W,H);
 const hx=c=>'#'+c.getHexString(),sec=M.sec.color,pri=M.pri.color,gold=M.metal.color;x.fillStyle=hx(sec.clone().multiplyScalar(.9));x.fillRect(0,0,W,H);
 for(let i=0;i<H;i+=3){x.fillStyle='rgba(255,255,255,'+(i%6?.025:.05)+')';x.fillRect(0,i,W,1)}for(let i=0;i<W;i+=4){x.fillStyle='rgba(0,0,0,.06)';x.fillRect(i,0,1,H)}
 for(const px of[W*.33,W*.67]){x.fillStyle='rgba(0,0,0,.22)';x.fillRect(px-1,0,2,H*.86)}
 const hem=H*.86;x.fillStyle=hx(pri);x.fillRect(0,hem,W,H-hem);x.fillStyle='rgba(0,0,0,.18)';for(let i=0;i<W;i+=W/8)x.fillRect(i,hem+6,1.5,H-hem-6);
 x.fillStyle=hx(gold);x.fillRect(0,hem-6,W,4);x.fillRect(0,hem+3,W,2);x.fillRect(0,0,6,H);x.fillRect(W-6,0,6,H);x.fillRect(0,H-5,W,5);
 e.fillStyle='#fff';e.fillRect(0,hem-1,W,2);
 const cx=W/2,cy=H*.2,hex=(ctx,r)=>{ctx.beginPath();for(let k=0;k<6;k++){const a=Math.PI/6+k*Math.PI/3;ctx.lineTo(cx+Math.cos(a)*r,cy+Math.sin(a)*r)}ctx.closePath()};
 x.strokeStyle=hx(gold);x.lineWidth=5;hex(x,34);x.stroke();x.lineWidth=2;hex(x,24);x.stroke();e.strokeStyle='#fff';e.lineWidth=3;hex(e,24);e.stroke();e.fillStyle='#fff';e.beginPath();e.arc(cx,cy,6,0,7);e.fill();x.fillStyle=hx(gold);x.beginPath();x.arc(cx,cy,6,0,7);x.fill();
 x.fillStyle=hx(gold);x.fillRect(cx-1.5,cy+40,3,H*.5);e.fillStyle='#fff';e.fillRect(cx-1,cy+48,2,H*.42);
 const t=new T.CanvasTexture(cv),te=new T.CanvasTexture(ev);t.colorSpace=T.SRGBColorSpace;t.anisotropy=4;te.colorSpace=T.SRGBColorSpace;
 return new T.MeshStandardMaterial({map:t,emissiveMap:te,emissive:M.glow.emissive.clone(),emissiveIntensity:1.6,roughness:.86,metalness:.05,side:T.DoubleSide})}
/* wire it into the build: polish, then merge each bone mount per material for speed (cloth stays separate so it can move) */
var MSET89=new WeakMap();
{const oM=amats89;amats89=function(){const M=oM.apply(this,arguments);for(const k in M)MSET89.set(M[k],M);return M}}
function setOf89(root){let M=null;root.traverse(o=>{if(!M&&o.isMesh&&MSET89.has(o.material))M=MSET89.get(o.material)});return M}
{const oB=buildArmor89;buildArmor89=function(C){oB.apply(this,arguments);try{if(!C||!C.mh||C._pol89===C._sig89)return;C._pol89=C._sig89;const P=rest89(C),G=bn=>mount89(C,bn);let M=null;for(const g of Object.values(C._m89||{})){M=M||setOf89(g)}if(!M)return;
  try{helmetHW89(OUT.ahelmet,C,M,P,G)}catch(e){}try{chestHW89(OUT.achest,C,M,P,G)}catch(e){}
  for(const c of C._cloth89||[]){if(c.k==='cape'&&c.m.isMesh){try{const om=c.m.material;c.m.material=capeMat89(M);c.m.userData.cm89=1}catch(e){}}c.m.traverse(q=>{q.userData.isBeam78=1})}
  for(const g of Object.values(C._m89||{})){polish89(g,M);g.traverse(q=>{if(q.isMesh&&q.material&&q.material.transparent)q.userData.isBeam78=1});try{merge78(g)}catch(e){console.warn('merge89',e)}g.traverse(o=>{if(o.isMesh){o.frustumCulled=false;o.castShadow=!o.material.transparent}})}}catch(e){console.warn('polish89',e)}}}
