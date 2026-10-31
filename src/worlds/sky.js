// Procedural skies: deep space (stars + nebula + a planet below the ship) and atmospheric domes for surfaces.
import * as THREE from 'three';

const NOISE = `
float h3(vec3 p){p=fract(p*.3183099+.1);p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
float n3(vec3 x){vec3 i=floor(x),f=fract(x);f=f*f*(3.-2.*f);
 return mix(mix(mix(h3(i),h3(i+vec3(1,0,0)),f.x),mix(h3(i+vec3(0,1,0)),h3(i+vec3(1,1,0)),f.x),f.y),
            mix(mix(h3(i+vec3(0,0,1)),h3(i+vec3(1,0,1)),f.x),mix(h3(i+vec3(0,1,1)),h3(i+vec3(1,1,1)),f.x),f.y),f.z);}
float fbm(vec3 p){float s=0.,a=.5;for(int i=0;i<5;i++){s+=a*n3(p);p*=2.03;a*=.5;}return s;}`;

// Baked planet maps (tools/blender/planets.py), registered by the game once loaded.
export const planetMaps = {};

// Deep space as a camera sees it next to a sunlit planet: exposure is set for the bright limb, so only the brightest
// stars show, the Milky Way is a faint dusty band and there is no colourful nebula.
export function spaceSky(opts = {}) {
  const m = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, toneMapped: true,
    uniforms: { sunDir: { value: (opts.sunDir || new THREE.Vector3(-.3, .5, -.8)).clone().normalize() } },
    vertexShader: `varying vec3 vD;void main(){vD=normalize(position);vec4 p=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_Position=p.xyww;}`,
    fragmentShader: NOISE + `varying vec3 vD;uniform vec3 sunDir;
      float star(vec3 d,float cells,float thr,float seed){vec3 c=floor(d*cells);float h=h3(c+seed);if(h<thr)return 0.;
        vec3 j=vec3(h3(c+seed+1.7),h3(c+seed+3.1),h3(c+seed+5.3));vec3 sp=(c+.2+j*.6)/cells;
        float r=length(normalize(sp)-d)*cells;return smoothstep(1.,.0,r*2.6)*(.35+.65*h3(c+seed+9.1));}
      void main(){vec3 d=normalize(vD);
        // galactic plane tilted across the sky: faint, grainy, with dark dust lanes
        vec3 gp=normalize(vec3(.35,1.,.25));float gl=dot(d,gp);
        float band=exp(-gl*gl*40.);float dust=smoothstep(.5,.72,fbm(d*16.+vec3(4.)));
        vec3 c=vec3(.03,.028,.034)*band*(.5+fbm(d*7.)*.7)*(1.-dust*.6);
        // sparse stars: a few bright ones, a dusting of faint ones thicker along the band
        float s=star(d,150.,.9992,1.)*2.2+star(d,320.,.9985-band*.002,7.)*.45;
        vec3 tint=mix(vec3(1.,.86,.72),vec3(.75,.85,1.),h3(floor(d*420.)));
        c+=tint*s;
        // the sun: hard disc, tight glare
        float sd=max(dot(d,sunDir),0.);c+=vec3(1.,.95,.88)*(smoothstep(.99985,.99993,sd)*60.+pow(sd,900.)*6.+pow(sd,60.)*.12);
        gl_FragColor=vec4(c,1.);}`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(900, 48, 24), m);
  mesh.frustumCulled = false; mesh.renderOrder = -10;
  return mesh;
}

// A planet seen from orbit. Earth uses the baked maps: day albedo with sun glint on the oceans, relief shading,
// city lights on the night side, a separate cloud shell that casts shadows, and an atmosphere rim that goes
// blue on the day side and amber along the terminator. Other worlds stay procedural.
export function orbitPlanet(colors, sunDir, radius = 420) {
  const M = colors.ocean && planetMaps.earth;
  if (M) return earthPlanet(M, sunDir, radius);
  const m = new THREE.ShaderMaterial({
    uniforms: { a: { value: new THREE.Color(colors[0]) }, b: { value: new THREE.Color(colors[1]) }, c: { value: new THREE.Color(colors[2] || colors[1]) },
      sunDir: { value: sunDir.clone().normalize() }, time: { value: 0 }, ocean: { value: colors.ocean ? 1 : 0 } },
    vertexShader: `varying vec3 vN,vP,vW;void main(){vN=normalize(normalMatrix*normal);vP=position;vec4 w=modelMatrix*vec4(position,1.);vW=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}`,
    fragmentShader: NOISE + `varying vec3 vN,vP,vW;uniform vec3 a,b,c,sunDir;uniform float time,ocean;
      float fbm8(vec3 p){float s=0.,am=.5;for(int i=0;i<8;i++){s+=am*n3(p);p*=2.03;am*=.5;}return s;}
      void main(){vec3 p=normalize(vP);float n=fbm8(p*3.5);float n2=fbm8(p*9.+3.);
        vec3 col=mix(a,b,smoothstep(.35,.65,n));col=mix(col,c,smoothstep(.55,.8,n2)*.6);
        col*=.85+fbm8(p*40.)*.3;
        float cl=smoothstep(.58,.78,fbm8(p*5.+vec3(time*.01,0.,0.)));col=mix(col,vec3(1.),cl*.55);
        vec3 N=normalize(vN);vec3 L=normalize((viewMatrix*vec4(sunDir,0.)).xyz);
        float dl=max(dot(N,L),0.);vec3 V=normalize(-(viewMatrix*vec4(vW,1.)).xyz);
        float rim=pow(1.-max(dot(N,V),0.),3.);
        vec3 lit=col*(dl*1.2+.015)+vec3(.35,.6,1.)*rim*(dl*.8+.03)*1.2;
        gl_FragColor=vec4(lit,1.);}`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, 128, 64), m);
  return mesh;
}

function earthPlanet(M, sunDir, radius) {
  const L = sunDir.clone().normalize();
  const uni = { day: { value: M.day }, night: { value: M.night }, clouds: { value: M.clouds }, ms: { value: M.ms },
    sunDir: { value: L }, time: { value: 0 }, texel: { value: new THREE.Vector2(1 / 2048, 1 / 1024) } };
  const vs = `varying vec3 vN,vW;varying vec2 vUv;void main(){vUv=uv;vN=normalize(mat3(modelMatrix)*normal);vec4 w=modelMatrix*vec4(position,1.);vW=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}`;
  const surf = new THREE.ShaderMaterial({
    uniforms: uni, vertexShader: vs,
    fragmentShader: `uniform sampler2D day,night,clouds,ms;uniform vec3 sunDir;uniform float time;uniform vec2 texel;varying vec3 vN,vW;varying vec2 vUv;
      void main(){vec3 N=normalize(vN),V=normalize(cameraPosition-vW);
        vec3 alb=texture2D(day,vUv).rgb;
        vec3 m=texture2D(ms,vUv).rgb;float ocean=m.g;
        // relief: bend the normal along the height gradient (east/north tangent frame)
        vec3 E=normalize(cross(vec3(0.,1.,0.),N)+1e-5);vec3 Nn=cross(N,E);
        float hx=texture2D(ms,vUv+vec2(texel.x,0.)).r-texture2D(ms,vUv-vec2(texel.x,0.)).r;
        float hy=texture2D(ms,vUv+vec2(0.,texel.y)).r-texture2D(ms,vUv-vec2(0.,texel.y)).r;
        vec3 Nb=normalize(N-(E*hx+Nn*hy)*1.1*(1.-ocean));
        float dl=dot(Nb,sunDir),d0=dot(N,sunDir);
        float day0=smoothstep(-.12,.25,d0);
        // cloud shadow, sampled a little toward the sun
        float cs=texture2D(clouds,vUv+vec2(time*.0004+.004,0.)).r;
        vec3 col=alb*max(dl,0.)*1.35*(1.-cs*.55);
        // ocean sun glint
        vec3 H=normalize(sunDir+V);col+=vec3(1.,.92,.8)*pow(max(dot(N,H),0.),180.)*ocean*1.6*day0;
        col+=vec3(.25,.45,.9)*pow(max(dot(N,H),0.),12.)*ocean*.06*day0;
        // night: city lights fade in past the terminator
        vec3 nl=texture2D(night,vUv).rgb;col+=nl*nl*vec3(1.,.82,.55)*2.2*(1.-smoothstep(-.18,.06,d0))*(1.-cs*.8);
        // atmospheric haze toward the limb
        float mu=max(dot(N,V),0.);float haze=pow(1.-mu,2.2);
        vec3 sky=mix(vec3(1.,.45,.2),vec3(.3,.55,1.),smoothstep(-.05,.35,d0));
        col=mix(col,sky*max(d0+.15,0.)*.9,haze*.75);
        gl_FragColor=vec4(col,1.);}`,
  });
  const g = new THREE.Group();
  const seg = [192, 96];
  const ground = new THREE.Mesh(new THREE.SphereGeometry(radius, ...seg), surf);
  g.add(ground);
  const cloudMat = new THREE.ShaderMaterial({
    uniforms: uni, vertexShader: vs, transparent: true, depthWrite: false,
    fragmentShader: `uniform sampler2D clouds;uniform vec3 sunDir;uniform float time;varying vec3 vN,vW;varying vec2 vUv;
      void main(){vec3 N=normalize(vN),V=normalize(cameraPosition-vW);
        float c=texture2D(clouds,vUv+vec2(time*.0004,0.)).r;c=smoothstep(.04,.85,c);
        float d0=dot(N,sunDir);float lit=smoothstep(-.15,.3,d0);
        vec3 col=mix(vec3(1.,.7,.5),vec3(1.),smoothstep(0.,.35,d0))*(.08+lit*1.05);
        float mu=max(dot(N,V),0.);
        gl_FragColor=vec4(col,c*(.25+.75*smoothstep(0.,.25,mu)));}`,
  });
  const cl = new THREE.Mesh(new THREE.SphereGeometry(radius * 1.006, ...seg), cloudMat);
  g.add(cl);
  // atmosphere shell: scattered light around the limb
  const atmo = new THREE.Mesh(new THREE.SphereGeometry(radius * 1.045, 96, 48), new THREE.ShaderMaterial({
    uniforms: uni, transparent: true, depthWrite: false, side: THREE.BackSide, blending: THREE.AdditiveBlending,
    vertexShader: `varying vec3 vN,vW;void main(){vN=normalize(mat3(modelMatrix)*normal);vec4 w=modelMatrix*vec4(position,1.);vW=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}`,
    fragmentShader: `uniform vec3 sunDir;varying vec3 vN,vW;
      void main(){vec3 N=normalize(vN),V=normalize(cameraPosition-vW);
        // impact parameter of the view ray, in planet radii: 1 at the surface limb, 1.045 at the shell edge
        float ndv=abs(dot(N,V));float b=sqrt(max(0.,1.-ndv*ndv))*1.045;float t=clamp((1.045-b)/.045,0.,1.);
        float glow=t*t*1.7;
        float d0=dot(N,sunDir);
        vec3 c=mix(vec3(1.,.42,.15),vec3(.28,.55,1.),smoothstep(-.1,.4,d0))*smoothstep(-.35,.15,d0);
        gl_FragColor=vec4(c*glow,1.);}`,
  }));
  g.add(atmo);
  // ship.js animates `planet.material.uniforms.time` and spins the planet: keep both working on the group
  g.material = surf;
  return g;
}

// Surface sky dome: gradient + sun + drifting cloud noise; the horizon melts into the fog colour, and a world may
// hang a giant planet (banded, optionally ringed) or moons in its sky. Bodies are drawn analytically in direction
// space, so they sit at infinity and never clip.
export function atmosphereSky(top, horizon, sunColor, sunDir, opts = {}) {
  const B = opts.body || null, V3 = a => new THREE.Vector3(...a).normalize();
  const m = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false,
    uniforms: { top: { value: new THREE.Color(top) }, hor: { value: new THREE.Color(horizon) }, sunC: { value: new THREE.Color(sunColor) },
      sunDir: { value: sunDir.clone().normalize() }, time: { value: 0 }, fogC: { value: new THREE.Color(opts.fog || horizon) },
      hasBody: { value: B ? 1 : 0 }, bDir: { value: B ? V3(B.dir) : new THREE.Vector3(0, 1, 0) }, bSize: { value: B ? B.size : .1 },
      bCol: { value: new THREE.Color(B ? B.color : '#fff') }, bBand: { value: new THREE.Color(B ? B.band : '#fff') },
      ring: { value: new THREE.Vector2(...(B && B.ring ? B.ring : [0, 0])) }, ringCol: { value: new THREE.Color(B && B.ringColor ? B.ringColor : '#fff') },
      ringN: { value: B && B.tilt ? V3(B.tilt) : new THREE.Vector3(0, 1, 0) }, moon2: { value: B && B.moon2 ? V3(B.moon2) : new THREE.Vector3(0, -1, 0) } },
    vertexShader: `varying vec3 vD;void main(){vD=normalize(position);vec4 p=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_Position=p.xyww;}`,
    fragmentShader: NOISE + `varying vec3 vD;uniform vec3 top,hor,sunC,sunDir,fogC,bDir,bCol,bBand,ringCol,ringN,moon2;uniform float time,hasBody,bSize;uniform vec2 ring;
      // a sphere of angular radius r centred on direction C, lit by the sun; returns colour in rgb and coverage in a
      vec4 body(vec3 d,vec3 C,float r,vec3 col,vec3 band,float banded){
        vec3 T=normalize(cross(C,vec3(0.,1.,0.)+vec3(1e-4)));vec3 U=cross(T,C);
        vec2 q=vec2(dot(d,T),dot(d,U))/r;float r2=dot(q,q);if(dot(d,C)<0.||r2>1.)return vec4(0.);
        // the hemisphere facing us: normal points back toward the viewer
        vec3 N=normalize(q.x*T+q.y*U-sqrt(1.-r2)*C);
        float l=clamp(dot(N,sunDir),0.,1.);
        float lat=q.y+fbm(vec3(q*3.,1.))*.12;
        vec3 c=mix(col,band,banded*(.5+.5*sin(lat*22.+sin(lat*7.)*2.)));
        c*=.85+fbm(vec3(q*9.,3.))*.3;
        float edge=smoothstep(1.,.96,r2);
        return vec4(c*(l*1.1+.04),edge);}
      void main(){vec3 d=normalize(vD);float y=max(d.y,0.);
        vec3 c=mix(hor,top,pow(y,.55));if(d.y<0.)c=hor*.8;
        float s=max(dot(d,sunDir),0.);
        c+=sunC*(pow(s,1200.)*30.+pow(s,60.)*.5+pow(s,6.)*.18);
        vec2 uv=d.xz/(d.y+.15);float cl=smoothstep(.5,.85,fbm(vec3(uv*1.4+vec2(time*.004,0.),0.)));
        if(hasBody>.5){
          vec4 b=body(d,bDir,bSize,bCol,bBand,1.);
          // rings: intersect the view ray with the ring plane through the body (body at unit distance)
          if(ring.y>0.){float dn=dot(d,ringN);if(abs(dn)>1e-4){float t=dot(bDir,ringN)/dn;vec3 p=d*t-bDir;float rr=length(p)/bSize;
            if(t>0.&&rr>ring.x&&rr<ring.y){float k=(rr-ring.x)/(ring.y-ring.x);
              float dens=(.55+.45*sin(k*60.)*sin(k*13.+1.))*smoothstep(0.,.05,k)*smoothstep(1.,.9,k)*(1.-smoothstep(.42,.46,k)*smoothstep(.5,.46,k));
              vec3 rc=ringCol*(.35+.75*max(dot(ringN,sunDir)*sign(dot(ringN,-d)),0.)+.25);
              bool behind=b.a>0.&&t>1.;
              if(!behind)c=mix(c,rc,dens*.8);}}}
          c=mix(c,b.rgb+c*.25,b.a*.92);
          vec4 m2=body(d,moon2,bSize*.55,bCol*.9,bBand,.0);c=mix(c,m2.rgb+c*.2,m2.a*.9);
        }
        c=mix(c,mix(hor*1.1,vec3(1.),.4)+sunC*pow(s,8.)*.4,cl*smoothstep(0.,.25,d.y)*.55);
        // haze toward the horizon matches the scene fog so far terrain melts into the sky
        c=mix(c,fogC,smoothstep(.22,0.,d.y)*.85);
        gl_FragColor=vec4(c,1.);}`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(900, 32, 16), m);
  mesh.frustumCulled = false; mesh.renderOrder = -10;
  return mesh;
}
