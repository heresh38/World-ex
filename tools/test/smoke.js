// Smoke test: loads the built game, drives a hover car in first person, saves screenshots to test-out/.
// Usage: npm run serve (in one terminal), then: npm test   [BASE=http://localhost:8765]
const {chromium}=require('playwright');const fs=require('fs');
const BASE=process.env.BASE||'http://localhost:8765';fs.mkdirSync('test-out',{recursive:true});
(async()=>{const b=await chromium.launch({args:['--ignore-gpu-blocklist','--enable-unsafe-swiftshader']});
const p=await b.newPage({viewport:{width:1280,height:720}});const errs=[];p.on('pageerror',e=>{errs.push(e.message);console.log('PAGE ERROR',e.message.slice(0,300))});
await p.addInitScript(()=>{window.__TEST=1});
await p.goto(BASE+'/index.html');
await p.waitForFunction(()=>{const l=document.getElementById('load');return l&&getComputedStyle(l).display==='none'},null,{timeout:600000});
const ev=c=>p.evaluate(c=>window.__ev(`(async()=>{try{${c}}catch(e){return 'ERR '+e.message}})()`),c);
const W=ms=>`await new Promise(r=>setTimeout(r,${ms}));`;const shot=n=>p.screenshot({path:'test-out/'+n+'.jpg',type:'jpeg',quality:82});
console.log('vehicles',await ev(`closeMenu();${W(4000)}return cars.map(c=>c.hv97||c.air||'?').join(',')`));
console.log('enter',await ev(`const c=cars.find(c=>c.hv97==='vanta');pl.x=c.x-1.5;pl.z=c.z;pl.y=Gw(pl.x,pl.z);toggleCar();FP=true;${W(5000)}return cur&&cur.hv97`));await shot('cockpit');
console.log('steer',await ev(`keys.KeyA=true;keys.KeyW=true;${W(4000)}keys.KeyA=false;keys.KeyW=false;return 'steer '+cur.steer.toFixed(2)+' yoke '+SEAT69.st.toFixed(2)`));await shot('cockpit_turn');
console.log('exit',await ev(`FP=false;toggleCar();${W(3000)}return cur?'still in car':'on foot'`));await shot('outside');
console.log('page errors:',errs.length);await b.close();process.exit(errs.length?1:0)})();
