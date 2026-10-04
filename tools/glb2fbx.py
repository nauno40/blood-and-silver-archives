"""Script Blender (mode arrière-plan) : convertit des GLB en FBX, textures intégrées.
Usage : blender -b --factory-startup -P glb2fbx.py -- <liste.txt>
liste.txt : une ligne « chemin.glb<TAB>chemin.fbx » par modèle. Affiche OK/ERREUR par modèle."""
import bpy, sys, os, traceback

args = sys.argv[sys.argv.index("--") + 1:]
pairs = [l.rstrip("\r\n").split("\t") for l in open(args[0], encoding="utf-8-sig") if l.strip()]  # -sig : ignore le BOM

for src, dst in pairs:
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=src)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        bpy.ops.export_scene.fbx(filepath=dst, use_selection=False, object_types={"MESH", "EMPTY", "ARMATURE"},
                                 path_mode="COPY", embed_textures=True, axis_forward="-Z", axis_up="Y",
                                 apply_unit_scale=True, bake_space_transform=False, add_leaf_bones=False)
        print("OK", os.path.basename(dst), flush=True)
    except Exception as e:
        print("ERREUR", os.path.basename(src), type(e).__name__, str(e)[:200], flush=True)
