
/* ===== v91: human v2 — 7.75-head anatomical proportions, high-detail skin body, sculpted head+neck (thirds/fifths), modular clothing ===== */
var H90={suit:null,strand:null,K:{},fab:{},skinT:null};
const H90_SKIN=[0xf8e4d8,0xf3d6c3,0xedc8ae,0xe6ba9b,0xdeac8a,0xd59e7a,0xca8f6b,0xbd805e,0xae7252,0x9e6447,0x8d573d,0x7c4b34,0x6b402c,0x5b3625,0x4c2d1f,0x3e251a,0x332016,0x2a1a12];
const H90_HAIRC=[0x0e0b09,0x22180f,0x3b2819,0x5b3c24,0x7d5532,0xa6743e,0xc79e62,0xe0c58e,0xece0c4,0xa8461f,0x7d2a18,0xcfcfd2,0x8e8e94,0x55307f,0x2e58b8,0x2a9a80,0xc8467f,0xe8e8f2];
const H90_EYEC=[0x3a2416,0x5a3a20,0x7a5a2c,0x8a7a38,0x5a7a38,0x3a7a5a,0x3a6a8a,0x4a8ac2,0x7aaad2,0x8a9aaa,0x5a5a68,0xb04a1e,0xd8a01e,0x8a4ad2,0xe0405e,0xeef0f4];
const H90_MARKC=[0xd23a2a,0xeeeeee,0x111114,0x2a8ad2,0xe2b040,0x40d2a0,0x9040d2,0xf27030,0xff4082,0x30e8ff];
const H90_LIPC=[null,0xb85e5e,0x9e4242,0x7a3030,0xc47c6c,0x8a5a7a,0x5a3a4a,0xd24a5c,0x3a2a30,0xa2a2b2];
const H90_HAIRS=[['bald','Bald'],['buzz','Buzz'],['crew','Crew cut'],['short','Short'],['quiff','Quiff'],['undercut','Undercut'],['mohawk','Mohawk'],['bob','Bob'],['long','Long'],['ponytail','Ponytail'],['bun','Bun'],['braids','Braids'],['afro','Afro']];
const H90_FHAIR=[['none','None'],['stubble','Stubble'],['mustache','Mustache'],['goatee','Goatee'],['beard','Beard'],['full','Full beard'],['chinstrap','Chinstrap']];
const H90_BROWS=[['soft','Soft'],['straight','Straight'],['arched','Arched'],['angled','Angled'],['thick','Bold'],['thin','Thin'],['none','None']];
const H90_MARKS=[['none','None'],['freckles','Freckles'],['dots','Dots'],['tribal','Tribal'],['circuit','Circuit'],['scar','Scar'],['warpaint','Warpaint'],['tears','Tear lines']];
const H90_SLIDE={mood:'Expression',fw:'Face width',fl:'Face length',jaw:'Jaw',chin:'Chin',cheek:'Cheekbones',brow:'Brow ridge',nose:'Nose size',noseW:'Nose width',noseL:'Nose length',lips:'Lips',mouthW:'Mouth width',ears:'Ears',eyeS:'Eye size',eyeD:'Eye spacing',eyeT:'Eye tilt',browT:'Brow thickness',height:'Height',weight:'Build',liner:'Lash line'};
const H90_FACES=[{n:'Classic',v:{}},{n:'Angular',v:{fw:-.2,fl:.3,jaw:.6,chin:.5,cheek:.6,nose:.2,noseW:-.3,lips:-.3,brow:.4}},{n:'Round',v:{fw:.5,fl:-.3,jaw:-.4,chin:-.3,cheek:.2,nose:-.2,noseW:.3,lips:.3}},{n:'Long',v:{fw:-.4,fl:.7,jaw:0,chin:.3,nose:.4,noseL:.5,lips:-.2}},{n:'Broad',v:{fw:.6,fl:.1,jaw:.8,chin:.2,cheek:.4,nose:.3,noseW:.6,brow:.6}},{n:'Delicate',v:{fw:-.3,fl:-.1,jaw:-.6,chin:-.4,cheek:.5,nose:-.5,noseW:-.4,lips:.5,eyeS:.4}},{n:'Weathered',v:{fw:.1,fl:.2,jaw:.4,chin:.6,cheek:.7,nose:.6,noseL:.3,brow:.8,eyeS:-.3}},{n:'Youthful',v:{fw:.1,fl:-.4,jaw:-.3,chin:-.2,cheek:-.2,nose:-.4,lips:.2,eyeS:.5,brow:-.4}}];
function h90Def(sex){return{sex:sex||'male',height:0,weight:0,skin:0xd59e7a,face:0,fw:0,fl:0,jaw:0,chin:0,cheek:0,brow:0,nose:0,noseW:0,noseL:0,lips:0,mouthW:0,ears:0,eyeS:0,eyeD:0,eyeT:0,eyeC:0x5a3a20,glow:0,browS:'soft',browT:0,browC:null,hair:sex==='female'?'bob':'short',hairC:0x3b2819,fhair:'none',fhairC:null,mood:0,mouth:'natural',mark:'none',markC:0xd23a2a,lipC:null,liner:.35}}
function h90Rand(sex){const r=a=>a[Math.floor(Math.random()*a.length)],g=()=>Math.max(-1,Math.min(1,(Math.random()+Math.random()+Math.random()-1.5)*.9)),a=h90Def(sex);a.mood=Math.random()*1.6-.6;{const mk=Object.keys(H90_MOUTH);a.mouth=Math.random()<.35?'natural':mk[Math.floor(Math.random()*mk.length)]}a.skin=r(H90_SKIN);a.hairC=r(Math.random()<.9?H90_HAIRC.slice(0,13):H90_HAIRC);
 for(const k of['fw','fl','jaw','chin','cheek','brow','nose','noseW','noseL','lips','mouthW','ears','eyeS','eyeD','eyeT','browT','height','weight'])a[k]=g()*.8;
 a.eyeC=r(H90_EYEC.slice(0,11));a.browS=r(['soft','soft','straight','arched','angled','thick','thin']);a.hair=sex==='female'?r(['bob','long','long','ponytail','bun','braids','afro','short','undercut']):r(['short','short','crew','buzz','quiff','undercut','bald','afro','short','crew']);
 a.fhair=sex==='male'?r(['none','none','none','stubble','stubble','mustache','goatee','beard','full','chinstrap']):'none';a.mark=Math.random()<.08?r(['freckles','freckles','scar']):'none';a.lipC=sex==='female'&&Math.random()<.45?r(H90_LIPC.slice(1,8)):null;a.liner=sex==='female'?.5+Math.random()*.4:.25+Math.random()*.2;return a}
const _s90=(a,b,x)=>{const t=Math.max(0,Math.min(1,(x-a)/(b-a)));return t*t*(3-2*t)},_m90=(a,b,t)=>a+(b-a)*t,_g90=x=>Math.exp(-x*x);
function _tab90(T,x){if(x<=T[0][0])return T[0].slice(1);for(let i=1;i<T.length;i++)if(x<=T[i][0]){const a=T[i-1],b=T[i],t=(x-a[0])/(b[0]-a[0]),s=t*t*(3-2*t);return a.slice(1).map((v,k)=>v+(b[k+1]-v)*s)}return T[T.length-1].slice(1)}
/* Catmull-Rom table interpolation (smooth profiles, no terracing) */
function _cr90(T,x){const n=T.length;if(x<=T[0][0])return T[0].slice(1);if(x>=T[n-1][0])return T[n-1].slice(1);let i=0;while(x>T[i+1][0])i++;const p0=T[Math.max(0,i-1)],p1=T[i],p2=T[i+1],p3=T[Math.min(n-1,i+2)],h=p2[0]-p1[0],t=(x-p1[0])/h,t2=t*t,t3=t2*t,out=[];
 for(let k=1;k<p1.length;k++){const m1=(p2[k]-p0[k])/((p2[0]-p0[0])||1)*h,m2=(p3[k]-p1[k])/((p3[0]-p1[0])||1)*h;out.push((2*t3-3*t2+1)*p1[k]+(t3-2*t2+t)*m1+(-2*t3+3*t2)*p2[k]+(t3-t2)*m2)}return out}
function _h90hash(x,y){const s=Math.sin(x*127.1+y*311.7)*43758.5453;return s-Math.floor(s)}

/* ---------- skeleton: 7.75 heads (male 1.78 m), 7.5 heads (female 1.66 m); joint names match the animator, armor and IK ---------- */
function skel90(sex){const f=sex==='female',K=f?.933:1,sw=f?.955:1,hw=f?1.1:1,V=(x,y,z)=>new T.Vector3(x,y,z),W={};
 W.Hips=V(0,.945,0);W.Spine=V(0,1.03,-.01);W.Spine1=V(0,1.14,-.015);W.Spine2=V(0,1.27,-.02);W.Neck=V(0,1.478,-.034);W.Head=V(0,1.607,-.022);
 for(const [S,s] of [['Left',1],['Right',-1]]){const dU=V(s*.643,-.766,-.03).normalize(),dF=V(s*.58,-.81,.07).normalize();
  W[S+'Shoulder']=V(s*.028,1.432,-.014);W[S+'Arm']=V(s*.19*sw,1.445,-.028);W[S+'ForeArm']=W[S+'Arm'].clone().addScaledVector(dU,.33);W[S+'Hand']=W[S+'ForeArm'].clone().addScaledVector(dF,.262);
  W[S+'UpLeg']=V(s*.091*hw,.93,0);W[S+'Leg']=V(s*.097*hw,.505,.012);W[S+'Foot']=V(s*.101*hw,.08,-.03);W[S+'ToeBase']=V(s*.108*hw,.018,.118);
  const H=W[S+'Hand'],d=dF,w=V(0,0,1).addScaledVector(d,-d.z).normalize(),n=new T.Vector3().crossVectors(d,w).multiplyScalar(s).normalize();
  for(const [F,o,L] of [['Index',.024,1],['Middle',.0075,1.07],['Ring',-.0095,1],['Pinky',-.025,.8]]){const df=d.clone().addScaledVector(n,.16).normalize();let p=H.clone().addScaledVector(d,.098).addScaledVector(w,o);W[S+'Hand'+F+'1']=p.clone();const ls=[.046,.028,.022];for(let k=2;k<=3;k++){p=p.clone().addScaledVector(df,ls[k-2]*L);W[S+'Hand'+F+k]=p}}
  const td=d.clone().multiplyScalar(.5).addScaledVector(w,.7).addScaledVector(n,.35).normalize();let t=H.clone().addScaledVector(d,.024).addScaledVector(w,.024).addScaledVector(n,.013);W[S+'HandThumb1']=t.clone();t=t.clone().addScaledVector(td,.04);W[S+'HandThumb2']=t.clone();t=t.clone().addScaledVector(td,.032);W[S+'HandThumb3']=t}
 const par={Hips:null,Spine:'Hips',Spine1:'Spine',Spine2:'Spine1',Neck:'Spine2',Head:'Neck'};
 for(const S of['Left','Right']){par[S+'Shoulder']='Spine2';par[S+'Arm']=S+'Shoulder';par[S+'ForeArm']=S+'Arm';par[S+'Hand']=S+'ForeArm';for(const F of['Thumb','Index','Middle','Ring','Pinky']){par[S+'Hand'+F+'1']=S+'Hand';par[S+'Hand'+F+'2']=S+'Hand'+F+'1';par[S+'Hand'+F+'3']=S+'Hand'+F+'2'}par[S+'UpLeg']='Hips';par[S+'Leg']=S+'UpLeg';par[S+'Foot']=S+'Leg';par[S+'ToeBase']=S+'Foot'}
 const names=Object.keys(par),Wm={};for(const k in W)Wm[k]=W[k].clone();for(const k in W)W[k].multiplyScalar(K);
 const hcm=Wm.Head.clone().add(V(0,.058,.03));const S=names.map(n=>({n,p:par[n]?names.indexOf(par[n]):-1,t:(par[n]?W[n].clone().sub(W[par[n]]):W[n].clone()).toArray(),q:[0,0,0,1]}));return{S,W,Wm,K,names,hcm,f}}
H90.K.male=skel90('male');H90.K.female=skel90('female');

/* ---------- mesh builder with skin weights + vertex colours ---------- */
function MB90(){this.p=[];this.uv=[];this.si=[];this.sw=[];this.c=[];this.ix=[];this.pairs=[]}
MB90.prototype.v=function(p,u,v,sk,col){this.p.push(p.x,p.y,p.z);this.uv.push(u,v);const s=sk.slice().sort((a,b)=>b[1]-a[1]).slice(0,4);let t=0;for(const q of s)t+=q[1];for(let i=0;i<4;i++){const q=s[i];this.si.push(q?q[0]:0);this.sw.push(q&&t>0?q[1]/t:(i?0:1))}if(col)this.c.push(col[0],col[1],col[2]);else this.c.push(1,1,1);return this.p.length/3-1};
/* rows: [{c,X,Y,ra,rb,e,v,sk,pt?}] — ring point = c + X cos a ra + Z sin a rb, Z = X×Y (outward winding) */
MB90.prototype.loft=function(rows,seg,capA,capB,col){const base=this.p.length/3,W=seg+1,sp=(t,e)=>Math.sign(t)*Math.pow(Math.abs(t),2/(e||2));
 rows.forEach((r,ri)=>{const Z=r.pt?null:new T.Vector3().crossVectors(r.X,r.Y).normalize();for(let j=0;j<=seg;j++){const a=j/seg*Math.PI*2,ca=Math.cos(a),sa=Math.sin(a);const p=r.pt?r.pt(a):r.c.clone().addScaledVector(r.X,sp(ca,r.e)*r.ra).addScaledVector(Z,sp(sa,r.e)*r.rb);this.v(p,r.u0!==undefined?r.u0+(j/seg):j/seg,r.v,typeof r.sk==='function'?r.sk(p,a):r.sk,col?col(p,a,r,ri):null)}});
 for(let i=0;i<rows.length-1;i++)for(let j=0;j<seg;j++){const a=base+i*W+j,b=a+1,c=a+W,d=c+1;this.ix.push(a,c,b,b,c,d)}
 for(let i=0;i<rows.length;i++)this.pairs.push([base+i*W,base+i*W+seg]);
 const cap=(ri,end)=>{const r=rows[ri];let c=new T.Vector3();for(let j=0;j<seg;j++){const k=(base+ri*W+j)*3;c.x+=this.p[k];c.y+=this.p[k+1];c.z+=this.p[k+2]}c.multiplyScalar(1/seg);const k0=(base+ri*W)*3;const ci=this.v(c,.5,r.v,typeof r.sk==='function'?r.sk(c,0):r.sk,[this.c[k0],this.c[k0+1],this.c[k0+2]]);for(let j=0;j<seg;j++){const a=base+ri*W+j,b=a+1;if(end)this.ix.push(ci,b,a);else this.ix.push(ci,a,b)}};
 if(capA)cap(0,false);if(capB)cap(rows.length-1,true)};
MB90.prototype.addGeo=function(g,sk,col,uvFix){const P=g.attributes.position,base=this.p.length/3,U=g.attributes.uv;for(let i=0;i<P.count;i++){this.v(new T.Vector3(P.getX(i),P.getY(i),P.getZ(i)),uvFix?uvFix[0]:(U?U.getX(i):0),uvFix?uvFix[1]:(U?U.getY(i):0),sk,col)}const I=g.index?g.index.array:null;if(I)for(let k=0;k<I.length;k++)this.ix.push(base+I[k]);else for(let k=0;k<P.count;k++)this.ix.push(base+k)};
MB90.prototype.geo=function(scale,keepColor){const g=new T.BufferGeometry(),P=new Float32Array(this.p);if(scale&&scale!==1)for(let i=0;i<P.length;i++)P[i]*=scale;g.setAttribute('position',new T.BufferAttribute(P,3));g.setAttribute('uv',new T.Float32BufferAttribute(this.uv,2));g.setAttribute('skinIndex',new T.Uint16BufferAttribute(this.si,4));g.setAttribute('skinWeight',new T.Float32BufferAttribute(this.sw,4));if(keepColor)g.setAttribute('color',new T.Float32BufferAttribute(this.c,3));
 g.setIndex(this.p.length/3>65535?new T.Uint32BufferAttribute(this.ix,1):new T.Uint16BufferAttribute(this.ix,1));g.computeVertexNormals();
 const N=g.attributes.normal;for(const [a,b] of this.pairs){const x=N.getX(a)+N.getX(b),y=N.getY(a)+N.getY(b),z=N.getZ(a)+N.getZ(b),l=Math.hypot(x,y,z)||1;N.setXYZ(a,x/l,y/l,z/l);N.setXYZ(b,x/l,y/l,z/l)}g.computeBoundingSphere();return g};
function chainSk90(J,bones,bw,preB,postB){const L=[0];for(let i=1;i<J.length;i++)L.push(L[i-1]+J[i].distanceTo(J[i-1]));return s=>{let k=0;while(k<bones.length-1&&s>L[k+1])k++;const out=[[bones[k],1]];
  if(k>0&&s-L[k]<bw){const c=_s90(-bw,bw,s-L[k]);out[0][1]=c;out.push([bones[k-1],1-c])}else if(k<bones.length-1&&L[k+1]-s<bw){const c=_s90(-bw,bw,s-L[k+1]);out[0][1]=1-c;out.push([bones[k+1],c])}
  if(s<0&&preB!==undefined){const c=Math.min(.55,-s/.08*.55);out.forEach(q=>q[1]*=1-c);out.push([preB,c])}if(s>L[L.length-1]&&postB!==undefined){const c=Math.min(.6,(s-L[L.length-1])/.06*.6);out.forEach(q=>q[1]*=1-c);out.push([postB,c])}return out}}
/* polyline with start/end extensions; smooth direction through joints */
function chain90(J,e0,e1){const pts=[J[0].clone().addScaledVector(J[1].clone().sub(J[0]).normalize(),-e0),...J.map(v=>v.clone())];if(e1){const n=J.length;pts.push(J[n-1].clone().addScaledVector(J[n-1].clone().sub(J[n-2]).normalize(),e1))}
 const cum=[0];for(let i=1;i<pts.length;i++)cum.push(cum[i-1]+pts[i].distanceTo(pts[i-1]));const Lt=cum[cum.length-1];
 return{Lt,e0,at:u=>{const s=Math.max(0,Math.min(Lt,u*Lt));let k=0;while(k<pts.length-2&&s>cum[k+1])k++;const t=(s-cum[k])/((cum[k+1]-cum[k])||1),p=pts[k].clone().lerp(pts[k+1],t),dk=pts[k+1].clone().sub(pts[k]).normalize(),bw=.04;let d=dk;
  if(k>0&&s-cum[k]<bw){const dp=pts[k].clone().sub(pts[k-1]).normalize();d=dp.lerp(dk,.5+.5*(s-cum[k])/bw).normalize()}else if(k<pts.length-2&&cum[k+1]-s<bw){const dn=pts[k+2].clone().sub(pts[k+1]).normalize();d=dk.clone().lerp(dn,.5-.5*(cum[k+1]-s)/bw).normalize()}return{p,d,s:s-e0}}}}

/* ---------- body parts (shared by skin, clothes and the techsuit: same rings, so garments follow the body and its skinning) ---------- */
const H90_TORSO={male:[[.80,.13,.088,.1,-.005],[.86,.168,.097,.117,-.01],[.93,.172,.098,.12,-.01],[1.0,.158,.095,.105,-.008],[1.06,.145,.094,.095,-.006],[1.12,.147,.098,.092,-.005],[1.19,.155,.11,.095,-.003],[1.26,.165,.12,.1,-.002],[1.32,.172,.122,.105,-.004],[1.38,.18,.11,.105,-.008],[1.42,.19,.094,.1,-.012],[1.455,.186,.08,.088,-.016],[1.475,.16,.068,.078,-.021],[1.49,.112,.058,.068,-.026],[1.503,.07,.052,.06,-.03]],
 female:[[.80,.14,.088,.11,-.008],[.86,.18,.097,.128,-.012],[.92,.184,.096,.124,-.012],[.99,.145,.088,.1,-.01],[1.06,.128,.087,.088,-.008],[1.12,.132,.094,.088,-.006],[1.18,.145,.118,.09,-.004],[1.24,.152,.128,.092,-.002],[1.30,.156,.112,.096,-.004],[1.36,.166,.097,.097,-.008],[1.41,.174,.085,.092,-.012],[1.45,.168,.074,.082,-.016],[1.472,.142,.064,.072,-.021],[1.488,.1,.054,.062,-.026],[1.503,.064,.048,.056,-.03]]};
function torsoProf90(sex,y,wt,loose){const T0=H90_TORSO[sex];let p=_cr90(T0,y);if(loose>0){const a=_cr90(T0,y-.05),b=_cr90(T0,y+.05),c=_cr90(T0,y-.1),d=_cr90(T0,y+.1);const sm=p.map((v,k)=>(v+a[k]+b[k]+c[k]+d[k])/5);if(sex==='female'){const bust=_g90((y-1.22)/.07);sm[1]=Math.max(sm[1],_m90(sm[1],p[1],.85*bust))}p=p.map((v,k)=>_m90(v,Math.max(v,sm[k]),loose))}
 const waist=_s90(.95,1.05,y)*_s90(1.16,1.08,y),kw=1+.1*wt+.07*wt*waist,kd=1+.13*wt+.06*wt*waist;return[p[0]*kw,p[1]*kd,p[2]*kd,p[3]]}
function torso90(mb,C,o){const K=C.K,sex=C.sex,I=n=>K.names.indexOf(n),wt=C.wt,y0=o.y0,y1=o.y1,det=C.det,n=Math.max(6,Math.round((y1-y0)/.0075*det)),seg=Math.max(24,Math.round((o.seg||96)*det)),off=o.off||0;
 const sb=[[.93,I('Hips')],[1.04,I('Spine')],[1.15,I('Spine1')],[1.28,I('Spine2')]];
 const tsk=p=>{const y=p.y,ax=Math.abs(p.x),side=p.x>=0?'Left':'Right';let out;if(y<=sb[0][0])out=[[sb[0][1],1]];else if(y>=sb[3][0])out=[[sb[3][1],1]];else{let k=0;while(y>sb[k+1][0])k++;const t=(y-sb[k][0])/(sb[k+1][0]-sb[k][0]);out=[[sb[k][1],1-t],[sb[k+1][1],t]]}
  const nk=_s90(1.465,1.5,y)*.55;if(nk>0){out.forEach(q=>q[1]*=1-nk);out.push([I('Neck'),nk])}
  const sh=_s90(.1,.19,ax)*_s90(1.32,1.43,y);if(sh>0){out.forEach(q=>q[1]*=1-sh*.55);out.push([I(side+'Shoulder'),sh*.33],[I(side+'Arm'),sh*.22])}
  const lg=_s90(.9,.8,y)*_s90(.03,.12,ax)*.6;if(lg>0){out.forEach(q=>q[1]*=1-lg);out.push([I(side+'UpLeg'),lg])}return out};
 const row=(y,dOff)=>{const [w,df,db,zc]=torsoProf90(sex,y,wt,o.loose||0),fl=(o.flare||0)*_s90(y0+.1,y0,y),of=off+fl+(dOff||0);return{v:y*2.5,sk:tsk,pt:a=>{const ca=Math.cos(a),sa=Math.sin(a),sp=t=>Math.sign(t)*Math.pow(Math.abs(t),2/2.5);return new T.Vector3((w+of)*sp(ca),y,zc+(sa>0?df+of:db+of)*sp(sa))}}};
 const rows=[];if(o.rim)rows.push(row(y0+.004,-.004));for(let i=0;i<=n;i++)rows.push(row(y0+(y1-y0)*i/n));if(o.rimTop)rows.push(row(y1-.003,-.005));
 mb.loft(rows,seg,o.capBot?1:0,o.capTop?1:0,o.col)}
/* limbs: profile [[u, r, rbRatio, frontOffset]] along the chain (u 0..1 incl. extensions) */
const H90_ARM=[[0,.032,.95],[.04,.04,.95],[.085,.048,.95],[.14,.052,.95],[.25,.048,.95],[.38,.045,.93],[.5,.039,.92],[.57,.036,.9],[.63,.04,.9],[.72,.039,.86],[.85,.032,.8],[.96,.027,.72],[1,.026,.72]];
const H90_LEG=[[0,.045,.95],[.05,.058,.95],[.096,.07,.96],[.17,.08,.97,.004],[.25,.079,.97,.002],[.34,.072,.97],[.45,.06,.98],[.548,.052,.98],[.6,.054,.98,-.006],[.66,.057,.98,-.01],[.75,.05,.98,-.006],[.87,.039,1],[.97,.034,1],[1,.033,1]];
function limb90(mb,C,which,S,o){const K=C.K,W=K.Wm,I=n=>K.names.indexOf(n),det=C.det,fem=C.sex==='female',arm=which==='arm';
 const J=arm?[W[S+'Arm'],W[S+'ForeArm'],W[S+'Hand']]:[W[S+'UpLeg'],W[S+'Leg'],W[S+'Foot']],ch=chain90(J,arm?.035:.09,arm?.004:.004),sk=arm?chainSk90(J,[I(S+'Arm'),I(S+'ForeArm')],.045,I(S+'Shoulder'),I(S+'Hand')):chainSk90(J,[I(S+'UpLeg'),I(S+'Leg')],.055,I('Hips'));
 const prof=arm?H90_ARM:H90_LEG,k=(1+.1*C.wt)*(arm?(fem?.86:1):(fem?.98:1)),u0=o.u0||0,u1=o.u1===undefined?1:o.u1,n=Math.max(4,Math.round((u1-u0)*(arm?44:52)*det)),seg=Math.max(10,Math.round((arm?40:44)*det)),off=o.off||0,ref=new T.Vector3(0,0,1),rows=[];
 const row=(u,dOff)=>{const {p,d,s}=ch.at(u),[r,rr,ob]=_cr90(prof,u),X=ref.clone().addScaledVector(d,-ref.dot(d)).normalize(),c=p.clone();if(ob)c.addScaledVector(X,ob*k);const fl=(o.flare||0)*_s90(u1-.25,u1,u),R=r*k+off+fl+(o.loose||0)*.004+(dOff||0);return{c,X,Y:d,ra:R,rb:r*k*rr+off+fl+(dOff||0),e:2,v:s*2.5,sk:sk(s),_u:u}};
 if(o.rim&&u0>0)rows.push(row(u0+.004,-.004));for(let i=0;i<=n;i++)rows.push(row(u0+(u1-u0)*i/n));if(o.rim&&u1<1)rows.push(row(u1-.004,-.004));mb.loft(rows,seg,o.capA?1:0,o.capB?1:0,o.col)}
/* hand: palm + four fingers + thumb */
function hand90(mb,C,S,o){const K=C.K,W=K.Wm,I=n=>K.names.indexOf(n),det=C.det,fr=C.sex==='female'?.9:1,off=o.off||0,H=W[S+'Hand'],d=W[S+'HandMiddle1'].clone().sub(H).normalize(),w=new T.Vector3(0,0,1).addScaledVector(d,-d.z).normalize(),hb=I(S+'Hand');
 const pr=[[-.14,.027,.02],[-.05,.03,.019],[0,.034,.018],[.3,.043,.017],[.6,.046,.016],[.85,.045,.0145],[1.0,.042,.0125],[1.08,.034,.01]].map(([t,ra,rb])=>({c:H.clone().addScaledVector(d,t*.1),X:w,Y:d,ra:ra*fr+off,rb:rb*fr+off,e:2.8,v:t*.25,sk:[[hb,1]]}));mb.loft(pr,Math.max(14,Math.round(32*det)),1,1,o.col);
 for(const F of['Index','Middle','Ring','Pinky','Thumb']){const J=[1,2,3].map(k=>W[S+'Hand'+F+k]),dl=J[2].clone().sub(J[1]).normalize();J.push(J[2].clone().addScaledVector(dl,F==='Thumb'?.028:F==='Pinky'?.017:.021));const r=(F==='Thumb'?.0105:F==='Pinky'?.0078:.009)*fr+off,sk=chainSk90(J,[I(S+'Hand'+F+'1'),I(S+'Hand'+F+'2'),I(S+'Hand'+F+'3')],.006);
  const sp=[[0,-.3,r*1.08],[0,.5,r],[1,0,r*.96],[1,.5,r*.92],[2,0,r*.9],[2,.5,r*.86],[2,.85,r*.8],[2,.97,r*.62],[2,1.04,r*.25]],L=[0];for(let i=1;i<J.length;i++)L.push(L[i-1]+J[i].distanceTo(J[i-1]));
  const rows=sp.map(([k,t,rr])=>{const Y=J[k+1].clone().sub(J[k]).normalize(),c=J[k].clone().lerp(J[k+1],t),X=w.clone().addScaledVector(Y,-w.dot(Y)).normalize();return{c,X,Y,ra:rr,rb:rr*.9,e:2,v:(L[k]+t*(L[k+1]-L[k]))*2.5,sk:sk(L[k]+t*(L[k+1]-L[k]))}});mb.loft(rows,Math.max(8,Math.round(14*det)),1,1,o.col)}}
/* foot / shoe / boot: loft along the foot; shoe soles take the second colour */
function foot90(mb,C,S,o){const K=C.K,W=K.Wm,I=n=>K.names.indexOf(n),s=S==='Left'?1:-1,Fo=W[S+'Foot'],Tb=W[S+'ToeBase'],fb=I(S+'Foot'),tb=I(S+'ToeBase'),fw=new T.Vector3(s*.1,0,1).normalize(),X=new T.Vector3(1,0,0).addScaledVector(fw,-fw.x).normalize(),zT=Tb.clone().sub(Fo).dot(fw),fr=C.sex==='female'?.92:1,off=o.off||0,st=o.style||'skin';
 const FP=st==='skin'?[[-.072,.028,.05],[-.06,.035,.075],[-.03,.038,.085],[0,.039,.08],[.04,.042,.06],[.08,.046,.042],[.11,.047,.034],[.14,.044,.028],[.16,.036,.022],[.172,.022,.016],[.176,.008,.01]]:st==='boot'?[[-.085,.04,.08],[-.07,.046,.12],[-.04,.05,.15],[0,.051,.15],[.04,.052,.11],[.08,.055,.08],[.115,.055,.066],[.15,.05,.054],[.172,.04,.044],[.186,.025,.03],[.19,.01,.02]]:st==='dress'?[[-.08,.034,.05],[-.065,.04,.07],[-.035,.042,.078],[0,.043,.072],[.04,.046,.056],[.08,.049,.042],[.12,.048,.034],[.155,.04,.028],[.18,.026,.022],[.192,.01,.014]]:[[-.085,.038,.07],[-.07,.046,.095],[-.04,.049,.105],[0,.05,.1],[.04,.052,.078],[.08,.056,.058],[.115,.056,.05],[.15,.052,.044],[.175,.042,.036],[.188,.028,.026],[.192,.012,.016]];
 const rows=FP.map(([z,hw,ht])=>{const c=new T.Vector3(Fo.x,0,Fo.z).addScaledVector(fw,z);c.y=ht/2;const w2=_s90(zT-.035,zT+.01,z);return{c,X,Y:fw,ra:hw*fr*(1+.04*C.wt)+off*.6,rb:ht/2+off*.3,e:st==='skin'?3:3.4,v:z*2.5,sk:[[fb,1-w2],[tb,w2]]}});
 mb.loft(rows,Math.max(14,Math.round(30*C.det)),1,1,o.col)}
/* skirt: cone from the waist to the hem, weighted between hips and thighs */
function skirt90(mb,C,o){const K=C.K,I=n=>K.names.indexOf(n),y0=o.y0||1.0,y1=o.hem||.55,n=Math.max(8,Math.round(30*C.det)),seg=Math.max(24,Math.round(72*C.det)),rows=[];
 const [w0,df0,db0,zc0]=torsoProf90(C.sex,y0,C.wt,.5),hemW=Math.max(w0+.02,.2+(o.flare||0)),hemD=Math.max(df0,.15+(o.flare||0)*.6);
 for(let i=0;i<=n;i++){const t=i/n,y=_m90(y0,y1,t),[w,df,db,zc]=torsoProf90(C.sex,Math.max(y,.86),C.wt,.5),ww=Math.max(w+(o.off||.006),_m90(w0,hemW,Math.pow(t,1.1))),ff=Math.max(df+(o.off||.006),_m90(df0,hemD,t)),bb=Math.max(db+(o.off||.006),_m90(db0,hemD+.02,t));
  rows.push({v:y*2.5,sk:p=>{const side=p.x>=0?'Left':'Right',lw=_s90(.0,.16,Math.abs(p.x))*.75*t;return[[I('Hips'),1-lw],[I(side+'UpLeg'),lw]]},pt:a=>{const ca=Math.cos(a),sa=Math.sin(a),sp=q=>Math.sign(q)*Math.pow(Math.abs(q),2/2.3);return new T.Vector3(ww*sp(ca),y,zc+(sa>0?ff:bb)*sp(sa))}})}
 mb.loft(rows,seg,0,0,o.col)}

/* ---------- head + neck: one loft of horizontal rings (eye line = 0); facial landmarks follow the classical thirds and fifths ---------- */
/* Y, front half-width, back half-width, front depth, back depth, centre z */
const H90_HEAD=[[.1155,0,0,0,0,-.008],[.113,.022,.022,.03,.03,-.008],[.108,.04,.04,.052,.052,-.008],[.1,.053,.053,.068,.068,-.008],[.088,.063,.063,.082,.083,-.008],[.07,.0715,.071,.091,.094,-.008],[.05,.0745,.0755,.095,.102,-.008],[.03,.074,.0775,.097,.106,-.008],[.012,.0735,.0775,.095,.107,-.008],
 [-.005,.0725,.0765,.093,.105,-.008],[-.02,.0705,.074,.093,.1,-.007],[-.035,.0695,.071,.094,.092,-.005],[-.05,.0665,.067,.094,.083,-.003],[-.065,.0635,.062,.094,.075,-.001],[-.08,.0575,.0565,.093,.069,0],[-.092,.0505,.0525,.092,.066,0],[-.103,.0398,.0515,.088,.063,-.001],[-.111,.03,.0515,.079,.061,-.003],[-.117,.036,.0505,.07,.06,-.006],
 [-.124,.045,.0505,.059,.06,-.011],[-.135,.05,.051,.054,.061,-.015],[-.15,.052,.052,.056,.06,-.017],[-.17,.054,.054,.058,.062,-.019],[-.19,.06,.061,.059,.067,-.022],[-.205,.064,.065,.06,.071,-.025]].reverse();
function headP90(app){const f=app.sex==='female',F=k=>app[k]||0;return{f,smile:Math.max(0,Math.min(1,.32+.38*F('mood'))),blink:0,sx:(1+.055*F('fw'))*(f?.985:1.03),sy:(1+.06*F('fl'))*(f?.9:.93),sz:f?.97:1,jaw:F('jaw')*(f?.7:1)+(f?-.6:0),chin:F('chin')+(f?-.15:0),cheek:F('cheek')+(f?.12:0),brow:Math.max(-1,F('brow')+(f?-.75:0)),nose:F('nose')+(f?-.45:0),noseW:F('noseW')+(f?-.28:0),noseL:F('noseL'),lips:F('lips')+(f?.4:0),mouth:H90_MOUTH[app.mouth]||H90_MOUTH.natural,mouthW:F('mouthW'),ears:F('ears'),
 eyeX:.0295*(1+.06*F('eyeD')),eyeW:.0136*(1+.1*F('eyeS'))*(f?1.05:1),eyeH:.0061*(1+.14*F('eyeS'))*(f?1.08:1),eyeR:.0123*(1+.08*F('eyeS')),tilt:.14*F('eyeT')+(f?.05:0),browY:.019,nB:-.048-.004*F('noseL'),nT:-.039-.005*F('noseL'),mY:-.073,chY:-.104}}
/* almond eye opening: half-height along the eye, inner corner lower and tapered */
function eyeHU90(P,u){const s=u/P.eyeW,t=Math.max(0,1-s*s);let h=P.eyeH*Math.pow(t,.48);if(s<0)h*=1-.14*(-s);else h*=1+.06*s*(1-s);return h}
/* mouth styles: upper/lower lip height, fullness, cupid's bow, width, corner set */
const H90_MOUTH={natural:{n:'Natural'},full:{n:'Full',u:1.18,l:1.2,f:1.35,bow:1.1},thin:{n:'Thin',u:.62,l:.72,f:.65,bow:.75,w:1.03},wide:{n:'Wide',u:.92,l:.95,w:1.14,c:.0005},heart:{n:'Heart',u:1.15,l:.86,f:1.08,bow:1.45,w:.9},pouty:{n:'Pouty',u:1.02,l:1.38,f:1.32,bow:1.2,w:.93,c:-.0004},small:{n:'Small',u:.95,l:1.02,f:1.05,bow:1.05,w:.84},soft:{n:'Soft',u:.9,l:1.06,f:1.1,bow:.45},downturned:{n:'Serious',u:.9,l:.98,c:-.0019},upturned:{n:'Upturned',u:.98,l:1,f:1.05,c:.0016}};
function lipF90(P,X){const sm=P.smile||0,M=P.mouth||{},mw=.0238*(1+.12*P.mouthW)*(1+.06*sm)*(M.w||1),q=Math.min(1.2,(X/mw)**2),tq=Math.max(0,1-(X/mw)**2),my=P.mY+sm*.0042*q+(M.c||0)*q,ax=Math.abs(X),cb=((M.bow||1)*.001*_g90((ax-.0046*(M.w||1))/.0032)-.00045*(M.bow||1)*_g90(X/.0022))*tq,yU=my+.0085*(M.u||1)*Math.pow(tq,.75)+cb,yL=my-.0098*(M.l||1)*Math.pow(tq,.6);return{mw,tq,lw:Math.sqrt(tq),my,yU,yL,f:M.f||1}}
function eyeMg90(P,hu){const b=P.blink||0,sm=P.smile||0;return[hu*_m90(.73,-.4,b),-hu*_m90(.86-.14*sm,.4,b)]}
function eyeQ90(P,u,w){const hu=eyeHU90(P,u),[mu,ml]=eyeMg90(P,hu),mid=(mu+ml)/2,hf=Math.max((mu-ml)/2,1e-6),qv=Math.abs(w-mid)/hf;return Math.hypot(Math.min(qv,50),Math.pow(Math.abs(u)/P.eyeW,4))}
function eyeUW90(P,X,ys){const ex=Math.abs(X)-P.eyeX,ct=Math.cos(P.tilt),st=Math.sin(P.tilt);return[ex*ct-ys*st,ex*st+ys*ct]}
function hprof90(P,y){const yl=y<0?y/P.sy:y,q=_cr90(H90_HEAD,yl);let jw=1;if(yl<-.03&&yl>-.12)jw=1+.07*P.jaw*_g90((yl+.085)/.025);return{rxF:Math.max(0,q[0])*P.sx*jw,rxB:Math.max(0,q[1])*P.sx,rf:Math.max(0,q[2])*P.sz,rb:Math.max(0,q[3])*P.sz,zc:q[4]}}
function eyeC90(P,s){const k=s>0?'_eR':'_eL';if(P[k])return P[k];const th=Math.asin(P.eyeX/hprof90(P,0).rxF),sp=hpos90(P,s*th,-.0009,2);return P[k]=new T.Vector3(sp.x+s*.0006,sp.y,sp.z-P.eyeR-.0026)}
function _smax90(a,b,k){const h=Math.max(0,Math.min(1,.5+.5*(b-a)/k));return a+(b-a)*h+k*h*(1-h)}
/* head surface = cranial loft + skeletal landmarks (frontal ridge, orbits, zygoma, mandible, dental arch) + soft tissue (lids wrapping the eyeball, nose cartilage, lips) */
function hpos90(P,th,y,mode){const R=hprof90(P,y),s=Math.sin(th),c=Math.cos(th),cf=Math.max(0,c),rx=R.rxB+(R.rxF-R.rxB)*Math.pow(cf,.7),e=2.25,sp=t=>t*Math.pow(t*t+.0006,(2/e-1)/2)/Math.pow(1.0006,(2/e-1)/2);
 const x=sp(s)*rx,z=R.zc+sp(c)*(c>0?R.rf:R.rb),X=x,Y=y,ax=Math.abs(X),A=Math.abs(th),fr=_s90(0,.45,c),G=_g90,S=_s90;let d=0,df=0,dz=0;
 const nx=s/Math.max(rx,1e-4),nz=c/Math.max(c>0?R.rf:R.rb,1e-4),nl=Math.hypot(nx,nz)||1,nzN=nz/nl;
 if(mode===2)return new T.Vector3(x,y,z);
 const ys=Y<0?Y/P.sy:Y,js=Math.max(.25,1+.8*P.jaw);
 /* side structure: mandible body + angle, zygomatic arch */
 if(Y<-.05&&Y>-.14&&A<1.9){const yb=-.1175+.021*S(.1,1.3,A),env=S(.1,.45,A)*S(1.85,1.45,A);
  d+=env*js*(.0012*G((ys-yb-.0065)/.0075)-.0006*G((ys-yb+.0075)/.008));d+=.0006*js*G((A-1.33)/.22)*G((ys+.096)/.01)}
 if(Y>-.05&&Y<.01&&A>.6&&A<1.7)d+=.0011*G((A-1.12)/.24)*G((ys+.021)/.011);
 if(fr>0&&Y>-.135&&Y<.075){const bm=Math.max(.3,1+.6*P.brow);
  /* frontal bone: supraorbital ridge + glabella, nasion below it */
  const yr=.0125-.0055*((ax-.025)/.026)**2;df+=.0032*bm*G((ys-yr)/.0072)*G(X/.052)+.001*bm*G(X/.011)*G((ys-.012)/.007);df-=.0024*G(X/.011)*G((ys-.0025)/.0055);
  df+=.0014*bm*G((ax-P.eyeX-.021)/.005)*G((ys+.003)/.011);
  /* zygoma: cheekbone eminence, malar pad, hollow beneath */
  df+=.0036*(1+P.cheek)*G((ax-.046)/.0125)*G((ys+.025)/.0125)+.0014*G((ax-.031)/.011)*G((ys+.03)/.011);df+=(P.f?.0012:.0004)*G((ax-.048)/.01)*G((ys+.061)/.013);
  df-=.001*G((ax-.067)/.012)*G((ys-.04)/.018);
  /* nose: continuous bridge -> tip -> columella, wings with alar crease, nostrils */
  const kn=1+.38*P.nose,nb=P.nB,nt=P.nT,hN=_cr90([[.022,0],[.012,.003],[.003,.0062],[-.012,.0128],[nt+.006,.0203*kn],[nt,.0222*kn],[nt-.004,.019*kn],[nb+.003,.0085],[nb-.002,.0012],[nb-.006,0]].reverse(),Math.max(nb-.006,Math.min(.022,ys)))[0],sg=_m90(.0047,.0086,S(-.012,nt,ys))*(1+.25*P.noseW);df+=Math.max(0,hN)*G(X/sg);
  df+=.0033*kn*G(X/.0082)*G((ys-nt)/.0058)-.0007*G(X/.007)*G((ys-nt-.009)/.004);
  const wc=.0106*(1+.2*P.noseW),yc=nb+.0055,ra=Math.hypot(ax-wc,(ys-yc)*1.15);df+=.0042*(1+.3*P.nose)*G(ra/.0056)-.0017*G((ra-.0069)/.0014)*S(-.004,.002,(ax-wc)+(ys-yc)*.7);
  df-=.0022*G((ax-.0056)/.002)*G((ys-nb-.0002)/.0015)-.0012*G(X/.0022)*G((ys-nb-.0004)/.0024);
  /* dental arch muzzle + nasolabial fold */
  const sm=P.smile||0,LF=lipF90(P,X),mw=LF.mw,tq=LF.tq,lw=LF.lw,my=LF.my,lp=(1+.5*P.lips)*(1-.12*sm)*LF.f;
  df+=sm*(.0024*G((ax-.034)/.013)*G((ys+.036)/.012)+.0008*G((ax-.022)/.008)*G((ys+.018)/.007));
  df+=.0036*(P.f?.78:1)*G(X/.034)*S(nb+.004,nb-.007,ys)*S(P.chY+.002,my-.009,ys);
  {const t0=nb+.003,t1=my-.007,t=(t0-ys)/(t0-t1),win=S(-.15,.1,t)*S(1.25,.9,t),dl=ax-(.0175+.0115*t);df+=win*(-.0004*G(dl/.003)+.0005*G((dl-.006)/.005))}
  /* philtrum columns + groove */{const band=S(nb-.0005,nb-.006,ys)*S(LF.yU-.0005,LF.yU+.004,ys);df+=band*(.00045*G((ax-.0042)/.0019)-.00035*G(X/.0026))}
  /* lips: cupid's bow border, rolled vermilion, mouth line, corners, mentolabial sulcus */
  {const yU=LF.yU,yL=LF.yL;
   if(ys>my-.002&&ys<yU+.003){const tU=Math.max(0,Math.min(1,(ys-my)/(yU-my)));df+=.0021*lp*Math.pow(Math.sin(Math.PI*Math.pow(tU,.7)),.9)*lw+.00045*G((ys-yU)/.0008)*lw}
   if(ys<my+.002&&ys>yL-.003){const tL=Math.max(0,Math.min(1,(my-ys)/(my-yL)));df+=.0023*lp*Math.pow(Math.sin(Math.PI*Math.pow(tL,1.1)),.9)*lw}
   df-=.0015*G((ys-my)/.0011)*Math.min(1,tq*3)+.0007*G((ax-mw*1.08)/.003)*G((ys-my)/.004);df-=.0017*G(X/.019)*G((ys-(yL-.0045))/.0042)}
  /* chin: broad mental protuberance */df+=.0064*(1+.6*P.chin)*G(X/(P.f?.018:.0205))*G((ys-P.chY)/.0115)+.0012*js*G((ax-.03)/.012)*G((ys+.097)/.012);
  d+=df*fr;
  /* orbits: deep socket the eyeball sits in; lids are skin stretched over the eyeball */
  if(mode!==true&&ys>-.045&&ys<.045&&ax<.08&&fr>0){const sd=X>0?1:-1,E=eyeC90(P,sd),dx=X-E.x,dy=Y-E.y,re=Math.hypot(dx/1.22,dy*(dy<0?1.8:1)),hol=(P.f?.0056:.0066)*fr;dz-=hol*G(re/.0135);
   const zc=z+nzN*d+dz,[u,w]=eyeUW90(P,X,ys),q=eyeQ90(P,u,w),hu=eyeHU90(P,u),rr2=dx*dx+dy*dy,lt=.0011+(w>0?.0008*G((q-1.08)/.14):.0003*G((q-1.05)/.12)),Rl=P.eyeR+lt;
   let zl=E.z+Math.sqrt(Math.max(0,Rl*Rl-rr2));if(w>0)zl-=.0005*G((w-hu*.73-.0042)/.0012)*S(1.2,.7,Math.abs(u)/P.eyeW);
   let zt=_smax90(zc,zl,.0016);const a=1-S(1.05,1.4,q);if(a>0){const Ri=P.eyeR-.0004,zi=E.z+Math.sqrt(Math.max(0,Ri*Ri-rr2))-.0012;zt=zt+(zi-zt)*a}
   dz+=(zt-zc)*S(.022,.017,Math.hypot(dx,dy))}}
 return new T.Vector3(x+nx/nl*d,y,z+nzN*d+dz)}
function hnorm90(P,th,y){const e=.0025,a=hpos90(P,th+e,y).sub(hpos90(P,th-e,y)),c=hpos90(P,th,y+e*.6).sub(hpos90(P,th,y-e*.6)),n=new T.Vector3().crossVectors(c,a);const r=new T.Vector3(Math.sin(th),.3,Math.cos(th));if(n.lengthSq()<1e-14||y>.11)return new T.Vector3(Math.sin(th)*.2,1,Math.cos(th)*.2).normalize();if(n.dot(r)<0)n.negate();return n.normalize()}
const H90_Y0=-.205,H90_Y1=.1155;
function headLoft90(mb,P,K,det,o){const I=n=>K.names.indexOf(n),hb=I('Head'),nb=I('Neck'),sb=I('Spine2'),y0=o&&o.y0!==undefined?o.y0:H90_Y0,y1=o&&o.y1!==undefined?o.y1:H90_Y1,off=(o&&o.off)||0,ny=Math.max(30,Math.round((y1-y0)/.0021*det*1.45)),nt=Math.max(48,Math.round(176*det*1.45)),hc=K.hcm,base=mb.p.length/3;
 const sk=y=>{if(y>-.055)return[[hb,1]];if(y>-.15){const t=_s90(-.15,-.055,y);return[[hb,t],[nb,1-t]]}const t=_s90(-.205,-.15,y);return[[nb,t],[sb,1-t]]};
 const icdf=(a0,a1,rho,n)=>{const M=2000,c=[0];for(let k=1;k<=M;k++)c.push(c[k-1]+rho(_m90(a0,a1,(k-.5)/M)));const out=[];let k=0;for(let i=0;i<=n;i++){const tg=c[M]*i/n;while(k<M-1&&c[k+1]<tg)k++;const f=(tg-c[k])/Math.max(1e-9,c[k+1]-c[k]);out.push(_m90(a0,a1,(k+Math.min(1,f))/M))}out[0]=a0;out[n]=a1;return out};
 const Ys=icdf(y0,y1,y=>(1+1.7*_g90((y+.045)/.065))*(y>.1?1+3*_s90(.1,.1155,y):1),ny),As=icdf(0,Math.PI*2,a=>1+2.4*_g90((Math.PI-a)/.8),nt);
 for(const y of Ys)for(let j=0;j<=nt;j++){const a=As[j],th=Math.PI-a;let p=hpos90(P,th,y);if(off){p.addScaledVector(hnorm90(P,th,y),off)}p.add(hc);if(o&&o.rec)o.rec.push(th,y);mb.v(p,1-a/(Math.PI*2),(y-H90_Y0)/(H90_Y1-H90_Y0),sk(y))}
 const W=nt+1;for(let i=0;i<Ys.length-1;i++)for(let j=0;j<nt;j++){const a=base+i*W+j,b=a+1,c=a+W,d=c+1;mb.ix.push(a,c,b,b,c,d)}for(let i=0;i<Ys.length;i++)mb.pairs.push([base+i*W,base+i*W+nt]);return{ny:Ys.length,nt}}
/* parametric shells (hair, brows, beards): fn(u,v) -> [θ, Y, thickness, place?] */
function pshell90(P,nu,nv,fn){const Pa=[],U=[],ix=[];for(let j=0;j<=nv;j++)for(let i=0;i<=nu;i++){const u=i/nu,v=j/nv,[th,y,t,pl]=fn(u,v);let p=hpos90(P,th,y).addScaledVector(hnorm90(P,th,y),t);if(pl)p=pl(p,th,y,t);Pa.push(p.x,p.y,p.z);U.push(u*6,v*2)}
 const W=nu+1;for(let j=0;j<nv;j++)for(let i=0;i<nu;i++){const a=j*W+i,b=a+1,c=a+W,d=c+1;ix.push(a,b,c,b,d,c)}const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(Pa,3));g.setAttribute('uv',new T.Float32BufferAttribute(U,2));g.setIndex(ix);g.computeVertexNormals();return g}
function tubeGeo90(pts,rad,seg){const mb=new MB90(),rows=[];for(let i=0;i<pts.length;i++){const Y=pts[Math.min(i+1,pts.length-1)].clone().sub(pts[Math.max(i-1,0)]).normalize();let X=new T.Vector3(1,0,0).addScaledVector(Y,-Y.x);if(X.lengthSq()<1e-4)X=new T.Vector3(0,0,1);X.normalize();rows.push({c:pts[i],X,Y,ra:rad[i],rb:rad[i],e:2,v:i*.4,sk:[[0,1]]})}mb.loft(rows,seg||12,1,1);const g=mb.geo(1);g.deleteAttribute('skinIndex');g.deleteAttribute('skinWeight');g.deleteAttribute('color');return g}
/* region lines in (θ, Y) */
function hairline90(a){return _cr90([[0,.079],[.4,.076],[.7,.066],[.95,.052],[1.15,.024],[1.27,.002],[1.34,-.014],[1.4,-.012],[1.44,.026],[1.62,.031],[1.84,.027],[1.95,-.012],[2.3,-.042],[2.8,-.064],[Math.PI,-.07]],a)[0]}
function bobline90(a,low){return _cr90([[0,.055],[.5,.052],[.8,.046],[1.0,.012],[1.15,-.055],[1.3,low+.01],[1.6,low],[Math.PI,low-.005]],a)[0]}
function browC90(P,X,style){const t0=.011,t1=.053*(P.eyeX/.0295),t=(X-t0)/(t1-t0),tc=Math.max(0,Math.min(1,t));let c=.027,h={soft:.0034,straight:.0029,arched:.0027,angled:.0031,thick:.0052,thin:.0018}[style]||.0033;
 if(style==='straight')c+=.001*Math.sin(Math.PI*tc);else if(style==='arched')c+=.0068*Math.sin(Math.PI*Math.pow(tc,.75))-.0045*tc*tc*tc;else if(style==='angled')c+=.006*Math.min(tc/.65,1)-(tc>.65?.015*(tc-.65):0);else c+=.0038*Math.sin(Math.PI*Math.pow(tc,.9))-.003*tc*tc*tc;
 return{t,c,h:h*(1-.5*Math.max(0,t))*(t<.12?.55+3.7*Math.max(0,t):1)}}
function browM90(P,X,Y,style,bt){if(style==='none')return 0;const ax=Math.abs(X),B=browC90(P,ax,style),h=B.h*(1+.45*(bt||0));if(B.t<-.06||B.t>1.03)return 0;return(1-_s90(h*.6,h,Math.abs(Y-B.c)))*_s90(-.06,.02,B.t)*(1-_s90(.96,1.03,B.t))}
function beardTop90(a){return _cr90([[0,-.051],[.3,-.052],[.5,-.058],[.75,-.045],[1.0,-.032],[1.25,-.014],[1.4,-.012]],a)[0]}
function beardM90(P,th,Y,st){const a=Math.abs(th),X=Math.sin(th)*hprof90(P,Y).rxF,ax=Math.abs(X),my=P.mY,mw=.0238*(1+.12*P.mouthW);if(st==='none'||st==='stubble'||a>1.6)return 0;const fr=1-_s90(.5,.65,a);
 const must=(1-_s90(mw*1.0,mw*1.28,ax))*_s90(my+.004,my+.0095,Y)*(1-_s90(P.nB-.007,P.nB-.0015,Y))*fr;if(st==='mustache')return must;
 const lips=(1-_s90(mw*.92,mw*1.12,ax))*_s90(my-.016,my-.0105,Y)*(1-_s90(my+.0055,my+.0095,Y))*fr;
 if(st==='goatee')return Math.max(must,(1-_s90(.015,.023,ax))*_s90(-.13,-.118,Y)*(1-_s90(my-.017,my-.0105,Y))*fr)*(1-lips);
 const top=beardTop90(a);let m=(1-_s90(1.2,1.42,a))*_s90(-.16,-.13,Y)*(1-_s90(top-.03,top,Y));m=Math.max(m,must)*(1-lips);
 if(st==='chinstrap')m*=Math.max(1-_s90(-.098,-.084,Y),_s90(.9,1.1,a))*(1-must);return m}

/* ---------- textures ---------- */
function suitTex90(){if(H90.suit)return H90.suit;const S=512,c=document.createElement('canvas');c.width=c.height=S;const x=c.getContext('2d'),h=document.createElement('canvas');h.width=h.height=S;const hx=h.getContext('2d'),e=document.createElement('canvas');e.width=e.height=S;const ex=e.getContext('2d');
 x.fillStyle='#b9bcc2';x.fillRect(0,0,S,S);hx.fillStyle='#808080';hx.fillRect(0,0,S,S);ex.fillStyle='#000';ex.fillRect(0,0,S,S);
 for(let yy=0;yy<S;yy+=4)for(let xx=0;xx<S;xx+=4){const v=((xx/4+yy/4)%2)?12:-12;hx.fillStyle=`rgb(${128+v},${128+v},${128+v})`;hx.fillRect(xx,yy,4,4);x.fillStyle=`rgba(0,0,0,${.03+Math.random()*.05})`;x.fillRect(xx,yy,4,4)}
 const panel=(x0,y0,w,h2,raise)=>{hx.fillStyle=raise?'#a8a8a8':'#909090';hx.fillRect(x0+3,y0+3,w-6,h2-6);x.fillStyle=raise?'rgba(255,255,255,.07)':'rgba(0,0,0,.08)';x.fillRect(x0+3,y0+3,w-6,h2-6);hx.fillStyle='#3a3a3a';for(const [a,b,c2,d] of [[x0,y0,w,3],[x0,y0+h2-3,w,3],[x0,y0,3,h2],[x0+w-3,y0,3,h2]])hx.fillRect(a,b,c2,d);x.fillStyle='rgba(10,12,16,.55)';for(const [a,b,c2,d] of [[x0,y0,w,2],[x0,y0+h2-2,w,2],[x0,y0,2,h2],[x0+w-2,y0,2,h2]])x.fillRect(a,b,c2,d)};
 for(let r=0;r<4;r++)for(let k=0;k<4;k++)panel(k*128+(r%2)*64,r*128,128,128,(r+k)%3===0);for(let r=0;r<4;r++)panel(-64+(r%2)*64,r*128,128,128,false);
 for(let yy=0;yy<S;yy+=128)for(let k=0;k<6;k++){hx.fillStyle=k%2?'#6a6a6a':'#9a9a9a';hx.fillRect(0,yy+56+k*3,S,3)}
 const line=(x0,y0,x1,y1,w)=>{for(const g of [ex,x]){g.strokeStyle=g===ex?'#fff':'rgba(220,240,255,.6)';g.lineWidth=w;g.beginPath();g.moveTo(x0,y0);g.lineTo(x1,y1);g.stroke()}};line(126,10,126,118,3);line(126,138,126,246,3);line(382,266,382,374,3);line(382,394,382,502,3);
 const hd=hx.getImageData(0,0,S,S).data,nc=document.createElement('canvas');nc.width=nc.height=S;const nx=nc.getContext('2d'),nd=nx.createImageData(S,S),H=(i,j)=>hd[(((j+S)%S)*S+((i+S)%S))*4]/255;
 for(let j=0;j<S;j++)for(let i=0;i<S;i++){const dx=(H(i+1,j)-H(i-1,j))*3,dy=(H(i,j+1)-H(i,j-1))*3,l=Math.hypot(dx,dy,1),k=(j*S+i)*4;nd.data[k]=(-dx/l*.5+.5)*255;nd.data[k+1]=(dy/l*.5+.5)*255;nd.data[k+2]=(1/l*.5+.5)*255;nd.data[k+3]=255}nx.putImageData(nd,0,0);
 const mk=(cv,srgb)=>{const t=new T.CanvasTexture(cv);t.wrapS=t.wrapT=T.RepeatWrapping;t.anisotropy=8;if(srgb)t.colorSpace=T.SRGBColorSpace;return t};return H90.suit={map:mk(c,1),nrm:mk(nc),em:mk(e,1)}}
function strandTex90(){if(H90.strand)return H90.strand;const S=256,c=document.createElement('canvas');c.width=c.height=S;const x=c.getContext('2d');x.fillStyle='#9a9a9a';x.fillRect(0,0,S,S);for(let i=0;i<1100;i++){const px=Math.random()*S,l=40+Math.random()*120,py=Math.random()*S,v=Math.random();x.strokeStyle=v<.5?`rgba(0,0,0,${.12+Math.random()*.25})`:`rgba(255,255,255,${.1+Math.random()*.22})`;x.lineWidth=.5+Math.random()*1.2;x.beginPath();x.moveTo(px,py);x.bezierCurveTo(px+(Math.random()-.5)*6,py+l*.33,px+(Math.random()-.5)*6,py+l*.66,px+(Math.random()-.5)*8,py+l);x.stroke();x.beginPath();x.moveTo(px,py-S);x.lineTo(px,py+l-S);x.stroke()}
 const t=new T.CanvasTexture(c);t.wrapS=t.wrapT=T.RepeatWrapping;t.colorSpace=T.SRGBColorSpace;t.anisotropy=8;t.userData.shared=1;return H90.strand=t}
/* fabric detail maps (shared by every character; colours come from vertex colours) */
function fabric90(kind){if(H90.fab[kind])return H90.fab[kind];const S=256,c=document.createElement('canvas');c.width=c.height=S;const x=c.getContext('2d'),id=x.createImageData(S,S),D=id.data;
 for(let j=0;j<S;j++)for(let i=0;i<S;i++){let v;if(kind==='denim'){v=.82+.12*(((i+j)>>1)%4<2?1:-1)*.5+(_h90hash(i,j)-.5)*.18+.06*Math.sin(j*.9)}else if(kind==='leather'){v=.86+(_h90hash(i>>1,j>>1)-.5)*.16+(_h90hash(i>>3,j>>3)-.5)*.1}else{v=.86+.07*Math.sin(i*1.6)+(_h90hash(i,j)-.5)*.12}const k=(j*S+i)*4,g=Math.max(0,Math.min(255,v*255));D[k]=D[k+1]=D[k+2]=g;D[k+3]=255}
 x.putImageData(id,0,0);const t=new T.CanvasTexture(c);t.wrapS=t.wrapT=T.RepeatWrapping;t.colorSpace=T.SRGBColorSpace;t.anisotropy=8;const m=new T.MeshStandardMaterial({map:t,vertexColors:true,roughness:kind==='leather'?.45:kind==='denim'?.86:.9,metalness:0,side:T.DoubleSide});m.userData.shared=1;return H90.fab[kind]=m}
function skinTex90(){if(H90.skinT)return H90.skinT;const S=256,c=document.createElement('canvas');c.width=c.height=S;const x=c.getContext('2d'),id=x.createImageData(S,S),D=id.data;for(let j=0;j<S;j++)for(let i=0;i<S;i++){const v=.97+(_h90hash(i,j)-.5)*.05+(_h90hash(i>>3,j>>3)-.5)*.04,k=(j*S+i)*4;D[k]=Math.min(255,v*255);D[k+1]=Math.min(255,v*250);D[k+2]=Math.min(255,v*248);D[k+3]=255}x.putImageData(id,0,0);const t=new T.CanvasTexture(c);t.wrapS=t.wrapT=T.RepeatWrapping;t.colorSpace=T.SRGBColorSpace;t.userData.shared=1;return H90.skinT=t}
function eyeTex90(col,glow){const S=128,c=document.createElement('canvas');c.width=c.height=S;const x=c.getContext('2d'),C=new T.Color(col),hx=v=>'#'+v.getHexString();
 x.fillStyle='#ece8e2';x.fillRect(0,0,S,S);for(let i=0;i<14;i++){x.strokeStyle='rgba(180,60,60,.22)';x.lineWidth=.7;x.beginPath();const px=Math.random()*S;x.moveTo(px,S);x.lineTo(px+(Math.random()-.5)*20,S*.35);x.stroke()}
 const g=x.createLinearGradient(0,0,0,S*.2);g.addColorStop(0,hx(C.clone().multiplyScalar(.45)));g.addColorStop(.35,hx(C));g.addColorStop(.85,hx(C.clone().lerp(new T.Color(1,1,1),.2)));g.addColorStop(1,hx(C.clone().multiplyScalar(.35)));x.fillStyle=g;x.fillRect(0,0,S,S*.18);
 for(let i=0;i<70;i++){const px=Math.random()*S;x.strokeStyle=Math.random()<.5?'rgba(0,0,0,.35)':'rgba(255,255,255,.28)';x.lineWidth=.8;x.beginPath();x.moveTo(px,S*.05);x.lineTo(px,S*.16);x.stroke()}
 x.fillStyle='rgba(10,8,8,.85)';x.fillRect(0,S*.165,S,S*.025);x.fillStyle='#050505';x.fillRect(0,0,S,S*.058);
 const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;let em=null;if(glow){const e=document.createElement('canvas');e.width=e.height=S;const ex=e.getContext('2d');ex.fillStyle='#000';ex.fillRect(0,0,S,S);ex.fillStyle='#fff';ex.fillRect(0,S*.05,S,S*.13);em=new T.CanvasTexture(e);em.colorSpace=T.SRGBColorSpace}return{map:t,em}}
/* face + scalp paint in the head loft's (θ, Y) space */
const _sr90=h=>({r:((h>>16)&255)/255,g:((h>>8)&255)/255,b:(h&255)/255});
function faceTex90(P,app,S){const c=document.createElement('canvas');c.width=c.height=S;const x=c.getContext('2d'),id=x.createImageData(S,S),D=id.data,sk=_sr90(app.skin),hr=_sr90(app.hairC),br=_sr90(app.browC==null?app.hairC:app.browC),bd=_sr90(app.fhairC==null?app.hairC:app.fhairC);
 const lip=app.lipC!=null?_sr90(app.lipC):{r:sk.r*.84,g:sk.g*.6,b:sk.b*.64},fem=P.f,style=app.hair,fh=app.fhair,mw=.0238*(1+.12*P.mouthW)*(1+.06*(P.smile||0)),rows=[];for(let j=0;j<S;j++){const Y=H90_Y0+(1-(j+.5)/S)*(H90_Y1-H90_Y0);rows.push([Y,hprof90(P,Y).rxF])}
 for(let j=0;j<S;j++){const [Y,rx]=rows[j],ys=Y<0?Y/P.sy:Y;for(let i=0;i<S;i++){const th=(1-(i+.5)/S*2)*Math.PI,a=Math.abs(th),X=Math.sin(th)*rx,ax=Math.abs(X),front=Math.cos(th)>0;let r=sk.r,g=sk.g,b=sk.b;const n=_h90hash(i,j)-.5;r+=n*.016;g+=n*.016;b+=n*.016;
  const mix=(C,t)=>{if(t<=0)return;t=Math.min(1,t);r+=(C.r-r)*t;g+=(C.g-g)*t;b+=(C.b-b)*t},mul=(k,t)=>{r*=1+(k[0]-1)*t;g*=1+(k[1]-1)*t;b*=1+(k[2]-1)*t};
  if(front&&a<1.5&&Y>-.16&&Y<.09){const ex=ax-P.eyeX,[eu,ew]=eyeUW90(P,X,ys),q=eyeQ90(P,eu,ew),hu=eyeHU90(P,eu),au=Math.abs(eu)/P.eyeW,lid=_s90(1.35,.85,au);
   mul([.9,.84,.83],.16*_g90(Math.sqrt((ex/.02)**2+((ys-.002)/.014)**2))*(.6+.4*_s90(-.01,.006,ys)));mul([.78,.7,.7],.55*lid*_g90((ew-hu*1.12-.0048)/.0012));
   if(fem)mul([.92,.84,.86],.35*lid*_s90(hu*.9,hu*1.4,ew)*(1-_s90(hu*1.4+.004,hu*1.4+.009,ew)));mix({r:.86,g:.55,b:.55},.45*_g90((eu+P.eyeW*.98)/.0018)*_g90(ew/.0016));
   const l1=ew>0?Math.abs(ew/Math.max(hu,1e-5)-.75):9;if(l1<.25&&au<1.05)mul([.18,.15,.15],(1-l1/.25)*(.55+.45*app.liner)*_s90(1.08,.7,au));const l2=ew<0?Math.abs(-ew/Math.max(hu*.8,1e-5)-.9):9;if(l2<.2&&au<1)mul([.55,.48,.48],(1-l2/.2)*.4*app.liner);
   {const ax0=.016,ay0=P.nB+.003,bx0=mw*1.12,by0=P.mY-.003,vx=bx0-ax0,vy=by0-ay0,tt=Math.max(0,Math.min(1,((ax-ax0)*vx+(ys-ay0)*vy)/(vx*vx+vy*vy))),dd=Math.hypot(ax-ax0-vx*tt,ys-ay0-vy*tt);mul([.88,.82,.82],(fem?.1:.18)*_g90(dd/.0022)*Math.sin(Math.PI*tt))}
   mul([.86,.8,.8],.4*_g90((ys-P.mY+.0135)/.0028)*_g90(X/.016));mul([.9,.86,.86],.3*_s90(-.105,-.125,ys));
   mul([1.04,.93,.91],.3*_g90((ax-.044)/.016)*_g90((ys+.022)/.018)*(fem?1.2:.7));mul([1.04,.88,.86],.3*_g90(X/.01)*_g90((ys-P.nT)/.008));mul([.62,.52,.52],.3*_g90((ax-.0058)/.0018)*_g90((ys-P.nB-.0024)/.0013));
   const LF=lipF90(P,X),my=LF.my,mwL=LF.mw,tq=LF.tq,lw=Math.min(1,Math.sqrt(tq)*1.4),yU=LF.yU,yL=LF.yL,vm=_s90(yU+.0005,yU-.0004,ys)*_s90(yL-.0014,yL+.0008,ys);mix(lip,vm*Math.min(1,Math.sqrt(tq)*1.6)*(fem?.62:.45));mul([.55,.42,.42],.65*_g90((ys-my)/.0007)*Math.min(1,tq*2.5));mul([1.08,1.06,1.06],.45*_g90((ys-yU-.0004)/.0007)*lw);mul([1.1,1.08,1.08],.3*_g90(X/.008)*_g90((ys-my+.0058)/.0018));mul([.92,.86,.86],.3*_g90((ax-mwL*1.08)/.003)*_g90((ys-my)/.004));
   
   if(app.browS!=='none'){const bm=browM90(P,X,ys,app.browS,app.browT);if(bm>0)mix(br,bm*.32)}
   if(fh!=='none'){const bm=fh==='stubble'?beardM90(P,th,Y,'beard'):beardM90(P,th,Y,fh);if(bm>0){const dots=_h90hash(i*7,j*5)>.45?1:.25;mix(bd,bm*(fh==='stubble'?.3:.55)*dots)}}else if(!fem){const bm=beardM90(P,th,Y,'beard');if(bm>0)mul([.94,.93,.95],bm*.22)}}
  if(style!=='bald'&&Y>-.09){const hl=style==='bob'||style==='long'||style==='afro'?hairline90(a)-.002:hairline90(a);let m=_s90(-.002,.006,Y-hl);if(style==='mohawk'||style==='undercut')m*=.38;else if(style==='buzz')m*=.8;else m*=.92;if(m>0)mix(hr,m*(.75+.25*_h90hash(i*5,j*3)))}
  const k=(j*S+i)*4;D[k]=Math.max(0,Math.min(255,r*255));D[k+1]=Math.max(0,Math.min(255,g*255));D[k+2]=Math.max(0,Math.min(255,b*255));D[k+3]=255}}
 x.putImageData(id,0,0);let em=null;const U=(X,Y)=>{const rx=hprof90(P,Y).rxF,th=Math.asin(Math.max(-1,Math.min(1,X/Math.max(rx,1e-3))));return[(1-th/Math.PI)/2*S,(1-(Y-H90_Y0)/(H90_Y1-H90_Y0))*S]},
  bhex='#'+((app.browC==null?app.hairC:app.browC)>>>0).toString(16).padStart(6,'0');
 if(app.browS!=='none'){const bt=app.browT||0,t1=.053*(P.eyeX/.0295),N=Math.round(330*(1+.5*bt)*(app.browS==='thin'?.55:app.browS==='thick'?1.5:1));x.save();x.strokeStyle=bhex;x.lineCap='round';
  for(const s of[1,-1])for(let i=0;i<N;i++){const t=Math.random(),X0=.011+t*(t1-.011),B=browC90(P,X0,app.browS),h=B.h*(1+.45*bt),sv=(Math.random()*2-1)*(.6+.4*Math.random()),Y0=B.c+h*sv*.92,ang=_m90(1.35,.18,Math.pow(t,.7))+(Math.random()-.5)*.3,L=(.0024+.0016*Math.random())*(1-.3*t),dx=Math.cos(ang)*L,dy=Math.sin(ang)*L*(sv>0?.7:1);
   const [x0,y0]=U(s*X0,Y0),[x1,y1]=U(s*(X0+dx),Y0+dy);x.globalAlpha=.35+.45*Math.random()*(1-.4*Math.abs(sv));x.lineWidth=Math.max(.6,S/1024*(.9+.6*Math.random()));x.beginPath();x.moveTo(x0,y0);x.quadraticCurveTo((x0+x1)/2,(y0+y1)/2-S/1024*1.2,x1,y1);x.stroke()}x.restore()}
 const mc=new T.Color(app.markC||0xd23a2a),mcs='#'+mc.getHexString(),mk=app.mark;
 if(mk&&mk!=='none'){x.save();x.fillStyle=mcs;x.strokeStyle=mcs;x.lineCap='round';const sc=S/1024,path=(pts,w,al)=>{x.globalAlpha=al||.85;x.lineWidth=w*sc;x.beginPath();pts.forEach(([X,Y],k)=>{const [px,py]=U(X,Y);k?x.lineTo(px,py):x.moveTo(px,py)});x.stroke();x.globalAlpha=1},dot=(X,Y,rr,al)=>{const [px,py]=U(X,Y);x.globalAlpha=al||.9;x.beginPath();x.arc(px,py,rr*sc,0,7);x.fill();x.globalAlpha=1};
  for(const s of[1,-1]){if(mk==='freckles'){for(let i=0;i<60;i++)dot(s*(.008+Math.random()*.045),-.012+(Math.random()-.5)*.03,1.1+Math.random()*1.5,.3+Math.random()*.3)}
   else if(mk==='dots'){for(let i=0;i<6;i++)dot(s*(.022+i*.0065),-.006-i*.0018,3,.95);for(let i=0;i<4;i++)dot(s*.005,-.085-i*.007,2.4,.95);dot(0,.05,3.6,.95)}
   else if(mk==='tribal'){path([[s*.012,.065],[s*.026,.052],[s*.048,.034],[s*.058,.004],[s*.05,-.03],[s*.04,-.05]],5)}
   else if(mk==='circuit'){path([[s*.006,.06],[s*.006,.044],[s*.02,.044]],2.2);path([[s*.05,.016],[s*.06,.016],[s*.06,-.024],[s*.05,-.042]],2.2);for(const [X,Y] of [[.02,.044],[.05,.016],[.05,-.042],[.006,.06]])dot(s*X,Y,3.4,1)}
   else if(mk==='warpaint'){path([[s*.008,.004],[s*.062,.0]],26,.75)}
   else if(mk==='tears'){path([[s*P.eyeX,-.01],[s*(P.eyeX+.002),-.034]],3)}}
  if(mk==='scar'){x.strokeStyle='#'+new T.Color(app.skin).lerp(new T.Color(1,.85,.85),.45).getHexString();path([[.02,.06],[.036,.02],[.046,-.014]],4,.9)}x.restore();
  if(mk==='circuit'){const e=document.createElement('canvas');e.width=e.height=S;const ex=e.getContext('2d');ex.drawImage(c,0,0);const im=ex.getImageData(0,0,S,S),dd=im.data,mr=mc.r*255,mg=mc.g*255,mb2=mc.b*255;for(let k=0;k<dd.length;k+=4){const v=Math.abs(dd[k]-mr)+Math.abs(dd[k+1]-mg)+Math.abs(dd[k+2]-mb2)<60?255:0;dd[k]=dd[k+1]=dd[k+2]=v}ex.putImageData(im,0,0);em=new T.CanvasTexture(e);em.colorSpace=T.SRGBColorSpace}}
 const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;t.anisotropy=8;return{map:t,em}}

/* ---------- head group: head+neck+ears (skinned), eyes, hair, brows, facial hair ---------- */
function skinAt90(P,X,Y){let th=Math.asin(Math.max(-1,Math.min(1,X/Math.max(hprof90(P,Y).rxF,1e-3)))),p;for(let k=0;k<4;k++){p=hpos90(P,th,Y);const rx=hprof90(P,Y).rxF*Math.max(.3,Math.cos(th));th+=(X-p.x)/Math.max(rx,.02)}return[p,th]}
/* eyelids: smooth strips laid over the eyeball, margin tucked onto the cornea, blending outward into the skin */
function lids90(mb,P,K){const hb=K.names.indexOf('Head'),hc=K.hcm,ct=Math.cos(P.tilt),st=Math.sin(P.tilt),W=P.eyeW,R=P.eyeR,ts=[0,.04,.1,.18,.3,.45,.62,.8,1],nu=40;
 for(const s of[1,-1]){const E=eyeC90(P,s);for(const sg of[1,-1]){const base=mb.p.length/3,Lw=sg>0?.0046:.0032;
  for(let i=0;i<=nu;i++){const uu=(-1+2*i/nu)*.995*W,hu=eyeHU90(P,uu),qv0=Math.sqrt(Math.max(0,1-Math.pow(uu/W,8))),w0=eyeMg90(P,hu)[sg>0?0:1]*qv0;
   for(const t of ts){const u=uu*(1+.12*t),w=w0+sg*t*Lw*(.3+.7*qv0),ex=u*ct+w*st,ey=-u*st+w*ct,X=s*(P.eyeX+ex),Y=ey<0?ey*P.sy:ey,dx=X-E.x,dy=Y-E.y,rr2=dx*dx+dy*dy;
    const lt=t<.3?_m90(-.0004,sg>0?.0012:.0008,Math.sin(Math.min(1,t/.16)*Math.PI/2)):(sg>0?.0011:.0007),Rr=R+lt,zl=E.z+Math.sqrt(Math.max(Rr*Rr-rr2,(Rr*.4)**2));
    const [ps,th]=skinAt90(P,X,Y),k=_s90(.3,1,t);let z=zl+(ps.z+.00012-zl)*k;if(t>=.3)z=Math.max(z,ps.z+.00012*(1-k)+.00012*k);
    const p=new T.Vector3(X,Y,z).add(hc);mb.v(p,.5+th/(Math.PI*2),(Y-H90_Y0)/(H90_Y1-H90_Y0),[[hb,1]])}}
  const n=ts.length,tri=[];for(let i=0;i<nu;i++)for(let k=0;k<n-1;k++){const a=base+i*n+k,b=a+1,c=a+n,d=c+1;tri.push(a,c,b,b,c,d)}
  const Pp=mb.p,v3=j=>new T.Vector3(Pp[j*3],Pp[j*3+1],Pp[j*3+2]),mid=base+(nu>>1)*n+3,nn=new T.Vector3().crossVectors(v3(mid+n).sub(v3(mid)),v3(mid+1).sub(v3(mid)));
  if(nn.z<0)for(let j=0;j<tri.length;j+=3){const q=tri[j+1];tri[j+1]=tri[j+2];tri[j+2]=q}mb.ix.push(...tri)}}}
/* expression morph targets on the head: 0 = blink, 1 = smile (cheeks lift, corners rise, lower lids push up) */
function morph90(hg,P,K,rec,lid0,sc){const hc=K.hcm,pos=hg.attributes.position,N=pos.count,nL=rec.length/2,idx=hg.index.array;
 const mk=(P2,inR)=>{const d=new Float32Array(N*3),mark=new Uint8Array(N);for(let i=0;i<nL;i++){const th=rec[i*2],y=rec[i*2+1];if(!inR(th,y))continue;const p=hpos90(P2,th,y).add(hc).multiplyScalar(sc);d[i*3]=p.x-pos.getX(i);d[i*3+1]=p.y-pos.getY(i);d[i*3+2]=p.z-pos.getZ(i);mark[i]=1}
  const m2=new MB90();lids90(m2,P2,K);for(let i=0;i<m2.p.length/3;i++){const k=lid0+i;d[k*3]=m2.p[i*3]*sc-pos.getX(k);d[k*3+1]=m2.p[i*3+1]*sc-pos.getY(k);d[k*3+2]=m2.p[i*3+2]*sc-pos.getZ(k);mark[k]=1}
  const near=mark.slice();for(let t=0;t<idx.length;t+=3){if(mark[idx[t]]||mark[idx[t+1]]||mark[idx[t+2]]){near[idx[t]]=near[idx[t+1]]=near[idx[t+2]]=1}}
  const g2=new T.BufferGeometry(),P3=new Float32Array(pos.array);for(let i=0;i<N*3;i++)P3[i]+=d[i];g2.setAttribute('position',new T.BufferAttribute(P3,3));g2.setIndex(hg.index);g2.computeVertexNormals();const n0=hg.attributes.normal,n1=g2.attributes.normal,dn=new Float32Array(N*3);for(let i=0;i<N;i++)if(near[i]){dn[i*3]=n1.getX(i)-n0.getX(i);dn[i*3+1]=n1.getY(i)-n0.getY(i);dn[i*3+2]=n1.getZ(i)-n0.getZ(i)}g2.dispose();
  return[new T.BufferAttribute(d,3),new T.BufferAttribute(dn,3)]};
 const B=mk(Object.assign({},P,{blink:1}),(th,y)=>Math.cos(th)>.25&&y>-.04&&y<.045),S=mk(Object.assign({},P,{smile:Math.min(1,P.smile+.7)}),(th,y)=>Math.cos(th)>.05&&y<.02&&y>-.12);
 hg.morphAttributes.position=[B[0],S[0]];hg.morphAttributes.normal=[B[1],S[1]];hg.morphTargetsRelative=true}
/* ear: one continuous shell — helix rim rolling over to the back, scapha, antihelix, concha bowl, tragus, antitragus, fleshy lobe */
function ear90(mb,P,s,hc,hb){const G=_g90,S=_s90,k=1+.15*P.ears,cy=-.0145,cz=-.014,R0=hprof90(P,cy),xb=R0.rxB+.0004,tb=.26,ct=Math.cos(tb),st=Math.sin(tb),uv=[(1-(s*1.75)/Math.PI)/2,(-.07-H90_Y0)/(H90_Y1-H90_Y0)];
 const Rr=a=>{const c=Math.cos(a),n=Math.sin(a),ax=(c>0?.0118:.0182)*k,ay=(n>0?.0312:.0335)*k;return Math.pow(Math.pow(Math.abs(c)/ax,2.5)+Math.pow(Math.abs(n)/ay,2.5),-1/2.5)};
 const fl=(r,a)=>{const c=Math.cos(a),n=Math.sin(a);return .0024+.0108*k*Math.pow(r,1.25)*S(.4,-.8,c)*(1-.45*S(-.55,-.95,n))*(1-.4*S(.4,.95,n))};
 const rel=(r,a,f,u)=>{let A=a%(Math.PI*2);if(A<0)A+=Math.PI*2;const wh=S(.1,.5,A)*S(4.75,4.3,A);let d=.0031*G((r-.93)/.055)*wh-.0017*G((r-.78)/.05)*wh*S(1.1,1.9,A)+.0026*G((r-.6)/.08)*S(1.2,1.8,A)*S(4.35,3.8,A);
  d-=.0044*G(Math.hypot(f+.001*k,u+.0045*k)/(.0085*k));d+=.0034*G(Math.hypot(f-.0088*k,u+.0045*k)/(.0027*k))+.0019*G(Math.hypot(f+.0035*k,u+.0155*k)/(.0026*k))+.0012*G((r-.7)/.15)*S(-.6,-.95,Math.sin(a));return d};
 const ts=[];for(const r of[0,.08,.16,.25,.34,.43,.52,.6,.67,.74,.8,.85,.89,.92,.95,.975,1])ts.push(['f',r]);for(const ph of[.3,.55,.8])ts.push(['r',ph]);for(const r of[1,.93,.82,.68,.52])ts.push(['b',r]);
 const nA=56,base=mb.p.length/3,nt=ts.length,pt=(a,q)=>{const R=Rr(a),c=Math.cos(a),n=Math.sin(a);let r,o,ex=0;const thick=.0026*k;
  if(q[0]==='f'){r=q[1];const f=r*R*c,u=r*R*n;o=fl(r,a)+rel(r,a,f,u)}else if(q[0]==='b'){r=q[1];o=fl(r,a)-thick}else{r=1;const of=fl(1,a)+rel(1,a,R*c,R*n),ob=fl(1,a)-thick,m=(of+ob)/2,h=(of-ob)/2,ph=q[1]*Math.PI;o=m+h*Math.cos(ph);ex=h*Math.sin(ph)}
  const rr=r*R+ex,f=rr*c,u=rr*n,z=cz+f*ct-u*st,y=cy+f*st+u*ct;return new T.Vector3(s*(xb+o),y,z)};
 for(let i=0;i<=nA;i++){const a=i/nA*Math.PI*2;for(const q of ts){const p=pt(a,q).add(hc);mb.v(p,uv[0],uv[1],[[hb,1]])}}
 const tri=[];for(let i=0;i<nA;i++)for(let j=0;j<nt-1;j++){const a=base+i*nt+j,b=a+1,c=a+nt,d=c+1;tri.push(a,b,c,b,d,c)}
 const v3=j=>new T.Vector3(mb.p[j*3],mb.p[j*3+1],mb.p[j*3+2]),m0=base+Math.round(nA*.25)*nt+8,nn=new T.Vector3().crossVectors(v3(m0+1).sub(v3(m0)),v3(m0+nt).sub(v3(m0)));if(nn.x*s<0)for(let j=0;j<tri.length;j+=3){const q=tri[j+1];tri[j+1]=tri[j+2];tri[j+2]=q}
 mb.ix.push(...tri)}
function headGeos90(app,K,C,det){det=det||(C&&C.det)||1;const P=headP90(app),hb=K.names.indexOf('Head'),hc=K.hcm,sc=K.K,out={},fin=g=>{g.translate(hc.x,hc.y,hc.z);g.scale(sc,sc,sc);const n=g.attributes.position.count,si=new Uint16Array(n*4),sw=new Float32Array(n*4);for(let i=0;i<n;i++){si[i*4]=hb;sw[i*4]=1}g.setAttribute('skinIndex',new T.BufferAttribute(si,4));g.setAttribute('skinWeight',new T.BufferAttribute(sw,4));if(!g.attributes.uv)g.setAttribute('uv',new T.BufferAttribute(new Float32Array(n*2),2));g.computeBoundingSphere();return g};
 const mb=new MB90(),rec=[];headLoft90(mb,P,K,det,{rec});const lid0=mb.p.length/3;lids90(mb,P,K);
 for(const sd of[1,-1])ear90(mb,P,sd,hc,hb);
 const hg=mb.geo(sc);hg.deleteAttribute('color');out.head=hg;if(C)morph90(hg,P,K,rec,lid0,sc);
 /* eyes */const eg=[];for(const s of[1,-1]){const E=eyeC90(P,s),e=new T.SphereGeometry(P.eyeR,48,32);e.rotateX(Math.PI/2);e.translate(E.x,E.y,E.z);eg.push(e)}out.eyes=fin(mergeSimple90(eg));
 /* hair */const st=app.hair,hT={crew:(t,y)=>.0018+.0042*_s90(.03,.1,y),short:(t,y)=>.003+.011*_s90(.02,.105,y)+.006*_g90(t/.45)*_g90((y-.075)/.012),quiff:(t,y)=>.004+.03*_g90(t/.55)*_s90(.05,.09,y)*(1-_s90(.108,.1155,y))+.005*_s90(.06,.11,y),undercut:(t,y)=>.011+.012*_g90(t/.6)*_s90(.07,.1,y),bob:(t,y)=>.008+.009*_s90(.02,-.08,y),long:(t,y)=>.008+.007*_s90(.02,-.09,y),afro:(t,y)=>.042+.004*Math.sin(t*9)*Math.sin(y*90),ponytail:()=>.004,bun:()=>.004,braids:()=>.004};
 const hairParts=[];if(hT[st]&&st!=='mohawk'){const lb=th=>{const A=Math.abs(th),hl=hairline90(A);return st==='bob'||st==='long'?bobline90(A,st==='long'?-.12:-.098):st==='undercut'?Math.max(hl,.072):st==='afro'?hl-.004:hl};const tf=hT[st];
  const g=pshell90(P,Math.round(196*det),Math.round(40*det),(u,v)=>{const th=(u*2-1)*Math.PI,l=lb(th),y=l+(H90_Y1-l)*(1-Math.pow(1-v,1.25)),r=_s90(0,1,(y-l)/(st==='bob'||st==='long'?.008:.017)),t=.0006+tf(th,y)*(st==='afro'?_s90(0,1,(y-l)/.012):st==='undercut'?_s90(0,1,(y-l)/.018):r);
   const hang=(st==='bob'||st==='long')?(p,th2,y2,t2)=>{const hb2=_s90(.0,-.035,y2);if(hb2<=0)return p;const p0=hpos90(P,th2,.0),rr=Math.hypot(p0.x,p0.z+.008)+t2+.003,ang=Math.atan2(p0.x,p0.z+.008),k=1+.04*_s90(0,-.1,y2),q=new T.Vector3(Math.sin(ang)*rr*k,p.y,Math.cos(ang)*rr*k-.008);return p.lerp(q,hb2)}:null;return[th,y,t,hang]});
  if(st==='afro'){const A=g.attributes.position;for(let k=0;k<A.count;k++){const vx=A.getX(k),vy=A.getY(k),vz=A.getZ(k),nz=(Math.sin(vx*420)*Math.sin(vy*390+1)*Math.sin(vz*410+2))*.0016;const l=Math.hypot(vx,vy,vz)||1;A.setXYZ(k,vx+vx/l*nz,vy+vy/l*nz,vz+vz/l*nz)}g.computeVertexNormals()}hairParts.push(g)}
 if(st==='mohawk'){hairParts.push(pshell90(P,14,80,(u,v)=>{const w=u*2-1,b=v,th=Math.PI*b,yy=_m90(.079,-.05,Math.pow(b,1.6)),y=b<.5?_m90(.079,H90_Y1,Math.sin(b*Math.PI)):yy,tt=w*.11;return[th<.01?tt:th+tt*(1-b),Math.min(H90_Y1-.0005,y),.0006+(.02+.026*_s90(0,.4,v)*(1-_s90(.7,1,v)))*Math.sqrt(Math.max(0,1-w*w))*_s90(0,.04,v)]}))}
 if(st==='long'){const rows=[];for(let i=0;i<=10;i++){const v=i/10,row=[];for(let j=0;j<=24;j++){const th=Math.PI+(j/24*2-1)*(Math.PI-1.22),p0=hpos90(P,th,.0),rr=Math.hypot(p0.x,p0.z+.008)+.016+.004,ang=Math.atan2(p0.x,p0.z+.008),r2=rr*(1.04+.14*v),y0=-.122;row.push(new T.Vector3(Math.sin(ang)*r2,y0-.21*v*(.7+.3*Math.abs(Math.cos(th))),Math.cos(ang)*r2-.008-.03*v))}rows.push(row)}
  const P2=[],U2=[],I2=[];rows.forEach((row,i)=>row.forEach((p,j)=>{P2.push(p.x,p.y,p.z);U2.push(j/24*3,1-i/10*2)}));for(let i=0;i<10;i++)for(let j=0;j<24;j++){const a=i*25+j,b=a+1,c=a+25,d=c+1;I2.push(a,b,c,b,d,c)}const cg=new T.BufferGeometry();cg.setAttribute('position',new T.Float32BufferAttribute(P2,3));cg.setAttribute('uv',new T.Float32BufferAttribute(U2,2));cg.setIndex(I2);cg.computeVertexNormals();hairParts.push(cg)}
 if(st==='ponytail'){const s0=hpos90(P,Math.PI,.06);hairParts.push(tubeGeo90([s0.clone().add(new T.Vector3(0,0,-.005)),s0.clone().add(new T.Vector3(0,-.02,-.03)),s0.clone().add(new T.Vector3(0,-.07,-.05)),s0.clone().add(new T.Vector3(0,-.14,-.06)),s0.clone().add(new T.Vector3(0,-.21,-.052)),s0.clone().add(new T.Vector3(0,-.25,-.044))],[.015,.02,.023,.02,.012,.003],14))}
 if(st==='bun'){const s0=hpos90(P,Math.PI*.98,.1),b=new T.SphereGeometry(.033,18,14);b.scale(1,.85,1);b.translate(s0.x,s0.y+.008,s0.z-.02);hairParts.push(b)}
 if(st==='braids'){for(const s of[1,-1]){const s0=hpos90(P,s*2.05,-.04);for(let i=0;i<11;i++){const b=new T.SphereGeometry(.0125-.0004*i,10,8);b.scale(1,1.35,1);b.rotateZ(i%2?.35:-.35);b.translate(s0.x+s*.011,s0.y-.012-i*.022,s0.z-.016+i*.002);hairParts.push(b)}}}
 if(hairParts.length)out.hair=fin(mergeSimple90(hairParts.map(g=>{if(!g.attributes.uv)g.setAttribute('uv',new T.BufferAttribute(new Float32Array(g.attributes.position.count*2),2));return g})));
 /* brows are painted hair strokes now */if(false){const bt=app.browT||0,parts=[];for(const sd of[1,-1])parts.push(pshell90(P,22,7,(u,v)=>{const t1=.053*(P.eyeX/.0295),X=.011+(-.04+u*1.07)*(t1-.011),B=browC90(P,X,app.browS),h=B.h*(1+.45*bt),sv=v*2-1,Y=B.c+h*sv,th=sd*Math.asin(Math.min(.95,X/hprof90(P,Y).rxF));return[th,Y,.0003+.0013*(1+.5*bt)*Math.pow(Math.max(0,1-sv*sv),.6)*_s90(-.04,.06,B.t)*(1-_s90(.95,1.03,B.t))]}));out.brows=fin(mergeSimple90(parts))}
 const fh=app.fhair;if(fh&&fh!=='none'&&fh!=='stubble'){const th0={mustache:.0034,goatee:.0045,beard:.0042,full:.011,chinstrap:.0038}[fh]||.005,small=fh==='mustache'||fh==='goatee',A0=small?.5:1.45;
  const g=pshell90(P,small?48:110,small?48:56,(u,v)=>{const th=(u*2-1)*A0,top=small?P.nB:beardTop90(Math.abs(th)),y=-.165+(top+.165)*v,m=beardM90(P,th,y,fh),w=_s90(0,1,m);return[th,y,(th0*(y>P.mY?.55:1)+(fh==='full'?.01*_s90(-.09,-.125,y)*_g90(th/.5):0))*w-.0035*(1-w)]});out.fhair=fin(g)}
 /* eyelashes: fringe strips resting on the eyeball at the upper lid line (cannot sink behind the eye) */const lashB=P=>{const parts=[];for(const s of[1,-1]){const ce=eyeC90(P,s),R2=P.eyeR*P.eyeR,Pa=[],Ua=[],Ia=[],nu=20,ct=Math.cos(P.tilt),st=Math.sin(P.tilt);
  for(let i=0;i<=nu;i++){const uu=(-.97+1.95*i/nu)*P.eyeW,ww=eyeMg90(P,eyeHU90(P,uu))[0]*1.04,ex=uu*ct+ww*st,ey=-uu*st+ww*ct,X=s*(P.eyeX+ex),dx=X-ce.x,dy=ey-ce.y,r2=Math.min(dx*dx+dy*dy,R2*.97),b=new T.Vector3(X,ey+.0003,ce.z+Math.sqrt(R2-r2)+.0012+.0012*Math.max(0,-uu/P.eyeW)),sv=uu/P.eyeW,len=(.0042+.0024*Math.sin(Math.PI*(sv*.5+.5)))*(P.f?1.15:.8),lat=s*(len*.35*Math.max(0,sv)+dx*.12),bk=P.blink||0,mid=b.clone().add(new T.Vector3(lat*.5,len*(.22-.42*bk),len*.5)),tip=b.clone().add(new T.Vector3(lat,len*(.72-1.15*bk),len*(.62-.1*bk)));Pa.push(b.x,b.y,b.z,mid.x,mid.y,mid.z,tip.x,tip.y,tip.z);Ua.push(i/nu,0,i/nu,.5,i/nu,1)}
  for(let i=0;i<nu;i++){const a=i*3;Ia.push(a,a+3,a+1,a+1,a+3,a+4,a+1,a+4,a+2,a+2,a+4,a+5)}const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(Pa,3));g.setAttribute('uv',new T.Float32BufferAttribute(Ua,2));g.setIndex(Ia);g.computeVertexNormals();parts.push(g)}return mergeSimple90(parts)};out.lash=fin(lashB(P));if(C){const g2=lashB(Object.assign({},P,{blink:1}));g2.translate(hc.x,hc.y,hc.z);g2.scale(sc,sc,sc);const a0=out.lash.attributes.position,a1=g2.attributes.position,d=new Float32Array(a0.count*3);for(let i=0;i<a0.count*3;i++)d[i]=a1.array[i]-a0.array[i];out.lash.morphAttributes.position=[new T.BufferAttribute(d,3)];out.lash.morphTargetsRelative=true}
 out.P=P;return out}
function lashTex90(){if(H90.lash)return H90.lash;const W=256,Hh=32,c=document.createElement('canvas');c.width=W;c.height=Hh;const x=c.getContext('2d');x.clearRect(0,0,W,Hh);x.strokeStyle='#fff';x.lineCap='round';for(let i=0;i<190;i++){const px=Math.random()*W,l=Hh*(.5+.5*Math.random());x.globalAlpha=.55+.45*Math.random();x.lineWidth=.6+Math.random()*.6;x.beginPath();x.moveTo(px,Hh);x.quadraticCurveTo(px+(Math.random()-.5)*4,Hh-l*.5,px+(Math.random()-.5)*8,Hh-l);x.stroke()}const t=new T.CanvasTexture(c);t.generateMipmaps=false;t.minFilter=T.LinearFilter;t.userData.shared=1;return H90.lash=t}
function poreTex90(){if(H90.pore)return H90.pore;const S=256,h=new Float32Array(S*S);for(let i=0;i<S*S;i++)h[i]=Math.random();for(let k=0;k<2;k++){const o=h.slice();for(let j=0;j<S;j++)for(let i=0;i<S;i++){let a=0;for(const [dx,dy] of [[0,0],[1,0],[-1,0],[0,1],[0,-1]])a+=o[((j+dy+S)%S)*S+((i+dx+S)%S)];h[j*S+i]=a/5}}
 const c=document.createElement('canvas');c.width=c.height=S;const x=c.getContext('2d'),d=x.createImageData(S,S),H=(i,j)=>h[((j+S)%S)*S+((i+S)%S)];for(let j=0;j<S;j++)for(let i=0;i<S;i++){const dx=(H(i+1,j)-H(i-1,j))*6,dy=(H(i,j+1)-H(i,j-1))*6,l=Math.hypot(dx,dy,1),k=(j*S+i)*4;d.data[k]=(-dx/l*.5+.5)*255;d.data[k+1]=(dy/l*.5+.5)*255;d.data[k+2]=(1/l*.5+.5)*255;d.data[k+3]=255}x.putImageData(d,0,0);const t=new T.CanvasTexture(c);t.wrapS=t.wrapT=T.RepeatWrapping;t.repeat.set(18,18);t.userData.shared=1;return H90.pore=t}
function mergeSimple90(list){let n=0,ni=0;for(const g of list){if(!g.attributes.normal)g.computeVertexNormals();n+=g.attributes.position.count;ni+=g.index?g.index.count:g.attributes.position.count}
 const P=new Float32Array(n*3),N=new Float32Array(n*3),U=new Float32Array(n*2),I=new Uint32Array(ni);let o=0,oi=0;for(const g of list){const c=g.attributes.position.count;P.set(g.attributes.position.array.subarray(0,c*3),o*3);N.set(g.attributes.normal.array.subarray(0,c*3),o*3);if(g.attributes.uv)U.set(g.attributes.uv.array.subarray(0,c*2),o*2);if(g.index){const ix=g.index.array;for(let k=0;k<ix.length;k++)I[oi++]=ix[k]+o}else for(let k=0;k<c;k++)I[oi++]=o+k;o+=c}
 const g=new T.BufferGeometry();g.setAttribute('position',new T.BufferAttribute(P,3));g.setAttribute('normal',new T.BufferAttribute(N,3));g.setAttribute('uv',new T.BufferAttribute(U,2));g.setIndex(new T.BufferAttribute(I,1));return g}
