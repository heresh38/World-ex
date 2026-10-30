
/* ===== v97: our own vehicles — hover cars (neon cyber, armoured, ivory luxury, steampunk brass) with full cockpits; the yoke turns with your hands ===== */
var HV97={mats:null,glowT:null,holoT:{}};
function hvGlowTex97(){if(HV97.glowT)return HV97.glowT;const c=document.createElement('canvas');c.width=c.height=128;const g=c.getContext('2d'),gr=g.createRadialGradient(64,64,0,64,64,64);gr.addColorStop(0,'rgba(255,255,255,.95)');gr.addColorStop(.35,'rgba(255,255,255,.45)');gr.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=gr;g.fillRect(0,0,128,128);const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;return HV97.glowT=t}
function hvHolo97(kind,col){const k=kind+col;if(HV97.holoT[k])return HV97.holoT[k];const c=document.createElement('canvas');c.width=512;c.height=256;const g=c.getContext('2d'),hex='#'+new T.Color(col).getHexString(),W=512,H=256;g.lineCap='round';
 const bg=(a)=>{g.fillStyle='rgba(5,9,14,'+a+')';g.fillRect(0,0,W,H)};
 if(kind==='cluster'){bg(1);g.strokeStyle=hex;g.fillStyle=hex;g.globalAlpha=.25;g.lineWidth=2;for(let x=0;x<W;x+=32){g.beginPath();g.moveTo(x,0);g.lineTo(x,H);g.stroke()}g.globalAlpha=1;
  for(const [cx,lab,val,fr] of[[128,'KM/H','184',.62],[384,'LIFT','98',.9]]){g.lineWidth=10;g.globalAlpha=.25;g.beginPath();g.arc(cx,138,92,Math.PI*.78,Math.PI*2.22);g.stroke();g.globalAlpha=1;g.beginPath();g.arc(cx,138,92,Math.PI*.78,Math.PI*(.78+1.44*fr));g.stroke();g.lineWidth=2;for(let i=0;i<=12;i++){const a=Math.PI*.78+i/12*Math.PI*1.44;g.beginPath();g.moveTo(cx+Math.cos(a)*74,138+Math.sin(a)*74);g.lineTo(cx+Math.cos(a)*82,138+Math.sin(a)*82);g.stroke()}g.font='bold 56px monospace';g.textAlign='center';g.fillText(val,cx,150);g.font='18px monospace';g.fillText(lab,cx,182)}
  g.font='16px monospace';g.textAlign='left';g.fillText('CELL ▮▮▮▮▮▮▮▯',200,236);g.fillStyle='#ff4a6a';g.fillRect(232,30,48,10)}
 else if(kind==='map'){bg(1);g.strokeStyle=hex;g.globalAlpha=.55;g.lineWidth=3;for(let i=0;i<9;i++){g.beginPath();g.moveTo(0,i*30+10);g.lineTo(W,i*30+20);g.stroke();g.beginPath();g.moveTo(i*60+15,0);g.lineTo(i*60+5,H);g.stroke()}g.globalAlpha=1;g.lineWidth=7;g.beginPath();g.moveTo(256,200);g.lineTo(256,130);g.lineTo(330,90);g.lineTo(420,90);g.stroke();g.fillStyle='#fff';g.beginPath();g.moveTo(256,170);g.lineTo(240,206);g.lineTo(272,206);g.fill();g.fillStyle=hex;g.font='bold 22px monospace';g.fillText('SECTOR 7  ·  1.2 KM',20,32)}
 else if(kind==='hud'){g.clearRect(0,0,W,H);g.strokeStyle=hex;g.fillStyle=hex;g.lineWidth=3;g.globalAlpha=.9;g.beginPath();g.moveTo(206,128);g.lineTo(236,128);g.moveTo(276,128);g.lineTo(306,128);g.moveTo(256,98);g.lineTo(256,112);g.stroke();g.font='bold 34px monospace';g.textAlign='center';g.fillText('184',256,190);g.font='16px monospace';g.fillText('◂ 320 m  NAV',256,222);g.strokeRect(150,60,212,140)}
 else if(kind==='gauge'){g.fillStyle='#2a1a10';g.fillRect(0,0,W,H);for(const cx of[128,384]){const r=g.createRadialGradient(cx,128,10,cx,128,110);r.addColorStop(0,'#fbf3df');r.addColorStop(1,'#d8c8a4');g.fillStyle=r;g.beginPath();g.arc(cx,128,108,0,7);g.fill();g.strokeStyle='#2a1e12';g.lineWidth=3;for(let i=0;i<=16;i++){const a=Math.PI*.75+i/16*Math.PI*1.5,l=i%4?84:74;g.beginPath();g.moveTo(cx+Math.cos(a)*l,128+Math.sin(a)*l);g.lineTo(cx+Math.cos(a)*96,128+Math.sin(a)*96);g.stroke()}g.fillStyle='#2a1e12';g.font='italic 20px serif';g.textAlign='center';g.fillText(cx<256?'PRESSURE':'VELOCITY',cx,178);g.strokeStyle='#9a1a10';g.lineWidth=6;g.beginPath();g.moveTo(cx,128);const a=cx<256?-.4:.9;g.lineTo(cx+Math.cos(a)*86,128+Math.sin(a)*86);g.stroke();g.fillStyle='#7a5a2a';g.beginPath();g.arc(cx,128,10,0,7);g.fill()}}
 else{bg(1);g.fillStyle=hex;g.font='bold 30px monospace';g.fillText('SYS  OK',24,52);g.font='22px monospace';g.fillText('THRUST  ▮▮▮▮▮▮▯▯',24,110);g.fillText('SHIELD  ▮▮▮▮▮▮▮▮',24,150);g.fillText('AUDIO   ▸ NIGHTLINE',24,190);g.fillText('CLIMATE 21°',24,230)}
 const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;t.anisotropy=8;return HV97.holoT[k]=t}
function hvMats97(){if(HV97.mats)return HV97.mats;const S=(c,r,m,o)=>{const q=new T.MeshStandardMaterial(Object.assign({color:c,roughness:r,metalness:m},o||{}));q.userData.noConv=1;return q};
 const wtex=typeof tx77==='function'?tx77('wood','c'):null;
 HV97.mats={gun:S(0x30343b,.42,.75),gunL:S(0x5b616a,.4,.7),bone:S(0xe6e0d0,.5,.2),brass:S(0xc9a24c,.3,.92),copper:S(0xb06a3c,.35,.85),wood:S(0x7a4c2c,.45,0,{map:wtex}),leather:S(0x3a2418,.6,0),leatherL:S(0x8a5432,.55,0),
  seat:S(0x1b1e24,.85,.02),seatT:S(0x2e323a,.55,.05),alc:S(0x24272e,.95,0),carbon:S(0x15171b,.3,.35),rubber:S(0x0d0e10,.9,0),chrome:S(0xd8dde2,.1,1),dash:S(0x121418,.55,.15),mesh:S(0x0b0c0e,.8,.4,{side:T.DoubleSide}),
  glass:new T.MeshPhysicalMaterial({color:0x3a5266,roughness:.04,metalness:.1,transparent:true,opacity:.22,depthWrite:false,side:T.DoubleSide,envMapIntensity:1.6}),
  clear:new T.MeshPhysicalMaterial({color:0xbfd8ea,roughness:.02,metalness:0,transparent:true,opacity:.16,depthWrite:false,side:T.DoubleSide,envMapIntensity:1.4}),
  head:new T.MeshBasicMaterial({color:0xeaf6ff,toneMapped:false})};HV97.mats.glass.userData.noConv=1;HV97.mats.clear.userData.noConv=1;return HV97.mats}
const NEON97={};function neon97(c){return NEON97[c]||(NEON97[c]=new T.MeshBasicMaterial({color:c,toneMapped:false}))}
function hvRBox97(w,h,d,r){r=Math.min(r,w/2-.001,h/2-.001,d/2);const s=new T.Shape(),x=w/2-r,y=h/2-r;s.moveTo(-x,-h/2);s.lineTo(x,-h/2);s.quadraticCurveTo(w/2,-h/2,w/2,-y);s.lineTo(w/2,y);s.quadraticCurveTo(w/2,h/2,x,h/2);s.lineTo(-x,h/2);s.quadraticCurveTo(-w/2,h/2,-w/2,y);s.lineTo(-w/2,-y);s.quadraticCurveTo(-w/2,-h/2,-x,-h/2);const dd=Math.max(.001,d-r*2),g=new T.ExtrudeGeometry(s,{depth:dd,bevelEnabled:true,bevelThickness:r,bevelSize:r*.7,bevelSegments:3,curveSegments:5});g.translate(0,0,-dd/2);g.computeVertexNormals();return g}
/* lofted shell: stations [z, halfWidth, yBottom, yTop, roundness] in ascending z, Catmull-Rom smoothed.
   half: only the upper arc (canopies). open:[z0,z1,yCut] leaves the cabin opening. keep(z,y,x): face filter. */
function loft97(st,o){o=o||{};const R=o.rings||48,S=o.seg||40,half=!!o.half,N=st.length,cols=st[0].length,cr=(a,b,c,d,t)=>.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t);
 const rows=[];for(let i=0;i<=R;i++){const u=i/R*(N-1),k=Math.min(N-2,Math.floor(u)),t=u-k,g=(j,c)=>st[Math.max(0,Math.min(N-1,j))][c],row=[];for(let c=0;c<cols;c++)row.push(cr(g(k-1,c),g(k,c),g(k+1,c),g(k+2,c),t));row[1]=Math.max(.005,row[1]);rows.push(row)}
 const P=[],U=[],I=[],J=half?S+1:S,tum=o.tumble===undefined?.2:o.tumble,und=o.under||0;
 for(let i=0;i<=R;i++){const r=rows[i],n=r[4];for(let j=0;j<J;j++){const a=half?Math.PI*j/S:2*Math.PI*j/S,c=Math.cos(a),s=Math.sin(a),e=s>=0?n:n*(o.flatB||1.5),xv=Math.sign(c)*Math.pow(Math.abs(c),2/e),yv=Math.sign(s)*Math.pow(Math.abs(s),2/e);
  let yc,hh;if(half){yc=r[2];hh=r[3]-r[2]}else{yc=(r[2]+r[3])/2;hh=(r[3]-r[2])/2}const x=r[1]*xv*(yv>0?1-tum*yv:1-und*(-yv));P.push(x,yc+hh*yv,r[0]);U.push(j/S*2,r[0]*.5)}}
 const V=(i,j)=>i*J+j,px=k=>P[k*3],py=k=>P[k*3+1],pz=k=>P[k*3+2];
 for(let i=0;i<R;i++)for(let j=0;j<S;j++){const j2=half?j+1:(j+1)%S,q=[V(i,j),V(i,j2),V(i+1,j2),V(i+1,j)];
  if(o.open){const [z0,z1,yc]=o.open;if(q.every(k=>pz(k)>z0&&pz(k)<z1&&py(k)>yc))continue}
  if(o.keep){const za=(pz(q[0])+pz(q[2]))/2,ya=(py(q[0])+py(q[2]))/2,xa=(px(q[0])+px(q[2]))/2;if(!o.keep(za,ya,xa))continue}
  I.push(q[0],q[2],q[1],q[0],q[3],q[2])}
 if(!half&&o.caps!==false){for(const i of[0,R]){const r=rows[i],c=P.length/3;P.push(0,(r[2]+r[3])/2,r[0]);U.push(.5,.5);for(let j=0;j<S;j++){const a=V(i,j),b=V(i,(j+1)%S);if(i===0)I.push(c,a,b);else I.push(c,b,a)}}}
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(P,3));g.setAttribute('uv',new T.Float32BufferAttribute(U,2));g.setIndex(I);g.computeVertexNormals();return g}
function hvM97(par,geo,mat,x,y,z,rx,ry,rz){const m=new T.Mesh(geo,mat);m.position.set(x||0,y||0,z||0);m.rotation.set(rx||0,ry||0,rz||0);const glow=mat.isMeshBasicMaterial||mat.transparent;m.castShadow=!glow;m.receiveShadow=!glow;par.add(m);return m}
const hvB97=(p,w,h,d,m,x,y,z,rx,ry,rz)=>hvM97(p,new T.BoxGeometry(w,h,d),m,x,y,z,rx,ry,rz);
const hvR97=(p,w,h,d,r,m,x,y,z,rx,ry,rz)=>hvM97(p,hvRBox97(w,h,d,r),m,x,y,z,rx,ry,rz);
const hvC97=(p,r0,r1,h,m,x,y,z,rx,ry,rz,s)=>hvM97(p,new T.CylinderGeometry(r0,r1,h,s||18),m,x,y,z,rx,ry,rz);
const hvT97=(p,r,t,m,x,y,z,rx,ry,rz,arc)=>hvM97(p,new T.TorusGeometry(r,t,8,32,arc||Math.PI*2),m,x,y,z,rx,ry,rz);
function hvRod97(p,a,b,r,m){const d=new T.Vector3().subVectors(b,a),me=new T.Mesh(new T.CylinderGeometry(r,r,d.length(),10),m);me.position.copy(a).add(b).multiplyScalar(.5);me.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),d.normalize());me.castShadow=true;p.add(me);return me}
/* ---------- designs ---------- */
const HVD97={
 vanta:{n:'Vanta Spectre',kind:'cyber',L:4.7,W:2.0,paint:0x1a1d24,neon:0x29e6ff,neon2:0xff3fd8,tum:.24,
  body:[[-2.36,.6,.44,.7,2.6],[-2.24,.92,.34,.86,3.2],[-1.6,1.0,.3,.94,3.4],[-.6,1.0,.29,.92,3.4],[.6,1.0,.29,.88,3.4],[1.5,.98,.3,.79,3.2],[2.1,.88,.33,.67,3],[2.38,.6,.4,.56,2.6]],open:[-1.25,.98,.78],
  canopy:[[-1.5,.66,.8,.84,2.2],[-1.15,.74,.8,1.15,2.4],[-.6,.79,.8,1.45,2.6],[0,.79,.8,1.47,2.6],[.6,.77,.8,1.18,2.4],[1.02,.72,.8,.83,2.2]],roof:[-1.0,-.32],seats:2,spoiler:1,stats:[1.26,1.15,1.06]},
 lumen:{n:'Lumen Regent',kind:'clean',L:4.95,W:2.04,paint:0xe6e0d0,neon:0xffc560,neon2:0xffe2a6,tum:.2,trim:'brass',
  body:[[-2.48,.66,.46,.78,3],[-2.36,.96,.34,.92,3.6],[-1.6,1.02,.3,.96,3.8],[0,1.02,.29,.94,3.8],[1.4,1.0,.3,.88,3.6],[2.2,.92,.33,.76,3.2],[2.5,.66,.42,.62,2.8]],open:[-1.7,1.05,.82],
  canopy:[[-1.95,.7,.84,.88,2.4],[-1.6,.8,.84,1.32,2.8],[-1.0,.82,.84,1.53,3],[.1,.82,.84,1.54,3],[.7,.8,.84,1.26,2.8],[1.12,.74,.84,.88,2.4]],roof:[-1.55,.38],seats:4,stats:[1.08,1.06,1.02]},
 ronin:{n:'Ronin Drift',kind:'cyber',L:4.85,W:2.08,paint:0x5a1428,neon:0xff2f6a,neon2:0x29e6ff,tum:.22,
  body:[[-2.42,.66,.44,.84,2.8],[-2.3,.98,.34,.98,3.4],[-1.4,1.04,.3,1.0,3.6],[0,1.04,.29,.96,3.6],[1.2,1.02,.3,.9,3.4],[2.1,.94,.32,.78,3],[2.44,.7,.38,.62,2.6]],open:[-1.15,.62,.84],
  canopy:[[-1.62,.68,.86,.9,2.2],[-1.3,.76,.86,1.3,2.4],[-.7,.8,.86,1.48,2.6],[-.1,.8,.86,1.46,2.6],[.35,.77,.86,1.2,2.4],[.68,.72,.86,.9,2.2]],roof:[-1.1,-.42],seats:2,scoop:1,stats:[1.2,1.12,1.04]},
 bastion:{n:'Bastion Warden',kind:'armor',L:4.6,W:2.14,paint:0x6d7262,neon:0x9dff5a,neon2:0xffd060,tum:.08,
  body:[[-2.3,.9,.38,1.0,5],[-2.18,1.06,.32,1.06,6],[0,1.07,.3,1.06,6],[1.6,1.06,.32,1.0,6],[2.2,1.0,.36,.92,5],[2.32,.86,.42,.84,4]],open:[-1.55,.62,.94],
  canopy:null,seats:2,cage:1,armor:1,stats:[1.0,1.18,.96]},
 courier:{n:'Courier Hauler',kind:'cyber',L:5.3,W:2.1,paint:0x2a3a52,neon:0x29e6ff,neon2:0xffb020,tum:.12,
  body:[[-2.66,.9,.38,1.0,4],[-2.5,1.05,.32,1.02,4.4],[0,1.06,.3,1.0,4.4],[1.6,1.04,.31,.95,4],[2.4,.94,.34,.8,3.4],[2.68,.7,.42,.66,2.8]],open:[-.55,1.18,.92],
  canopy:[[-.6,.88,.92,1.9,3.4],[-.2,.9,.92,1.9,3.4],[.5,.88,.92,1.66,3],[1.0,.84,.92,1.2,2.6],[1.3,.78,.92,.96,2.4]],roof:[-.6,.35],van:1,seats:2,stats:[.9,1.02,.92]},
 brass:{n:'Brassworks Landau',kind:'steam',L:4.9,W:2.06,paint:0x2f4a3a,neon:0x7dffb0,neon2:0xffa850,tum:.1,
  body:[[-2.46,.7,.44,.86,3],[-2.3,.98,.36,.94,3.6],[-1.2,1.03,.32,.96,3.8],[.4,1.03,.32,.94,3.8],[1.5,.96,.33,.86,3.4],[2.2,.8,.36,.74,3],[2.5,.55,.44,.62,2.6]],open:[-1.7,.98,.84],
  canopy:null,hood:1,seats:4,boiler:1,yoke:'wheel',thr:'fans',stats:[.95,1.05,.98]},
 aether:{n:'Aether Roadster',kind:'steam',L:4.6,W:1.98,paint:0x6a2418,neon:0xffb050,neon2:0x7dffb0,tum:.14,
  body:[[-2.32,.62,.44,.76,2.8],[-2.2,.92,.36,.86,3.4],[-1.3,.98,.32,.88,3.6],[.3,.98,.31,.84,3.6],[1.4,.94,.32,.78,3.2],[2.1,.82,.35,.68,2.8],[2.36,.56,.42,.58,2.4]],open:[-1.05,.82,.76],
  canopy:null,screen:1,pipes:1,seats:2,yoke:'wheel',thr:'fans',stats:[1.12,1.1,1.05]}};
const HV_SEAT97={hipZ:-.22,hipX:.4,cush:.64};
const HV_HEAD97=new T.Vector3(.4,1.3,-.28);
/* ---------- cockpit parts ---------- */
function hvSeat97(par,M,D,x,z,front){const steam=D.kind==='steam',cs=steam?M.leatherL:M.alc,bol=steam?M.leather:M.seatT,acc=steam?M.brass:neon97(D.neon),y=HV_SEAT97.cush,g=new T.Group();g.position.set(x,0,z);par.add(g);
 hvR97(g,.46,.1,.5,.04,cs,0,y-.04,0);for(const s of[-1,1])hvR97(g,.09,.13,.5,.04,bol,s*.24,y,0,0,0,s*.1);
 const bk=new T.Group();bk.position.set(0,y,-.27);bk.rotation.x=-.2;g.add(bk);hvR97(bk,.44,.6,.1,.04,cs,0,.32,0);for(const s of[-1,1])hvR97(bk,.09,.56,.15,.04,bol,s*.24,.3,.02,0,s*.25);hvR97(bk,.28,.2,.1,.04,cs,0,.74,-.01);
 if(steam){for(let i=0;i<3;i++)for(let j=0;j<3;j++)hvM97(bk,new T.SphereGeometry(.012,6,4),acc,-.12+j*.12,.14+i*.16,.055);hvB97(bk,.48,.02,.02,acc,0,.02,.04)}else{hvB97(bk,.012,.5,.012,acc,0,.32,.055);hvB97(g,.012,.012,.46,acc,0,y+.012,0);hvB97(bk,.2,.04,.015,acc,0,.74,.045)}
 hvB97(g,.38,.22,.4,M.gun,0,y-.19,0);if(front)for(const s of[-1,1])hvB97(g,.03,.03,.52,M.chrome,s*.16,y-.31,.02);return g}
function hvYoke97(D,M){/* pivot at the rim centre; after the tilt, the face looks at the driver; spin rotates in the rim plane */const piv=new T.Group(),spin0=new T.Group(),spin=new T.Group();piv.add(spin0);spin0.add(spin);const face=new T.Group();face.rotation.y=Math.PI;spin.add(face);const ne=neon97(D.neon);
 if(D.yoke==='wheel'){face.add(new T.Mesh(new T.TorusGeometry(.18,.017,10,44),M.wood));face.add(new T.Mesh(new T.TorusGeometry(.165,.004,6,40),M.brass));for(let i=0;i<3;i++){const a=Math.PI/2+i*Math.PI*2/3,s=new T.Mesh(new T.BoxGeometry(.012,.17,.006),M.brass);s.position.set(Math.cos(a)*.09,Math.sin(a)*.09,0);s.rotation.z=a-Math.PI/2;face.add(s)}const hub=new T.Mesh(new T.CylinderGeometry(.045,.052,.05,18),M.brass);hub.rotation.x=Math.PI/2;face.add(hub);const cap=new T.Mesh(new T.CylinderGeometry(.03,.03,.012,16),M.wood);cap.rotation.x=Math.PI/2;cap.position.z=.03;face.add(cap)}
 else{const bar=new T.Mesh(hvRBox97(.32,.06,.04,.015),M.carbon);bar.position.y=-.03;face.add(bar);const top=new T.Mesh(hvRBox97(.18,.03,.03,.01),M.carbon);top.position.y=.05;face.add(top);
  for(const s of[-1,1]){const gp=new T.Mesh(new T.CylinderGeometry(.021,.024,.17,12),M.rubber);gp.position.set(s*.17,.005,0);gp.rotation.z=s*.12;face.add(gp);const cap=new T.Mesh(hvRBox97(.04,.03,.045,.01),M.gun);cap.position.set(s*.175,.095,0);face.add(cap);const b=new T.Mesh(new T.CylinderGeometry(.008,.008,.01,8),ne);b.rotation.x=Math.PI/2;b.position.set(s*.175,.095,.024);face.add(b);const b2=b.clone();b2.position.set(s*.13,-.03,.022);face.add(b2)}
  const hub=new T.Mesh(new T.CylinderGeometry(.06,.065,.055,6),M.gun);hub.rotation.x=Math.PI/2;face.add(hub);const hl=new T.Mesh(new T.CircleGeometry(.042,6),ne);hl.position.z=.029;face.add(hl);const ring=new T.Mesh(new T.TorusGeometry(.068,.004,4,6),ne);ring.position.z=.02;face.add(ring)}
 piv.traverse(o=>{if(o.isMesh)o.castShadow=false});return{piv,spin}}
function hvScreen97(par,w,h,tex,x,y,z,look,frameM){look=look||{};const s=new T.Mesh(new T.PlaneGeometry(w,h),new T.MeshBasicMaterial({map:tex,toneMapped:false,transparent:!!look.add,blending:look.add?T.AdditiveBlending:T.NormalBlending,depthWrite:!look.add}));s.position.set(x,y,z);s.lookAt(look.p||HV_HEAD97);par.add(s);
 if(frameM){const f=new T.Mesh(hvRBox97(w+.03,h+.03,.02,.008),frameM);f.position.copy(s.position);f.quaternion.copy(s.quaternion);f.translateZ(-.012);par.add(f)}return s}
function hvInterior97(par,D,M){const steam=D.kind==='steam',W=D.W,x=HV_SEAT97.hipX,z=HV_SEAT97.hipZ,ne=neon97(D.neon),ne2=neon97(D.neon2),trim=steam?M.wood:M.carbon,acc=steam?M.brass:ne,oz0=D.open[0],oz1=D.open[1],iw=W/2-.16;
 /* tub: floor, mats, firewall, rear bulkhead */hvB97(par,W-.24,.04,oz1-oz0,M.carbon,0,.3,(oz0+oz1)/2);for(const s of[-1,1])hvB97(par,.42,.015,.5,M.rubber,s*x,.325,.34);hvB97(par,W-.26,.5,.04,M.dash,0,.55,oz1-.02);hvB97(par,W-.26,.42,.04,trim,0,.52,oz0+.03);
 /* door cards with armrest, handle, speaker, ambient line */
 for(const s of[-1,1]){const dx=s*iw;hvR97(par,.06,.46,Math.min(1.5,oz1-oz0-.2),.02,steam?M.leather:M.seatT,dx,.6,(oz0+oz1)/2+.05);hvR97(par,.09,.05,.55,.02,steam?M.wood:M.alc,dx-s*.05,.72,z+.05);hvB97(par,.02,.03,.12,M.chrome,dx-s*.035,.8,z+.42);hvC97(par,.07,.07,.02,M.mesh,dx-s*.035,.5,z+.5,0,0,Math.PI/2,20);hvT97(par,.072,.006,acc,dx-s*.04,.5,z+.5,0,Math.PI/2,0);hvB97(par,.008,.008,1.2,acc,dx-s*.035,.86,(oz0+oz1)/2+.05)}
 /* seats */hvSeat97(par,M,D,x,z,true);hvSeat97(par,M,D,-x,z,true);
 if(D.seats>2&&oz0<-1.3){const sm=steam?M.leatherL:M.alc;hvR97(par,W-.42,.12,.5,.05,sm,0,.58,oz0+.38);hvR97(par,W-.42,.55,.12,.05,sm,0,.84,oz0+.12,-.15);for(const s of[-1,1])hvR97(par,.26,.18,.1,.04,sm,s*.4,1.18,oz0+.08,-.15)}
 else hvB97(par,W-.3,.04,.42,trim,0,.84,oz0+.24);
 /* centre console, armrest, selector, cup holders */hvR97(par,.26,.3,.95,.04,steam?M.wood:M.gun,0,.45,.0);hvR97(par,.24,.07,.36,.03,steam?M.leather:M.alc,0,.63,-.32);hvB97(par,.2,.006,.4,trim,0,.603,.14);
 for(const q of[-.05,.05])hvC97(par,.035,.035,.01,M.rubber,q,.605,-.02,0,0,0,14);
 if(steam){hvC97(par,.012,.014,.26,M.brass,0,.72,.18,-.35);hvM97(par,new T.SphereGeometry(.028,12,8),M.wood,0,.84,.13);hvT97(par,.06,.012,M.brass,0,.61,.18,Math.PI/2);for(let i=0;i<3;i++)hvB97(par,.012,.04,.012,M.brass,-.06+i*.06,.63,.32)}
 else{hvC97(par,.045,.05,.04,M.gunL,0,.625,.2);hvT97(par,.05,.005,ne,0,.646,.2,Math.PI/2);hvB97(par,.004,.004,.08,ne2,0,.648,.2);hvScreen97(par,.14,.08,hvHolo97('sys',D.neon),0,.62,.36,{p:new T.Vector3(.2,1.3,-.2)},M.gun)}
 /* dashboard cowl across the cabin */
 const sh=new T.Shape(),pf=[[oz1-.5,.66],[oz1-.5,.9],[oz1-.44,.98],[oz1-.26,.96],[oz1-.1,.86],[oz1-.1,.66]];sh.moveTo(pf[0][0],pf[0][1]);for(const p of pf.slice(1))sh.lineTo(p[0],p[1]);sh.closePath();const dg=new T.ExtrudeGeometry(sh,{depth:W-.34,bevelEnabled:true,bevelThickness:.03,bevelSize:.025,bevelSegments:3,curveSegments:6});dg.translate(0,0,-(W-.34)/2);dg.rotateY(-Math.PI/2);hvM97(par,dg,steam?M.wood:M.dash);
 const dz=oz1-.46;hvB97(par,W-.36,.012,.012,acc,0,.95,dz-.04);
 if(steam){hvScreen97(par,.36,.18,hvHolo97('gauge',0xffffff),x,1.0,dz+.02,{},null);for(const s of[-1,1])hvT97(par,.085,.012,M.brass,x+s*.09,1.0,dz+.022).lookAt(HV_HEAD97);hvC97(par,.02,.02,.5,M.copper,0,.9,dz+.04,0,0,Math.PI/2,10);for(let i=0;i<5;i++){hvB97(par,.012,.04,.012,M.brass,-.3+i*.05,.93,dz-.02,-.5);hvC97(par,.012,.012,.012,M.chrome,-.3+i*.05,.95,dz-.04,0,0,0,8)}hvScreen97(par,.1,.1,hvHolo97('gauge',0xffffff),-x,.98,dz+.04,{p:new T.Vector3(-.4,1.3,-.28)},M.brass)}
 else{const hood=hvM97(par,new T.CylinderGeometry(.13,.13,.44,24,1,true,-Math.PI/2,Math.PI),M.dash,x,.99,dz+.12,0,0,Math.PI/2);hood.scale.set(1,1,.7);M.dash.side=T.DoubleSide;hvScreen97(par,.36,.15,hvHolo97('cluster',D.neon),x,1.04,dz+.1,{},null);
  hvScreen97(par,.3,.17,hvHolo97('map',D.neon2),0,.92,dz+.02,{p:new T.Vector3(.15,1.3,-.28)},M.gun);hvScreen97(par,.36,.12,hvHolo97('sys',D.neon),-x,.96,dz+.04,{p:new T.Vector3(-.4,1.3,-.28)},null);
  hvScreen97(par,.26,.13,hvHolo97('hud',D.neon),x,1.12,oz1-.12,{add:1},null);
  for(const vx of[-.62,-.15,.15,.68]){hvR97(par,.16,.05,.03,.01,M.gunL,vx,.9,dz-.035);for(let k=0;k<3;k++)hvB97(par,.14,.004,.03,M.carbon,vx,.89+k*.012,dz-.04)}}
 /* steering column, pedals, mirror, visors */hvC97(par,.035,.045,.32,steam?M.brass:M.gun,x,.95,.42,1.95);hvR97(par,.12,.1,.12,.02,M.gun,x,.92,.53);
 for(const k of[0,1]){const pg=new T.Group();pg.position.set(x-.07+k*.13,.38,.5);pg.rotation.x=-.45;par.add(pg);hvB97(pg,.015,.16,.015,M.gun,0,.08,0);hvR97(pg,.075,.1,.015,.005,M.chrome,0,.15,-.01)}
 if(D.canopy){const cn=D.canopy,rz=cn[cn.length-2][0]-.15,ry=cn[cn.length-2][3]-.08;hvR97(par,.22,.06,.02,.01,M.gun,0,ry-.03,rz);hvB97(par,.2,.05,.004,M.chrome,0,ry-.03,rz-.012);for(const s of[-1,1])hvR97(par,.38,.015,.16,.005,M.alc,s*.38,ry+.02,rz-.06,.25);hvB97(par,.12,.01,.06,ne,0,ry+.05,rz-.3)}}
/* ---------- hover hardware ---------- */
function hvThrusters97(ch,D,M,fx){const ne=neon97(D.neon),L=D.L,W=D.W;
 for(const [sx,sz] of[[1,1],[-1,1],[1,-1],[-1,-1]]){const z=sz*L*.31,x=sx*(W/2-.3);if(D.thr==='fans'){hvT97(ch,.27,.04,M.brass,x,.28,z,Math.PI/2);const fan=new T.Group();fan.name='fan97';fan.position.set(x,.25,z);for(let i=0;i<6;i++){const b=new T.Mesh(new T.BoxGeometry(.24,.01,.07),M.brass);b.position.x=.12;b.rotation.x=.45;const a=new T.Group();a.rotation.y=i/6*Math.PI*2;a.add(b);fan.add(a)}ch.add(fan);fx.push(fan);const gl=new T.Mesh(new T.CircleGeometry(.24,24),ne);gl.rotation.x=Math.PI/2;gl.position.set(x,.2,z);ch.add(gl)}
  else{hvC97(ch,.2,.25,.16,M.gun,x,.27,z);hvT97(ch,.2,.022,ne,x,.19,z,Math.PI/2);const gl=new T.Mesh(new T.CircleGeometry(.17,24),ne);gl.rotation.x=Math.PI/2;gl.position.set(x,.185,z);ch.add(gl);for(let k=0;k<4;k++)hvB97(ch,.34,.01,.02,M.gunL,x,.2,z,0,k*Math.PI/4,0)}}
 const pool=new T.Mesh(new T.PlaneGeometry(W*1.9,L*1.25),new T.MeshBasicMaterial({map:hvGlowTex97(),color:D.neon,transparent:true,opacity:.55,blending:T.AdditiveBlending,depthWrite:false,toneMapped:false}));pool.rotation.x=-Math.PI/2;pool.position.y=.04;pool.name='pool97';pool.castShadow=false;pool.receiveShadow=false;return pool}
/* ---------- body build ---------- */
function hvBuild97(key){const D=HVD97[key]||HVD97.vanta,M=hvMats97(),steam=D.kind==='steam',L=D.L,W=D.W,ne=neon97(D.neon),ne2=neon97(D.neon2);
 const root=new T.Group(),ch=new T.Group();root.add(ch);root.rotation.order='YXZ';
 const paint=new T.MeshPhysicalMaterial({color:D.paint,metalness:steam?.3:.55,roughness:steam?.38:.3,clearcoat:1,clearcoatRoughness:.07,envMapIntensity:1.15,side:T.DoubleSide});paint.userData={paint:true,rc:true,noConv:1};
 const tl=new T.MeshBasicMaterial({color:0x6a1010,toneMapped:false}),trim=D.trim==='brass'||steam?M.brass:M.gun;
 /* steering pivot first: the shared takeover code finds it as the first group-with-one-group child */
 const Y=hvYoke97(D,M),swT=new T.Group();swT.add(Y.piv);ch.add(swT);const yokeC=new T.Vector3(HV_SEAT97.hipX,.96,.28);Y.piv.position.copy(yokeC);Y.piv.rotation.x=.38;
 /* shell + gunmetal skirt + side neon */
 hvM97(ch,loft97(D.body,{open:D.open,tumble:D.tum,under:.12,rings:56,seg:44}),paint);
 hvM97(ch,loft97(D.body.map(r=>[r[0],r[1]*1.012,r[2]-.02,r[2]+.14,r[4]]),{tumble:0,rings:40,seg:32}),steam?M.copper:M.gun);
 const mz=D.body.reduce((a,r)=>Math.max(a,Math.abs(r[0])),0)*.8;for(const s of[-1,1]){hvB97(ch,.02,.025,mz*2,ne,s*(W/2+.012),.43,0);}
 if(D.canopy){hvM97(ch,loft97(D.canopy,{half:1,tumble:0,rings:40,seg:28}),M.glass).renderOrder=2;const rk=D.roof;hvM97(ch,loft97(D.canopy.map(r=>[r[0],r[1]+.008,r[2],r[3]+.008,r[4]]),{half:1,tumble:0,rings:40,seg:28,keep:(z,y,x)=>z>rk[0]&&z<rk[1]&&Math.abs(x)<.5}),paint);
  }
 if(D.van){hvR97(ch,W-.04,1.62,2.1,.12,paint,0,1.13,-1.55);for(const s of[-1,1]){hvB97(ch,.01,.05,1.9,ne2,s*(W/2-.015),1.5,-1.55);hvB97(ch,.01,.05,1.9,ne,s*(W/2-.015),.98,-1.55)}hvB97(ch,W-.3,.04,.04,ne,0,1.96,-.6);hvB97(ch,1.5,1.2,.02,M.gun,0,1.15,-2.61);hvB97(ch,1.4,.06,.03,tl,0,1.8,-2.62)}
 if(D.cage){const h=1.74,z0=-.95,z1=.52,X=.86;for(const s of[-1,1]){hvRod97(ch,new T.Vector3(s*.9,.98,z1+.32),new T.Vector3(s*X,h,z1),.035,M.gun);hvRod97(ch,new T.Vector3(s*X,h,z1),new T.Vector3(s*X,h,z0),.035,M.gun);hvRod97(ch,new T.Vector3(s*X,h,z0),new T.Vector3(s*.92,1.0,z0-.45),.035,M.gun);hvRod97(ch,new T.Vector3(s*X,h,z0),new T.Vector3(s*.92,1.0,z0+.1),.03,M.gun)}hvRod97(ch,new T.Vector3(-X,h,z1),new T.Vector3(X,h,z1),.035,M.gun);hvRod97(ch,new T.Vector3(-X,h,z0),new T.Vector3(X,h,z0),.035,M.gun);hvRod97(ch,new T.Vector3(-X,h,z0),new T.Vector3(X,1.0,z0-.45),.03,M.gun);
  hvB97(ch,1.66,.5,.012,M.clear,0,1.25,.78,-.55);hvB97(ch,1.7,.04,.05,M.gun,0,1.48,.66,-.55);hvB97(ch,1.7,.04,.05,M.gun,0,1.03,.9,-.55);for(let i=0;i<4;i++)hvB97(ch,.25,.06,.04,ne2,-.6+i*.4,1.76,z1);hvB97(ch,1.5,.07,.18,M.gunL,0,1.78,z1-.05)}
 if(D.armor){for(const s of[-1,1]){hvR97(ch,.07,.34,1.4,.02,M.gunL,s*(W/2+.03),.7,1.1);hvR97(ch,.07,.32,1.0,.02,M.gunL,s*(W/2+.03),.72,-1.55);for(let k=0;k<5;k++)hvC97(ch,.018,.018,.02,M.chrome,s*(W/2+.07),.82,.55+k*.28,0,0,Math.PI/2,8)}hvR97(ch,1.1,.04,1.1,.015,M.gun,0,1.06,1.55);for(let i=0;i<5;i++)hvB97(ch,.9,.01,.03,ne,0,1.085,1.1+i*.2);hvR97(ch,W*.9,.18,.12,.03,M.gun,0,.56,L/2+.02)}
 if(D.hood){const hz0=D.open[0]+.02;for(let k=0;k<4;k++)hvT97(ch,.86,.02,M.brass,0,.92,hz0+.15+k/3*.62,0,0,0,Math.PI).scale.set(1,.62,1);hvM97(ch,loft97([[hz0+.12,.86,.92,1.46,2.2],[hz0+.5,.88,.92,1.48,2.2],[hz0+.82,.86,.92,1.44,2.2]],{half:1,tumble:0,rings:12,seg:24}),M.leather);
  hvB97(ch,1.7,.48,.012,M.clear,0,1.15,D.open[1]-.12,-.3);hvB97(ch,1.74,.03,.03,M.brass,0,1.39,D.open[1]-.18,-.3);for(const s of[-1,1])hvB97(ch,.03,.52,.03,M.brass,s*.86,1.13,D.open[1]-.12,-.3);
  for(const s of[-1,1])for(const zz of[-.6,.2]){hvT97(ch,.11,.02,M.brass,s*(W/2+.01),.66,zz,0,Math.PI/2,0);hvM97(ch,new T.CircleGeometry(.1,18),ne,s*(W/2+.012),.66,zz,0,s*Math.PI/2,0)}}
 if(D.boiler){const bz=-L/2+.55;hvC97(ch,.34,.34,1.0,M.copper,0,1.12,bz,0,0,Math.PI/2,24);for(const xx of[-.4,0,.4])hvT97(ch,.35,.025,M.brass,xx,1.12,bz,0,Math.PI/2,0);hvC97(ch,.08,.11,.85,M.gun,.32,1.62,bz);hvT97(ch,.11,.03,M.brass,.32,2.05,bz,Math.PI/2);const sm=new T.Group();sm.name='stack97';sm.position.set(.32,2.1,bz);ch.add(sm);hvC97(ch,.06,.06,.4,M.brass,-.42,1.3,bz,0,0,.4);hvM97(ch,new T.SphereGeometry(.08,12,8),M.brass,-.5,1.5,bz);
  hvB97(ch,.2,.2,.04,M.gun,-.25,1.12,bz+.34);hvScreen97(ch,.14,.14,hvHolo97('gauge',0xffffff),-.25,1.12,bz+.365,{p:new T.Vector3(-.25,1.12,5)},null)}
 if(D.pipes){for(const s of[-1,1]){for(let k=0;k<3;k++)hvC97(ch,.03,.03,2.3,M.copper,s*(W/2+.05),.48+k*.07,-.25,Math.PI/2,0,0,10);hvC97(ch,.075,.05,.22,M.brass,s*(W/2+.05),.55,-1.5,Math.PI/2);hvC97(ch,.075,.05,.22,M.brass,s*(W/2+.05),.55,.95,Math.PI/2)}
  hvB97(ch,1.4,.3,.012,M.clear,0,1.0,D.open[1]-.05,-.45);hvB97(ch,1.44,.025,.025,M.brass,0,1.13,D.open[1]-.11,-.45);hvR97(ch,.9,.2,.5,.08,M.leather,0,.86,D.open[0]-.2);const fan=new T.Group();fan.name='fan97r';fan.position.set(0,.66,-L/2+.02);ch.add(fan);hvT97(ch,.24,.03,M.brass,0,.66,-L/2+.02);for(let i=0;i<5;i++){const b=new T.Mesh(new T.BoxGeometry(.2,.012,.06),M.copper);b.position.x=.1;const a=new T.Group();a.rotation.z=i/5*Math.PI*2;a.add(b);fan.add(a)}}
 if(D.spoiler){hvR97(ch,W*.92,.035,.34,.012,M.carbon,0,1.0,-L/2+.22,.1);for(const s of[-1,1])hvB97(ch,.03,.18,.18,M.carbon,s*.62,.9,-L/2+.25);hvB97(ch,W*.9,.012,.012,ne2,0,1.02,-L/2+.06)}
 if(D.scoop){hvR97(ch,.5,.1,.85,.04,M.carbon,0,1.0,1.25,-.07);for(let i=0;i<4;i++)hvB97(ch,.4,.01,.02,ne,0,1.05,.92+i*.2)}
 /* lights (the tail strip is the brake material) */const fz=D.body[D.body.length-1][0];hvB97(ch,W*.62,.03,.03,M.head,0,.6,fz-.04);for(const s of[-1,1]){hvR97(ch,.3,.06,.06,.02,M.dash,s*(W/2-.46),.56,fz-.2);hvB97(ch,.26,.03,.02,M.head,s*(W/2-.46),.565,fz-.165)}
 const rz=D.body[0][0];hvB97(ch,W*.72,.04,.03,tl,0,.7,rz+.04);for(const s of[-1,1])hvB97(ch,.03,.16,.03,tl,s*(W/2-.15),.64,rz+.08);
 if(!steam&&!D.van)for(const s of[-1,1]){hvC97(ch,.12,.16,.26,M.gun,s*.5,.5,rz+.15,Math.PI/2);const g=new T.Mesh(new T.CircleGeometry(.1,20),ne);g.position.set(s*.5,.5,rz+.015);g.rotation.y=Math.PI;ch.add(g)}
 hvInterior97(ch,D,M);
 const fx=[];const pool=hvThrusters97(ch,D,M,fx);
 /* wheel-pivot stand-ins for the shared physics code: front ones carry small steering vanes */
 const wh=[];for(let i=0;i<4;i++){const pv=new T.Group(),g=new T.Group();pv.add(g);const front=i<2;pv.position.set((i%2?1:-1)*(W/2-.3),.24,(front?1:-1)*L*.31);if(front){const vane=new T.Mesh(new T.BoxGeometry(.02,.12,.3),M.gunL);vane.position.y=-.1;g.add(vane)}root.add(pv);wh.push(g)}
 root.add(pool);const fp=[root.children[2],root.children[4]];
 const rf=D.canopy?D.canopy.reduce((a,r)=>Math.max(a,r[3]),0)-.07:(D.cage?1.7:D.hood?1.4:2.4);
 root.userData.seat97={hip:[HV_SEAT97.hipX,HV_SEAT97.cush+.08,HV_SEAT97.hipZ],wheel:[yokeC.x,yokeC.y,yokeC.z],roof:rf,W,L,wr:D.yoke==='wheel'?.18:.17,tilt:.38};root.userData.hv97=key;
 return{root,ch,wh,fp,tl,paints:[paint],rc:true,meta:{size:[W,1.6,L],wheels:[{r:.38}]},yoke:Y.spin}}
