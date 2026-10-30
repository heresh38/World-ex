"""Cuts texture swatches out of the owner's reference art (art/reference/*.jpg) inside Blender.

Every crop box is in source pixels (x0, y0, x1, y1). Output: assets/textures/char_<name>.jpg (used by wardrobe.py and
civilians.py).
"""
import bpy, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl

REF = os.path.join(bl.ROOT, 'art', 'reference')

# name: (image, box, out_size, mode)   mode 'tile' = mirrored-seam tile, 'stretch' = keep as is
SWATCHES = {
    # female, circuit coat / crop look
    'coat_circuit': ('female_circuit_coat', (610, 372, 648, 470), (256, 512), 'tile'),
    'ribbed_white': ('female_knit', (668, 420, 704, 500), (256, 512), 'rib'),
    'harness_olive': ('female_circuit_coat', (664, 168, 678, 214), (128, 256), 'tile'),
    'chest_sparkle': ('female_circuit_coat', (722, 204, 758, 220), (256, 128), 'stretch'),
    'gauntlet_dark': ('female_circuit_coat', (642, 283, 688, 304), (256, 128), 'stretch'),
    'kneepad': ('female_circuit_coat', (642, 505, 684, 545), (256, 256), 'stretch'),
    'greave_dark': ('female_circuit_coat', (646, 568, 674, 628), (128, 256), 'tile'),
    'boot_tech': ('female_circuit_coat', (626, 684, 668, 736), (256, 256), 'stretch'),
    # female, knit look
    'knit_white': ('female_knit', (700, 238, 748, 278), (256, 256), 'knit'),
    'boot_white': ('female_knit', (628, 660, 664, 712), (256, 256), 'stretch'),
    # female, off-duty look
    'tank_black': ('female_offduty', (700, 210, 760, 272), (256, 256), 'rib'),
    'pants_olive': ('female_offduty', (692, 352, 738, 450), (256, 512), 'canvas'),
    'boot_brown': ('female_offduty', (630, 668, 668, 716), (256, 256), 'stretch'),
    # hair
    'hair_ponytail': ('female_knit', (576, 300, 604, 560), (128, 1024), 'stretch'),
    'hair_top_f': ('female_knit', (690, 44, 752, 66), (256, 128), 'tile'),
    'hair_long': ('female_offduty', (652, 150, 678, 300), (128, 512), 'stretch'),
    'braid_lilac': ('female_knit', (650, 92, 664, 250), (64, 512), 'stretch'),
    'hair_male': ('male_vanguard', (860, 118, 950, 160), (256, 128), 'tile'),
    # male, vanguard plate armour
    'plate_steel': ('male_vanguard', (822, 470, 880, 556), (256, 256), 'tile'),
    'abdomen_plates': ('male_vanguard', (840, 640, 975, 720), (512, 256), 'stretch'),
    'pauldron_steel': ('male_vanguard', (690, 420, 760, 500), (256, 256), 'stretch'),
    'undersuit_black': ('male_vanguard', (872, 346, 926, 380), (256, 128), 'rib'),
    'glove_black': ('male_vanguard', (1228, 470, 1284, 540), (256, 256), 'stretch'),
    # male, ranger armour
    'plate_rust': ('male_ranger_armor', (700, 172, 740, 214), (256, 256), 'tile'),
    'shoulder_emblem': ('male_ranger_armor', (604, 152, 664, 214), (256, 256), 'stretch'),
    'plate_green': ('male_ranger_armor', (766, 392, 800, 460), (256, 512), 'stretch'),
    'plate_rust_leg': ('male_ranger_armor', (662, 392, 700, 460), (256, 512), 'stretch'),
    'plate_tan': ('male_ranger_armor', (650, 522, 690, 560), (256, 256), 'stretch'),
    'under_olive': ('male_ranger_armor', (662, 252, 690, 292), (128, 256), 'canvas'),
    'pouch_olive': ('male_ranger_armor', (702, 250, 752, 292), (256, 256), 'stretch'),
    'boot_dark': ('male_ranger_armor', (622, 700, 660, 736), (256, 256), 'stretch'),
    'wrist_screen': ('male_ranger_armor', (586, 302, 620, 350), (128, 256), 'stretch'),
    # male, field jacket
    'vest_camo': ('male_field_jacket', (684, 182, 712, 240), (256, 256), 'tile'),
    'sleeve_blue_red': ('male_field_jacket', (616, 165, 652, 290), (128, 512), 'stretch'),
    'sleeve_tan': ('male_field_jacket', (788, 190, 812, 262), (128, 256), 'canvas'),
    'cargo_pants': ('male_field_jacket', (700, 420, 748, 520), (256, 512), 'canvas'),
    'boot_black': ('male_field_jacket', (630, 642, 668, 700), (256, 256), 'stretch'),
}

def load(name):
    img = bpy.data.images.load(os.path.join(REF, name + '.jpg'), check_existing=True)
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    return a[::-1]          # top-down rows to match the pixel boxes


def resize(a, size):
    """Bilinear resize of an (h, w, c) array to (W, H)."""
    W, H = size
    h, w = a.shape[:2]
    ys = np.linspace(0, h - 1, H); xs = np.linspace(0, w - 1, W)
    y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int)
    y1 = np.minimum(y0 + 1, h - 1); x1 = np.minimum(x0 + 1, w - 1)
    fy = (ys - y0)[:, None, None]; fx = (xs - x0)[None, :, None]
    top = a[y0][:, x0] * (1 - fx) + a[y0][:, x1] * fx
    bot = a[y1][:, x0] * (1 - fx) + a[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy


def make_tileable(a):
    """Cross-fade with a half-offset copy so the swatch repeats without hard seams."""
    h, w = a.shape[:2]
    b = np.roll(np.roll(a, h // 2, 0), w // 2, 1)
    yy = np.abs(np.linspace(-1, 1, h))[:, None]; xx = np.abs(np.linspace(-1, 1, w))[None, :]
    m = np.clip(np.maximum(xx, yy) * 1.6 - .6, 0, 1)[..., None]   # 1 near the edges -> use the shifted copy
    return a * (1 - m) + b * m


def fabric(crop, mode):
    """Clean, seamless fabric in the swatch's measured colour: vertical rib, cable knit or canvas weave."""
    rng = np.random.default_rng(len(mode))
    h, w = crop.shape[:2]
    base = np.median(crop[..., :3].reshape(-1, 3), axis=0)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    if mode == 'rib':
        pat = .5 + .5 * np.cos(xx / w * 2 * np.pi * 24)
        shade = .86 + .14 * pat
    elif mode == 'knit':
        pat = np.abs(np.sin((xx / w * 16 + np.abs(((yy / h * 32) % 2) - 1) * .5) * np.pi))
        shade = .84 + .16 * pat
    else:
        warp = .5 + .5 * np.sin(xx / w * 2 * np.pi * 48); weft = .5 + .5 * np.sin(yy / h * 2 * np.pi * 48)
        shade = .9 + .06 * (warp * weft) + .04 * rng.random((h, w))
    n = rng.normal(0, .015, (h, w))
    out = np.empty((h, w, 4), dtype=np.float32)
    out[..., :3] = base[None, None, :] * (shade + n)[..., None]
    out[..., 3] = 1
    return out


def save(arr, name):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h)
    out = np.ones((h, w, 4), dtype=np.float32)
    out[..., :3] = np.clip(arr[..., :3], 0, 1)
    img.pixels = out[::-1].ravel()
    path = os.path.join(bl.TEXTURES, name + '.jpg')
    sc = bpy.context.scene
    sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 90
    img.save_render(path)
    print('[ref]', name, w, h)
    return path


def main():
    for name, (img, box, size, mode) in SWATCHES.items():
        a = load(img)
        x0, y0, x1, y1 = box
        crop = resize(a[y0:y1, x0:x1], size)
        if mode == 'tile':
            crop = make_tileable(crop)
        elif mode in ('rib', 'knit', 'canvas'):
            crop = fabric(crop, mode)
        save(crop, 'char_' + name)


if __name__ == '__main__':
    main()


def hair_cards():
    """RGBA strand texture for alpha-tested hair cards, coloured from the reference hair swatches."""
    rng = np.random.default_rng(7)
    for name, src in (('hair_card_f', 'char_hair_ponytail'), ('hair_card_m', 'char_hair_male')):
        img = bpy.data.images.load(os.path.join(bl.TEXTURES, src + '.jpg'), check_existing=True)
        px = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)[..., :3]
        base = np.percentile(px.reshape(-1, 3), 45, axis=0); hi = np.percentile(px.reshape(-1, 3), 92, axis=0)
        W, Ht = 256, 1024
        out = np.zeros((Ht, W, 4), dtype=np.float32)
        x = np.arange(W)
        # strands: many thin bands with their own brightness and length
        bright = np.zeros(W); alpha = np.zeros((Ht, W))
        for s in range(140):
            c = rng.uniform(0, W); w = rng.uniform(.8, 2.6); b = rng.uniform(0, 1)
            prof = np.exp(-((x - c) ** 2) / (2 * w * w))
            bright = np.maximum(bright, prof * b)
            length = rng.uniform(.55, 1.0)
            col = np.clip(np.linspace(0, 1, Ht) / length, 0, 1)        # 0 at root .. 1 at tip
            tip = np.clip((1 - col) * 6, 0, 1)                        # taper the last sixth
            alpha = np.maximum(alpha, prof[None, :] * tip[:, None])
        wave = .5 + .5 * np.sin(np.linspace(0, 40, Ht))[:, None] * .15
        shade = np.clip(bright[None, :] * .9 + wave * .2, 0, 1)
        out[..., :3] = base[None, None, :] * (1 - shade[..., None] * .8) + hi[None, None, :] * (shade[..., None] * .8)
        out[..., :3] *= (.75 + .25 * np.linspace(0, 1, Ht))[:, None, None] ** -.3
        out[..., 3] = np.clip(alpha * 1.6, 0, 1)
        h, w = out.shape[:2]
        im = bpy.data.images.new(name, w, h, alpha=True)
        im.pixels = np.clip(out, 0, 1)[::-1].ravel()
        im.filepath_raw = os.path.join(bl.TEXTURES, name + '.png'); im.file_format = 'PNG'; im.save()
        print('[ref]', name)


if __name__ == '__main__':
    hair_cards()
