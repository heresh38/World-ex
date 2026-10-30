
/* ---------- gunplay kit: frag grenade (G), melee bash (F), dodge roll (Z), slide (C) — no supers, no elemental powers ---------- */
var A89={gr:0,me:0,cl:0,slide:0,sDir:new T.Vector3(),sSp:0,dodge:0,dDir:new T.Vector3(),dSp:0,inv:0,bash:0,throwT:0,lunge:0,lTgt:null,proj:[],fx:[]};
function sv89(k){return stats89()[k]||0}
function cd89(base,stat){const s=sv89(stat);return base*(1-.45*Math.min(1,s/100))*(1-.15*Math.max(0,s-100)/100)}
function mult89(stat,max){return 1+max*Math.max(0,sv89(stat)-100)/100}
function grounded89(){return pl.y<=Gw(pl.x,pl.z)+.12||!!pl.sw}
function canAct89(){return started&&!paused&&!menuOpen&&!invOpen&&!(typeof homeOpen!=='undefined'&&homeOpen)&&!(typeof ED!=='undefined'&&ED.on)&&!cur&&pdead<=0}
function look89(){const p=(typeof FUN!=='undefined'&&FUN.q0)||cam.quaternion;return new T.Vector3(0,0,-1).applyQuaternion(p).normalize()}
function targets89(){const out=[];for(const p of allPeds()){if(p.dead||!p.g)continue;out.push({p,pos:p.g.position.clone().add(new T.Vector3(0,1.1,0))})}return out}
function hitT89(t,dmg,from,kb){const a=Math.atan2(t.pos.x-from.x,t.pos.z-from.z);hitPed(t.p,dmg*(t.p.mx||40)/100,Math.sin(a)*(kb||6),Math.cos(a)*(kb||6))}
function snd89(kind){try{if(kind==='throw'){tone87('sine',500,900,.1,.04);noise87(.08,3000,.04,'highpass')}else if(kind==='boom'){noise87(.7,520,.34);tone87('sine',70,28,.55,.28)}else if(kind==='melee'){noise87(.14,1500,.16);tone87('square',200,80,.1,.05)}else if(kind==='roll'){noise87(.3,900,.1);tone87('sine',140,90,.2,.04)}else if(kind==='slide'){noise87(.6,700,.07,'bandpass',1)}else if(kind==='ready'){tone87('sine',880,1320,.1,.03)}}catch(e){}}
/* frag grenade: thrown, bounces, 2.2 s fuse */
function grenade89(){if(!canAct89()||A89.gr>0)return;A89.gr=cd89(20,'grenade');A89.throwT=.45;const d=look89(),o=FP?cam.position.clone().addScaledVector(d,.55).add(new T.Vector3(0,-.15,0)):new T.Vector3(pl.x,pl.y+1.6,pl.z).addScaledVector(d,.5);
 const g=new T.Group(),body=new T.Mesh(new T.SphereGeometry(.055,14,10),new T.MeshStandardMaterial({color:0x3d4630,roughness:.6,metalness:.3}));body.scale.set(1,1.15,1);g.add(body);const cap=new T.Mesh(new T.CylinderGeometry(.02,.022,.03,10),new T.MeshStandardMaterial({color:0x8a8f96,metalness:.8,roughness:.3}));cap.position.y=.07;g.add(cap);
 const led=new T.Mesh(new T.SphereGeometry(.012,8,6),new T.MeshBasicMaterial({color:0xff3020,toneMapped:false}));led.position.set(0,.035,.05);g.add(led);g.position.copy(o);actScene79().add(g);
 A89.proj.push({m:g,led,p:o.clone(),v:d.clone().multiplyScalar(17).add(new T.Vector3(0,4,0)).add(new T.Vector3(pl.vx||0,0,pl.vz||0)),t:0,spin:new T.Vector3(Math.random()*8,Math.random()*8,0)});snd89('throw');uiAb89(true)}
function boom89(pt){snd89('boom');const dm=mult89('grenade',.6);fxw87(pt.clone(),false,4.5,.25,null,1.6,0xffd090,true);for(let i=0;i<9;i++)fxw87(pt.clone().add(new T.Vector3((Math.random()-.5)*2,Math.random()*1.2,(Math.random()-.5)*2)),false,1.4+Math.random()*1.4,.45+Math.random()*.3,new T.Vector3((Math.random()-.5)*5,1.5+Math.random()*3,(Math.random()-.5)*5),1.8,0xff8a30,true);
 try{for(let i=0;i<8;i++)fx79(pt.clone().add(new T.Vector3((Math.random()-.5)*2,Math.random()*1.4,(Math.random()-.5)*2)),true,1.6+Math.random()*2,2.2+Math.random(),new T.Vector3((Math.random()-.5)*2,1.2+Math.random()*1.5,(Math.random()-.5)*2),2.6,0x5a5550)}catch(e){}
 for(let i=0;i<5;i++)try{impact(pt.x+(Math.random()-.5),pt.y+.2,pt.z+(Math.random()-.5))}catch(e){}
 const R=5.5;let n=0;for(const t of targets89()){const e=t.pos.distanceTo(pt);if(e<R){hitT89(t,(150*(1-e/R)+40)*dm,pt,10*(1-e/R)+3);n++}}if(n)hitMark();const me=new T.Vector3(pl.x,pl.y+1,pl.z),e=me.distanceTo(pt);if(e<R*.8)hurt((1-e/(R*.8))*45)}
/* melee: quick weapon bash or punch; with the melee charge ready it lunges and hits much harder */
function melee89(){if(!canAct89())return;const charged=A89.me<=0,d=look89();d.y=0;d.normalize();const me=new T.Vector3(pl.x,pl.y+1.1,pl.z);let best=null,bd=charged?5.5:2.4;for(const t of targets89()){const v=t.pos.clone().sub(me),L=Math.hypot(v.x,v.z);if(L>bd)continue;if((v.x*d.x+v.z*d.z)/Math.max(.01,L)<.55)continue;best=t;bd=L}
 snd89('melee');if(!gunOn){startAct('push');if(!charged||!best)return}else{A89.bash=.32}
 const dm=mult89('melee',.3);if(charged&&best){A89.me=cd89(9,'melee');A89.lunge=.16;A89.lTgt=best.pos.clone();uiAb89(true)}
 if(best){const ch=charged;setTimeout(()=>{hitT89(best,(ch?120:38)*dm,me,ch?13:6);hitMark(ch);try{impact(best.pos.x,best.pos.y,best.pos.z)}catch(e){}},ch?160:110)}}
/* dodge roll: quick evasive roll in the movement direction (backwards if standing still) */
function dodge89(){if(!canAct89()||A89.cl>0||!grounded89()||pl.sw)return;A89.cl=cd89(7,'mobility');snd89('roll');const fx=Math.sin(camA),fz=Math.cos(camA),K=KEYS89,f=(K.KeyW?1:0)-(K.KeyS?1:0),r=(K.KeyD?1:0)-(K.KeyA?1:0);let dx=fx*f-fz*r,dz=fz*f+fx*r;if(Math.hypot(dx,dz)<.1){dx=-fx;dz=-fz}const L=Math.hypot(dx,dz);
 A89.dodge=.42;A89.dSp=11*(1+.15*Math.min(1,sv89('mobility')/100));A89.dDir.set(dx/L,0,dz/L);A89.inv=.3;pl.st=0;uiAb89(true)}
/* slide: crouch while sprinting */
function slide89(){if(!canAct89()||!grounded89()||A89.slide>0||A89.dodge>0)return false;const sp=Math.hypot(pl.vx||0,pl.vz||0);if(sp<5)return false;A89.slide=.85;A89.sSp=Math.max(sp*1.2,8.5);A89.sDir.set(pl.vx/sp,0,pl.vz/sp);pl.st=0;snd89('slide');return true}
var KEYS89={};
addEventListener('keydown',e=>{KEYS89[e.code]=true;if(!canAct89()||e.repeat)return;const c=e.code;let eat=false;
 if(c==='KeyG'){grenade89();eat=true}else if(c==='KeyF'){melee89();eat=true}else if(c==='KeyZ'){dodge89();eat=true}else if(c==='KeyC'){if(slide89())eat=true}else if(c==='KeyK'){try{proneKey()}catch(er){}eat=true}else if(c==='KeyJ'){try{cycleGear()}catch(er){}eat=true}
 if(eat){e.stopImmediatePropagation();e.preventDefault()}},true);
addEventListener('keyup',e=>{KEYS89[e.code]=false},true);addEventListener('blur',()=>{for(const k in KEYS89)KEYS89[k]=false});
/* movement: mobility stat, slide, roll, melee lunge */
{const oF=footMove;footMove=function(inp,dt){const r=oF.apply(this,arguments);try{
 const mob=1+.12*Math.min(1,sv89('mobility')/100);if(grounded89()&&!A89.slide&&!A89.dodge){pl.x+=(pl.vx||0)*dt*(mob-1);pl.z+=(pl.vz||0)*dt*(mob-1)}
 if(A89.slide>0){A89.slide-=dt;const k=Math.max(0,A89.slide/.85),sp=2.4+(A89.sSp-2.4)*k*k;const down=Gw(pl.x+A89.sDir.x,pl.z+A89.sDir.z)<Gw(pl.x,pl.z)-.05;pl.vx=A89.sDir.x*sp*(down?1.15:1);pl.vz=A89.sDir.z*sp*(down?1.15:1);if(A89.slide<=0&&KEYS89.KeyC)pl.st=1}
 if(A89.dodge>0){A89.dodge-=dt;const k=Math.max(0,A89.dodge/.42);pl.vx=A89.dDir.x*A89.dSp*(.3+.7*k);pl.vz=A89.dDir.z*A89.dSp*(.3+.7*k)}
 if(A89.lunge>0&&A89.lTgt){A89.lunge-=dt;const v=A89.lTgt.clone().sub(new T.Vector3(pl.x,pl.y+1.1,pl.z));v.y=0;const L=v.length();if(L>1.3){v.normalize();pl.vx=v.x*20;pl.vz=v.z*20}else{pl.vx*=.3;pl.vz*=.3}}}catch(e){}return r}}
/* stat hooks: health, recovery, weapons */
{const oH=hurt;hurt=function(a){if(A89.inv>0)return;const h=sv89('health');a*=1-.22*Math.min(1,h/100)-.08*Math.max(0,h-100)/100;return oH.call(this,a)}}
{const oR=regenStep;regenStep=function(dt){const rc=sv89('recovery');if(!paused&&pdead<=0)tSinceHurt+=dt*1.2*Math.min(1.6,rc/100);const r=oR.apply(this,arguments);try{if(!paused&&pdead<=0&&php<100&&tSinceHurt>10)php=Math.min(100,php+4*dt*Math.min(2,rc/100))}catch(e){}return r}}
{const oR=reload;reload=function(){const r=oR.apply(this,arguments);try{if(WST.rl>0&&WST.rlKind!=='shell'){const k=1-.3*Math.min(1,sv89('weapons')/100);WST.rl*=k;WST.rlT*=k}}catch(e){}return r}}
/* bullet damage bonus from Weapons (bullet hits only) */
var WB89=0;{const oB=bulletStep;bulletStep=function(){WB89=1;try{return oB.apply(this,arguments)}finally{WB89=0}}}
{const oH=hitPed;hitPed=function(p,a){if(WB89)arguments[1]=a*(1+.1*Math.min(1,sv89('weapons')/100));return oH.apply(this,arguments)}}
/* viewmodel: weapon bash, grenade toss dip, slide cant, roll dip */
{const oA=wpnAnimOff;wpnAnimOff=function(){const r=oA.apply(this,arguments);if(A89.bash>0){const p=1-A89.bash/.32,b=Math.sin(Math.PI*Math.min(1,p*1.4));r.dz+=.14*b;r.pitch+=-.35*b;r.roll+=.25*b;r.dy+=.03*b}if(A89.throwT>0){const p=1-A89.throwT/.45,b=Math.sin(Math.PI*p);r.dy-=.16*b;r.pitch+=.5*b;r.roll+=.3*b}if(A89.slide>0){r.roll+=.2;r.dy-=.012}if(A89.dodge>0){const p=1-A89.dodge/.42;r.dy-=.08*Math.sin(Math.PI*p);r.roll+=.4*Math.sin(Math.PI*p)}return r}}
