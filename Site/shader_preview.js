// Aperçu en direct des shaders du jeu : exécute le vrai code GLSL ES 3 extrait (HLSLcc / Unity URP) dans WebGL2,
// en fournissant ce que Unity fournit normalement : matrices, caméra, lumière principale, ambiance (harmoniques sphériques),
// temps, blocs d'uniformes (std140, rempli d'après les décalages réels), propriétés et textures d'un vrai matériau du jeu.
// window.ShaderPreview.create(canvas, { shader, header, glsl:[urls], preview:"shader_preview/<dossier>" }) -> api
(function () {
  "use strict";
  const M4 = {  // petites matrices 4x4 (colonne par colonne, comme WebGL)
    id: () => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    mul(a, b) { const o = new Array(16); for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) { let s = 0; for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k]; o[c * 4 + r] = s; } return o; },
    persp(fovy, asp, n, f) { const t = 1 / Math.tan(fovy / 2); return [t / asp, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) / (n - f), -1, 0, 0, 2 * f * n / (n - f), 0]; },
    rotY(a) { const c = Math.cos(a), s = Math.sin(a); return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]; },
    rotX(a) { const c = Math.cos(a), s = Math.sin(a); return [1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1]; },
    trans(x, y, z) { return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]; },
    scale(s) { return [s, 0, 0, 0, 0, s, 0, 0, 0, 0, s, 0, 0, 0, 0, 1]; },
    inv(m) {
      const a = m, o = new Array(16);
      const b00 = a[0] * a[5] - a[1] * a[4], b01 = a[0] * a[6] - a[2] * a[4], b02 = a[0] * a[7] - a[3] * a[4], b03 = a[1] * a[6] - a[2] * a[5],
        b04 = a[1] * a[7] - a[3] * a[5], b05 = a[2] * a[7] - a[3] * a[6], b06 = a[8] * a[13] - a[9] * a[12], b07 = a[8] * a[14] - a[10] * a[12],
        b08 = a[8] * a[15] - a[11] * a[12], b09 = a[9] * a[14] - a[10] * a[13], b10 = a[9] * a[15] - a[11] * a[13], b11 = a[10] * a[15] - a[11] * a[14];
      let d = b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06; if (!d) return M4.id(); d = 1 / d;
      o[0] = (a[5] * b11 - a[6] * b10 + a[7] * b09) * d; o[1] = (a[2] * b10 - a[1] * b11 - a[3] * b09) * d; o[2] = (a[13] * b05 - a[14] * b04 + a[15] * b03) * d;
      o[3] = (a[10] * b04 - a[9] * b05 - a[11] * b03) * d; o[4] = (a[6] * b08 - a[4] * b11 - a[7] * b07) * d; o[5] = (a[0] * b11 - a[2] * b08 + a[3] * b07) * d;
      o[6] = (a[14] * b02 - a[12] * b05 - a[15] * b01) * d; o[7] = (a[8] * b05 - a[10] * b02 + a[11] * b01) * d; o[8] = (a[4] * b10 - a[5] * b08 + a[7] * b06) * d;
      o[9] = (a[1] * b08 - a[0] * b10 - a[3] * b06) * d; o[10] = (a[12] * b04 - a[13] * b02 + a[15] * b00) * d; o[11] = (a[9] * b02 - a[8] * b04 - a[11] * b00) * d;
      o[12] = (a[5] * b07 - a[4] * b09 - a[6] * b06) * d; o[13] = (a[0] * b09 - a[1] * b07 + a[2] * b06) * d; o[14] = (a[13] * b01 - a[12] * b03 - a[14] * b00) * d;
      o[15] = (a[8] * b03 - a[9] * b01 + a[10] * b00) * d; return o;
    },
  };
  // --- géométries de secours
  function sphere(n = 64) {
    const P = [], N = [], U = [], T = [], I = [];
    for (let y = 0; y <= n; y++) for (let x = 0; x <= n * 2; x++) {
      const u = x / (n * 2), v = y / n, th = u * Math.PI * 2, ph = v * Math.PI;
      const px = -Math.cos(th) * Math.sin(ph), py = Math.cos(ph), pz = Math.sin(th) * Math.sin(ph);
      P.push(px, py, pz); N.push(px, py, pz); U.push(u, 1 - v); T.push(Math.sin(th), 0, Math.cos(th), 1);
    }
    for (let y = 0; y < n; y++) for (let x = 0; x < n * 2; x++) { const a = y * (n * 2 + 1) + x, b = a + n * 2 + 1; I.push(a, b, a + 1, b, b + 1, a + 1); }
    return { position: P, normal: N, uv: U, tangent: T, index: I };
  }
  function quad() { return { position: [-1, -1, 0, 1, -1, 0, 1, 1, 0, -1, 1, 0], normal: [0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1], uv: [0, 0, 1, 0, 1, 1, 0, 1],
    tangent: [1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1], color: new Array(16).fill(1), index: [0, 1, 2, 0, 2, 3] }; }
  function cube() { const p = [], idx = []; const f = [[0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]];
    [[1, 1, -1, -1], [-1, 1, -1, -1]]; // (non utilisé)
    const V = [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]];
    V.forEach(v => p.push(...v)); [[0, 2, 1, 0, 3, 2], [4, 5, 6, 4, 6, 7], [0, 1, 5, 0, 5, 4], [3, 7, 6, 3, 6, 2], [0, 4, 7, 0, 7, 3], [1, 2, 6, 1, 6, 5]].forEach(q => idx.push(...q));
    return { position: p, normal: p.slice(), uv: new Array(16).fill(0), index: idx }; }

  // --- propriétés par défaut lues dans le .shader
  function parseProps(txt) {
    const out = {}, m = txt.replace(/\r\n/g, "\n").match(/Properties \{\n([\s\S]*?)\n  \}/); if (!m) return out;
    for (const l of m[1].split("\n")) {
      const x = l.trim().match(/^(?:\[[^\]]*\]\s*)*(\w+) \(".*", (.+?)\) = (.*)$/); if (!x) continue;
      const [, name, type, def] = x;
      if (/^\(/.test(def)) out[name] = { v: def.slice(1, -1).split(",").map(Number) };
      else if (/^"/.test(def)) out[name] = { tex: def.match(/^"(.*)"/)[1] || "gray", dim: type };
      else out[name] = { v: [Number(def) || 0] };
    }
    return out;
  }

  function create(canvas, sh) {
    const gl = canvas.getContext("webgl2", { antialias: true, premultipliedAlpha: false, alpha: true, preserveDrawingBuffer: true });
    if (!gl) throw new Error("WebGL2 indisponible");
    const api = { snapshot: () => { draw(true); return canvas.toDataURL("image/png"); }, variants: [], materials: [], geometry: "auto", variant: null, material: 0, onInfo: null, dispose, setVariant, setMaterial, setGeometry, error: null };
    let disposed = false, raf = 0, defaults = {}, mat = null, geo = null, prog = null, outline = null, textures = new Map(), drag = null;
    let yaw = 0.6, pitch = 0.15, dist = 3, auto = true, center = [0, 0, 0], radius = 1;
    const t0 = performance.now();
    const kind = /^Skybox\//.test(sh.name) ? "sky" : /^(Sprites|UI|Spine|TextMeshPro|Nova\/Sprite|Universal Render Pipeline\/2D|Nova\/FX\/Transition)/.test(sh.name) ? "plan" : "objet";
    const blendMode = /Additive/.test(sh.name) ? "add" : /(Transparent|FX|Sprite|UI|Spine|TextMeshPro|Fire|Mask)/.test(sh.name) ? "alpha" : "opaque";

    // --- textures
    function texFromImage(url) {
      if (textures.has(url)) return textures.get(url);
      const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([128, 128, 128, 255]));
      const im = new Image(); im.onload = () => { if (disposed) return; gl.bindTexture(gl.TEXTURE_2D, t); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, im); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false); gl.generateMipmap(gl.TEXTURE_2D);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR); t.w = im.width; t.h = im.height; };
      im.src = url; t.w = 1; t.h = 1; textures.set(url, t); return t;
    }
    function solid(rgba, key) {
      if (textures.has(key)) return textures.get(key);
      const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(rgba)); t.w = t.h = 1; textures.set(key, t); return t;
    }
    function cubeTex(urls, key) {
      if (textures.has(key)) return textures.get(key);
      const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_CUBE_MAP, t);
      for (let i = 0; i < 6; i++) gl.texImage2D(gl.TEXTURE_CUBE_MAP_POSITIVE_X + i, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([140, 140, 150, 255]));
      if (urls) urls.forEach((u, i) => { const im = new Image(); im.onload = () => { if (disposed) return; gl.bindTexture(gl.TEXTURE_CUBE_MAP, t);
        gl.texImage2D(gl.TEXTURE_CUBE_MAP_POSITIVE_X + i, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, im); gl.texParameteri(gl.TEXTURE_CUBE_MAP, gl.TEXTURE_MIN_FILTER, gl.LINEAR); }; im.src = u; });
      gl.texParameteri(gl.TEXTURE_CUBE_MAP, gl.TEXTURE_MIN_FILTER, gl.LINEAR); t.cube = true; textures.set(key, t); return t;
    }
    function shadowTex() {
      if (textures.has("shadow")) return textures.get("shadow");
      const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.DEPTH_COMPONENT32F, 1, 1, 0, gl.DEPTH_COMPONENT, gl.FLOAT, new Float32Array([1]));
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_COMPARE_MODE, gl.COMPARE_REF_TO_TEXTURE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST); t.shadow = true; textures.set("shadow", t); return t;
    }
    const DEF = { white: [255, 255, 255, 255], black: [0, 0, 0, 0], gray: [128, 128, 128, 255], grey: [128, 128, 128, 255], bump: [128, 128, 255, 255], red: [255, 0, 0, 255] };
    function textureFor(name, type) {
      if (type === gl.SAMPLER_2D_SHADOW) return shadowTex();
      const base = name.replace(/^hlslcc_zcmp/, "");
      if (type === gl.SAMPLER_CUBE) { const tx = mat && mat.textures[base]; return cubeTex(tx && tx.cube ? tx.cube.map(u => sh.preview + "/" + u) : null, "cube:" + base + ":" + api.material); }
      const tx = mat && mat.textures[base];
      if (tx && tx.file) return texFromImage(sh.preview + "/" + tx.file);
      if (/shadowmap/i.test(base)) return solid([255, 255, 255, 255], "white");
      if (/^_MainTex$|^_BaseMap$|^_Albedo$/.test(base) && kind === "plan") return texFromImage(SAMPLE);
      const d = defaults[base]; const k = d && d.tex ? d.tex.toLowerCase() : (/normal|bump/i.test(base) ? "bump" : "white");
      return solid(DEF[k] || DEF.white, k);
    }
    const SAMPLE = "img/PNG/UI/Atlas_Roleskin/6020000.webp";  // illustration de secours pour les shaders 2D sans texture

    // --- valeurs des uniformes
    let frame = {};
    function matVal(name) {
      if (mat) {
        if (name in mat.colors) return mat.colors[name];
        if (name in mat.floats) return [mat.floats[name]];
        const st = name.match(/^(.*)_ST$/); if (st && mat.textures[st[1]]) return mat.textures[st[1]].st;
      }
      const ts = name.match(/^(.*)_TexelSize$/);
      if (ts) { const t = mat && mat.textures[ts[1]] && mat.textures[ts[1]].file ? textures.get(sh.preview + "/" + mat.textures[ts[1]].file) : null; const w = t ? t.w : 1, h = t ? t.h : 1; return [1 / w, 1 / h, w, h]; }
      if (/_ST$/.test(name)) return [1, 1, 0, 0];
      if (/_HDR$/.test(name)) return [1, 1, 0, 0];
      if (defaults[name] && defaults[name].v) return defaults[name].v;
      return null;
    }
    function value(name) {
      const mx = name.match(/^hlslcc_mtx4x4(\w+)/); if (mx) return frame.mat[mx[1]] || M4.id();
      if (name in frame.vec) return frame.vec[name];
      const v = matVal(name); if (v) return v;
      if (/^unity_SH/.test(name)) return [0, 0, 0, 0];
      if (/Color$/.test(name)) return [1, 1, 1, 1];
      return [0, 0, 0, 0];
    }
    function setupFrame(W, H) {
      const t = (performance.now() - t0) / 1000;
      if (auto && !drag) yaw += 0.006;
      const proj = M4.persp(kind === "sky" ? 1.2 : 0.62, W / H, radius / 50, radius * 60);
      const eye = kind === "sky" ? [0, 0, 0] : [center[0] + Math.sin(yaw) * Math.cos(pitch) * dist, center[1] + Math.sin(pitch) * dist, center[2] + Math.cos(yaw) * Math.cos(pitch) * dist];
      let view;
      if (kind === "sky") view = M4.mul(M4.rotX(-pitch), M4.rotY(-yaw));
      else { // lookAt
        const f = [center[0] - eye[0], center[1] - eye[1], center[2] - eye[2]]; const fl = Math.hypot(...f); f[0] /= fl; f[1] /= fl; f[2] /= fl;
        let s = [f[1] * 0 - f[2] * 1, f[2] * 0 - f[0] * 0, f[0] * 1 - f[1] * 0]; const sl = Math.hypot(...s) || 1; s = s.map(x => x / sl);
        const u = [s[1] * f[2] - s[2] * f[1], s[2] * f[0] - s[0] * f[2], s[0] * f[1] - s[1] * f[0]];
        view = [s[0], u[0], -f[0], 0, s[1], u[1], -f[1], 0, s[2], u[2], -f[2], 0, -(s[0] * eye[0] + s[1] * eye[1] + s[2] * eye[2]), -(u[0] * eye[0] + u[1] * eye[1] + u[2] * eye[2]), f[0] * eye[0] + f[1] * eye[1] + f[2] * eye[2], 1];
      }
      const model = kind === "sky" ? M4.scale(radius * 20) : M4.id();
      const vp = M4.mul(proj, view), n = radius / 50, fr = radius * 60;
      const L = [0.45, 0.75, 0.5]; const ll = Math.hypot(...L);
      frame = {
        mat: { unity_ObjectToWorld: model, unity_WorldToObject: M4.inv(model), unity_MatrixVP: vp, unity_MatrixV: view, unity_MatrixInvV: M4.inv(view),
               unity_MatrixP: proj, glstate_matrix_projection: proj, unity_CameraProjection: proj, unity_CameraInvProjection: M4.inv(proj),
               unity_MatrixInvVP: M4.inv(vp), unity_MatrixInvP: M4.inv(proj), unity_MatrixMV: M4.mul(view, model), unity_MatrixPreviousM: model,
               unity_MatrixPreviousMI: M4.inv(model), unity_WorldToCamera: view, unity_CameraToWorld: M4.inv(view), _MainLightWorldToShadow: M4.id() },
        vec: { _WorldSpaceCameraPos: [...eye, 1], _ProjectionParams: [1, n, fr, 1 / fr], _ScreenParams: [W, H, 1 + 1 / W, 1 + 1 / H],
               _ZBufferParams: [1 - fr / n, fr / n, (1 - fr / n) / fr, (fr / n) / fr], _Time: [t / 20, t, t * 2, t * 3], _SinTime: [Math.sin(t / 8), Math.sin(t / 4), Math.sin(t / 2), Math.sin(t)],
               _CosTime: [Math.cos(t / 8), Math.cos(t / 4), Math.cos(t / 2), Math.cos(t)], unity_DeltaTime: [0.016, 60, 0.016, 60], _TimeParameters: [t, Math.sin(t), Math.cos(t), 0],
               _MainLightPosition: [L[0] / ll, L[1] / ll, L[2] / ll, 0], _MainLightColor: [1.15, 1.1, 1.05, 1], _AdditionalLightsCount: [0, 0, 0, 0],
               unity_LightData: [0, 0, 1, 0], unity_LightIndices: [0, 0, 0, 0], unity_WorldTransformParams: [0, 0, 0, 1], unity_LODFade: [1, 1, 0, 0],
               unity_RenderingLayer: [1, 0, 0, 0], unity_ProbesOcclusion: [1, 1, 1, 1], unity_SpecCube0_HDR: [1, 1, 0, 0], unity_SpecCube1_HDR: [1, 1, 0, 0],
               unity_SHAr: [0, 0, 0, 0.42], unity_SHAg: [0, 0, 0, 0.40], unity_SHAb: [0, 0, 0, 0.46], unity_SHBr: [0, 0, 0, 0], unity_SHBg: [0, 0, 0, 0],
               unity_SHBb: [0, 0, 0, 0], unity_SHC: [0, 0, 0, 0], _GlossyEnvironmentColor: [0.45, 0.45, 0.5, 1], _MainLightShadowParams: [0, 0, 0, 0],
               unity_AmbientSky: [0.5, 0.5, 0.55, 1], unity_AmbientEquator: [0.45, 0.45, 0.5, 1], unity_AmbientGround: [0.35, 0.33, 0.38, 1],
               unity_FogParams: [0, 0, 0, 0], unity_FogColor: [0, 0, 0, 0], _ClipRect: [-1e5, -1e5, 1e5, 1e5], _TextureSampleAdd: [0, 0, 0, 0],
               _ScaledScreenParams: [W, H, 1 + 1 / W, 1 + 1 / H], _WorldSpaceLightPos0: [L[0] / ll, L[1] / ll, L[2] / ll, 0], _LightColor0: [1.15, 1.1, 1.05, 1] },
      };
    }

    // --- programmes
    function compile(type, src) {
      const s = gl.createShader(type);
      gl.shaderSource(s, src.replace("#define UNITY_SUPPORTS_UNIFORM_LOCATION 1", "#define UNITY_SUPPORTS_UNIFORM_LOCATION 0"));
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s).split("\n")[0]);
      return s;
    }
    async function build(v) {
      const [vs, fs] = await Promise.all([fetch(v.vert).then(r => r.text()), fetch(v.frag).then(r => r.text())]);
      const p = gl.createProgram(); gl.attachShader(p, compile(gl.VERTEX_SHADER, vs)); gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p).split("\n")[0]);
      // uniformes : blocs (std140, décalages réels) et uniformes libres
      const P = { p, blocks: [], free: [], samplers: [], vsLen: vs.length, fsLen: fs.length };
      const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS), idx = [...Array(n).keys()];
      const blockIdx = n ? gl.getActiveUniforms(p, idx, gl.UNIFORM_BLOCK_INDEX) : [], offs = n ? gl.getActiveUniforms(p, idx, gl.UNIFORM_OFFSET) : [],
        strides = n ? gl.getActiveUniforms(p, idx, gl.UNIFORM_ARRAY_STRIDE) : [];
      const nb = gl.getProgramParameter(p, gl.ACTIVE_UNIFORM_BLOCKS);
      for (let b = 0; b < nb; b++) {
        gl.uniformBlockBinding(p, b, b);
        P.blocks.push({ b, size: gl.getActiveUniformBlockParameter(p, b, gl.UNIFORM_BLOCK_DATA_SIZE), members: [], ubo: gl.createBuffer() });
      }
      let unit = 0;
      for (const i of idx) {
        const info = gl.getActiveUniform(p, i), name = info.name.replace(/\[0\]$/, "");
        const u = { name, type: info.type, size: info.size, off: offs[i], stride: strides[i] };
        if (blockIdx[i] >= 0) P.blocks[blockIdx[i]].members.push(u);
        else if ([gl.SAMPLER_2D, gl.SAMPLER_CUBE, gl.SAMPLER_2D_SHADOW, gl.SAMPLER_3D, gl.SAMPLER_2D_ARRAY].includes(info.type)) {
          u.loc = gl.getUniformLocation(p, info.name); u.unit = unit++; P.samplers.push(u);
        } else { u.loc = gl.getUniformLocation(p, info.name); P.free.push(u); }
      }
      P.attribs = [];
      for (let i = 0, na = gl.getProgramParameter(p, gl.ACTIVE_ATTRIBUTES); i < na; i++) { const a = gl.getActiveAttrib(p, i); P.attribs.push({ name: a.name, loc: gl.getAttribLocation(p, a.name) }); }
      return P;
    }
    const COMP = t => ({ [gl.FLOAT]: 1, [gl.FLOAT_VEC2]: 2, [gl.FLOAT_VEC3]: 3, [gl.FLOAT_VEC4]: 4, [gl.INT]: 1, [gl.INT_VEC2]: 2, [gl.INT_VEC3]: 3, [gl.INT_VEC4]: 4,
      [gl.UNSIGNED_INT]: 1, [gl.UNSIGNED_INT_VEC4]: 4, [gl.BOOL]: 1, [gl.FLOAT_MAT4]: 16, [gl.FLOAT_MAT3]: 9 }[t] || 4);
    const ISINT = t => [gl.INT, gl.INT_VEC2, gl.INT_VEC3, gl.INT_VEC4, gl.BOOL, gl.UNSIGNED_INT, gl.UNSIGNED_INT_VEC4].includes(t);
    function elems(u) {  // valeurs pour un uniforme (tableaux : hlslcc_mtx4x4X[4] -> 4 colonnes de la matrice X)
      const v = value(u.name), c = COMP(u.type);
      if (u.size > 1) { const out = []; for (let k = 0; k < u.size; k++) out.push(v.length >= (k + 1) * c ? v.slice(k * c, (k + 1) * c) : (u.size === 1 ? v : new Array(c).fill(0))); return out; }
      const a = v.slice(0, c); while (a.length < c) a.push(0); return [a];
    }
    function upload(P) {
      gl.useProgram(P.p);
      for (const B of P.blocks) {
        const buf = new ArrayBuffer(B.size), f = new Float32Array(buf), iv = new Int32Array(buf);
        for (const u of B.members) elems(u).forEach((a, k) => { const base = (u.off + k * (u.stride || 16)) / 4; a.forEach((x, j) => { if (ISINT(u.type)) iv[base + j] = x | 0; else f[base + j] = x; }); });
        gl.bindBuffer(gl.UNIFORM_BUFFER, B.ubo); gl.bufferData(gl.UNIFORM_BUFFER, buf, gl.DYNAMIC_DRAW); gl.bindBufferBase(gl.UNIFORM_BUFFER, B.b, B.ubo);
      }
      for (const u of P.free) {
        const flat = elems(u).flat(); const fn = ISINT(u.type) ? "uniform" + COMP(u.type) + "iv" : u.type === gl.FLOAT_MAT4 ? null : "uniform" + COMP(u.type) + "fv";
        if (u.type === gl.FLOAT_MAT4) gl.uniformMatrix4fv(u.loc, false, value(u.name).slice(0, 16)); else gl[fn](u.loc, ISINT(u.type) ? new Int32Array(flat) : new Float32Array(flat));
      }
      for (const s of P.samplers) {
        const t = textureFor(s.name, s.type); gl.activeTexture(gl.TEXTURE0 + s.unit);
        gl.bindTexture(s.type === gl.SAMPLER_CUBE ? gl.TEXTURE_CUBE_MAP : gl.TEXTURE_2D, t); gl.uniform1i(s.loc, s.unit);
      }
    }
    // --- géométrie
    const ATTR = { in_POSITION0: ["position", 3], in_NORMAL0: ["normal", 3], in_TANGENT0: ["tangent", 4], in_TEXCOORD0: ["uv", 2], in_TEXCOORD1: ["uv", 2], in_COLOR0: ["color", 4] };
    function loadGeo(g) {
      const G = { n: g.index.length, buf: {}, ib: gl.createBuffer() };
      for (const k of ["position", "normal", "tangent", "uv", "color"]) if (g[k]) { G.buf[k] = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, G.buf[k]); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(g[k]), gl.STATIC_DRAW); }
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, G.ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint32Array(g.index), gl.STATIC_DRAW);
      // cadrage
      const p = g.position; let mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
      for (let i = 0; i < p.length; i += 3) for (let k = 0; k < 3; k++) { mn[k] = Math.min(mn[k], p[i + k]); mx[k] = Math.max(mx[k], p[i + k]); }
      center = mn.map((v, k) => (v + mx[k]) / 2); radius = Math.max(Math.hypot(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]) / 2, 1e-3);
      dist = kind === "plan" ? radius * 3.1 : radius * 2.6; pitch = kind === "plan" ? 0 : 0.15; if (kind === "plan") { yaw = 0; auto = false; }
      return G;
    }
    function bindGeo(P, G) {
      const vao = P.vao || (P.vao = gl.createVertexArray()); gl.bindVertexArray(vao);
      for (const a of P.attribs) {
        const m = ATTR[a.name] || (a.name.startsWith("in_TEXCOORD") ? ["uv", 2] : null);
        if (m && G.buf[m[0]]) { gl.bindBuffer(gl.ARRAY_BUFFER, G.buf[m[0]]); gl.enableVertexAttribArray(a.loc); gl.vertexAttribPointer(a.loc, m[1], gl.FLOAT, false, 0, 0); }
        else { gl.disableVertexAttribArray(a.loc); gl.vertexAttrib4f(a.loc, ...(a.name === "in_COLOR0" ? [1, 1, 1, 1] : a.name === "in_TANGENT0" ? [1, 0, 0, 1] : [0, 0, 0, 1])); }
      }
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, G.ib);
    }
    // --- rendu
    function draw(once) {
      if (disposed) return;
      const W = canvas.clientWidth * devicePixelRatio | 0, H = canvas.clientHeight * devicePixelRatio | 0;
      if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
      gl.viewport(0, 0, W, H); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      if (prog && geo) {
        setupFrame(W, H);
        gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL);
        if (outline && api.showOutline !== false) {  // passe de contour (faces avant éliminées), comme la passe OUTLINE du jeu
          gl.disable(gl.BLEND); gl.enable(gl.CULL_FACE); gl.cullFace(gl.FRONT); gl.depthMask(true);
          upload(outline); bindGeo(outline, geo); gl.drawElements(gl.TRIANGLES, geo.n, gl.UNSIGNED_INT, 0);
        }
        if (kind === "sky") { gl.disable(gl.CULL_FACE); gl.depthMask(false); }
        else if (kind === "plan") gl.disable(gl.CULL_FACE);
        else { gl.enable(gl.CULL_FACE); gl.cullFace(gl.BACK); }
        if (blendMode === "opaque") { gl.disable(gl.BLEND); gl.depthMask(kind !== "sky"); }
        else { gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, blendMode === "add" ? gl.ONE : gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false); }
        upload(prog); bindGeo(prog, geo); gl.drawElements(gl.TRIANGLES, geo.n, gl.UNSIGNED_INT, 0);
        gl.depthMask(true);
      }
      if (!once) raf = requestAnimationFrame(() => draw());
    }
    // --- choix variante / matériau / géométrie
    async function setVariant(i) {
      api.variant = i; const v = api.variants[i];
      try { prog = v.prog || (v.prog = await build(v)); api.error = null; }
      catch (e) { prog = null; api.error = "Variante " + (+v.id + 1) + " : " + e.message; }
      api.onInfo && api.onInfo(api);
    }
    function score() {  // pixels visibles x contraste (luminance), lus sur une image réduite
      const W = canvas.width, H = canvas.height, px = new Uint8Array(W * H * 4);
      gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, px);
      let n = 0, s1 = 0, s2 = 0;
      for (let i = 0; i < px.length; i += 16) { if (px[i + 3] < 8) continue; const l = (px[i] * 0.3 + px[i + 1] * 0.59 + px[i + 2] * 0.11) * px[i + 3] / 255; n++; s1 += l; s2 += l * l; }
      if (!n) return 0; const m = s1 / n, sd = Math.sqrt(Math.max(0, s2 / n - m * m));
      return n * (sd + 4) * (m > 2 ? 1 : 0.1);
    }
    async function autoVariant() {
      let best = -1, bi = 0;
      for (let i = 0; i < Math.min(api.variants.length, 14); i++) {
        await setVariant(i); if (!prog) continue;
        draw(true); const sc = score(); if (sc > best) { best = sc; bi = i; }
      }
      await setVariant(bi);
    }
    async function setGeometry(g) {
      api.geometry = g;
      let data = null;
      if (g === "piece" && mat && mat.mesh) data = await fetch(sh.preview + "/" + mat.mesh).then(r => r.json());
      if (!data) data = kind === "sky" ? cube() : kind === "plan" ? quad() : (g === "plan" ? quad() : sphere());
      geo = loadGeo(data);
      api.onInfo && api.onInfo(api);
    }
    async function setMaterial(i) {
      api.material = i; mat = api.materials[i] || null;
      await setGeometry(mat && mat.mesh && kind === "objet" ? "piece" : "boule");
      if (api.variants.length && api.variants.some(v => v.prog)) await autoVariant();
    }
    function dispose() { disposed = true; cancelAnimationFrame(raf); textures.forEach(t => gl.deleteTexture(t)); }
    // souris : rotation
    canvas.addEventListener("pointerdown", e => { drag = [e.clientX, e.clientY]; auto = false; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener("pointermove", e => { if (!drag) return; yaw -= (e.clientX - drag[0]) * 0.01; pitch = Math.max(-1.3, Math.min(1.3, pitch + (e.clientY - drag[1]) * 0.01)); drag = [e.clientX, e.clientY]; });
    canvas.addEventListener("pointerup", () => { drag = null; });
    canvas.addEventListener("wheel", e => { e.preventDefault(); dist *= e.deltaY > 0 ? 1.1 : 0.9; }, { passive: false });

    api.ready = (async () => {
      const [hdr, mj] = await Promise.all([fetch(sh.header).then(r => r.text()).catch(() => ""), sh.preview ? fetch(sh.preview + "/material.json").then(r => r.ok ? r.json() : null).catch(() => null) : null]);
      defaults = parseProps(hdr);
      api.materials = mj ? mj.materials : [];
      // variantes : paires sommets/fragments ; contour = sommets qui poussent le long de la normale (_OutlineWidth)
      const V = new Map();
      sh.glsl.forEach(f => { const m = f.match(/(\d{3})_(\w+)\.(vert|frag)\.glsl$/); if (!m) return; if (!V.has(m[1])) V.set(m[1], { id: m[1] }); V.get(m[1])[m[3]] = f; });
      const all = [...V.values()].filter(v => v.vert && v.frag);
      const texts = await Promise.all(all.map(v => Promise.all([fetch(v.vert).then(r => r.text()), fetch(v.frag).then(r => r.text())])));
      all.forEach((v, k) => { const [vs, fs] = texts[k]; v.outline = /_OutlineWidth/.test(vs) && !/_Albedo|_MainTex|_BaseMap/.test(fs); v.depth = fs.length < 600 && /vec4\(0\.0, 0\.0, 0\.0, 0\.0\)/.test(fs);
        v.score = (fs.match(/texture\(/g) || []).length * 1000 + fs.length; });
      api.variants = all.filter(v => !v.outline && !v.depth).sort((a, b) => b.score - a.score);
      // matériaux : d'abord ceux dont les textures sont réellement lues par ce shader
      const samplers = new Set(texts.flatMap(([vs, fs]) => [...(vs + fs).matchAll(/uniform\s+\w+\s+sampler\w+\s+(\w+)/g)].map(m => m[1])));
      const fit = m => Object.entries(m.textures).filter(([k, t]) => (t.file || t.cube) && samplers.has(k)).length * 10 + (m.mesh ? 35 : 0);
      api.materials.sort((a, b) => fit(b) - fit(a));
      if (!api.variants.length) api.variants = all;
      const ol = all.find(v => v.outline);
      if (ol && kind === "objet") { try { outline = await build(ol); } catch (e) { outline = null; } }
      await setMaterial(0);
      if (!api.variants.length) api.error = "aucun programme GPU de ce shader n'est présent sur le téléphone";
      else await autoVariant();
      draw();
      return api;
    })();
    return api;
  }
  window.ShaderPreview = { create };
})();
