"""Builds a single-page, self-contained web build in dist/ (for hosts that only serve a page plus data files).

The game modules and three.js are bundled with esbuild and inlined into dist/world-ex.html; the models and
textures are copied next to it. Hosts that will not serve .glb files get the models under a .wasm name
(BINARY_EXT); the loader only reads raw bytes, so the extension does not matter to the game.
Usage: python3 tools/build_artifact.py        (needs node; fetches esbuild with npx on first run)
"""
import json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, 'dist')
BINARY_EXT = os.environ.get('BINARY_EXT', '.wasm')
TEXTURES = re.compile(r'(concrete|asphalt|rock|sand|ice|moss)_[cn]\.jpg$|(facade|ribbon)_e\.jpg$|(wheat|field_rows)_c\.jpg$|earth_(day|clouds|night|ms)\.jpg$')


def main():
    os.makedirs(DIST, exist_ok=True)
    js_out = os.path.join(DIST, 'game.js')
    subprocess.run(['npx', '--yes', 'esbuild@0.24.0', 'src/main.js', '--bundle', '--format=esm', '--minify', '--target=es2020',
                    '--alias:three=./lib/three/build/three.module.js', '--alias:three/addons=./lib/three/jsm',
                    '--outfile=' + js_out], cwd=ROOT, check=True)
    js = open(js_out).read()
    assert '</script' not in js
    if BINARY_EXT != '.glb':
        js = js.replace('.glb"', BINARY_EXT + '"')
    css = open(os.path.join(ROOT, 'src/ui/style.css')).read()
    idx = open(os.path.join(ROOT, 'index.html')).read()
    head_meta = '\n'.join(m for m in re.findall(r'<meta name="(?:apple|mobile)[^>]*>', idx))
    body = idx[idx.index('<body>') + 6:idx.index('<noscript>')]
    html = f'''<title>WORLD EX</title>
{head_meta}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600&display=swap">
<style>
:root{{color-scheme:dark}}
{css}
</style>
{body}
<script type="module">
{js}
</script>
'''
    open(os.path.join(DIST, 'world-ex.html'), 'w').write(html)
    os.remove(js_out)
    files = {}
    for d in ('assets/models', 'assets/textures'):
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            if d.endswith('textures') and not TEXTURES.match(f):
                continue
            pub = f'{d}/{f}'
            if pub.endswith('.glb'):
                pub = pub[:-4] + BINARY_EXT
            files[pub] = f'{d}/{f}'
            dst = os.path.join(DIST, pub)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, d, f), dst)
    json.dump(files, open(os.path.join(DIST, 'files.json'), 'w'), indent=1)
    print('dist/world-ex.html', len(html) // 1024, 'KB;', len(files), 'asset files')


if __name__ == '__main__':
    main()
