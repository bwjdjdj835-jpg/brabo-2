# Executado DENTRO do Blender: blender -b --factory-startup -P blender_anime.py -- config.json
import bpy, json, math, sys, random
from mathutils import Vector
cfg = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene

def hexcor(h):
    h = h.lstrip("#"); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c] + [1]

def toon(nome, cor, sombra=.35):
    m = bpy.data.materials.new(nome); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); dif = nt.nodes.new("ShaderNodeBsdfDiffuse"); s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB"); emi = nt.nodes.new("ShaderNodeEmission")
    r = ramp.color_ramp; r.interpolation = "CONSTANT"
    r.elements[0].color = [c * sombra for c in cor[:3]] + [1]; r.elements[1].position = .35; r.elements[1].color = cor
    nt.links.new(dif.outputs[0], s2r.inputs[0]); nt.links.new(s2r.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], emi.inputs[0]); nt.links.new(emi.outputs[0], out.inputs[0])
    m.diffuse_color = cor; return m

PELE = toon("Pele", hexcor("#f2c9a0")); CAB = toon("Cabelo", hexcor(cfg["cabelo"])); ROUPA = toon("Roupa", hexcor(cfg["roupa"]))
BRANCO = toon("Branco", [1, 1, 1, 1], .8); OLHO = toon("Olho", hexcor("#2a6df4"), .5); PRETO = toon("Preto", [0.01, 0.01, 0.01, 1], 1)
CHAO = toon("Chao", hexcor("#3a3f58"), .6); FUNDO = toon("Fundo", hexcor("#ffb36b"), .7)

def obj(op, mat, **kw):
    op(**kw); o = bpy.context.object; o.data.materials.append(mat)
    bpy.ops.object.shade_smooth() if hasattr(o.data, "polygons") else None; return o

# personagem (corpo/cabeça) — formas simples estilizadas
corpo = obj(bpy.ops.mesh.primitive_cylinder_add, ROUPA, radius=.32, depth=1.0, location=(0, 0, 1.0)); corpo.scale = (1, .7, 1)
bpy.ops.object.modifier_add(type="SUBSURF")
for s in (-1, 1):
    b = obj(bpy.ops.mesh.primitive_cylinder_add, ROUPA, radius=.09, depth=.8, location=(s * .42, 0, 1.05)); b.rotation_euler = (0, s * .25, 0)
    m = obj(bpy.ops.mesh.primitive_uv_sphere_add, PELE, radius=.1, location=(s * .52, 0, .62))
    p = obj(bpy.ops.mesh.primitive_cylinder_add, PRETO, radius=.11, depth=.7, location=(s * .15, 0, .3))
cab = obj(bpy.ops.mesh.primitive_uv_sphere_add, PELE, radius=.36, location=(0, 0, 1.85), segments=48, ring_count=24); cab.scale = (1, .95, 1.08)
for s in (-1, 1):   # olhos anime grandes
    e = obj(bpy.ops.mesh.primitive_uv_sphere_add, BRANCO, radius=.085, location=(s * .13, -.31, 1.86)); e.scale = (1, .35, 1.35)
    i = obj(bpy.ops.mesh.primitive_uv_sphere_add, OLHO, radius=.06, location=(s * .13, -.345, 1.84)); i.scale = (1, .3, 1.3)
    br = obj(bpy.ops.mesh.primitive_uv_sphere_add, BRANCO, radius=.018, location=(s * .13 + .02, -.37, 1.9))
    sb = obj(bpy.ops.mesh.primitive_cube_add, CAB, size=.1, location=(s * .14, -.32, 2.0)); sb.scale = (1.3, .2, .2); sb.rotation_euler = (0, s * -.25, 0)
# cabelo espetado (cones) penteado para trás e para cima
for k in range(34):
    u = random.uniform(.15, .85) * math.pi; w = random.uniform(.15, 1)
    d = Vector((math.cos(u) * math.sqrt(1 - w * w), abs(math.sin(u)) * math.sqrt(1 - w * w) * .8 + .1, w)).normalized()
    base = Vector((0, 0, 1.9)) + d * .3
    dirv = (d + Vector((random.uniform(-.2, .2), .5, .5))).normalized()
    c = obj(bpy.ops.mesh.primitive_cone_add, CAB, radius1=.11, radius2=0, depth=random.uniform(.35, .55), vertices=8, location=base + dirv * .2)
    c.rotation_euler = dirv.to_track_quat("Z", "Y").to_euler()
for k in range(7):   # franja
    x = -.24 + k * .08
    c = obj(bpy.ops.mesh.primitive_cone_add, CAB, radius1=.07, radius2=0, depth=.28, vertices=8, location=(x, -.28, 2.02))
    c.rotation_euler = (math.radians(160), x * .8, 0)
calota = obj(bpy.ops.mesh.primitive_uv_sphere_add, CAB, radius=.375, location=(0, .03, 1.93)); calota.scale = (1.02, 1, .95)
# cenário
obj(bpy.ops.mesh.primitive_plane_add, CHAO, size=20, location=(0, 0, 0))
f = obj(bpy.ops.mesh.primitive_plane_add, FUNDO, size=20, location=(0, 4, 5)); f.rotation_euler = (math.pi / 2, 0, 0)
# texto
bpy.ops.object.text_add(location=(-2.6, 3.9, 3.2), rotation=(math.pi / 2, 0, 0)); t = bpy.context.object
t.data.body = cfg["titulo"][:28]; t.data.size = .45; t.data.extrude = .03; t.data.materials.append(PRETO)
# luz + câmera
bpy.ops.object.light_add(type="SUN", location=(3, -4, 6)); sol = bpy.context.object; sol.data.energy = 4; sol.rotation_euler = (math.radians(50), 0, math.radians(35))
bpy.ops.object.camera_add(location=(1.6, -5.2, 2.1)); cam = bpy.context.object; S.camera = cam; cam.data.lens = 50
cam.rotation_euler = (Vector((0, 0, 1.45)) - cam.location).to_track_quat("-Z", "Y").to_euler()
W = S.world = bpy.data.worlds.new("W"); W.use_nodes = True; W.node_tree.nodes["Background"].inputs[0].default_value = (1, .75, .5, 1)
# render toon: Cycles + Freestyle
S.render.engine = "CYCLES"; S.cycles.samples = int(cfg["amostras"]); S.cycles.use_denoising = False
S.render.resolution_x, S.render.resolution_y = int(cfg["largura"]), int(cfg["altura"])
S.view_settings.view_transform = "Standard"
S.render.use_freestyle = True; S.render.line_thickness = 1.6
vl = S.view_layers[0]; ls = vl.freestyle_settings.linesets.new("Contorno"); ls.linestyle = bpy.data.linestyles.new("Anime"); ls.linestyle.color = (0, 0, 0)
S.render.filepath = cfg["png"]; bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=cfg["blend"])
bpy.ops.export_scene.gltf(filepath=cfg["glb"], export_apply=True)
print("JARVIS_OK", cfg["png"])
