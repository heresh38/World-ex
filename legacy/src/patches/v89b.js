
/* ---------- armor builders (designed in rest pose, character space, then parented to bone mounts) ---------- */
const _Y89=new T.Vector3(0,1,0);
function orient89(mesh,d,fwd){const y=d.clone().normalize();let z=(fwd||new T.Vector3(0,0,1)).clone();z.addScaledVector(y,-z.dot(y));if(z.lengthSq()<1e-6)z.set(1,0,0);z.normalize();const x=new T.Vector3().crossVectors(y,z);mesh.quaternion.setFromRotationMatrix(new T.Matrix4().makeBasis(x,y,z));return mesh}
/* limb shell: tapered (partial) tube between rest points a,b (absolute) on a bone mount */
function limb89(g,P0,a,b,r1,r2,mat,th0,thL,f0,f1,fwd){const d=b.clone().sub(a),L=d.length();const geo=new T.CylinderGeometry(r2,r1,L*(f1-f0),18,1,thL<6.2,th0===undefined?0:th0,thL===undefined?Math.PI*2:thL);const m=new T.Mesh(geo,mat);m.castShadow=true;m.receiveShadow=true;
 const c=a.clone().addScaledVector(d,(f0+f1)/2).sub(P0);m.position.copy(c);orient89(m,d,fwd);m.userData.d89={k:'limb',r1,r2,L:L*(f1-f0),th0:th0===undefined?0:th0,thL:thL===undefined?Math.PI*2:thL};g.add(m);return m}
function ell89(g,P0,c,rx,ry,rz,mat,ph0,phL,th0,thL){const geo=new T.SphereGeometry(1,24,14,ph0||0,phL===undefined?Math.PI*2:phL,th0||0,thL===undefined?Math.PI:thL);geo.scale(rx,ry,rz);const m=new T.Mesh(geo,mat);m.position.copy(c.clone().sub(P0));m.castShadow=true;m.receiveShadow=true;m.userData.d89={k:'ell',rx,ry,rz,ph0:ph0||0,phL:phL===undefined?Math.PI*2:phL,th0:th0||0,thL:thL===undefined?Math.PI:thL};g.add(m);return m}
function bx89(g,P0,c,w,h,d,mat,rx,ry,rz,r){const m=new T.Mesh(rbox89(w,h,d,r),mat);m.userData.d89={k:'box',w,h,d};m.position.copy(c.clone().sub(P0));m.rotation.set(rx||0,ry||0,rz||0);m.castShadow=true;m.receiveShadow=true;g.add(m);return m}
function V89(x,y,z){return new T.Vector3(x,y,z)}

/* HELMETS (Head mount). hc = head centre */
function helmet89(id,C,M,P,G){const g=G('Head'),P0=P.Head,f=C.sex==='female'?.93:1,hc=V89(0,P0.y+.078*f,P0.z-.004),R=.128*f;
 if(id==='vanguard'){ell89(g,P0,hc,R*1.02,R*1.06,R*1.14,M.pri);ell89(g,P0,hc.clone().add(V89(0,-.07*f,.02)),R*.92,R*.55,R*1.02,M.sec,0,Math.PI*2,Math.PI*.45,Math.PI*.55);
  ell89(g,P0,hc,R*1.035,R*1.07,R*1.155,M.visor,Math.PI/2-.95,1.9,Math.PI*.43,Math.PI*.1);ell89(g,P0,hc,R*1.035,R*1.07,R*1.155,M.visor,Math.PI/2-.16,.32,Math.PI*.5,Math.PI*.2);
  ell89(g,P0,hc,R*1.04,R*1.075,R*1.16,M.glow,Math.PI/2-.97,1.94,Math.PI*.425,Math.PI*.012);for(const s of[-1,1]){const e=new T.Mesh(new T.CylinderGeometry(.034*f,.04*f,.03,16),M.metal);e.rotation.z=Math.PI/2;e.position.copy(hc.clone().add(V89(s*R*1.0,-.01,.0)).sub(P0));g.add(e);bx89(g,P0,hc.clone().add(V89(s*R*.55,R*.9,-.01)),.03,.025,.16*f,M.metal,0,0,s*.35)}
  bx89(g,P0,hc.clone().add(V89(0,R*1.04,.0)),.035,.03,.2*f,M.sec)}
 else if(id==='hood'){const h=ell89(g,P0,hc.clone().add(V89(0,.012,-.012)),R*1.22,R*1.25,R*1.25,M.cloth,0,Math.PI*2,0,Math.PI*.78);h.rotation.x=-.5;const tip=new T.Mesh(new T.ConeGeometry(.06*f,.12*f,12),M.cloth);tip.position.copy(hc.clone().add(V89(0,.05,-.15*f)).sub(P0));tip.rotation.x=-2.2;g.add(tip);
  const mk=new T.Mesh(new T.CylinderGeometry(R*.95,R*.85,.14*f,24,1,true,-1.15,2.3),M.pri);mk.position.copy(hc.clone().add(V89(0,-.03,.012)).sub(P0));g.add(mk);for(const s of[-1,1])bx89(g,P0,hc.clone().add(V89(s*.04*f,.0,R*.97)),.045*f,.009,.012,M.glow,0,s*.35,s*.12,.004);
  bx89(g,P0,hc.clone().add(V89(0,-.06*f,R*.92)),.07*f,.01,.012,M.metal);ell89(g,P0,hc.clone().add(V89(0,-.12*f,-.01)),R*1.15,.05,R*1.1,M.cloth)}
 else if(id==='seer'){ell89(g,P0,hc.clone().add(V89(0,.01,0)),R*.98,R*1.12,R*1.1,M.pri);ell89(g,P0,hc.clone().add(V89(0,-.012,.008)),R*1.0,R*1.13,R*1.12,M.visor,Math.PI/2-1.0,2.0,Math.PI*.4,Math.PI*.26);
  const crest=shape89([[0,0],[.05,.0],[.22,.1],[.06,.06]],.012);const cm=new T.Mesh(crest,M.metal);cm.rotation.y=-Math.PI/2;cm.position.copy(hc.clone().add(V89(0,R*.9,.06)).sub(P0));cm.scale.setScalar(f);cm.rotation.x=0;g.add(cm);
  bx89(g,P0,hc.clone().add(V89(0,.045*f,R*1.08)),.012,.012,.012,M.glow,0,0,Math.PI/4,.003);bx89(g,P0,hc.clone().add(V89(0,-.02*f,R*1.06)),.006,.07*f,.01,M.glow);for(const s of[-1,1])bx89(g,P0,hc.clone().add(V89(s*R*.92,-.02,-.01)),.02,.09*f,.07*f,M.metal,0,0,s*.1)}
 else if(id==='warden'){bx89(g,P0,hc.clone().add(V89(0,.012,.004)),.25*f,.26*f,.29*f,M.pri,0,0,0,.06);bx89(g,P0,hc.clone().add(V89(0,-.03,.145*f)),.2*f,.12*f,.03,M.sec,-.1,0,0,.02);
  bx89(g,P0,hc.clone().add(V89(0,.0,.162*f)),.12*f,.012,.012,M.glow);bx89(g,P0,hc.clone().add(V89(0,-.035*f,.162*f)),.012,.06*f,.012,M.glow);
  for(const s of[-1,1]){const hn=new T.Mesh(new T.TorusGeometry(.09*f,.016*f,8,14,Math.PI*.55),M.metal);hn.position.copy(hc.clone().add(V89(s*.12*f,.06*f,-.01)).sub(P0));hn.rotation.set(0,s>0?0:Math.PI,s>0?-.2:-.2);g.add(hn);const tip=new T.Mesh(new T.ConeGeometry(.016*f,.07*f,8),M.metal);tip.position.copy(hc.clone().add(V89(s*.12*f,.15*f,-.01)).sub(P0));g.add(tip)}
  bx89(g,P0,hc.clone().add(V89(0,.14*f,-.01)),.03,.03,.24*f,M.metal,0,0,0,.01)}
 else if(id==='recon'){ell89(g,P0,hc,R*1.03,R*1.05,R*1.1,M.pri);const v=ell89(g,P0,hc,R*1.045,R*1.065,R*1.12,M.visorC,Math.PI/2-1.15,2.3,Math.PI*.38,Math.PI*.3);
  ell89(g,P0,hc.clone().add(V89(0,-.075*f,.01)),R*.9,R*.4,R*1.02,M.sec,0,Math.PI*2,Math.PI*.5,Math.PI*.5);for(const s of[-1,1])bx89(g,P0,hc.clone().add(V89(s*R*1.0,-.01,-.01)),.03,.06*f,.09*f,M.metal,0,0,0,.012);
  const ant=new T.Mesh(new T.CylinderGeometry(.003,.004,.14*f,6),M.metal);ant.position.copy(hc.clone().add(V89(-R*1.02,.07*f,-.04)).sub(P0));ant.rotation.x=-.3;g.add(ant);bx89(g,P0,hc.clone().add(V89(0,R*.98,-.03)),.04,.016,.14*f,M.sec);bx89(g,P0,hc.clone().add(V89(0,.055*f,R*1.04)),.14*f,.004,.01,M.glow)}}

/* CHEST (Spine2 + Spine1 mounts) */
function chest89(id,C,M,P,G){const f=C.sex==='female',g=G('Spine2'),g1=G('Spine1'),P0=P.Spine2,P1=P.Spine1,shX=Math.abs(P.LeftArm.x),y0=P0.y-.02,y1=P.LeftArm.y+.025,cy=(y0+y1)/2,H=y1-y0,cz=(C._cz89=fitZ89(y0,y1-.03,shX*.5,P0.z+(f?.03:.025))),kT=(C._kT89=fitE89(y0,y1-.03,shX*.8,shX*(f?1.0:.96),f?.152:.138,cz)),rx=shX*(f?1.0:.96)*kT,rz=(f?.152:.138)*kT;
 const barrel=(sx,sz,mat,h,yy)=>{const geo=new T.CylinderGeometry(1,1,h||H,28,1,true);geo.scale(rx*sx,1,rz*sz);const m=new T.Mesh(geo,mat||M.pri);m.position.set(0,(yy||cy)-P0.y,cz-P0.z);m.castShadow=true;g.add(m);return m};
 const arc=(t0,tl,h,yy,sx,sz,mat,tap)=>{const geo=new T.CylinderGeometry(tap||1,1,h,Math.max(3,Math.ceil(tl*14)),1,true,t0,tl);geo.scale(rx*sx,1,rz*sz);const m=new T.Mesh(geo,mat||M.pri);m.position.set(0,yy-P0.y,cz-P0.z);m.castShadow=true;g.add(m);return m};
 const collar=(r,t,mat)=>{const tg=new T.TorusGeometry(1,t,8,28);tg.rotateX(Math.PI/2);tg.scale(rx*r,1,rz*r);const m=new T.Mesh(tg,mat||M.sec);m.position.set(0,y1-P0.y,cz-P0.z);g.add(m);return m};
 const abs=(n,mat,w,sz)=>{const ar=rx*(w||.86),az=rz*(sz||.98),kA=fitE89(P1.y-.04-n*.042,P1.y+.07,shX*.75,ar,az,cz-.005),R=ar*kA,Z=az*kA,pm=(mat===M.metal)?M.metal:M.pri,zc=cz-.005-P1.z;
  const band=new T.CylinderGeometry(1,1,n*.042+.02,28,1,true);band.scale(R*.985,1,Z*.985);const bm=new T.Mesh(band,M.sec);bm.position.set(0,P1.y+.06-(n*.042+.02)/2-P1.y+.004,zc);g1.add(bm);
  for(let i=0;i<n;i++){const y=P1.y+.05-i*.042-P1.y;for(const sd of[-1,1]){const geo=new T.CylinderGeometry(1,1,.034,14,1,true,sd>0?.06:-1.16,1.1);geo.scale(R*(1.02-i*.01),1,Z*(1.04-i*.01));const m=new T.Mesh(geo,pm);m.position.set(0,y,zc);m.castShadow=true;g1.add(m);
    const tg=new T.CylinderGeometry(1,1,.004,14,1,true,sd>0?.08:-1.14,1.06);tg.scale(R*(1.03-i*.01),1,Z*(1.05-i*.01));const t=new T.Mesh(tg,M.metal);t.position.set(0,y-.015,zc);g1.add(t)}}
  const sg=new T.CylinderGeometry(1,1,n*.042-.008,3,1,true,-.03,.06);sg.scale(R*1.03,1,Z*1.05);const sm=new T.Mesh(sg,M.glow);sm.position.set(0,P1.y+.05-(n-1)*.021-P1.y,zc);g1.add(sm);
  for(const sd of[-1,1]){const p=new T.Mesh(new T.SphereGeometry(.006,8,6),M.glow);p.position.set(Math.sin(sd*1.0)*R*1.04,P1.y+.05-P1.y,zc+Math.cos(1.0)*Z*1.06);g1.add(p)}};
 const fr=(z0)=>cz+rz*z0;
 if(id==='vanguard'){barrel(1.08,1.12);collar(1.0,.035);
  /* sculpted front: two curved pectoral plates with gold piping and edge glow, graphite sternum with a light strip, clavicle plate and a core ring */
  const yc=cy+.035,hp=H*.62;for(const sd of[1,-1]){const a0=sd>0?.07:-1.07;arc(a0,1.0,hp,yc,1.14,1.22,M.pri,1.04);for(const dy of[-hp/2,hp/2])arc(a0+.01,.98,.007,yc+dy,1.155,1.235,M.metal);arc(sd>0?.93:-.97,.04,hp*.7,yc,1.152,1.232,M.glow);arc(sd>0?.2:-.8,.6,.004,yc-hp*.18,1.146,1.226,M.dark)}
  arc(-.07,.14,H*.84,cy+.02,1.11,1.17,M.sec);arc(-.016,.032,H*.62,cy+.02,1.12,1.18,M.glow);arc(-.95,1.9,.04,y1-.04,1.1,1.16,M.pri);arc(-.93,1.86,.006,y1-.062,1.112,1.172,M.metal);
  const core=new T.Mesh(new T.TorusGeometry(.024,.004,8,24),M.glow);core.position.set(0,cy+.0-P0.y,fr(1.19)-P0.z);g.add(core);const cc=new T.Mesh(new T.CylinderGeometry(.016,.016,.012,6),M.metal);cc.rotation.x=Math.PI/2;cc.position.copy(core.position);g.add(cc);for(const s of[-1,1]){bx89(g,P0,V89(s*rx*.75,y1-.02,cz),.11,.05,rz*1.6,M.pri,0,0,s*.25,.02);}
  bx89(g,P0,V89(0,cy,cz-rz*1.12),rx*1.4,H*.8,.05,M.pri,.06,0,0,.025);bx89(g,P0,V89(0,cy+.02,cz-rz*1.12-.04),.13,.14,.05,M.sec,0,0,0,.015);abs(3,M.sec,.92,1.05)}
 else if(id==='hood'){barrel(1.0,1.04,M.sec);collar(1.02,.045,M.cloth);for(const s of[-1,1]){const st=bx89(g,P0,V89(s*rx*.35,cy,fr(1.06)),.03,H*1.15,.012,M.dark,0,0,s*.42,.004);const sb=bx89(g,P0,V89(s*rx*.35,cy,cz-rz*1.06),.03,H*1.15,.012,M.dark,0,0,-s*.42,.004)}
  for(const [x,y] of[[-.07,0],[.07,0],[0,-.06]])bx89(g,P0,V89(x*(rx/.18),cy+y,fr(1.08)+.012),.055,.05,.03,M.pri,0,0,0,.008);bx89(g,P0,V89(0,cy+.05,fr(1.08)),rx*1.1,.06,.02,M.pri,0,0,0,.01);bx89(g,P0,V89(0,cy+.0,cz-rz*1.08),rx*1.2,H*.7,.03,M.pri,0,0,0,.02);
  bx89(g,P0,V89(-rx*.3,cy+.06,fr(1.1)+.03),.02,.005,.01,M.glow);abs(2,M.dark,.9,1.0)}
 else if(id==='seer'){barrel(1.02,1.06);collar(1.1,.05,M.metal);const ro=new T.CylinderGeometry(1,1.25,.62,24,1,true,-2.9,5.8);ro.scale(rx*1.05,1,rz*1.12);const rm=new T.Mesh(ro,M.clothP);rm.position.set(0,P1.y-.24-P1.y,cz-P1.z);g1.add(rm);
  bx89(g,P0,V89(0,cy+.01,fr(1.07)),rx*.55,H*.95,.025,M.metal,-.06,0,0,.02);bx89(g,P0,V89(0,cy+.02,fr(1.07)+.016),.012,H*.8,.01,M.glow);for(const s of[-1,1])bx89(g,P0,V89(s*rx*.62,cy+.02,fr(1.04)),rx*.4,H*.7,.02,M.sec,-.06,s*.3,0,.02);abs(2,M.metal,.88,1.02)}
 else if(id==='warden'){barrel(1.06,1.1);collar(.98,.04,M.metal);for(let i=0;i<3;i++)bx89(g,P0,V89(0,y1-.04-i*.075,fr(1.12)),rx*(1.6-i*.2),.07,.035,M.pri,-.12,0,0,.01);for(let i=0;i<3;i++)bx89(g,P0,V89(0,y1-.04-i*.075-.03,fr(1.12)+.02),rx*(1.5-i*.2),.006,.01,M.glow,-.12);
  for(const s of[-1,1])bx89(g,P0,V89(s*rx*.8,cy+.06,cz),.08,.14,rz*2.1,M.metal,0,0,s*.12,.02);bx89(g,P0,V89(0,cy,cz-rz*1.1),rx*1.5,H*.85,.04,M.pri,.05,0,0,.02);abs(3,M.metal,.9,1.04)}
 else if(id==='recon'){barrel(1.02,1.06);collar(1.0,.03,M.sec);bx89(g,P0,V89(0,cy+.02,fr(1.08)),rx*1.35,H*.85,.035,M.pri,-.08,0,0,.04);const c=new T.Mesh(new T.CylinderGeometry(.04,.04,.02,24),M.visorC);c.rotation.x=Math.PI/2-.08;c.position.set(0,cy+.03-P0.y,fr(1.08)+.024-P0.z);g.add(c);
  const ring=new T.Mesh(new T.TorusGeometry(.046,.005,8,28),M.glow);ring.rotation.x=-.08;ring.position.copy(c.position).add(V89(0,0,.008));g.add(ring);for(const s of[-1,1])bx89(g,P0,V89(s*rx*.62,cy-.05,fr(1.05)),.012,.1,.012,M.glow,-.08,0,s*.3,.004);bx89(g,P0,V89(0,cy,cz-rz*1.1),rx*1.3,H*.8,.06,M.sec,0,0,0,.025);
  for(const s of[-1,1]){const th=new T.Mesh(new T.CylinderGeometry(.022,.028,.08,12),M.metal);th.position.set(s*.06,cy-.06-P0.y,cz-rz*1.1-.05-P0.z);g.add(th);const fl=new T.Mesh(new T.CylinderGeometry(.018,.018,.004,12),M.glow);fl.position.copy(th.position).add(V89(0,-.042,0));g.add(fl)}abs(3,M.sec,.88,1.02)}}

/* ARMS (Arm, ForeArm, Hand mounts, both sides) */
function arms89(id,C,M,P,G){const f=C.sex==='female'?.9:1;for(const [S,s] of[['Left',1],['Right',-1]]){const A=P[S+'Arm'],F=P[S+'ForeArm'],Hd=P[S+'Hand'],gu=G(S+'Arm'),gf=G(S+'ForeArm'),gh=G(S+'Hand'),out=V89(s,0,0);
 const pauld=(rx,ry,rz,mat,lift)=>{const m=ell89(gu,A,A.clone().add(V89(s*.02,.035+(lift||0),.0)),rx*f,ry*f,rz*f,mat||M.pri,0,Math.PI*2,0,Math.PI*.55);m.rotation.z=-s*.45;return m};
 const glove=(mat)=>{const hd=P[S+'HandMiddle1']?P[S+'HandMiddle1'].clone().sub(Hd):V89(s*.3,-.3,.6);const m=bx89(gh,Hd,Hd.clone().addScaledVector(hd.normalize(),.045),.075*f,.03*f,.085*f,mat||M.sec,0,0,0,.01);orient89(m,hd,out);m.rotateX(Math.PI/2);return m};
 limb89(gu,A,A,F,.056*f,.05*f,M.sec,0,Math.PI*2,.18,.85,out);
 limb89(gf,F,F,Hd,.048*f,.043*f,M.dark,0,Math.PI*2,.08,.96,out);
 if(id==='vanguard'){pauld(.105,.075,.115);pauld(.092,.06,.1,M.metal,-.03);limb89(gf,F,F,Hd,.058*f,.052*f,M.pri,-1.6,3.6,.25,.95,out);limb89(gf,F,F,Hd,.06*f,.06*f,M.metal,0,Math.PI*2,.2,.27,out);glove(M.pri);limb89(gf,F,F,Hd,.059*f,.054*f,M.glow,-.15,.3,.45,.85,out)}
 else if(id==='hood'){pauld(.075,.05,.085,M.cloth);for(let i=0;i<4;i++)limb89(gf,F,F,Hd,.054*f,.052*f,i%2?M.cloth:M.sec,0,Math.PI*2,.2+i*.18,.32+i*.18,out);limb89(gf,F,F,Hd,.056*f,.05*f,M.pri,-1.2,2.4,.55,.95,out);glove(M.dark)}
 else if(id==='seer'){pauld(.085,.06,.095,M.metal);limb89(gu,A,A,F,.064*f,.06*f,M.clothP,0,Math.PI*2,.1,.6,out);limb89(gf,F,F,Hd,.057*f,.05*f,M.metal,0,Math.PI*2,.3,.95,out);for(let i=0;i<3;i++)limb89(gf,F,F,Hd,.059*f,.059*f,M.glow,0,Math.PI*2,.4+i*.16,.415+i*.16,out);glove(M.sec)}
 else if(id==='warden'){const p=pauld(.14,.11,.14);p.scale.multiplyScalar(1.05);pauld(.12,.09,.12,M.metal,-.045);const sp=new T.Mesh(new T.ConeGeometry(.02*f,.08*f,8),M.metal);sp.position.copy(A.clone().add(V89(s*.07,.13,.0)).sub(A));sp.rotation.z=-s*.5;gu.add(sp);
  limb89(gf,F,F,Hd,.062*f,.056*f,M.pri,0,Math.PI*2,.22,.95,out);limb89(gf,F,F,Hd,.064*f,.064*f,M.metal,0,Math.PI*2,.6,.66,out);glove(M.metal)}
 else if(id==='recon'){pauld(.09,.065,.1);limb89(gu,A,A,F,.06*f,.055*f,M.pri,-1.4,2.8,.2,.8,out);limb89(gf,F,F,Hd,.055*f,.05*f,M.pri,0,Math.PI*2,.3,.95,out);limb89(gf,F,F,Hd,.057*f,.052*f,M.glow,-.25,.5,.3,.95,out);glove(M.pri)}}}

/* LEGS (Hips belt, UpLeg, Leg, Foot mounts) */
function legs89(id,C,M,P,G){const fm=C.sex==='female',f=fm?.93:1,gh=G('Hips'),H0=P.Hips,hx0=Math.abs(P.LeftUpLeg.x)+(fm?.085:.075),kH=fitE89(H0.y+.01,H0.y+.08,hx0*1.05,hx0,fm?.135:.125,H0.z+(fm?0:-.01)),hx=hx0*kH,hz=(fm?.135:.125)*kH;
 const belt=(mat,h)=>{const geo=new T.CylinderGeometry(1,1,h||.05,28,1,true);geo.scale(hx,1,hz);const m=new T.Mesh(geo,mat||M.sec);m.position.set(0,.045,(fm?.0:-.01));gh.add(m);return m};
 const fauld=(w,h,mat,z,y,rx)=>{const m=bx89(gh,H0,V89(0,H0.y+(y||-.04),H0.z+z),w,h,.02,mat||M.pri,rx||0,0,0,.01);return m};
 belt(M.sec,.055);bx89(gh,H0,V89(0,H0.y+.045,H0.z+hz+.005),.06,.04,.02,M.metal,0,0,0,.008);
 for(const [S,s] of[['Left',1],['Right',-1]]){const U=P[S+'UpLeg'],K=P[S+'Leg'],Ft=P[S+'Foot'],Tb=P[S+'ToeBase']||Ft.clone().add(V89(0,-.06,.13)),gu=G(S+'UpLeg'),gk=G(S+'Leg'),gf=G(S+'Foot'),fw=V89(0,0,1);
  limb89(gu,U,U,K,.082*f,.062*f,M.sec,0,Math.PI*2,.1,.95,fw);limb89(gk,K,K,Ft,.058*f,.045*f,M.sec,0,Math.PI*2,.06,.9,fw);
  const boot=(mat,h)=>{const L=Tb.clone().sub(Ft);const c=Ft.clone().add(V89(0,-.02,.0)).addScaledVector(L,.45);const m=bx89(gf,Ft,c.clone().add(V89(0,.0,0)),.1*f,(h||.1)*f,.26*f,mat||M.pri,0,0,0,.035);m.position.y=(c.y-Ft.y)+.005;limb89(gk,K,K,Ft,.056*f,.05*f,mat||M.pri,0,Math.PI*2,.78,1.02,fw);return m};
  const knee=(mat,r)=>{const kc=K.clone().add(V89(s*.005,.0,.052*f));const m=ell89(gk,K,kc,(r||.052)*f,(r||.052)*1.1*f,.03*f,mat||M.metal);return m};
  const thighP=(mat,w)=>limb89(gu,U,U,K,.088*f,.068*f,mat||M.pri,-(w||1.2),2*(w||1.2),.22,.92,fw);const shin=(mat,w)=>limb89(gk,K,K,Ft,.064*f,.05*f,mat||M.pri,-(w||1.1),2*(w||1.1),.12,.8,fw);
  if(id==='vanguard'){thighP();shin();knee(M.metal,.06);boot();limb89(gk,K,K,Ft,.066*f,.052*f,M.glow,-.12,.24,.25,.65,fw);ell89(gu,U,U.clone().add(V89(s*.07,-.02,0)),.075*f,.06*f,.09*f,M.pri,0,Math.PI*2,0,Math.PI*.55).rotation.z=-s*.6}
  else if(id==='hood'){thighP(M.sec,.8);const hol=bx89(gu,U,U.clone().add(V89(s*.085*f,-.17,.0)),.03,.12,.07,M.dark,0,0,0,.01);shin(M.sec,.9);for(let i=0;i<3;i++)limb89(gk,K,K,Ft,.06*f,.055*f,M.cloth,0,Math.PI*2,.15+i*.2,.24+i*.2,fw);knee(M.dark,.045);boot(M.dark,.11)}
  else if(id==='seer'){limb89(gu,U,U,K,.09*f,.075*f,M.clothP,0,Math.PI*2,.05,.75,fw);shin(M.metal,.9);knee(M.metal,.05);boot(M.sec,.09);limb89(gk,K,K,Ft,.066*f,.052*f,M.glow,-.08,.16,.2,.7,fw)}
  else if(id==='warden'){thighP(M.pri,1.4);ell89(gu,U,U.clone().add(V89(s*.08,-.03,0)),.09*f,.075*f,.1*f,M.metal,0,Math.PI*2,0,Math.PI*.55).rotation.z=-s*.5;shin(M.pri,1.3);knee(M.metal,.07);const kp=new T.Mesh(new T.ConeGeometry(.018*f,.06*f,8),M.metal);kp.position.set(0,.0,.09*f);kp.rotation.x=Math.PI/2;gk.add(kp);boot(M.metal,.12)}
  else if(id==='recon'){thighP(M.pri,1);shin(M.pri,1);knee(M.sec,.05);boot(M.pri,.1);const th=new T.Mesh(new T.CylinderGeometry(.018,.022,.05,12),M.metal);th.position.set(0,.03,-.08*f);gf.add(th);const fl=new T.Mesh(new T.CylinderGeometry(.015,.015,.004,12),M.glow);fl.position.set(0,.003,-.08*f);gf.add(fl);limb89(gu,U,U,K,.09*f,.07*f,M.glow,-.1,.2,.3,.85,fw)}}
 if(id==='vanguard'){fauld(.16,.11,M.pri,hz+.01,-.03,-.1);fauld(.18,.12,M.pri,-hz-.01,-.03,.1)}else if(id==='warden'){for(const s of[-1,1]){const m=bx89(gh,H0,V89(s*hx*.9,H0.y-.03,H0.z),.03,.14,.16,M.pri,0,0,s*.15,.01)}fauld(.14,.13,M.metal,hz+.01,-.04,-.08)}else if(id==='seer'){fauld(.13,.2,M.clothP,hz+.006,-.09,-.06)}}

/* CLASS ITEMS (cloth pieces are animated in tick89) */
const strap89=(C,M,P,G,mat,shells)=>{const P2=P.Spine2,g=G('Spine2'),shX=Math.abs(P.LeftArm.x),rz=(C.sex==='female'?.158:.144)*(OUT.achest!=='none'&&C._kT89||1),cz=(OUT.achest!=='none'&&C._cz89||P2.z+.025),y1=P.LeftArm.y+.02,y0=P2.y-.04,cy=(y0+y1)/2,ang=Math.atan2(y1-y0,shX*1.7);for(const side of[1,-1]){const z=cz+side*rz+side*.008,m=bx89(g,P2,V89(0,cy,z),Math.hypot(shX*1.9,y1-y0),.05,.012,mat,side>0?-.08*side:.06,0,-ang*side,.005);if(shells&&side>0)for(let i=-3;i<=3;i++){const t=i/7,sm=new T.Mesh(new T.CylinderGeometry(.008,.008,.04,8),M.metal);sm.position.set(Math.cos(ang)*t*shX*1.9,cy-P2.y+Math.sin(-ang)*t*shX*1.9*-1+.0,z+.012-P2.z);sm.rotation.z=-ang;g.add(sm)}}};

function cloth89(w,h,nx,ny){const g=new T.PlaneGeometry(w,h,nx,ny);g.translate(0,-h/2,0);g.userData.base=g.attributes.position.array.slice();return g}
function shapeCloak89(g,hw,L){const P=g.attributes.position.array;for(let i=0;i<P.length;i+=3){const x=P[i],y=P[i+1],u=Math.min(1,-y/L),e=Math.abs(x)/hw;P[i]=x*(1-.28*u);P[i+2]=.085*e*e*(1-.6*u);P[i+1]=y-.1*u*(1-e*e)}g.userData.base=P.slice();g.attributes.position.needsUpdate=true;g.computeVertexNormals();return g}
function cls89(id,C,M,P,G){const f=C.sex==='female'?.92:1,P2=P.Spine2,shX=Math.abs(P.LeftArm.x),rz=(C.sex==='female'?.152:.138)*(OUT.achest!=='none'&&C._kT89||1),cz=(OUT.achest!=='none'&&C._cz89||P2.z+.025),y1=P.LeftArm.y+.03;C._cloth89=[];
 if(id==='cloak'){const g=G('Spine2'),cg=shapeCloak89(cloth89(shX*2.3,.95*f,8,12),shX*1.15,.95*f),m=new T.Mesh(cg,M.cloth);m.position.set(0,y1-P2.y,cz-rz*1.16-.075-P2.z);m.castShadow=true;g.add(m);C._cloth89.push({m,k:'cape',L:.95*f});const hd=new T.Mesh(new T.TorusGeometry(1,.035,8,24,Math.PI),M.cloth);hd.scale.set(shX*1.05,shX*.9,.9);hd.rotation.x=Math.PI/2;hd.rotation.z=Math.PI;hd.position.set(0,y1-.005-P2.y,cz-.01-P2.z);g.add(hd)}
 else if(id==='mark'){const g=G('Hips'),H0=P.Hips,cg=cloth89(.15*f,.42*f,3,8),m=new T.Mesh(cg,M.clothP),hz=C.sex==='female'?.14:.13;m.position.set(.03,.03,H0.z+hz+.012-H0.z);g.add(m);C._cloth89.push({m,k:'mark',L:.42*f});bx89(g,H0,V89(.03,H0.y+.03,H0.z+hz+.016),.1,.02,.01,M.metal);const e=new T.Mesh(new T.CircleGeometry(.025,6),M.glow);e.position.set(.03,-.06,hz+.016);g.add(e)}
 else if(id==='bandolier'){strap89(C,M,P,G,M.dark,1);const g=G('Hips');bx89(g,P.Hips,V89(-.12,P.Hips.y+.0,P.Hips.z+.1),.06,.07,.035,M.sec,0,.5,0,.01)}
 else if(id==='sash'){strap89(C,M,P,G,M.clothP,0);const g=G('Hips'),H0=P.Hips,cg=cloth89(.08,.32*f,2,6),m=new T.Mesh(cg,M.clothP),hz=C.sex==='female'?.14:.13;m.position.set(-.13,.03,hz*.6);m.rotation.y=-.9;g.add(m);C._cloth89.push({m,k:'mark',L:.32*f});bx89(g,H0,V89(-.13,H0.y+.035,H0.z+hz*.62),.05,.05,.03,M.metal,0,-.9,0,.01)}
 else if(id==='scarf'){const g=G('Neck'),N=P.Neck,t=new T.TorusGeometry(.075*f,.03*f,8,24);t.rotateX(Math.PI/2);const m=new T.Mesh(t,M.cloth);m.position.set(0,-.03,.01);g.add(m);const g2=G('Spine2'),cg=cloth89(.11,.55*f,2,8),tail=new T.Mesh(cg,M.cloth);tail.position.set(.07,(N.y-.05)-P2.y,cz-rz-.02-P2.z);g2.add(tail);C._cloth89.push({m:tail,k:'cape',L:.55*f})}
 else if(id==='tails'){const g=G('Hips'),H0=P.Hips,hz=C.sex==='female'?.14:.13;for(const s of[-1,1]){const cg=cloth89(.14,.55*f,2,8),m=new T.Mesh(cg,M.clothP);m.position.set(s*.075,.02,-hz-.015);m.rotation.y=Math.PI+s*.15;g.add(m);C._cloth89.push({m,k:'cape',L:.55*f,flip:1})}}
 else if(id==='pack'){const g=G('Spine2');bx89(g,P2,V89(0,(P2.y+y1)/2,cz-rz-.08),.28*f,.32*f,.13,M.sec,0,0,0,.03);bx89(g,P2,V89(0,(P2.y+y1)/2-.12,cz-rz-.15),.24*f,.1,.05,M.pri,0,0,0,.015);bx89(g,P2,V89(0,(P2.y+y1)/2+.08,cz-rz-.145),.12,.012,.01,M.glow)}}

/* ---------- assemble + wear ---------- */
var ARMOR89={sig:'',grps:[]};
function clearArmor89(C){if(C._m89)for(const k in C._m89){const g=C._m89[k];while(g.children.length){const o=g.children[0];g.remove(o);o.traverse(q=>{if(q.geometry)q.geometry.dispose()})}}C._cloth89=[]}
function buildArmor89(C,force){if(!C||!C.mh)return;const sh=shader89(),H=OUT.ahelmet;try{if(H==='cap'||H==='beanie')mhHat(C,H,sh.pri);else if(H!=='none')mhHat(C,'none')}catch(e){}
 const sig=[C.sex,OUT.ahelmet,OUT.aarms,OUT.achest,OUT.alegs,OUT.acls,sh.pri,sh.sec,sh.glow,sh.metal].join('|');if(!force&&C._sig89===sig)return;C._sig89=sig;clearArmor89(C);
 const P=rest89(C),M=amats89(),G=bn=>mount89(C,bn);
 try{if(H!=='none'&&H!=='cap'&&H!=='beanie')helmet89(H,C,M,P,G)}catch(e){console.warn('helm89',e)}
 for(const [fn,k] of[[chest89,'achest'],[arms89,'aarms'],[legs89,'alegs'],[cls89,'acls']]){try{if(OUT[k]&&OUT[k]!=='none')fn(OUT[k],C,M,P,G)}catch(e){console.warn('armor89',k,e)}}
 for(const g of Object.values(C._m89||{}))g.traverse(o=>{if(o.isMesh){o.castShadow=!o.material.transparent;o.frustumCulled=false}})}
/* clothes under armor: a fitted undersuit in the shader's secondary colour, hair hidden under closed helmets */
{const oA=mhApplyOutfit;mhApplyOutfit=function(C){if(!C||!C.mh||C!==CHAR)return oA.apply(this,arguments);const save={},set=(k,v)=>{save[k]=OUT[k];OUT[k]=v};const sh=shader89(),dark=new T.Color(sh.sec).multiplyScalar(.55).getHex();
 if(OUT.achest!=='none'){set('mtop','shirt');set('mouter','none');set('top',dark)}if(OUT.alegs!=='none'){set('mbot','jeans');set('pants',dark);set('mshoe','shoes');set('shoes',0x15161a)}
 if(OUT.ahelmet!=='none'&&OUT.ahelmet!=='cap'&&OUT.ahelmet!=='beanie'){set('mhair','none');set('hat','none')}if(OUT.ahelmet==='cap'||OUT.ahelmet==='beanie')set('hat','none');if(OUT.acls!=='none')set('packOn',false);
 let r;try{r=oA.apply(this,arguments)}finally{Object.assign(OUT,save)}try{buildArmor89(C)}catch(e){console.warn('arm89',e)}return r}}
