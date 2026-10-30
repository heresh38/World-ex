
/* ===== v96: one combat path for every world (city, landing zones, frontier), clear-glass optics, laser alignment, aim smoothing, surface-aware impacts ===== */
/* ---------- 1. weapon tick runs once per frame from the render hook, never from world-specific systems ---------- */
const v63Tick96=v63Tick;v63Tick=function(){};/* traffic no longer drives the weapons */
const BS96=bulletStep;/* the real projectile/casing integrator */
var TK96={last:0,frame:0};
{const oW=wpnTick;wpnTick=function(dt){const n=performance.now();if(n-TK96.last<4)return;TK96.last=n;/* a second call within the same frame is ignored */
  if(WST.sens0===null)WST.sens0=SET.sens;/* the old scoped-sensitivity hack must never touch the saved setting */
  return oW.apply(this,arguments)}}
function worldTick96(dt){if(!started||paused)return;
 try{if(!(typeof GEN!=='undefined'&&GEN.on)&&!(typeof BIO!=='undefined'&&BIO.on)){tlPaint(false)}}catch(e){}
 try{if(!(typeof GEN!=='undefined'&&GEN.on))garageCols()}catch(e){}
 try{airCol()}catch(e){}
 try{wpnTick(dt)}catch(e){if(!window._wt96){window._wt96=1;console.warn('wpnTick',e)}}
 try{fx96Parent()}catch(e){}}
/* frontier world: same integrator, with that world's adapters (no city peds/buildings/traffic) */
if(typeof bioBullets==='function'){bioBullets=function(dt){const aP=allPeds,aB=bNearSeg,aR=propsNear,bv=BVH.ready,tr=TRF.splice(0),cs=cars.splice(0);allPeds=()=>[];bNearSeg=()=>[];propsNear=function(){_pnOut.length=0;return _pnOut};BVH.ready=false;
  try{BS96(dt)}finally{allPeds=aP;bNearSeg=aB;propsNear=aR;BVH.ready=bv;TRF.push(...tr);cars.push(...cs)}}}
/* effects follow the scene that is actually being drawn */
function fx96Parent(){const S=actScene79();for(const o of[typeof _TRCL!=='undefined'?_TRCL:null,DEC.im,PX96.pts,PX96.lines,typeof mflash!=='undefined'?mflash:null,typeof LZ78!=='undefined'?LZ78.dot:null])if(o&&o.parent!==S)S.add(o);for(const c of WST.cas)if(c.m.parent!==S)S.add(c.m)}
{const oE=ejectCase;ejectCase=function(){const r=oE.apply(this,arguments);try{const c=WST.cas[WST.cas.length-1];if(c){const S=actScene79();if(c.m.parent!==S)S.add(c.m)}}catch(e){}return r}}

/* ---------- 2. look input: raw deltas -> smoothed, FOV-consistent sensitivity, ADS multiplier, gentle aim friction ---------- */
const SETD96={adsSens:.8,aimSmooth:.25,aimAssist:true,scopeSens:.9};for(const k in SETD96)if(SET[k]===undefined)SET[k]=SETD96[k];
var LOOK96={dx:0,dy:0,t:0};
addEventListener('pointermove',e=>{if(paused||!locked)return;if(typeof PR!=='undefined'&&PR.playing)return;if(typeof ED!=='undefined'&&ED.on)return;window._lookT=performance.now();LOOK96.dx+=e.movementX||0;LOOK96.dy+=e.movementY||0;mX=innerWidth/2;mY=innerHeight/2;e.stopImmediatePropagation()},true);
function lookMul96(){if(cur||!gunOn||!ADS)return 1;const w=WD(),f=Math.max(1,cam.fov)/Math.max(1,SET.fov);const sc=SCP85(w);return(sc?SET.scopeSens:SET.adsSens)*Math.min(1,f*1.05)}
function aimFriction96(){if(!SET.aimAssist||cur||!gunOn)return 1;try{const d=_lk96.set(0,0,-1).applyQuaternion(cam.quaternion),o=cam.position;let best=1;for(const p of allPeds()){if(p.dead||!p.g)continue;const g=p.g.position,vx=g.x-o.x,vy=g.y+1.2-o.y,vz=g.z-o.z,L=Math.hypot(vx,vy,vz);if(L>120||L<1)continue;const c=(vx*d.x+vy*d.y+vz*d.z)/L;if(c<.99)continue;const ang=Math.acos(Math.min(1,c)),rad=.5/L;if(ang<rad*2.2)best=Math.min(best,ADS?.55:.75)}return best}catch(e){return 1}}
const _lk96=new T.Vector3();
function lookApply96(){const n=performance.now(),dt=Math.min(.05,Math.max(.001,(n-(LOOK96.t||n))/1000));LOOK96.t=n;if(!LOOK96.dx&&!LOOK96.dy)return;
 const sm=Math.max(0,Math.min(1,SET.aimSmooth||0)),a=sm<.02?1:1-Math.exp(-dt/(sm*.07));const ux=LOOK96.dx*a,uy=LOOK96.dy*a;LOOK96.dx-=ux;LOOK96.dy-=uy;if(Math.abs(LOOK96.dx)<.01)LOOK96.dx=0;if(Math.abs(LOOK96.dy)<.01)LOOK96.dy=0;
 const k=lookMul96()*aimFriction96(),sx=.0035*SET.sens*k,sy=.003*SET.sens*k*(SET.invY?-1:1);if(cur)orb-=ux*sx;else camA-=ux*sx;camP=cl(camP+uy*sy,-.2,.9);aimP=cl(aimP-uy*sy,-1.15,.9);try{updCross()}catch(e){}}

/* ---------- 3. optics: clear glass, hairline rims, reticle drawn on screen; switching guns resets everything ---------- */
{const oG=gOptic;gOptic=function(g,kind){const before=new Set(g.children);const r=oG.apply(this,arguments);for(const c of g.children)if(!before.has(c)){c.userData.optic96=kind;c.traverse(q=>{q.userData.optic96=kind})}return r}}
{const oM=merge78;merge78=function(inner){const held=[];inner.traverse(o=>{if(o.userData&&o.userData.optic96&&o.parent&&!(o.parent.userData&&o.parent.userData.optic96))held.push([o,o.parent])});for(const[o,p]of held)p.remove(o);try{return oM.apply(this,arguments)}finally{for(const[o,p]of held)p.add(o)}}}
/* the old clip-plane trick is replaced by hiding the optic body */
{const oS=vmClipSetup85;vmClipSetup85=function(){const r=oS.apply(this,arguments);VMCL85.z=null;VMCL85.on=false;for(const m of VMCL85.mats)m.clippingPlanes=null;return r}}
{const oE=wpnEquip;wpnEquip=function(){const r=oE.apply(this,arguments);try{OPT96.vmw=null;WST.fov=null;OPT96.k=0;if(VMW)VMW.traverse(q=>{if(q.userData.optic96)q.visible=true})}catch(e){}return r}}
var OPT96={vmw:null,list:[],k:0,el:null,kind:''};
const RET96={
 reddot:k=>`<div class=o96f style="width:30vmin;height:30vmin;border-radius:50%"></div><div class=o96d></div>`,
 holo:k=>`<div class=o96f style="width:38vmin;height:27vmin;border-radius:2.2vmin"></div><div class=o96r style="width:7vmin;height:7vmin"></div><div class=o96d style="width:4px;height:4px"></div>`,
 acog:k=>`<div class=o96f style="width:72vmin;height:72vmin;border-radius:50%"></div><svg class=o96s viewBox="-50 -50 100 100"><path d="M-2.2 1.6 L0 -1.2 L2.2 1.6" fill="none" stroke="#ff3b2f" stroke-width=".7" stroke-linejoin="round"/><line x1="0" y1="2.6" x2="0" y2="14" stroke="#111" stroke-width=".35"/><line x1="-14" y1="0" x2="-5" y2="0" stroke="#111" stroke-width=".25"/><line x1="5" y1="0" x2="14" y2="0" stroke="#111" stroke-width=".25"/></svg>`,
 scope:k=>`<div class=o96f style="width:86vmin;height:86vmin;border-radius:50%"></div><svg class=o96s viewBox="-50 -50 100 100"><line x1="-43" y1="0" x2="-1.2" y2="0" stroke="#0c0c0c" stroke-width=".22"/><line x1="1.2" y1="0" x2="43" y2="0" stroke="#0c0c0c" stroke-width=".22"/><line x1="0" y1="-43" x2="0" y2="-1.2" stroke="#0c0c0c" stroke-width=".22"/><line x1="0" y1="1.2" x2="0" y2="43" stroke="#0c0c0c" stroke-width=".22"/>${[-24,-18,-12,-6,6,12,18,24].map(v=>`<circle cx="${v}" cy="0" r=".45" fill="#0c0c0c"/><circle cx="0" cy="${v}" r=".45" fill="#0c0c0c"/>`).join('')}<circle r=".55" fill="#ff3b2f"/></svg>`};
function optEl96(){if(OPT96.el)return OPT96.el;const st=document.createElement('style');st.textContent=`#opt96{position:fixed;inset:0;pointer-events:none;z-index:5;display:none}#opt96>*{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%)}.o96f{border:1.5px solid rgba(18,20,24,.78);box-shadow:0 0 0 .5px rgba(255,255,255,.18),inset 0 0 0 .5px rgba(255,255,255,.12)}.o96d{width:5px;height:5px;border-radius:50%;background:#ff3b2f;box-shadow:0 0 6px 2px rgba(255,60,40,.55)}.o96r{border-radius:50%;border:1.5px solid #ff3b2f;box-shadow:0 0 5px rgba(255,60,40,.45)}.o96s{width:100vmin;height:100vmin}#scopeov{background:none!important}#scopeov>*{display:none!important}`;document.head.appendChild(st);const e=document.createElement('div');e.id='opt96';document.body.appendChild(e);return OPT96.el=e}
function optTick96(){const e=optEl96(),w=WD&&WD();if(!w){e.style.display='none';return}const cfg=gCfg(w.id),sc=SCP85(w),opt=sc?'scope':(cfg.opt||'none');
 const fpAds=started&&!paused&&!menuOpen&&gunOn&&!cur&&pdead<=0&&ADS&&(FP||sc)&&!(typeof _rlPhase==='function'&&_rlPhase())&&!w.scope87;
 const k=fpAds&&opt!=='none'&&RET96[opt]?opt:'';
 if(VMW&&OPT96.vmw!==VMW){OPT96.vmw=VMW;OPT96.list=[];VMW.traverse(q=>{if(q.userData.optic96&&q.parent&&!q.parent.userData.optic96)OPT96.list.push(q)})}
 const hide=!!k&&k!=='scope';for(const q of OPT96.list)q.visible=!hide;
 if(k!==OPT96.kind){OPT96.kind=k;e.innerHTML=k?RET96[k]():''}e.style.display=k?'block':'none'}

/* ---------- 4. laser: the beam ends exactly where the dot is drawn (screen-space match between world and viewmodel cameras) ---------- */
const _lz96={p:new T.Vector3(),d:new T.Vector3()};
laserTick78=function(){const w=WD&&WD(),cfg=w?gCfg(w.id):null,on=!!(cfg&&cfg.laser&&gunOn&&!cur&&pdead<=0&&started&&!paused);
 if(!LZ78.dot){const c=document.createElement('canvas');c.width=c.height=64;const g=c.getContext('2d'),gr=g.createRadialGradient(32,32,0,32,32,32);gr.addColorStop(0,'rgba(255,255,255,1)');gr.addColorStop(.18,'rgba(255,60,50,1)');gr.addColorStop(.45,'rgba(255,0,0,.35)');gr.addColorStop(1,'rgba(255,0,0,0)');g.fillStyle=gr;g.fillRect(0,0,64,64);
  LZ78.dot=new T.Sprite(new T.SpriteMaterial({map:new T.CanvasTexture(c),blending:T.AdditiveBlending,depthWrite:false,depthTest:false,toneMapped:false}));LZ78.dot.renderOrder=9;LZ78.dot.frustumCulled=false}
 const host=actScene79();if(LZ78.dot.parent!==host)host.add(LZ78.dot);LZ78.dot.visible=on;
 for(const H of[TPW,VMW]){if(!H)continue;H.traverse(o=>{if(o.userData.laserEmitter)for(const c of o.children)c.visible=false})}
 if(!on)return;const t=aimPoint78(LZ78.tgt),dist=t.distanceTo(cam.position);LZ78.dot.position.copy(t).lerp(cam.position,Math.min(.5,.06/Math.max(.1,dist)));LZ78.dot.scale.setScalar(.05+dist*.012);
 const vis=FP?VMW:TPW;if(!vis)return;vis.updateMatrixWorld(true);
 let tgtV=null;if(FP&&_vmCam){cam.updateMatrixWorld();const ndc=_lz96.p.copy(t).project(cam);_vmCam.updateMatrixWorld();_vmCam.updateProjectionMatrix();const a=new T.Vector3(ndc.x,ndc.y,-1).unproject(_vmCam),b=new T.Vector3(ndc.x,ndc.y,1).unproject(_vmCam);const dir=b.sub(a).normalize();tgtV=_vmCam.position.clone().addScaledVector(dir,Math.min(dist,18))}
 vis.traverse(e=>{if(!e.userData.laserEmitter)return;let beam=e.userData.b78;if(!beam){const g=new T.CylinderGeometry(.0013,.0013,1,8,1,true).translate(0,.5,0).rotateX(Math.PI/2);beam=new T.Mesh(g,new T.MeshBasicMaterial({color:0xff2a20,transparent:true,opacity:.75,blending:T.AdditiveBlending,depthWrite:false,toneMapped:false}));beam.frustumCulled=false;beam.userData.isBeam78=1;e.add(beam);e.userData.b78=beam}
  beam.visible=true;const tl=(FP&&tgtV)?tgtV.clone():_lz96.d.copy(t);e.worldToLocal(tl);const L=tl.length();if(L<1e-4){beam.visible=false;return}beam.quaternion.setFromUnitVectors(new T.Vector3(0,0,1),tl.clone().divideScalar(L));beam.scale.set(1,1,L)})};

/* ---------- 5. impacts that match the surface: dirt, sand, snow, concrete/brick dust, metal sparks, wood splinters, glass, water ---------- */
var PX96={n:900,i:0,pts:null,g:null,P:null,V:null,C:null,S:null,A:null,L:null,L0:null,S1:null,G:null,D:null,ln:220,li:0,lines:null,lg:null,LP:null,LV:null,LL:null,LC:null,ctx:null};
function px96Init(){const n=PX96.n,g=new T.BufferGeometry();PX96.P=new Float32Array(n*3).fill(-9999);PX96.C=new Float32Array(n*3);PX96.S=new Float32Array(n);PX96.A=new Float32Array(n);g.setAttribute('position',new T.BufferAttribute(PX96.P,3));g.setAttribute('color',new T.BufferAttribute(PX96.C,3));g.setAttribute('size',new T.BufferAttribute(PX96.S,1));g.setAttribute('alpha',new T.BufferAttribute(PX96.A,1));
 PX96.V=new Float32Array(n*3);PX96.L=new Float32Array(n);PX96.L0=new Float32Array(n);PX96.S0=new Float32Array(n);PX96.S1=new Float32Array(n);PX96.G=new Float32Array(n);PX96.D=new Float32Array(n);PX96.K=new Uint8Array(n);
 const m=new T.ShaderMaterial({uniforms:{uScale:{value:600},uLight:{value:1}},vertexShader:`attribute float size;attribute float alpha;varying vec3 vC;varying float vA;uniform float uScale;void main(){vC=color;vA=alpha;vec4 mv=modelViewMatrix*vec4(position,1.);gl_PointSize=clamp(size*uScale/max(.1,-mv.z),1.,180.);gl_Position=projectionMatrix*mv;}`,
  fragmentShader:`varying vec3 vC;varying float vA;uniform float uLight;void main(){vec2 q=gl_PointCoord*2.-1.;float r=dot(q,q);if(r>1.)discard;float a=vA*smoothstep(1.,.35,r);gl_FragColor=vec4(vC*uLight,a);}`,vertexColors:true,transparent:true,depthWrite:false});
 PX96.pts=new T.Points(g,m);PX96.pts.frustumCulled=false;PX96.pts.renderOrder=3;PX96.pts.userData.keep=1;PX96.g=g;
 const N=PX96.ln,lg=new T.BufferGeometry();PX96.LP=new Float32Array(N*6).fill(-9999);PX96.LC=new Float32Array(N*6);lg.setAttribute('position',new T.BufferAttribute(PX96.LP,3));lg.setAttribute('color',new T.BufferAttribute(PX96.LC,3));PX96.LV=new Float32Array(N*3);PX96.LL=new Float32Array(N);PX96.LX=new Float32Array(N*3);
 PX96.lines=new T.LineSegments(lg,new T.LineBasicMaterial({vertexColors:true,transparent:true,blending:T.AdditiveBlending,depthWrite:false,toneMapped:false}));PX96.lines.frustumCulled=false;PX96.lines.userData.keep=1;PX96.lg=lg;fx96Parent()}
function px96(x,y,z,vx,vy,vz,col,s0,s1,life,grav,drag,alpha){const i=PX96.i++%PX96.n,P=PX96.P;P[i*3]=x;P[i*3+1]=y;P[i*3+2]=z;PX96.V[i*3]=vx;PX96.V[i*3+1]=vy;PX96.V[i*3+2]=vz;PX96.C[i*3]=col[0];PX96.C[i*3+1]=col[1];PX96.C[i*3+2]=col[2];PX96.S0[i]=s0;PX96.S1[i]=s1;PX96.S[i]=s0;PX96.L[i]=life;PX96.L0[i]=life;PX96.G[i]=grav;PX96.D[i]=drag;PX96.A[i]=alpha;PX96.K[i]=alpha*255}
function spark96(x,y,z,vx,vy,vz,life,col){const i=PX96.li++%PX96.ln;PX96.LX[i*3]=x;PX96.LX[i*3+1]=y;PX96.LX[i*3+2]=z;PX96.LV[i*3]=vx;PX96.LV[i*3+1]=vy;PX96.LV[i*3+2]=vz;PX96.LL[i]=life;for(let k=0;k<2;k++){PX96.LC[i*6+k*3]=col[0]*(k?1:.25);PX96.LC[i*6+k*3+1]=col[1]*(k?1:.2);PX96.LC[i*6+k*3+2]=col[2]*(k?1:.1)}}
const R96=Math.random,J96=(a)=>(R96()-.5)*2*a;
const SURF96={
 dirt:{deb:[.33,.25,.17],dust:[.52,.43,.32],n:9,dn:3},
 grass:{deb:[.26,.3,.15],dust:[.48,.44,.33],n:8,dn:2},
 sand:{deb:[.78,.68,.5],dust:[.84,.76,.6],n:10,dn:3},
 snow:{deb:[.92,.94,.97],dust:[.95,.96,.98],n:10,dn:3},
 concrete:{deb:[.62,.6,.56],dust:[.74,.72,.68],n:7,dn:3},
 asphalt:{deb:[.22,.23,.25],dust:[.5,.5,.5],n:6,dn:2},
 brick:{deb:[.56,.34,.27],dust:[.66,.5,.42],n:7,dn:3},
 wood:{deb:[.5,.36,.22],dust:[.62,.52,.4],n:7,dn:2,splinter:1},
 metal:{deb:[.35,.36,.38],dust:[.55,.55,.56],n:2,dn:1,spark:1},
 glass:{deb:[.8,.9,.95],dust:[.85,.9,.95],n:10,dn:0,glass:1},
 water:{deb:[.85,.9,.95],dust:[.9,.94,.97],n:14,dn:1,water:1}};
function groundSurf96(x,y,z){try{if(waterDepth(x,z)>.05&&y<WL+.4)return'water'}catch(e){}
 if(typeof GEN!=='undefined'&&GEN.on){const b=GEN.biome;return b===3||b===4?'snow':b===5?'sand':b===1||b===2||b===8?'grass':'dirt'}
 if(typeof BIO!=='undefined'&&BIO.on){try{const w=bioWeights(x,z,[0,0,0,0,0]);let bi=0;for(let i=1;i<w.length;i++)if(w[i]>w[bi])bi=i;const k=BIOM[bi].k;return k==='snow'?'snow':k==='desert'?'sand':k==='valley'?'grass':'dirt'}catch(e){return'dirt'}}
 try{const d=roadD(x,z);if(d<5.5)return'asphalt';if(d<9)return'concrete'}catch(e){}return'grass'}
function matSurf96(m){if(!m)return'concrete';if(Array.isArray(m))m=m[0];const src=((m.map&&m.map.image&&(m.map.image.currentSrc||m.map.image.src))||'')+' '+(m.name||'');if(/wood|plank|bark|log/i.test(src))return'wood';if(/brick|wroof|terra/i.test(src))return'brick';if(/glass|window/i.test(src)||(m.transparent&&m.opacity<.7)||m.transmission>.3)return'glass';if(/snow|ice/i.test(src))return'snow';if(/sand/i.test(src))return'sand';if(/asph/i.test(src))return'asphalt';if((m.metalness||0)>=.45||/metal|corr|steel|iron/i.test(src))return'metal';return'concrete'}
function impactFx96(x,y,z,kind,nx,ny,nz){if(!PX96.pts)px96Init();const S=SURF96[kind]||SURF96.concrete;if(nx===undefined){nx=0;ny=1;nz=0}
 const up=(v)=>v;for(let k=0;k<S.n;k++){const sp=S.water?1.2:S.glass?2.6:2;const vx=nx*sp*(.6+R96())+J96(1.6),vy=ny*sp*(.6+R96())+R96()*(S.water?3.2:1.8),vz=nz*sp*(.6+R96())+J96(1.6),c=S.deb,t=.85+R96()*.3;
  px96(x+nx*.03,y+ny*.03,z+nz*.03,vx,vy,vz,[c[0]*t,c[1]*t,c[2]*t],S.splinter?.03:S.glass?.022:.026+R96()*.02,S.water?.05:.02,S.water?.55:.45+R96()*.4,S.water?7:9.8,S.water?1.5:.8,S.glass?.95:1)}
 for(let k=0;k<S.dn;k++){const c=S.dust;px96(x+nx*.06,y+ny*.06,z+nz*.06,nx*.6+J96(.35),ny*.6+.35+R96()*.3,nz*.6+J96(.35),c,.12+R96()*.08,.55+R96()*.4,S.water?.5:.9+R96()*.6,-.15,2.2,S.water?.5:.42)}
 if(S.spark){for(let k=0;k<9;k++){const v=4+R96()*7;spark96(x,y,z,nx*v*.6+J96(v*.6),ny*v*.6+J96(v*.5)+1,nz*v*.6+J96(v*.6),.12+R96()*.2,[1,.72+R96()*.2,.32])}px96(x,y,z,0,0,0,[1,.8,.5],.16,.02,.06,0,0,1)}}
/* who/what was hit -> surface kind, consumed by the next impact() */
{const oD=bulletDecal;bulletDecal=function(h,hp){try{const n=h.face?h.face.normal.clone().transformDirection(h.object.matrixWorld):null;PX96.ctx={k:matSurf96(h.object&&h.object.material),n}}catch(e){}return oD.apply(this,arguments)}}
{const oC=hitCar;hitCar=function(){PX96.ctx={k:'metal'};return oC.apply(this,arguments)}}
{const oP=damageProp;damageProp=function(p){PX96.ctx={k:p&&p.big?'metal':'metal'};return oP.apply(this,arguments)}}
impact=function(x,y,z){let c=PX96.ctx;PX96.ctx=null;let k,n=null;if(c){k=c.k;n=c.n}else{let g=-1e9;try{g=Gw(x,z)}catch(e){}k=(y<=g+.25)?groundSurf96(x,y,z):'concrete'}
 if(n)impactFx96(x,y,z,k,n.x,n.y,n.z);else if(k==='concrete'||k==='brick'||k==='metal'||k==='wood'||k==='glass'){const d=cam.position.clone().sub(_lk96.set(x,y,z)).normalize();impactFx96(x,y,z,k,d.x,d.y,d.z)}else impactFx96(x,y,z,k)};
impStep=function(dt){if(!PX96.pts)return;const n=PX96.n,P=PX96.P,V=PX96.V;let any=false;for(let i=0;i<n;i++){if(PX96.L[i]<=0)continue;any=true;PX96.L[i]-=dt;if(PX96.L[i]<=0){P[i*3+1]=-9999;PX96.A[i]=0;continue}const t=1-PX96.L[i]/PX96.L0[i],dr=Math.exp(-PX96.D[i]*dt);V[i*3]*=dr;V[i*3+1]=V[i*3+1]*dr-PX96.G[i]*dt;V[i*3+2]*=dr;P[i*3]+=V[i*3]*dt;P[i*3+1]+=V[i*3+1]*dt;P[i*3+2]+=V[i*3+2]*dt;
  if(PX96.G[i]>0){let g=-1e9;if((i&3)===0){try{g=Gw(P[i*3],P[i*3+2])}catch(e){}if(P[i*3+1]<g){P[i*3+1]=g;V[i*3+1]=Math.abs(V[i*3+1])*.25;V[i*3]*=.5;V[i*3+2]*=.5}}}
  PX96.S[i]=PX96.S0[i]+(PX96.S1[i]-PX96.S0[i])*t;PX96.A[i]=(PX96.K[i]/255)*(1-t*t)}
 if(any){PX96.g.attributes.position.needsUpdate=PX96.g.attributes.size.needsUpdate=PX96.g.attributes.alpha.needsUpdate=true}
 const LP=PX96.LP,LX=PX96.LX,LV=PX96.LV;let la=false;for(let i=0;i<PX96.ln;i++){if(PX96.LL[i]<=0)continue;la=true;PX96.LL[i]-=dt;if(PX96.LL[i]<=0){LP[i*6+1]=LP[i*6+4]=-9999;continue}LV[i*3+1]-=9.8*dt;LX[i*3]+=LV[i*3]*dt;LX[i*3+1]+=LV[i*3+1]*dt;LX[i*3+2]+=LV[i*3+2]*dt;const k=.035;LP[i*6]=LX[i*3]-LV[i*3]*k;LP[i*6+1]=LX[i*3+1]-LV[i*3+1]*k;LP[i*6+2]=LX[i*3+2]-LV[i*3+2]*k;LP[i*6+3]=LX[i*3];LP[i*6+4]=LX[i*3+1];LP[i*6+5]=LX[i*3+2]}
 if(la)PX96.lg.attributes.position.needsUpdate=true;
 try{PX96.pts.material.uniforms.uScale.value=R.domElement.height*cam.projectionMatrix.elements[5]*.5;PX96.pts.material.uniforms.uLight.value=1-.65*(typeof night!=='undefined'?night:0)}catch(e){}};
/* the old square debris points are retired */
if(typeof IMP!=='undefined'){IMP.g=null}

/* ---------- 6. the one per-frame hook (runs in every world: main loop and the frontier loop both call preRender) ---------- */
{const oP=preRender;preRender=function(){try{lookApply96()}catch(e){}const n=performance.now(),dt=Math.min(.05,Math.max(0,(n-(TK96.fr||n))/1000));TK96.fr=n;try{worldTick96(dt)}catch(e){}oP.apply(this,arguments);try{optTick96()}catch(e){}}}

/* ---------- 7. settings: aiming ---------- */
{const oH=screenHtml;screenHtml=function(){let h=oH.apply(this,arguments);try{if(menuScr==='settings'&&setTab==='gameplay'){const add=sld('ADS sensitivity','adsSens',.3,1.5,.05,v=>Math.round(v*100)+'%')+sld('Scope sensitivity','scopeSens',.3,1.5,.05,v=>Math.round(v*100)+'%')+sld('Aim smoothing','aimSmooth',0,1,.05,v=>v<.02?'Off':Math.round(v*100)+'%')+tgl('Aim assist (slows over targets)','aimAssist');const i=h.indexOf('data-set=invY');const j=i>0?h.indexOf('</div></div>',i):-1;h=j>0?h.slice(0,j+12)+add+h.slice(j+12):h+add}}catch(e){}return h}}
{const oS=setVal;if(typeof setVal==='function'){setVal=function(k,v){if(k==='aimAssist'){SET.aimAssist=v===true||v==='true'||v==='on';saveSet();return}const r=oS.apply(this,arguments);if(k==='adsSens'||k==='scopeSens'||k==='aimSmooth'){const e=document.getElementById('v_'+k);if(e)e.textContent=k==='aimSmooth'?(+v<.02?'Off':Math.round(v*100)+'%'):Math.round(v*100)+'%'}return r}}}
