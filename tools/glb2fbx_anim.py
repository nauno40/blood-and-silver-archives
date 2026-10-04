"""Script Blender (arrière-plan) : GLB riggé -> FBX avec armature + toutes les animations (une pile par clip),
puis réimport du FBX pour compter os et animations.
Usage : blender -b --factory-startup -P glb2fbx_anim.py -- <liste.txt>  (lignes « glb<TAB>fbx »)
Affiche « OK nom os=N clips=A/B » ou « ERREUR nom ... »."""
import bpy, sys, os

args = sys.argv[sys.argv.index("--") + 1:]
pairs = [l.rstrip("\r\n").split("\t") for l in open(args[0], encoding="utf-8-sig") if l.strip()]

for src, dst in pairs:
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=src)
        n_src = len(bpy.data.actions)
        bones = sum(len(a.data.bones) for a in bpy.data.objects if a.type == "ARMATURE")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        bpy.ops.export_scene.fbx(filepath=dst, use_selection=False, object_types={"MESH", "EMPTY", "ARMATURE"},
                                 path_mode="COPY", embed_textures=True, axis_forward="-Z", axis_up="Y",
                                 apply_unit_scale=True, bake_space_transform=False, add_leaf_bones=False,
                                 bake_anim=True, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
                                 bake_anim_force_startend_keying=True, bake_anim_simplify_factor=1.0)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=dst)
        n_dst = len({a.name.split("|")[-1] for a in bpy.data.actions})
        print(f"OK {os.path.basename(dst)} os={bones} clips={n_dst}/{n_src}", flush=True)
    except Exception as e:
        print("ERREUR", os.path.basename(src), type(e).__name__, str(e)[:200], flush=True)
