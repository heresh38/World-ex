/* ---------- integration with the shared vehicle code ---------- */
for(const k of Object.keys(CARDEF))delete CARDEF[k];for(const k in HVD97)CARDEF[k]=HVD97[k].stats;
SPAWN.length=0;SPAWN.push('aether','vanta','bastion','courier','lumen','ronin','brass');
NPCCOL.length=0;NPCCOL.push(0x1a1d24,0xe6e0d0,0x5a1428,0x2a3a52,0x33363c,0x6d7262,0xc9a24c,0x3a1f5a,0x14505a,0xd9d2c0,0x8a1f2a,0x24302a);
function hvFlat97(r){/* bake nested static parts into the chassis so the shared per-material merge can fold them into a few draw calls */const ch=r.ch,sw=ch.children[0],L=[];ch.updateMatrixWorld(true);ch.traverse(o=>{if(o.isMesh&&o.parent!==ch){let p=o.parent,ok=true;while(p&&p!==ch){if(p===sw||p.name==='fan97'||p.name==='fan97r'||p.name==='stack97')ok=false;p=p.parent}if(ok)L.push(o)}});for(const o of L)ch.attach(o);
 for(const o of ch.children)if(o.isMesh&&!o.geometry.index){const n=o.geometry.attributes.position.count,I=n>65535?new Uint32Array(n):new Uint16Array(n);for(let i=0;i<n;i++)I[i]=i;o.geometry.setIndex(new T.BufferAttribute(I,1))}
 for(const o of[...ch.children])if(o.isGroup&&o!==sw){let m=0;o.traverse(q=>{if(q.isMesh)m++});if(!m)ch.remove(o)}if(typeof mergeGroup79==='function')try{mergeGroup79(ch)}catch(e){console.warn('hv merge',e)}}
modelRoot=function(name){if(!HVD97[name])name='vanta';const r=hvBuild97(name);hvFlat97(r);scene.add(r.root);return r};
{const oM=modelCar;modelCar=function(name,x,z,yaw,hex){const c=oM.apply(this,arguments);try{if(c&&c.m.userData.seat97){c.hv97=c.m.userData.hv97}}catch(e){}return c}}
makeAlfa=function(x,z,yaw){const c=modelCar('aether',x,z,yaw,0x6a2418);if(c)c.alfa=true;return c};
alfaCredit=function(){};
{const oS=seatCompute;seatCompute=function(c){const s=c&&c.m&&c.m.userData&&c.m.userData.seat97;if(s){const V=a=>new T.Vector3(a[0],a[1],a[2]);return{hip:V(s.hip),wheel:V(s.wheel),roof:s.roof,W:s.W,L:s.L,ok:true,wr:s.wr,tilt:s.tilt,rim:true}}return oS.apply(this,arguments)}}
/* per-frame: hover bob, fans, yoke follows the hands, stack smoke */
function hvFind97(root){if(root._h97!==undefined)return root._h97;let fans=[],yoke=null,stack=null;root.traverse(o=>{if(o.name==='fan97'||o.name==='fan97r')fans.push(o);if(o.name==='stack97')stack=o});const ch=root.children[0],sw=ch&&ch.children.find(o=>o.isGroup&&o.children.length===1&&o.children[0].isGroup);let piv=null;if(sw){piv=sw.children[0];yoke=piv.children[0]&&piv.children[0].children[0]||null}return root._h97={ch,fans,yoke,piv,stack,ph:Math.random()*6.28}}
function hvTick97(dt){const t=performance.now()/1000,L=[];for(const c of cars)if(c.m&&c.m.userData&&c.m.userData.hv97)L.push([c.m,c]);for(const q of TRF)if(q.m&&q.m.userData&&q.m.userData.hv97)L.push([q.m,q]);
 for(const [root,c] of L){if(!root.visible)continue;const h=hvFind97(root);if(h.ch){const sp=Math.abs(c.vf||c.v||0);h.ch.position.y=c===cur?0:.035*Math.sin(t*2.2+h.ph)+.012*Math.sin(t*5.3+h.ph*2)*(1+sp*.05)}for(const f of h.fans)f.rotation[f.name==='fan97r'?'z':'y']+=dt*(14+Math.abs(c.vf||c.v||0)*1.5);
  if(h.yoke){const target=c===cur?(typeof SEAT69!=='undefined'&&SEAT69.st!==undefined?SEAT69.st:(c.steer||0)*1.9):(c.steer||0)*1.9;h.yoke.rotation.z=target;if(h.piv)h.piv.rotation.z=0}
  if(h.stack&&(c===cur||Math.random()<.1)&&typeof puff==='function'&&Math.random()<dt*6){const p=new T.Vector3();h.stack.getWorldPosition(p);puff(p.x,p.y,p.z)}}}
{const oP=preRender;preRender=function(){oP.apply(this,arguments);try{const n=performance.now(),dt=Math.min(.05,(n-(HV97.t||n))/1000);HV97.t=n;if(started&&!paused)hvTick97(dt)}catch(e){if(!window._hv97){window._hv97=1;console.warn('hv97',e)}}}}
/* the starting cars were created before this module ran — swap them for hover cars in place; later calls build hover cars directly */
{let k97=0;const hvMake97=(x,z,yaw)=>modelCar(SPAWN[k97++%SPAWN.length],x,z,yaw);
 for(let i=0;i<cars.length;i++){const o=cars[i];if(o.air||o.kart||o.hv97||!o.m)continue;const n=hvMake97(o.x,o.z,o.yaw);if(!n)continue;cars.pop();scene.remove(o.m);n.y=o.y;n.g=o.g;cars[i]=n}
 makeCar=function(color,x,z,yaw){return hvMake97(x,z,yaw)}}
