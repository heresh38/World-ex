/* ===== v89: Guardian armor (helmet, arms, chest, legs, class item), shaders, stats, movement & gunplay, Destiny-style character screen ===== */
var STAT89=[['weapons','Weapons','Faster reloads and up to 10% more weapon damage'],['health','Health','Take up to 30% less damage'],['mobility','Mobility','Faster movement and a shorter dodge cooldown'],['recovery','Recovery','Health starts regenerating sooner and faster'],['grenade','Grenade','Shorter frag grenade cooldown, bigger blasts above 100'],['melee','Melee','Shorter melee cooldown, harder hits']];
var ARCH89={bulwark:['Bulwark','health','recovery'],brawler:['Brawler','melee','health'],grenadier:['Grenadier','grenade','weapons'],gunner:['Gunner','weapons','mobility'],specialist:['Specialist','mobility','recovery'],marksman:['Marksman','weapons','recovery']};
var SLOTS89=[['helmet','Helmet'],['arms','Gauntlets'],['chest','Chest Armor'],['legs','Leg Armor'],['cls','Class Item']];
/* designs: [id, name, archetype, rarity, flavour, third stat] */
var ARM89={
 helmet:[['none','No helmet'],['cap','Field Cap','gunner','common','Standard issue. Shows off the haircut.'],['beanie','Cold-Weather Beanie','specialist','common','Warm ears, warm heart.'],
  ['vanguard','Vanguard Crown','bulwark','legendary','A T-visor forged for the front line.','melee'],['hood','Pathfinder Hood','specialist','legendary','Cloth over a ghost-lit mask.','weapons'],['seer','Seer Crest','marksman','legendary','The third eye never closes.','grenade'],
  ['warden','Warden Horns','brawler','legendary','Fear is a weapon. Wear it.','recovery'],['recon','Starlight Recon','gunner','exotic','A wide visor that reads the battlefield.','mobility']],
 arms:[['none','Bare arms'],['vanguard','Vanguard Gauntlets','brawler','legendary','Fists like falling stars.','health'],['hood','Pathfinder Grips','specialist','legendary','Wrapped for silence.','grenade'],['seer','Seer Bracers','grenadier','legendary','Runes that hum before the storm.','melee'],
  ['warden','Warden Pauldrons','bulwark','legendary','Shoulders built like ramparts.','weapons'],['recon','Starlight Sleeves','marksman','exotic','Light gathers along the forearm.','recovery']],
 chest:[['none','No chest armor'],['vanguard','Vanguard Plate','bulwark','legendary','A wall that walks.','grenade'],['hood','Pathfinder Vest','gunner','legendary','Straps, pockets, and a plan.','recovery'],['seer','Seer Robes','marksman','legendary','Every thread is a sentence.','weapons'],
  ['warden','Warden Cuirass','brawler','legendary','Carved with the names of the fallen.','mobility'],['recon','Starlight Carapace','grenadier','exotic','A heart of bottled sunlight.','health']],
 legs:[['none','No leg armor'],['vanguard','Vanguard Greaves','bulwark','legendary','Planted. Unmoving.','weapons'],['hood','Pathfinder Strides','specialist','legendary','Quiet boots for loud work.','melee'],['seer','Seer Wraps','grenadier','legendary','Silk over steel.','health'],
  ['warden','Warden Tassets','brawler','legendary','Every plate a promise.','mobility'],['recon','Starlight Striders','gunner','exotic','Thrusters in the heels.','recovery']],
 cls:[['none','No class item'],['cloak','Pathfinder Cloak','specialist','legendary','It moves like smoke.','weapons'],['mark','Vanguard Mark','bulwark','legendary','Worn at the belt, earned in the breach.','melee'],['bandolier','Gunner Bandolier','gunner','legendary','Every round within reach.','grenade'],
  ['scarf','Wanderer Scarf','gunner','legendary','For the long road between stars.','recovery'],['tails','Duelist Coat Tails','brawler','legendary','Flair is a tactic.','mobility'],['pack','Field Pack','specialist','common','Snacks. Ammo. More snacks.','health'],['sash','Officer Sash','marksman','exotic','Rank, worn across the heart.','health']]};
var SHD89=[['standard','Halcyon Standard',0xe9e4d6,0x2a2c31,0xc9a24c,0xffe2a6],['vanguard','Vanguard Blue',0xd9d4c6,0x3a3f48,0xb8964a,0x7fd8ff],['obsidian','Obsidian Ember',0x1d1e22,0x34302c,0xc79a3a,0xff8a2a],['crimson','Crimson Oath',0x9a1f24,0xe6e0d4,0xc0a060,0xffd060],['arctic','Arctic Sentinel',0xe8eef4,0x5a7a9a,0x9fb8d0,0x7fe6ff],
 ['jade','Jade Rabbit',0x3d7a5e,0xd8d0b8,0xb8a060,0x8dffcf],['royal','Royal Eclipse',0x3a2a5a,0x1c1a24,0xd6b45a,0xb98aff],['dune','Dune Runner',0xb8a07a,0x5a5a3a,0x8a6a40,0xffc060],['neon','Neon Ronin',0x16171b,0xd0306a,0x5a5f6a,0x30e8ff],
 ['rust','Rustbelt',0x8a4a2a,0x3a3a3a,0x6a5a4a,0xffa040],['ivory','Ivory Saint',0xf2efe6,0xc9b48a,0xe0c070,0xfff0b0]];
for(const [k,v] of Object.entries({ahelmet:'none',aarms:'none',achest:'none',alegs:'none',acls:'none',ashader:'standard',apri:null,asec:null,aglow:null,_v89:0}))if(OUT[k]===undefined)OUT[k]=v;
/* first run: suit up so the Guardian look is visible immediately (all items are unlocked) */
if(!OUT._v89){Object.assign(OUT,{ahelmet:'vanguard',aarms:'vanguard',achest:'vanguard',alegs:'vanguard',acls:'cloak',_v89:1});try{saveOut()}catch(e){}}
function des89(slot,id){return(ARM89[slot]||[]).find(d=>d[0]===id)||null}
function pieceStats89(slot,id){const d=des89(slot,id),o={weapons:0,health:0,mobility:0,recovery:0,grenade:0,melee:0};if(!d||!d[2])return o;const a=ARCH89[d[2]];const ex=d[3]==='exotic',com=d[3]==='common';o[a[1]]+=com?18:ex?32:30;o[a[2]]+=com?12:ex?22:20;if(d[5])o[d[5]]+=ex?14:10;return o}
function stats89(){const o={weapons:0,health:0,mobility:0,recovery:0,grenade:0,melee:0};for(const [s] of SLOTS89){const p=pieceStats89(s,OUT['a'+s]);for(const k in o)o[k]+=p[k]}for(const k in o)o[k]=Math.min(200,o[k]+10);return o}
function power89(){let p=0,n=0;for(const [s] of SLOTS89){const d=des89(s,OUT['a'+s]);p+=d&&d[3]?(d[3]==='exotic'?2030:d[3]==='legendary'?2010:1950):1900;n++}return Math.round(p/n)}
function shader89(){const s=SHD89.find(q=>q[0]===OUT.ashader)||SHD89[0];return{pri:OUT.apri??s[2],sec:OUT.asec??s[3],metal:s[4],glow:OUT.aglow??s[5]}}

/* ---------- rest pose of the current character (character space) ---------- */
function rest89(C){if(C._r89)return C._r89;const S=CHARPK.mh.meta.skel[C.sex],W={},P={};S.forEach((b,i)=>{const q=new T.Quaternion().fromArray(b.q),t=new T.Vector3().fromArray(b.t);if(b.p<0){W[i]=q;P[b.n]=t}else{W[i]=W[b.p].clone().multiply(q);P[b.n]=t.clone().applyQuaternion(W[b.p]).add(P[S[b.p].n])}});return C._r89=P}
/* mounts: char-axis frames riding each bone (like the hat mount) */
function mount89(C,bn){C._m89=C._m89||{};if(C._m89[bn])return C._m89[bn];const B=C.B[bn];if(!B)return null;const g=new T.Group();g.name='armor:'+bn;g.quaternion.copy(C.restCS[bn]).invert();B.add(g);return C._m89[bn]=g}

/* ---------- materials ---------- */
function amats89(){const s=shader89(),S=(c,m,r,o)=>Object.assign(new T.MeshStandardMaterial({color:c,metalness:m,roughness:r}),o||{});
 const glow=S(0x0a0a0a,.1,.4,{emissive:new T.Color(s.glow),emissiveIntensity:2.4});glow.userData.glow89=1;glow.userData.glow87=1;
 const M={pri:S(s.pri,.28,.34),sec:S(s.sec,.45,.42),metal:S(s.metal,.95,.22),dark:S(0x22242a,.55,.4),glow,visor:S(0x0a0c10,.9,.06,{envMapIntensity:1.6}),
  visorC:S(new T.Color(s.glow).multiplyScalar(.55).getHex(),.95,.05,{emissive:new T.Color(s.glow),emissiveIntensity:.25}),cloth:S(s.sec,0,.92,{side:T.DoubleSide}),clothP:S(s.pri,0,.88,{side:T.DoubleSide}),
  wing:new T.MeshBasicMaterial({color:s.glow,transparent:true,opacity:.55,blending:T.AdditiveBlending,depthWrite:false,side:T.DoubleSide,toneMapped:false})};
 for(const k in M)M[k].userData.noConv=1;return M}

/* ---------- geometry helpers ---------- */
function m89(g,geo,mat,x,y,z,rx,ry,rz,sx,sy,sz){const m=new T.Mesh(geo,mat);m.position.set(x||0,y||0,z||0);m.rotation.set(rx||0,ry||0,rz||0);if(sx!==undefined)m.scale.set(sx,sy===undefined?sx:sy,sz===undefined?sx:sz);m.castShadow=true;m.receiveShadow=true;g.add(m);return m}
function rbox89(w,h,d,r){const s=new T.Shape(),x=-w/2,y=-h/2;r=Math.min(r||Math.min(w,h)*.2,w/2,h/2);s.moveTo(x+r,y);s.lineTo(x+w-r,y);s.quadraticCurveTo(x+w,y,x+w,y+r);s.lineTo(x+w,y+h-r);s.quadraticCurveTo(x+w,y+h,x+w-r,y+h);s.lineTo(x+r,y+h);s.quadraticCurveTo(x,y+h,x,y+h-r);s.lineTo(x,y+r);s.quadraticCurveTo(x,y,x+r,y);const b=Math.min(.004,d*.3);const g=new T.ExtrudeGeometry(s,{depth:Math.max(.001,d-b*2),bevelEnabled:true,bevelThickness:b,bevelSize:b,bevelSegments:2,curveSegments:4});g.translate(0,0,-(d-b*2)/2);return g}
function shape89(pts,d,bev){const s=new T.Shape();s.moveTo(pts[0][0],pts[0][1]);for(let i=1;i<pts.length;i++)s.lineTo(pts[i][0],pts[i][1]);const b=bev===undefined?Math.min(.003,d*.3):bev;const g=new T.ExtrudeGeometry(s,{depth:Math.max(.001,d-b*2),bevelEnabled:b>0,bevelThickness:b,bevelSize:b,bevelSegments:2});g.translate(0,0,-(d-b*2)/2);return g}
/* a shell section of an elliptic cylinder (torso/limb plates): angles a0..a1 around y, radii rx/rz, height h */
function shell89(rx,rz,h,a0,a1,t,segs){const g=new T.CylinderGeometry(1,1,h,segs||20,1,true,a0,a1-a0);g.scale(rx,1,rz);const g2=g.clone();g2.scale(1+(t||.01)/rx,1,1+(t||.01)/rz);/* thickness: inner + outer + caps approximated by DoubleSide outer */return g2}
function along89(g,mesh,a,b){/* orient mesh's +y along a->b, centre at midpoint */const d=b.clone().sub(a),L=d.length();mesh.position.copy(a).addScaledVector(d,.5);mesh.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),d.normalize());return L}
