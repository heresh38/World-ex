
/* ===== v96b: landing zones get real geometry physics (walk inside wrecks/ruins, bullets hit what you see) and an Earth sky with ship traffic instead of planets ===== */
/* ---------- walkable crashed ship: torn hull, interior deck, bulkheads with doorways ---------- */
kitWreck88=function(g,R,M,sc){sc=sc||1;if(!M._w96){M._w96=1;M.hullS=mat88({t:'w4c',c:0xe2dccd,r:.6,m:.25,side:1});M.hull=mat88({t:'w4c',c:0xe2dccd,r:.6,m:.25});M.metalD=mat88({t:'sbrick',c:0x8d939b,r:.55,m:.5});M.metalDS=mat88({c:0x3a3e45,r:.5,m:.6,side:1})}const prof=[[.01,-46],[5,-44],[8.5,-38],[10,-26],[10.4,-8],[10.4,-1]].map(p=>new T.Vector2(p[0]*sc,p[1]*sc)),prof2=[[10.2,1],[10.2,6],[9.6,20],[7.6,32],[4.4,41],[.01,46]].map(p=>new T.Vector2(p[0]*sc,p[1]*sc));
 const hull=new T.Group();g.add(hull);const gapC=Math.PI/2,gapW=.95;
 const parts=[[prof,gapC+gapW,Math.PI*2-gapW*2,0,-.05],[prof2,gapC+gapW*.7,Math.PI*2-gapW*1.4,7*sc,.08]];
 for(const[pr,ps,pl,dz,yaw]of parts){const lg=new T.LatheGeometry(pr,22,ps,pl);uvs88(lg,6,6);const part=new T.Group();part.position.z=dz;part.rotation.y=yaw;hull.add(part);add88(part,lg,M.hullS,0,0,0,Math.PI/2,0,0,1,1,.72)}
 /* deck at ground level inside the hull + ribs + bulkheads with doorways */
 const deckY=(.35-3.2)*sc;add88(hull,box88(13*sc,.4*sc,78*sc),M.metalD,0,deckY,0);
 for(let z=-36;z<=36;z+=6){const r=add88(hull,new T.TorusGeometry(9.6*sc,.35*sc,6,18,Math.PI*1.1),M.metalDS,0,0,z*sc,0,0,Math.PI*.95);r.scale.y=.72}
 for(const z of[-20,0,20]){const H=7*sc,W=12*sc,dw=3.2*sc,dh=4.4*sc;add88(hull,box88((W-dw)/2,H,.4*sc),M.metalD,-(dw/2+(W-dw)/4),deckY+H/2,z*sc);add88(hull,box88((W-dw)/2,H,.4*sc),M.metalD,(dw/2+(W-dw)/4),deckY+H/2,z*sc);add88(hull,box88(dw,H-dh,.4*sc),M.metalD,0,deckY+dh+(H-dh)/2,z*sc)}
 add88(hull,box88(1.2*sc,1.2*sc,16*sc),M.metalD,0,6.8*sc,-1*sc);
 for(const s of[-1,1]){const fin=new T.Shape();fin.moveTo(0,0);fin.lineTo(14*sc,-4*sc);fin.lineTo(16*sc,-12*sc);fin.lineTo(2*sc,-10*sc);const fg=new T.ExtrudeGeometry(fin,{depth:.8*sc,bevelEnabled:false});const m=add88(hull,fg,M.hull,s*6*sc,0,-30*sc,0,s>0?Math.PI/2:-Math.PI/2,0);m.rotation.z=s*.3}
 for(const [x,y] of[[-3.5,-1],[3.5,-1],[0,3]]){add88(hull,new T.CylinderGeometry(2.6*sc,3.2*sc,5*sc,14,1,true),M.metalDS,x*sc,y*sc,-46*sc,Math.PI/2,0,0);add88(hull,new T.CircleGeometry(2.4*sc,14),M.engine,x*sc,y*sc,-47.5*sc,0,Math.PI,0)}
 /* interior lights so the inside reads */for(let z=-30;z<=30;z+=15){const l=add88(hull,box88(.6*sc,.15*sc,2.4*sc),M.glowA,0,deckY+6.4*sc,z*sc);l.castShadow=false}
 for(let i=0;i<14;i++){const s=(1+R()*3)*sc;add88(g,box88(s*2,s*.4,s),M.hull,(R()-.5)*30*sc,s*.15,(R()-.5)*80*sc,R()*.6,R()*3,R()*.6)}
 hull.rotation.set(.02,R()*6.28,.06);hull.position.y=3.2*sc};
LMN88.ring='Sundered Ring';

/* ---------- geometry collision for landing zones ---------- */
const COLL96=collide;/* the city collider, restored when leaving a landing zone */
var COL96={list:[],mat:null,rc:null,saved:null,_o:new T.Vector3(),_d:new T.Vector3(),_n:new T.Vector3(),_m3:new T.Matrix3()};
colliders88=function(){};/* no more invisible cylinders/boxes around ruins: the meshes themselves collide */
function col96Ensure(){const L=window.MESHBVH;if(!L)return false;if(!T.BufferGeometry.prototype.computeBoundsTree){T.BufferGeometry.prototype.computeBoundsTree=L.computeBoundsTree;T.BufferGeometry.prototype.disposeBoundsTree=L.disposeBoundsTree;T.Mesh.prototype.raycast=L.acceleratedRaycast}if(!COL96.rc){COL96.rc=new T.Raycaster();COL96.rc.firstHitOnly=true}if(!COL96.mat)COL96.mat=new T.MeshBasicMaterial({side:T.DoubleSide});return true}
function col96Build(root){COL96.list=[];if(!root||!col96Ensure())return;root.updateMatrixWorld(true);const vis=[];
 root.traverse(o=>{if(!o.isMesh||o.isInstancedMesh||o.isPoints||o.isSprite)return;let p=o;while(p){if(p.name==='Alien flora')return;p=p.parent}const g=o.geometry;if(!g||!g.attributes.position)return;if(!g.boundingSphere)g.computeBoundingSphere();try{if(!g.boundsTree)g.computeBoundsTree({targetLeafSize:16})}catch(e){return}
  const c=new T.Mesh(g,COL96.mat);c.matrixAutoUpdate=false;c.matrixWorld.copy(o.matrixWorld);c.userData.src=o;const s=g.boundingSphere.clone().applyMatrix4(o.matrixWorld);COL96.list.push({m:c,s,src:o});vis.push(o)});
 return vis}
function col96Near(x,y,z,r){const out=[];for(const c of COL96.list){const s=c.s,dx=s.center.x-x,dy=s.center.y-y,dz=s.center.z-z,R=s.radius+r;if(dx*dx+dy*dy+dz*dz<R*R)out.push(c)}return out}
function col96Ray(near,o,d,far){const rc=COL96.rc;rc.set(o,d);rc.near=0;rc.far=far;let best=null;for(const c of near){const h=c.m.raycast?null:null;const arr=[];c.m.raycast(rc,arr);if(arr.length){arr.sort((a,b)=>a.distance-b.distance);if(!best||arr[0].distance<best.distance)best=arr[0]}}return best}
/* horizontal push-out against walls (player: knee/chest/head; vehicles: body height) */
function col96Push(o,r){if(!COL96.list.length||o.x===undefined)return false;const isP=o===pl,y0=(o.y!==undefined?o.y:0),hs=isP?[.35,.95,1.55]:[.7,1.3],near=col96Near(o.x,y0+1,o.z,r+3);if(!near.length)return false;let hit=false;const O=COL96._o,D=COL96._d,N=COL96._n;
 for(const h of hs){for(let k=0;k<8;k++){const a=k/8*Math.PI*2;D.set(Math.sin(a),0,Math.cos(a));O.set(o.x,y0+h,o.z);const q=col96Ray(near,O,D,r+.05);if(!q||q.distance>=r)continue;let nx=-D.x,nz=-D.z;if(q.face){N.copy(q.face.normal).applyMatrix3(COL96._m3.getNormalMatrix(q.object.matrixWorld));if(Math.abs(N.y)>.7)continue;if(N.x*D.x+N.z*D.z>0){N.x=-N.x;N.z=-N.z}const l=Math.hypot(N.x,N.z);if(l>.2){nx=N.x/l;nz=N.z/l}}
  const pen=r-q.distance;o.x+=nx*pen;o.z+=nz*pen;if(o.vx!==undefined){const vn=o.vx*nx+o.vz*nz;if(vn<0){o.vx-=vn*nx;o.vz-=vn*nz}}hit=true}}return hit}
/* floors: the top surface under the body (decks, ramps, rubble) counts as ground */
function col96Floor(x,z,y){if(!COL96.list.length)return -1e9;const near=col96Near(x,y,z,4);if(!near.length)return -1e9;const O=COL96._o.set(x,y+.6,z),D=COL96._d.set(0,-1,0),q=col96Ray(near,O,D,4.5);if(!q)return -1e9;if(q.face){const N=COL96._n.copy(q.face.normal).applyMatrix3(COL96._m3.getNormalMatrix(q.object.matrixWorld));if(Math.abs(N.y)<.55)return -1e9}return q.point.y}
function col96Ceil(x,z,y){if(!COL96.list.length)return 1e9;const near=col96Near(x,y+1,z,3);if(!near.length)return 1e9;const q=col96Ray(near,COL96._o.set(x,y+.9,z),COL96._d.set(0,1,0),1.2);return q?q.point.y:1e9}
{const oE=genEnter;genEnter=async function(){const r=await oE.apply(this,arguments);try{if(GEN.on&&A88&&A88.grp){const vis=col96Build(A88.grp);COL96.saved={list:BVH.list,rc:BVH.rc,ready:BVH.ready};if(vis&&vis.length&&COL96.rc){BVH.list=vis;BVH.rc=BVH.rc||COL96.rc;BVH.ready=true}
   const g0=Gw;const fl=(x,z)=>{const g=genH(x,z);if(_qy===null||_qy===undefined)return g;const f=col96Floor(x,z,_qy);return f>g?f:g};Gw=fl;Hp=fl;
   if(GEN.fn)GEN.fn.collide=COLL96;collide=function(o,r){let h=false;try{h=genCollide88(o,r)}catch(e){}try{h=col96Push(o,r)||h}catch(e){}return h}}}catch(e){console.warn('col96',e)}return r}}
{const oL=genLeave;genLeave=function(){const r=oL.apply(this,arguments);try{if(COL96.saved){BVH.list=COL96.saved.list;BVH.rc=COL96.saved.rc;COL96.saved=null}COL96.list=[]}catch(e){}return r}}
/* head bump: no jumping through a ceiling */
{const oF=footMove;footMove=function(inp,dt){const r=oF.apply(this,arguments);try{if(GEN.on&&COL96.list.length&&pl.vy>0){const c=col96Ceil(pl.x,pl.z,pl.y);if(pl.y+1.85>c){pl.vy=0;pl.y=Math.min(pl.y,c-1.86)}}if(GEN.on&&COL96.list.length&&!cur)col96Push(pl,.38)}catch(e){}return r}}

/* ---------- Earth sky: distant ship traffic instead of planets/moons-that-aren't ---------- */
function shipMats96(){if(shipMats96.m)return shipMats96.m;const M=(c,r,m,e,ei)=>{const q=new T.MeshStandardMaterial({color:c,roughness:r,metalness:m,fog:false});if(e){q.emissive=new T.Color(e);q.emissiveIntensity=ei||1}q.userData.noConv=1;return q};
 return shipMats96.m={hull:M(0x9aa1aa,.5,.55,0x1a1d22,1),dark:M(0x34383f,.45,.7,0x0b0d10,1),bone:M(0xe4ded0,.55,.25,0x2a2824,1),brass:M(0xc9a24c,.35,.85,0x2a2010,1),glow:new T.MeshBasicMaterial({color:0x9fd8ff,fog:false,toneMapped:false}),warm:new T.MeshBasicMaterial({color:0xffc070,fog:false,toneMapped:false}),red:new T.MeshBasicMaterial({color:0xff3b2f,fog:false,toneMapped:false})}}
function ship96(R,kind){const M=shipMats96(),g=new T.Group();
 const ext=(pts,depth,bev,m,y)=>{const sh=new T.Shape();sh.moveTo(pts[0][0],pts[0][1]);for(let i=1;i<pts.length;i++)sh.lineTo(pts[i][0],pts[i][1]);sh.closePath();const geo=new T.ExtrudeGeometry(sh,{depth,bevelEnabled:true,bevelThickness:bev,bevelSize:bev,bevelSegments:2,curveSegments:4});geo.translate(0,0,-depth/2);geo.rotateX(Math.PI/2);const me=new T.Mesh(geo,m);me.position.y=y||0;g.add(me);return me};
 const box=(w,h,d,m,x,y,z)=>{const b=new T.Mesh(new T.BoxGeometry(w,h,d),m);b.position.set(x,y,z);g.add(b);return b};
 const eng=(x,y,z,r,L)=>{const c=new T.Mesh(new T.CylinderGeometry(r,r*1.15,L,14),M.dark);c.rotation.x=Math.PI/2;c.position.set(x,y,z);g.add(c);const e=new T.Mesh(new T.CircleGeometry(r*.85,14),M.glow);e.position.set(x,y,z-L/2-.001);e.rotation.y=Math.PI;g.add(e)};
 if(kind==='capital'){/* top-view wedge hull, nose toward +z */
  ext([[0,.62],[.07,.36],[.15,.05],[.17,-.32],[.12,-.5],[-.12,-.5],[-.17,-.32],[-.15,.05],[-.07,.36]],.05,.012,M.bone,0);
  ext([[0,.44],[.08,.1],[.1,-.3],[.07,-.46],[-.07,-.46],[-.1,-.3],[-.08,.1]],.035,.01,M.hull,.045);
  ext([[0,.3],[.05,0],[.06,-.3],[-.06,-.3],[-.05,0]],.04,.008,M.dark,-.045);
  /* bridge tower */box(.07,.045,.09,M.hull,0,.09,-.3);box(.05,.03,.06,M.bone,0,.125,-.31);box(.09,.008,.03,M.dark,0,.141,-.29);
  /* brass trim stripes */for(const s of[-1,1]){const t=box(.004,.006,.5,M.brass,s*.13,.028,-.08);t.rotation.y=s*.12}
  for(let k=0;k<6;k++){const s=k%2?1:-1;box(.03,.02,.05,M.dark,s*(.1+R()*.03),.05,-.1-k*.05)}
  eng(0,.0,-.53,.045,.08);eng(-.09,.0,-.52,.035,.07);eng(.09,.0,-.52,.035,.07);
  for(let k=0;k<40;k++){const w=new T.Mesh(new T.BoxGeometry(.003,.003,.003),R()<.12?M.red:M.warm);const zz=(R()-.5)*.9;w.position.set((R()<.5?-1:1)*(.02+R()*.12*(1-Math.abs(zz))),.03+R()*.03,zz);g.add(w)}}
 else if(kind==='freighter'){box(.035,.035,.8,M.dark,0,0,0);for(let i=0;i<7;i++)for(const s of[-1,1])box(.05,.045,.09,i%3===0?M.brass:(i%2?M.bone:M.hull),s*.045,0,-.28+i*.095);
  ext([[0,.14],[.05,0],[.05,-.06],[-.05,-.06],[-.05,0]],.05,.01,M.bone,0).position.z=.42;eng(-.03,0,-.42,.025,.06);eng(.03,0,-.42,.025,.06)}
 else{ext([[0,.18],[.03,.02],[.16,-.12],[.14,-.15],[0,-.1],[-.14,-.15],[-.16,-.12],[-.03,.02]],.012,.004,M.bone,0);ext([[0,.2],[.018,0],[.02,-.13],[-.02,-.13],[-.018,0]],.025,.006,M.hull,.01);eng(0,.005,-.14,.012,.03)}
 g.traverse(o=>{o.frustumCulled=false;o.castShadow=false;o.receiveShadow=false;o.renderOrder=-1});return g}
skyBody88=function(kind,E,grp){const out=[],R=rng88(((E&&E.seed)||0)+kind.length*31+7);const mk=(dir,dist,obj,scale,drift)=>{obj.scale.setScalar(scale);obj.userData.sky88={dir:new T.Vector3(...dir).normalize(),dist};obj.userData.drift96=drift;grp.add(obj);out.push(obj)};
 const nCap=1+Math.floor(R()*2);for(let i=0;i<nCap;i++){const a=(R()-.5)*1.6,el=.18+R()*.22;mk([Math.sin(a),el,-Math.cos(a)],2600+R()*800,ship96(R,'capital'),380+R()*260,(R()<.5?-1:1)*(.004+R()*.004))}
 for(let i=0;i<2;i++){const a=(R()-.5)*2.4,el=.1+R()*.15;mk([Math.sin(a),el,-Math.cos(a)],1800+R()*600,ship96(R,'freighter'),120+R()*60,(R()<.5?-1:1)*(.01+R()*.01))}
 for(let i=0;i<5;i++){const a=R()*6.28,el=.12+R()*.3;mk([Math.sin(a),el,-Math.cos(a)],900+R()*500,ship96(R,'fighter'),26+R()*14,(R()<.5?-1:1)*(.03+R()*.03))}
 return out};
{const oP=preRender;preRender=function(){oP.apply(this,arguments);try{if(!(typeof GEN!=='undefined'&&GEN.on&&A88.on))return;const n=performance.now(),dt=Math.min(.05,(n-(COL96.st||n))/1000);COL96.st=n;const Y=COL96._yy||(COL96._yy=new T.Vector3(0,1,0));
  for(const o of A88.sky){const w=o.userData.drift96;if(!w)continue;const s=o.userData.sky88;s.dir.applyAxisAngle(Y,w*dt);const tx=-s.dir.z*Math.sign(w),tz=s.dir.x*Math.sign(w);o.rotation.set(0,Math.atan2(tx,tz),0)}}catch(e){}}}
