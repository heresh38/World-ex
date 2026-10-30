// Procedural skies: deep space (stars + nebula + a planet below the ship) and atmospheric domes for surfaces.
import * as THREE from 'three';

const NOISE = `
float h3(vec3 p){p=fract(p*.3183099+.1);p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
float n3(vec3 x){vec3 i=floor(x),f=fract(x);f=f*f*(3.-2.*f);
 return mix(mix(mix(h3(i),h3(i+vec3(1,0,0)),f.x),mix(h3(i+vec3(0,1,0)),h3(i+vec3(1,1,0)),f.x),f.y),
            mix(mix(h3(i+vec3(0,0,1)),h3(i+vec3(1,0,1)),f.x),mix(h3(i+vec3(0,1,1)),h3(i+vec3(1,1,1)),f.x),f.y),f.z);}
float fbm(vec3 p){float s=0.,a=.5;for(int i=0;i<5;i++){s+=a*n3(p);p*=2.03;a*=.5;}return s;}`;

export function spaceSky(opts = {}) {
  const m = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, toneMapped: true,
    uniforms: { tint: { value: new THREE.Color(opts.nebula || '#3a5a9a') }, tint2: { value: new THREE.Color(opts.nebula2 || '#8a3a6a') }, sunDir: { value: (opts.sunDir || new THREE.Vector3(-.3, .5, -.8)).clone().normalize() } },
    vertexShader: `varying vec3 vD;void main(){vD=normalize(position);vec4 p=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_Position=p.xyww;}`,
    fragmentShader: NOISE + `varying vec3 vD;uniform vec3 tint,tint2,sunDir;
      void main(){vec3 d=normalize(vD);
        float st=pow(h3(floor(d*420.)),60.)*3.+pow(h3(floor(d*900.)+3.),120.)*2.;
        float neb=fbm(d*2.2+vec3(3.));float neb2=fbm(d*3.7-vec3(5.));
        vec3 c=tint*pow(neb,3.)*1.1+tint2*pow(neb2,4.)*.9;
        float band=exp(-pow(d.y*2.5+sin(d.x*3.)*.3,2.));c+=vec3(.6,.55,.5)*band*pow(fbm(d*8.),2.)*.25;
        c+=vec3(st);
        float s=max(dot(d,sunDir),0.);c+=vec3(1.,.9,.75)*(pow(s,800.)*40.+pow(s,24.)*.25);
        gl_FragColor=vec4(c,1.);}`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(900, 32, 16), m);
  mesh.frustumCulled = false; mesh.renderOrder = -10;
  return mesh;
}

// A planet seen from orbit: banded/noisy surface, cloud layer, atmosphere rim lit by the sun direction.
export function orbitPlanet(colors, sunDir, radius = 420) {
  const m = new THREE.ShaderMaterial({
    uniforms: { a: { value: new THREE.Color(colors[0]) }, b: { value: new THREE.Color(colors[1]) }, c: { value: new THREE.Color(colors[2] || colors[1]) },
      sunDir: { value: sunDir.clone().normalize() }, time: { value: 0 }, ocean: { value: colors.ocean ? 1 : 0 } },
    vertexShader: `varying vec3 vN,vP,vW;void main(){vN=normalize(normalMatrix*normal);vP=position;vec4 w=modelMatrix*vec4(position,1.);vW=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}`,
    fragmentShader: NOISE + `varying vec3 vN,vP,vW;uniform vec3 a,b,c,sunDir;uniform float time,ocean;
      void main(){vec3 p=normalize(vP);float n=fbm(p*3.5);float n2=fbm(p*9.+3.);
        vec3 col=mix(a,b,smoothstep(.35,.65,n));col=mix(col,c,smoothstep(.55,.8,n2)*.6);
        if(ocean>.5){float land=smoothstep(.5,.53,n);col=mix(vec3(.02,.08,.2),mix(vec3(.15,.32,.12),vec3(.5,.42,.3),n2),land);
          col=mix(col,vec3(.9),smoothstep(.75,.95,abs(p.y)));}
        float cl=smoothstep(.55,.75,fbm(p*5.+vec3(time*.01,0.,0.)));col=mix(col,vec3(1.),cl*.7);
        vec3 N=normalize(vN);vec3 L=normalize((viewMatrix*vec4(sunDir,0.)).xyz);
        float dl=max(dot(N,L),0.);vec3 V=normalize(-(viewMatrix*vec4(vW,1.)).xyz);
        float rim=pow(1.-max(dot(N,V),0.),3.);
        vec3 lit=col*(dl*1.2+.03)+vec3(.35,.6,1.)*rim*(dl*.8+.05)*1.5;
        float night=1.-smoothstep(0.,.15,dl);if(ocean>.5)lit+=vec3(1.,.7,.3)*night*smoothstep(.62,.7,n2)*smoothstep(.5,.53,n)*.6;
        gl_FragColor=vec4(lit,1.);}`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, 64, 32), m);
  return mesh;
}

// Surface sky dome: gradient + sun + drifting cloud noise.
export function atmosphereSky(top, horizon, sunColor, sunDir) {
  const m = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false,
    uniforms: { top: { value: new THREE.Color(top) }, hor: { value: new THREE.Color(horizon) }, sunC: { value: new THREE.Color(sunColor) },
      sunDir: { value: sunDir.clone().normalize() }, time: { value: 0 } },
    vertexShader: `varying vec3 vD;void main(){vD=normalize(position);vec4 p=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_Position=p.xyww;}`,
    fragmentShader: NOISE + `varying vec3 vD;uniform vec3 top,hor,sunC,sunDir;uniform float time;
      void main(){vec3 d=normalize(vD);float y=max(d.y,0.);
        vec3 c=mix(hor,top,pow(y,.55));if(d.y<0.)c=hor*.8;
        float s=max(dot(d,sunDir),0.);
        c+=sunC*(pow(s,1200.)*30.+pow(s,60.)*.5+pow(s,6.)*.18);
        vec2 uv=d.xz/(d.y+.15);float cl=smoothstep(.5,.85,fbm(vec3(uv*1.4+vec2(time*.004,0.),0.)));
        c=mix(c,mix(hor*1.1,vec3(1.),.4)+sunC*pow(s,8.)*.4,cl*smoothstep(0.,.25,d.y)*.55);
        gl_FragColor=vec4(c,1.);}`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(900, 32, 16), m);
  mesh.frustumCulled = false; mesh.renderOrder = -10;
  return mesh;
}
