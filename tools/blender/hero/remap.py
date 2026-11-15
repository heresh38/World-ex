"""Writes some of the players' cloth / plate maps again without building a body (fabric.make skips a map that
exists, and a body's build is minutes): the maps of the given kinds are made afresh for both bodies, in their own
folders and names, and copied over the exported copies the import reads.

  blender --background --python tools/blender/hero/remap.py -- polymer [leather rubber ...]

then `SO_IMPORT_ONLY=player_textures` brings them into the game.
"""
import os
import shutil
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.dirname(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import fabric                                                   # noqa: E402
import wardrobe                                                 # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "unreal", "ShatteredOrbit", "SourceArt", "Characters"))


def main():
    kinds = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["polymer"]
    for sex in ("male", "female"):
        out_dir = os.path.join(ROOT, "src", "tex", sex)
        for name, (kind, _clip) in fabric.TEXTURED.items():
            if kind not in kinds or name not in wardrobe.PALETTE:
                continue
            col, rough, metal = wardrobe.PALETTE[name]
            prefix = f"hero_{sex}_{name[6:]}"
            for s in ("c", "n", "m"):
                p = os.path.join(out_dir, f"{prefix}_{kind}_{s}.png")
                if os.path.exists(p):
                    os.remove(p)
            paths = fabric.make(kind, col, rough, out_dir, prefix, metal, seed=zlib.crc32(name.encode()) % 9973)
            for folder in (f"Player{sex.capitalize()}", f"Player{sex.capitalize()}Arms"):
                dest = os.path.join(ROOT, folder, "Textures")
                for p in paths:
                    if os.path.exists(os.path.join(dest, os.path.basename(p))):
                        shutil.copyfile(p, os.path.join(dest, os.path.basename(p)))
            print(f"[remap] {prefix}_{kind}", flush=True)


main()
