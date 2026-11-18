"""The layout sheet: the reference with our hand's outline and joints drawn over it, our clay with the reference's
outline over it, and where the two differ (red ours only, blue the reference's only).
python handsheet.py <ref.png> <x0> <x1> <ref_prefix: handref.py's> <ours_prefix: handlay.py's> <out.png> [--title=...]
The overlap and the areas only one of them covers (above the wrist) are printed and written on the sheet."""
import sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

ref_png, x0, x1, rp, op, outp = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6]
flags = dict(a.split("=", 1) for a in sys.argv[7:] if "=" in a)
R = Image.open(ref_png).convert("RGB").crop((x0, 0, x1, Image.open(ref_png).size[1]))
W, H = R.size
mr = np.load(rp + "_mask.npy")
sil = np.asarray(Image.open(op + "_sil.png").convert("RGBA"))[..., 3] > 127
J = json.load(open(op + "_joints.json"))["joints"]
refj = json.load(open(rp + ".json"))
wrist_row = int(round(refj["origin"][1]))


def outline(m):
    return m ^ ndi.binary_erosion(m, iterations=2)


def paint(img, m, col):
    a = np.asarray(img).copy()
    a[m] = col
    return Image.fromarray(a)


# A: the reference, our outline and joints over it
A = paint(R, outline(sil), (230, 30, 30))
dA = ImageDraw.Draw(A)
for name, pts in J.items():
    if name == "wrist":
        continue
    pts = [tuple(p) for p in pts]
    dA.line(pts, fill=(230, 30, 30), width=2)
    for p in pts:
        dA.ellipse([p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4], fill=(230, 30, 30))
w = J["wrist"]
dA.ellipse([w[0] - 5, w[1] - 5, w[0] + 5, w[1] + 5], outline=(230, 30, 30), width=2)
# B: our clay, the reference's outline over it
try:
    C = Image.open(op + "_clay.png").convert("RGBA")
    bgc = Image.new("RGBA", C.size, (245, 245, 245, 255))
    C = Image.alpha_composite(bgc, C).convert("RGB")
except FileNotFoundError:
    C = Image.new("RGB", (W, H), (245, 245, 245))
B = paint(C, outline(mr), (30, 90, 255))
# C: the difference (above the wrist only: the forearms are not ours to match)
hand = np.zeros_like(mr); hand[:wrist_row] = True
D = np.full((H, W, 3), 255, np.uint8)
both = mr & sil
D[both] = (205, 205, 205)
D[sil & ~mr] = (230, 40, 40)
D[mr & ~sil] = (40, 90, 255)
D[~hand] = (D[~hand] * .35 + 255 * .65).astype(np.uint8)
Dm = Image.fromarray(D)
dD = ImageDraw.Draw(Dm)
dD.line([(0, wrist_row), (W, wrist_row)], fill=(0, 0, 0), width=1)
inter = (both & hand).sum(); uni = ((mr | sil) & hand).sum()
ours_only = (sil & ~mr & hand).sum(); ref_only = (mr & ~sil & hand).sum()
px_cm = 1.0 / refj["scale_cm_px"]
txt = (f"overlap {inter / uni:.3f}   ours only {ours_only / px_cm ** 2:.1f} cm2   reference only "
       f"{ref_only / px_cm ** 2:.1f} cm2")
print(txt)
sheet = Image.new("RGB", (W * 3 + 40, H + 60), (255, 255, 255))
for i, im in enumerate((A, B, Dm)):
    sheet.paste(im, (10 + i * (W + 10), 50))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("arial.ttf", 18)
except Exception:
    font = None
d.text((12, 8), flags.get("--title", "") + "   red: ours   blue: the reference   " + txt, fill=(0, 0, 0), font=font)
sheet.save(outp)
print("saved", outp)
