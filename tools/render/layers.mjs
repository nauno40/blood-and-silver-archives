// Analyse des couches d'un squelette : quels os / slots chaque animation pilote.
// Usage : node layers.mjs <dossier_squelette>
import fs from "node:fs"; import path from "node:path"; import * as spine from "@esotericsoftware/spine-core";
class T extends spine.Texture { setFilters() {} setWraps() {} dispose() {} }
const D = process.argv[2], fl = fs.readdirSync(D);
const atlas = new spine.TextureAtlas(fs.readFileSync(path.join(D, fl.find(f => f.endsWith(".atlas"))), "utf8"));
for (const p of atlas.pages) p.setTexture(new T({ width: 1, height: 1 }));
const data = new spine.SkeletonBinary(new spine.AtlasAttachmentLoader(atlas))
  .readSkeletonData(new Uint8Array(fs.readFileSync(path.join(D, fl.find(f => f.endsWith(".skel"))))));
console.log("skins:", data.skins.map(s => s.name).join(", "));
const total = { bones: data.bones.length, slots: data.slots.length };
console.log("total", total);
for (const a of data.animations) {
  const bones = new Set(), slots = new Set(), att = new Set();
  for (const tl of a.timelines) {
    if (tl.boneIndex !== undefined) bones.add(tl.boneIndex);
    if (tl.slotIndex !== undefined) slots.add(tl.slotIndex);
    if (tl instanceof spine.AttachmentTimeline) att.add(tl.slotIndex);
  }
  console.log(`${a.name.padEnd(24)} ${a.duration.toFixed(2).padStart(6)}s  os=${String(bones.size).padStart(4)}  slots=${String(slots.size).padStart(4)}  attach=${String(att.size).padStart(3)}`);
}
