import sys
from PIL import Image, ImageDraw, ImageFont, ImageChops
S, out = sys.argv[1], sys.argv[2]
views = ["a_front", "b_3q_left", "c_profile_left", "d_back_3q_left", "e_back", "f_3q_right", "g_profile_right", "h_above"]
labels = ["front", "3/4 left", "profile left", "back 3/4", "back", "3/4 right", "profile right", "above"]
def img(k, v): return Image.open(f"{S}/cmp/{k}_{v}.png").convert("RGB")
def overlay(k, v):
    a = img("mh", v).convert("L"); b = img(k, v).convert("L")
    # Epic in cyan, ours in orange: where they agree the shapes overlap (grey/white), mismatches show as a colour fringe
    return Image.merge("RGB", (b, ImageChops.lighter(a, b).point(lambda x: x * .9), a))
rows = [("Epic MetaHuman", lambda v: img("mh", v)), ("Ours male", lambda v: img("male", v)),
        ("Overlay male\n(cyan Epic,\n orange ours)", lambda v: overlay("male", v)), ("Ours female", lambda v: img("female", v)),
        ("Overlay female", lambda v: overlay("female", v))]
C, L, T = 260, 170, 30
sheet = Image.new("RGB", (L + C * 8, T + C * len(rows)), (24, 26, 30)); d = ImageDraw.Draw(sheet)
try: f = ImageFont.truetype("arial.ttf", 17)
except Exception: f = ImageFont.load_default()
for i, l in enumerate(labels): d.text((L + i * C + 8, 6), l, fill=(220, 225, 235), font=f)
for r, (name, fn) in enumerate(rows):
    d.multiline_text((8, T + r * C + C // 2 - 24), name, fill=(220, 225, 235), font=f)
    for i, v in enumerate(views):
        sheet.paste(fn(v).resize((C - 4, C - 4)), (L + i * C + 2, T + r * C + 2))
sheet.save(out, quality=90)
