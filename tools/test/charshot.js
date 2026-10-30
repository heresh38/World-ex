// Renders character viewer shots in three.js. Usage: node tools/test/charshot.js out.png model outfit hair [views] [W H]
const { chromium } = require('playwright');
(async () => {
  const [out, m, o, h, vs, W, H] = process.argv.slice(2);
  const views = (vs || 'front,q,back,face').split(',');
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: +(W || 420), height: +(H || 680) } });
  p.on('pageerror', e => console.log('PAGE ERROR', e.message));
  const shots = [];
  for (const v of views) {
    await p.goto(`http://localhost:8765/tools/test/charview.html?m=${m}&o=${o}&h=${h}&v=${v}`);
    await p.waitForFunction(() => window.__ready, null, { timeout: 300000 });
    shots.push(await p.screenshot({ timeout: 300000 }));
  }
  await b.close();
  // stitch horizontally
  const fs = require('fs');
  shots.forEach((s, i) => fs.writeFileSync(out.replace(/\.png$/, '_' + i + '.png'), s));
  console.log('ok', views.length);
})();
