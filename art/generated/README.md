# Generated base characters

Untextured Hunyuan3D-2 shape meshes made from the owner's female and male base character sheets
(front, side and back views). Reference only: no rig, UVs or materials, and body, hair and clothing are one mesh.

| File | Faces | Verts | Size | Generation |
|---|---|---|---|---|
| `female_base.glb` | 100,000 (raw 258,184) | 50,002 | 1.8 MB | 7.0 s |
| `male_base.glb` | 100,000 (raw 292,336) | 50,002 | 1.8 MB | 6.6 s |

- Model: `tencent/Hunyuan3D-2mv`, subfolder `hunyuan3d-dit-v2-mv-turbo`, FlashVDM on, seed 12345
- Settings: 5 steps, octree resolution 380, 20,000 chunks; rembg cutouts; sheet side view in the `right` slot
- Cleanup: floaters and degenerate faces removed, reduced to 100k faces
- Hardware: RTX 4070 Ti (12 GB), 5.5 GB peak VRAM (`torch.cuda.max_memory_allocated`)
- Software: PyTorch 2.14.1+cu126, transformers 4.48.3, diffusers 0.32.2. Newer transformers 5.x fails to load the image encoder weights
- Scale: normalised to about 2 units tall, not metres

Texture generation was not run: the texture extensions need the CUDA toolkit and Visual Studio C++ Build Tools,
and the card is under the 16 GB target.

The Tencent Hunyuan 3D 2.0 Community License excludes the EU, UK and South Korea, including use of its output there.
Shipping these in the game would also conflict with the Blender-only asset rule in `CLAUDE.md`.
