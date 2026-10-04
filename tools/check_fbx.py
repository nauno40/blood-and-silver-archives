"""Script Blender : réimporte des FBX et compare au GLB d'origine (maillages, triangles, textures).
Usage : blender -b --factory-startup -P check_fbx.py -- <liste.txt>   (lignes « glb<TAB>fbx »)"""
import bpy, sys

args = sys.argv[sys.argv.index("--") + 1:]
pairs = [l.rstrip("\r\n").split("\t") for l in open(args[0], encoding="utf-8-sig") if l.strip()]

def stats():
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
    imgs = [i for i in bpy.data.images if i.size[0] > 0]
    return len(meshes), tris, len(imgs)

for glb, fbx in pairs:
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb); a = stats()
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.fbx(filepath=fbx); b = stats()
    ok = a[0] == b[0] and a[1] == b[1] and b[2] >= min(a[2], 1)
    print(("IDENTIQUE" if ok else "DIFFERENT"), fbx.split("\\")[-1], "glb(maillages,triangles,textures)=", a, "fbx=", b, flush=True)
