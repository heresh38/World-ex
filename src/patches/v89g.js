
/* ---------- garment fit: armor shells are sized from the actual undersuit mesh so plates sit outside the cloth ---------- */
var FIT89={C:null},FITC89={q:.85,cut:1.45,capA:.024,capL:.03,qT:.92,capT:1.14,m:.004};
function cloud89(C){const vis=[];for(const me of C.meshes||[]){const it=String(me.userData.item||'');if(!me.visible||/eye|brow|lash|teeth|tongue|hair|head/i.test(it))continue;vis.push(me)}
 const key=vis.map(m=>m.userData.item+':'+m.geometry.uuid).join('|');if(C._fc89&&C._fc89.key===key)return C._fc89.pts;
 let n=0;for(const m of vis)n+=m.geometry.attributes.position.count;const pts=new Float32Array(n*3);let o=0;for(const m of vis){const a=m.geometry.attributes.position;for(let i=0;i<a.count;i++){pts[o++]=a.getX(i);pts[o++]=a.getY(i);pts[o++]=a.getZ(i)}}
 C._fc89={key,pts,seg:{}};return pts}
function pct89(arr,q){if(!arr.length)return 0;arr.sort((a,b)=>a-b);return arr[Math.min(arr.length-1,Math.floor(arr.length*q))]}
/* ellipse fit for torso/belt rings: returns the scale (>=1) that puts the ring outside 97% of cloth verts in the band */
function fitE89(ya,yb,xmax,rx,rz,cz){const C=FIT89.C;if(!C)return 1;try{const p=cloud89(C),e=[];for(let i=0;i<p.length;i+=3){const y=p[i+1];if(y<ya||y>yb)continue;const x=p[i];if(Math.abs(x)>xmax)continue;e.push(Math.hypot(x/rx,(p[i+2]-cz)/rz))}
 if(e.length<20)return 1;return Math.max(1,Math.min(FITC89.capT,pct89(e,FITC89.qT)*1.02+.008))}catch(er){return 1}}
/* torso centre: the cloth's real front/back midpoint (the rest skeleton's spine sits behind the chest's centre) */
function fitZ89(ya,yb,xmax,cz0){const C=FIT89.C;if(!C)return cz0;try{const p=cloud89(C),z=[];for(let i=0;i<p.length;i+=3){const y=p[i+1];if(y<ya||y>yb||Math.abs(p[i])>xmax)continue;z.push(p[i+2])}if(z.length<20)return cz0;const a=pct89(z,.03),b=pct89(z.slice(),.97);return Math.max(cz0-.01,Math.min(cz0+.045,(a+b)/2))}catch(e){return cz0}}
/* compression undersuit: under armor, the shirt and trousers are pulled in toward the body (nearest skin vertex) so plates can sit close */
function tight89(C){if(!C||!C.mh||!C.byItem||!C.byItem.body)return;const hy=rest89(C).Hips.y-.03,on={shirt:OUT.achest!=='none',tshirt:OUT.achest!=='none',jeans:OUT.alegs!=='none'};let grid=null,bp=null;const cs=.04,key=(x,y,z)=>((Math.floor(x/cs)+512)*1048576)+((Math.floor(y/cs)+512)*1024)+(Math.floor(z/cs)+512);
 const build=()=>{bp=[];for(const m of C.byItem.body){const a=m.geometry.attributes.position;for(let i=0;i<a.count;i++)bp.push(a.getX(i),a.getY(i),a.getZ(i))}grid=new Map();for(let i=0;i<bp.length;i+=3){const k=key(bp[i],bp[i+1],bp[i+2]);let L=grid.get(k);if(!L)grid.set(k,L=[]);L.push(i)}};
 let changed=false;for(const [it,want] of Object.entries(on))for(const m of (C.byItem[it]||[])){const g=m.geometry,a=g.attributes.position,st=!!m.userData.t89;if(want===st)continue;changed=true;
  if(!m.userData.o89)m.userData.o89=new Float32Array(a.array);const o=m.userData.o89,arr=new Float32Array(o);
  if(want){if(!grid)build();for(let i=0;i<arr.length;i+=3){const x=o[i],y=o[i+1],z=o[i+2];let best=1e9,bi=-1;const cx=Math.floor(x/cs),cy=Math.floor(y/cs),cz=Math.floor(z/cs);
    for(let r=1;r<=2&&bi<0;r++)for(let dx=-r;dx<=r;dx++)for(let dy=-r;dy<=r;dy++)for(let dz=-r;dz<=r;dz++){const L=grid.get(((cx+dx+512)*1048576)+((cy+dy+512)*1024)+(cz+dz+512));if(!L)continue;for(const j of L){const ex=bp[j]-x,ey=bp[j+1]-y,ez=bp[j+2]-z,d=ex*ex+ey*ey+ez*ez;if(d<best){best=d;bi=j}}}
    if(bi<0)continue;const d=Math.sqrt(best),keep=(it!=='jeans'&&y<hy)?0:d<1e-5?0:Math.min(d,Math.max(.005,d*.3))/d;arr[i]=bp[bi]+(x-bp[bi])*keep;arr[i+1]=bp[bi+1]+(y-bp[bi+1])*keep;arr[i+2]=bp[bi+2]+(z-bp[bi+2])*keep}}
  g.setAttribute('position',new T.BufferAttribute(arr,3));g.computeBoundingSphere();m.userData.t89=want}
 if(changed){C._fc89=null;C._sig89=null;C._pol89=null}}
/* limb profile: per-segment radial clearance; the first shell on a segment fixes the offset so layered shells keep their spacing */
{const oL=limb89;limb89=function(g,P0,a,b,r1,r2,mat,th0,thL,f0,f1,fwd){const C=FIT89.C;try{const nm=(g&&g.name)||'',arm=/Arm|Hand/.test(nm),leg=/UpLeg|Leg|Foot|Toe/.test(nm);
  if(C&&(arm||leg)){cloud89(C);const S=C._fc89.seg,key=nm+'|'+a.x.toFixed(3)+','+a.y.toFixed(3)+'|'+b.x.toFixed(3)+','+b.y.toFixed(3);let st=S[key];
   if(!st){const s=nm.indexOf('Left')>=0?1:-1,shX=Math.abs(rest89(C).LeftArm.x),thr=arm?shX*.9:.012,p=C._fc89.pts,d=b.clone().sub(a),L2=d.lengthSq(),bins=[];for(let k=0;k<10;k++)bins.push([]);const cut=Math.max(r1,r2)*FITC89.cut+.01;
    for(let i=0;i<p.length;i+=3){const x=p[i];if(x*s<thr)continue;const vx=x-a.x,vy=p[i+1]-a.y,vz=p[i+2]-a.z,t=(vx*d.x+vy*d.y+vz*d.z)/L2;if(t<0||t>=1)continue;const ex=vx-d.x*t,ey=vy-d.y*t,ez=vz-d.z*t,r=Math.sqrt(ex*ex+ey*ey+ez*ez);if(r>cut)continue;bins[Math.floor(t*10)].push(r)}
    const prof=bins.map(b=>b.length>6?pct89(b,FITC89.q)+FITC89.m:0);let dl=0;for(let k=Math.floor(f0*10);k<=Math.min(9,Math.floor(f1*10-1e-6));k++){if(k<0)continue;const t=(k+.5)/10,rr=r1+(r2-r1)*Math.min(1,Math.max(0,(t-f0)/Math.max(.01,f1-f0)));dl=Math.max(dl,prof[k]-rr)}
    st=S[key]={dl:Math.min(arm?FITC89.capA:FITC89.capL,dl)};g.userData.fd89=Math.max(g.userData.fd89||0,st.dl)}
   if(st.dl>0){r1+=st.dl;r2+=st.dl}}}catch(er){}
  return oL.call(this,g,P0,a,b,r1,r2,mat,th0,thL,f0,f1,fwd)}}
/* push non-tube parts on grown limbs (knee guards, pads) outward by the same clearance */
function fitPush89(C){for(const g of Object.values(C._m89||{})){const dl=g.userData.fd89;if(!dl)continue;for(const o of g.children){if(!o.isMesh||(o.userData.d89&&o.userData.d89.k==='limb'))continue;const h=Math.hypot(o.position.x,o.position.z);if(h<.012)continue;o.position.x+=o.position.x/h*dl;o.position.z+=o.position.z/h*dl}}}
{const oB=buildArmor89;buildArmor89=function(C){if(C&&C.mh&&C===CHAR)try{tight89(C)}catch(e){console.warn('tight89',e)}FIT89.C=(C&&C.mh)?C:null;if(C&&C._m89)for(const g of Object.values(C._m89))g.userData.fd89=0;const s0=C&&C._sig89;try{if(C&&C._fc89)C._fc89.seg={};const r=oB.apply(this,arguments);if(C&&C.mh&&C._sig89!==s0)try{fitPush89(C)}catch(e){}return r}finally{FIT89.C=null}}}
