"""v97: our own gun-wear and ocean textures (replace the last provided images)."""
import sys
import os;src=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'texgen95.py')).read();src=src[:src.index('S = 1024')]
sys.argv=['x',sys.argv[1] if len(sys.argv)>1 else 'tex'];exec(src)
S=512
# --- gun wear: gunmetal micro-scratches, brushed grain, worn bright edges (mask lives in luminance) ---
r=rng(7);x,y=grid(S)
grain=blur(gnoise(S,(14,0.6),11),.6)*.5
scr=np.zeros((S,S))
for k in range(900):
    x0,y0=r.random(2)*S;a=r.normal(0,.5)+(np.pi/2 if r.random()<.3 else 0);L=r.random()*60+8
    t=np.linspace(0,1,int(L));xs=((x0+np.cos(a)*L*t)%S).astype(int);ys=((y0+np.sin(a)*L*t)%S).astype(int);scr[ys,xs]+=r.random()*.8+.2
scr=blur(scr,.5)
pit=ss(.65,.9,fbm(S,4,3,21)*.5+.5)*.5
h=grain*.15+scr*.25-pit*.3+fbm(S,24,4,31)*.08
blot=ss(-.25,.35,fbm(S,18,5,41)+gnoise(S,(22,1.0),43)*.45)
lum=np.clip(blot*.85+grain*.08+np.clip(scr,0,1)*.4-pit*.25,0,1)
c=np.repeat(np.clip(lum,0,1)[...,None],3,-1)
save('gwear',c,h,ns=3.0)
# --- ocean: tileable wave height fields (integer wave numbers -> seamless), crest foam and caustic lines ---
def waves(S,n,kmin,kmax,seed,sharp=1.5):
    r=rng(seed);u=x/S*2*np.pi;v=y/S*2*np.pi;h=np.zeros((S,S))
    for i in range(n):
        kx,ky=r.integers(-kmax,kmax+1,2)
        if abs(kx)+abs(ky)<kmin:continue
        w=1/np.hypot(kx,ky)**.9;ph=r.random()*6.283
        s=np.sin(kx*u+ky*v+ph);h+=w*(np.abs(s)**sharp*np.sign(s))
    return (h-h.mean())/h.std()
for key,(deep,shal),seed,k in [('sea1',(hx('1d4a63'),hx('4fa3c6')),3,(2,18)),('sea2',(hx('082a36'),hx('1f6a78')),9,(1,9))]:
    hgt=waves(S,90,k[0],k[1],seed)*.6+waves(S,120,k[1],k[1]*3,seed+1,2.2)*.4+fbm(S,10,4,seed+5)*.25
    d1,d2,_=vor(S,90 if key=='sea1' else 40,seed+2);caus=ss(4,0,d2-d1)*.4
    foam=ss(2.0,3.2,hgt)*.5
    t=np.clip(hgt*.22+.5,0,1)
    c=lerp(deep,shal,t)+caus[...,None]*.08+foam[...,None]*np.array([.5,.55,.55])*.6
    save(key,c,hgt,ns=2.0)
import json;print(MEANS)
