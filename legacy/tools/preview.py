import os
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
a=open(os.path.join(R,'src','patches','v97a.js')).read()
b=open(os.path.join(R,'src','patches','v97b.js')).read()
html='''<!doctype html><html><body style="margin:0;background:#222"><script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.186.1/build/three.module.js"}}</script>
<script type="module">import * as THREE from 'three';window.T=THREE;
const R=new T.WebGLRenderer({antialias:true});R.setSize(innerWidth,innerHeight);R.toneMapping=T.ACESFilmicToneMapping;R.shadowMap.enabled=true;document.body.appendChild(R.domElement);
var scene=new T.Scene();scene.background=new T.Color(0x6f8090);var BPK={},mpMake=null,shipGroup=null,preRender=function(){},started=0,paused=0;
const pm=new T.PMREMGenerator(R);const es=new T.Scene();es.background=new T.Color(0x8899aa);const hl=new T.HemisphereLight(0xdde8ff,0x443322,3);es.add(hl);scene.environment=pm.fromScene(es).texture;
const sun=new T.DirectionalLight(0xfff2dd,2.5);sun.position.set(8,14,6);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-20,right:20,top:20,bottom:-20});scene.add(sun);scene.add(new T.HemisphereLight(0xcfe0ff,0x302820,.8));
const gr=new T.Mesh(new T.PlaneGeometry(200,200),new T.MeshStandardMaterial({color:0x50555c,roughness:.9}));gr.rotation.x=-Math.PI/2;gr.receiveShadow=true;scene.add(gr);
'''+a+'\n'+b+'''
const cam=new T.PerspectiveCamera(40,innerWidth/innerHeight,.05,500);
const P=new URLSearchParams(location.search),mode=P.get('m')||'line';
if(mode==='line'){const keys=Object.keys(HVD97);keys.forEach((k,i)=>{const r=hvBuild97(k);r.root.position.set((i-3)*3.0,0,(i%2)*2.5);r.root.rotation.y=.55;scene.add(r.root)});cam.position.set(4,6,16);cam.lookAt(0,.8,0)}
else if(mode==='side'){const k=P.get('k');const r=hvBuild97(k);r.root.rotation.y=+(P.get('ry')||.7);scene.add(r.root);cam.position.set(+(P.get('cx')||5),+(P.get('cy')||2.2),+(P.get('cz')||5));cam.lookAt(0,.8,0)}
else if(mode==='cock'){const k=P.get('k');const r=hvBuild97(k);scene.add(r.root);r.yoke.rotation.z=+(P.get('st')||0);const s=r.root.userData.seat97;cam.fov=70;cam.updateProjectionMatrix();cam.position.set(s.hip[0],s.hip[1]+.62,s.hip[2]-.05);cam.lookAt(s.hip[0]-.05,s.hip[1]+.35,s.hip[2]+2)}
else if(mode==='ships'){const ks=['s_zodiac','s_ship','s_container','s_cruise','s_liberty'];let x=-70;for(const k of ks){const g=vessel97(k);const bb=new T.Box3().setFromObject(g),w=bb.max.x-bb.min.x;g.rotation.y=Math.PI/2;g.position.x=x+ (bb.max.z-bb.min.z)/2;x+=bb.max.z-bb.min.z+6;scene.add(g)}gr.material.color.set(0x1d4a63);cam.position.set(0,45,120);cam.lookAt(0,5,0);cam.far=1000;cam.updateProjectionMatrix();sun.shadow.camera.left=-120;sun.shadow.camera.right=120;sun.shadow.camera.top=60;sun.shadow.camera.bottom=-60;sun.shadow.camera.updateProjectionMatrix()}
else if(mode==='props'){const ks=Object.keys(PD97).filter(k=>k.startsWith('p_'));ks.forEach((k,i)=>{const ms=mpMake(k,[[ (i-ks.length/2)*2.2+ (k==='p_lamp'?0:0),0,0,0,1]]);});cam.position.set(0,4,16);cam.lookAt(0,2,0)}
R.render(scene,cam);setTimeout(()=>{R.render(scene,cam);window.done=1},1500);
</script></body></html>'''
os.makedirs(os.path.join(R,'preview'),exist_ok=True);open(os.path.join(R,'preview','vehicles.html'),'w').write(html);print('wrote preview/vehicles.html')
