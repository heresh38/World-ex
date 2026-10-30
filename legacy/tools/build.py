import re
import os,sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P=lambda *a:os.path.join(ROOT,*a)
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
s=open(P('src','base.html')).read()
def rep(a,b,n=1):
    global s
    c=s.count(a);assert c==n,(c,a[:90]);s=s.replace(a,b)
def match_brace(t,i):
    assert t[i]=='{';d=0;q=None;j=i
    while j<len(t):
        c=t[j]
        if q:
            if c=='\\':j+=2;continue
            if c==q:q=None
        elif c in '\'"`':q=c
        elif c=='{':d+=1
        elif c=='}':
            d-=1
            if d==0:return j
        j+=1
    raise Exception('unbalanced')
# ---- 1. remove the dinosaur arena module, keep its glTF loader for the editor ----
a=s.index('/* ===== v70: Dino Arena');b=s.index('/* ===== v72: arcade feel')
blk=s[a:b];i=blk.index('async function dinoLib(){');j=match_brace(blk,blk.index('{',i))
lib=blk[i:j+1].replace('async function dinoLib(){','async function gltfLib(){').replace('DINO.lib','GLTF89.lib')
assert 'DINO' not in lib and 'dino' not in lib.lower(),lib[:400]
s=s[:a]+'/* v89: arena mode removed — the shared glTF loader stays for the editor */\nvar GLTF89={lib:null};\n'+lib+'\n'+s[b:]
rep('await dinoLib()','await gltfLib()')
# ---- 2. strip every remaining arena branch ----
s=s.replace("(typeof DINO!=='undefined'&&DINO.on&&DINO.DS)?DINO.DS:scene","scene")
s=s.replace("if(typeof DINO!=='undefined'&&DINO.on)return 0;","")
s=s.replace("if(typeof DINO!=='undefined'&&DINO.on&&typeof dinoLeave==='function')dinoLeave();","")
key="if(typeof DINO!=='undefined'&&DINO.on){"
while key in s:
    k=s.index(key);ob=k+len(key)-1;cb=match_brace(s,ob);rest=s[cb+1:]
    m=re.match(r'\s*else\s*\{',rest);m2=re.match(r'\s*else\s+(?=if)',rest)
    if m:s=s[:k]+s[cb+1+m.end()-1:]
    elif m2:s=s[:k]+s[cb+1+m2.end():]
    else:s=s[:k]+s[cb+1:]
# report leftovers outside base64 data
left=[(mm.start(),s[max(0,mm.start()-60):mm.start()+60]) for mm in re.finditer(r'DINO|dino',s) if not re.search(r'[A-Za-z0-9+/]{40}',s[max(0,mm.start()-40):mm.start()+40])]
print('leftover refs',len(left))
for x in left[:20]:print(x)
MODULES=['v89a.js','v89b.js','v89c.js','v89d.js','v89e.js','v89g.js','v89f.js','v91a.js','v91b.js','v90b.js','v90c.js','v91c.js','v96d.js','v96c.js','v96b.js','v96e.js','v96a.js','v97a.js','v97b.js','v97c.js']
js=''.join(open(P('src','patches',f)).read() for f in MODULES)
M='function frame(){requestAnimationFrame(frame);'
rep(M,js+'\n'+M)
rep("['female','male','mh'].map(async n=>","[].map(async n=>")

# ---- v95: unified world texture set (generated, matches the weapon art direction) ----
import re as _re
s,_n=_re.subn(r"TMEAN77=\{[^}]*\};",lambda m:'TMEAN77={"tmud":[0.336,0.276,0.214],"tsand":[0.856,0.769,0.631],"tsand2":[0.644,0.576,0.484],"tsnow":[0.864,0.876,0.872],"tdry":[0.606,0.52,0.361],"tforest":[0.331,0.283,0.208],"wood":[0.382,0.274,0.206],"plaza":[0.543,0.518,0.473],"tgrass":[0.389,0.44,0.228],"cliffa":[0.406,0.412,0.411],"cliffb":[0.307,0.235,0.183],"cdmg":[0.538,0.532,0.507],"cgold":[0.607,0.595,0.559],"crun":[0.536,0.536,0.525],"tice":[0.671,0.765,0.804],"twet":[0.333,0.282,0.231]};',s);assert _n==1,_n
rep("S('w5','plast');S('w6','ybrick')}","S('w5','plast');S('w6','ybrick');S('grass','tgrass',1);S('cliffA','cliffa',1);S('cliffB','cliffb',1);S('conc_dmg','cdmg',1);S('conc_gold','cgold',1);S('conc_run','crun',1);S('ice','tice',1);S('wet','twet',1);S('w4','w4c');S('w7','wsiding');S('w8','wplaster');S('w9','w9blk');S('w10','wroof')}")

# ---- v97: no provided models or textures remain ----
import re as _r2
def _blk(id,content):
    global s
    i=s.index('id="%s"'%id);i=s.index('>',i)+1;j=s.index('</script>',i);s=s[:i]+content+s[j:]
for _id in ['cardata','tdata','adata','bdata']:_blk(_id,'')
_G={'cobble':'plaza','gravel':'gravel','cliffA':'cliffa','cliffB':'cliffb','mud':'tmud','dry':'tdry','wet':'twet','sand':'tsand','sand2':'tsand2','snow':'tsnow','conc_gold':'cgold','conc_dmg':'cdmg','conc_run':'crun','ice':'tice','wood':'wood','sea1':'sea1','sea2':'sea2','w1':'brick','w2':'gbrick','w3':'brickg','w4':'w4c','w5':'plast','w6':'ybrick','w7':'wsiding','w8':'wplaster','w9':'w9blk','w10':'wroof'}
_blk('gdata','\n'+'\n'.join('%s\ttex/%s_c.jpg'%(k,v) for k,v in _G.items())+'\n')
for f in ['loadCarsHQ','loadShips','loadHousesHQ','loadCharsHQ']:rep('async function %s(){'%f,'async function %s(){return;'%f)
rep("const TREEV=['tr_birch','tr_pine','tr_anim1','tr_jungle'].every(n=>BPK[n]);","const TREEV=true;")
i=s.index('e.innerHTML="<b>Car models (Sketchfab)</b>');j=s.index('";',i);s=s[:i]+'e.innerHTML="'+s[j:]
i=s.index("e.textContent='\"Alfa Romeo Stradale 1967\"");j=s.index("';",i);s=s[:i]+"e.textContent='"+s[j:]
s=s.replace('/* ===== Alfa Romeo Stradale 1967 (imported model) ===== */','/* ===== showcase car ===== */')
s=s.replace('/vec3(.237,.505,.68)','/vec3(.215,.468,.586)').replace('/vec3(.066,.309,.382)','/vec3(.079,.292,.343)')
import names;s=names.apply(s)
s=s.replace(M,'if(window.__TEST)window.__ev=s=>eval(s);'+M,1) if M in s else s
# local vendored libraries (offline-capable, no CDN dependency); inline-script imports resolve against the page URL
s=s.replace('https://cdn.jsdelivr.net/npm/three@0.186.1/examples/jsm/','../lib/three/jsm/')
s=s.replace('https://cdn.jsdelivr.net/npm/three@0.186.1/build/three.module.js','../lib/three/build/three.module.js')
s=s.replace('https://cdn.jsdelivr.net/npm/three-mesh-bvh@0.9.16/build/index.module.js','../lib/bvh/index.module.js')
assert 'cdn.jsdelivr' not in s
open(P('index.html'),'w').write(s);print('built index.html',len(s))
