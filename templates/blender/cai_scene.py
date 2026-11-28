"""PACAR Tuning Truth: cold air intake. Transverse inline-4 in an engine bay (simplified), exhaust manifold at the front,
radiator + electric fan in front of it, open cone filter on the intake pipe right next to the hot manifold.
Phase A: hot (orange) engine-bay air is sucked into the cone filter. Slow-mo. Phase B (t>=8.3): heat shield + duct from
the front appear; cold (blue) outside air feeds the filter, hot air rises away. Only fan + particles + camera move.
usage: python3 cai_scene.py <samples> <percent> <frame_start> <frame_end>"""
import bpy, math, sys, time, json, random
from mathutils import Vector

SAMPLES, PCT, F0, F1 = [int(v) for v in sys.argv[-4:]]
FPS, N = 24, 300
DUR = N / FPS
OUTD = "/home/claude/blender/cai"
T_SWITCH, T_BUILD = 8.3, 0.7

def speed(t):  # sim speed (slow motion 4.5-6.5 s)
    segs = [(0, 1), (4.3, 1), (4.6, 0.22), (6.4, 0.22), (6.7, 1), (99, 1)]
    for (a, wa), (b, wb) in zip(segs, segs[1:]):
        if a <= t < b: return wa + (wb - wa) * (t - a) / (b - a)
    return 1
_S = [0.0]; _DT = 1 / 480
for i in range(int((DUR + 2) / _DT)): _S.append(_S[-1] + speed((i + 0.5) * _DT) * _DT)
def simt(t):
    x = t / _DT; i = min(int(x), len(_S) - 2); return _S[i] + (_S[i + 1] - _S[i]) * (x - i)
S_SWITCH = simt(T_SWITCH)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True; sc.cycles.max_bounces = 4
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920; sc.render.resolution_percentage = PCT
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, N
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Punchy"

def mat(name, color, metal=0.0, rough=0.4, coat=0.0, emis=None, es=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough; b.inputs["Coat Weight"].default_value = coat
    if emis:
        b.inputs["Emission Color"].default_value = (*emis, 1); b.inputs["Emission Strength"].default_value = es
    return m, b
alu, _ = mat("alu", (0.80, 0.81, 0.83), 1.0, 0.28)
block_m, _ = mat("block", (0.30, 0.31, 0.33), 1.0, 0.42)
cover, _ = mat("cover", (0.55, 0.02, 0.015), 0.0, 0.2, coat=1.0)
mani_m, mani_b = mat("mani", (0.45, 0.33, 0.25), 1.0, 0.35, emis=(1.0, 0.18, 0.02), es=0.0)
plastic, _ = mat("plastic", (0.025, 0.025, 0.03), 0.0, 0.45, coat=0.3)
pipe_m, _ = mat("pipe", (0.04, 0.04, 0.045), 0.0, 0.3, coat=0.6)
rad_m, _ = mat("rad", (0.12, 0.12, 0.13), 1.0, 0.5)
floor, _ = mat("floor", (0.006, 0.006, 0.008), 0.0, 0.4)
steel, _ = mat("steel", (0.8, 0.8, 0.82), 1.0, 0.18)
shield_m, _ = mat("shield", (0.72, 0.73, 0.75), 1.0, 0.32)

# pleated cone filter material: radial pleats via wave texture on object coords
filt = bpy.data.materials.new("filter"); filt.use_nodes = True
nt = filt.node_tree; fb = nt.nodes["Principled BSDF"]
tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(tc.outputs["Object"], sep.inputs[0])
at = nt.nodes.new("ShaderNodeMath"); at.operation = "ARCTAN2"
nt.links.new(sep.outputs[0], at.inputs[0]); nt.links.new(sep.outputs[2], at.inputs[1])
mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 22
nt.links.new(at.outputs[0], mul.inputs[0])
sn = nt.nodes.new("ShaderNodeMath"); sn.operation = "SINE"; nt.links.new(mul.outputs[0], sn.inputs[0])
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].color = (0.25, 0.005, 0.005, 1); ramp.color_ramp.elements[1].color = (0.75, 0.03, 0.02, 1)
mp = nt.nodes.new("ShaderNodeMapRange"); nt.links.new(sn.outputs[0], mp.inputs[0])
mp.inputs[1].default_value = -1; mp.inputs[2].default_value = 1
nt.links.new(mp.outputs[0], ramp.inputs[0]); nt.links.new(ramp.outputs[0], fb.inputs["Base Color"])
bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.8
nt.links.new(mp.outputs[0], bump.inputs["Height"]); nt.links.new(bump.outputs[0], fb.inputs["Normal"])
fb.inputs["Roughness"].default_value = 0.8

def finish(o, m, smooth=True):
    o.data.materials.clear(); o.data.materials.append(m)
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    if smooth:
        try: bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
        except Exception: bpy.ops.object.shade_smooth()
    o.select_set(False); return o
def boolean(target, cutter, op="DIFFERENCE"):
    m = target.modifiers.new("b", "BOOLEAN"); m.object = cutter; m.operation = op; m.solver = "EXACT"
    bpy.context.view_layer.objects.active = target; bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter)
def cyl(radius, depth, loc, rot=(0, 0, 0), verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot)
    return bpy.context.object
def cyl_between(r, a, b, v=40):
    a, b = Vector(a), Vector(b); d = b - a
    o = cyl(r, d.length, (a + b) / 2, (0, 0, 0), v)
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler(); return o
def box(loc, scale, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot); o = bpy.context.object; o.scale = scale
    bpy.ops.object.transform_apply(scale=True, rotation=True); return o
def bevel(o, w=0.03):
    m = o.modifiers.new("bv", "BEVEL"); m.width = w; m.segments = 3; return o
def tube_path(pts, r, m):
    for a, b in zip(pts, pts[1:]): finish(cyl_between(r, a, b), m)
    for p in pts[1:-1]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=p, segments=32, ring_count=16); finish(bpy.context.object, m)

# ---------------- engine (transverse I4; front of car = -Y) ----------------
finish(bevel(box((0, 0, 0.5), (1.8, 1.0, 1.0))), block_m)
finish(bevel(box((0, 0, 1.12), (1.7, 0.9, 0.24))), alu)                       # cylinder head
finish(bevel(box((0, 0.02, 1.36), (1.55, 0.72, 0.24)), 0.06), cover)          # cam cover
for x in (-0.6, -0.2, 0.2, 0.6):                                              # coil packs
    finish(cyl(0.07, 0.12, (x, 0.02, 1.53)), plastic)
finish(cyl(0.35, 0.14, (1.0, 0.0, 0.5), (0, math.pi / 2, 0)), steel)          # crank pulley side (fixed cover)
# exhaust manifold: 4 runners from the head front face down into a collector
for x in (-0.6, -0.2, 0.2, 0.6):
    tube_path([(x, -0.45, 1.1), (x, -0.68, 1.02), (x * 0.45 + 0.1, -0.72, 0.62), (0.1, -0.7, 0.4)], 0.075, mani_m)
finish(cyl_between(0.11, (0.1, -0.7, 0.42), (0.1, -0.7, -0.3)), mani_m)
# intake manifold on the rear face + throttle body at the left end
for x in (-0.6, -0.2, 0.2, 0.6):
    tube_path([(x, 0.45, 1.1), (x, 0.7, 1.12), (x, 0.78, 0.85)], 0.07, alu)
finish(cyl_between(0.16, (-0.85, 0.82, 0.85), (0.85, 0.82, 0.85)), alu)       # plenum
finish(cyl_between(0.13, (-0.85, 0.82, 0.85), (-1.05, 0.82, 0.85)), steel)    # throttle body
# radiator + electric fan in front
finish(bevel(box((0, -1.72, 0.55), (2.3, 0.12, 1.3)), 0.02), rad_m)
shroud = cyl(0.55, 0.12, (0.15, -1.6, 0.55), (math.pi / 2, 0, 0), 64)
boolean(shroud, cyl(0.5, 0.3, (0.15, -1.6, 0.55), (math.pi / 2, 0, 0), 64)); finish(shroud, plastic)
bpy.ops.object.empty_add(location=(0.15, -1.6, 0.55)); fan = bpy.context.object
hub = cyl(0.1, 0.1, (0, 0, 0), (math.pi / 2, 0, 0)); finish(hub, plastic); hub.parent = fan; hub.location = (0, 0, 0)
for k in range(7):
    bl = box((0, 0, 0.28), (0.13, 0.015, 0.4), rot=(0, 0, 0)); finish(bl, plastic, False)
    bl.rotation_euler = (0, math.radians(360 / 7 * k), math.radians(25)); bl.parent = fan
    a = math.radians(360 / 7 * k); bl.location = (0.28 * math.sin(a), 0, 0.28 * math.cos(a))
    bl.rotation_euler = (0, a, 0); bl.rotation_mode = "XYZ"
    bl.rotation_euler = (math.radians(0), a, 0)
    bl.delta_rotation_euler = (0, 0, 0)
    bl.scale = (1, 1, 1)
    # twist blade about its own radial axis for pitch
    bl.rotation_euler.rotate_axis("Z", math.radians(28))
# motor struts
for a in (30, 150, 270):
    r = math.radians(a); finish(box((0.15 + 0.27 * math.cos(r), -1.55, 0.55 + 0.27 * math.sin(r)), (0.54, 0.02, 0.03), (0, -r, 0)), plastic, False)
# intake pipe: throttle body -> MAF -> cone filter (filter faces the front, next to the manifold)
FC = Vector((-1.38, -0.72, 0.98))      # filter centre
tube_path([(-1.05, 0.82, 0.85), (-1.35, 0.75, 0.92), (-1.38, 0.2, 0.98), (-1.38, -0.38, 0.98)], 0.12, pipe_m)
finish(cyl_between(0.135, (-1.38, -0.02, 0.98), (-1.38, 0.18, 0.98)), plastic)  # MAF housing
finish(box((-1.38, 0.08, 1.16), (0.12, 0.1, 0.12)), plastic)                     # MAF sensor head
finish(cyl_between(0.15, (-1.38, -0.36, 0.98), (-1.38, -0.44, 0.98)), steel)     # clamp
bpy.ops.mesh.primitive_cone_add(vertices=96, radius1=0.16, radius2=0.26, depth=0.62, location=(FC.x, -0.75, FC.z), rotation=(math.pi / 2, 0, 0))
cone = bpy.context.object; finish(cone, filt)
finish(cyl(0.27, 0.04, (FC.x, -1.07, FC.z), (math.pi / 2, 0, 0)), steel)         # end cap
finish(cyl(0.2, 0.045, (FC.x, -1.09, FC.z), (math.pi / 2, 0, 0)), alu)
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -0.35)); finish(bpy.context.object, floor, False)

# ---------------- phase B: heat shield airbox + cold-air duct (rises into place) ----------------
bpy.ops.object.empty_add(location=(FC.x, -0.72, 0.6)); shield = bpy.context.object
sh_parts = [box((-1.03, -0.72, 0.98), (0.03, 0.78, 0.8)),        # wall between filter and engine
            box((-1.38, -0.72, 1.4), (0.74, 0.78, 0.03)),       # lid
            box((-1.38, -0.72, 0.57), (0.74, 0.78, 0.03)),      # floor
            box((-1.38, -0.31, 0.98), (0.74, 0.03, 0.8))]       # rear wall (pipe passes through)
for o in sh_parts: finish(bevel(o, 0.01), shield_m, False); o.parent = shield; o.location -= shield.location
duct_pts = [(-1.38, -2.35, 0.62), (-1.38, -1.35, 0.62), (-1.38, -1.12, 0.8)]
duct = []
for a, b in zip(duct_pts, duct_pts[1:]):
    o = cyl_between(0.13, a, b); boolean(o, cyl_between(0.11, Vector(a) - (Vector(b) - Vector(a)) * 0.1, Vector(b) + (Vector(b) - Vector(a)) * 0.1))
    boolean(o, box((-1.38 - 0.5, -1.7, 0.7), (1.0, 2.0, 1.0)))   # cut the camera-facing half to see the air inside
    finish(o, pipe_m); duct.append(o)
for o in duct: o.parent = shield; o.location -= shield.location
# keyframe build: shield/duct rise from below the floor
def ease(x): x = max(0, min(1, x)); return x * x * (3 - 2 * x)

# ---------------- air particles ----------------
def bez(p0, p1, p2, p3, u):
    return p0 * (1 - u) ** 3 + p1 * 3 * u * (1 - u) ** 2 + p2 * 3 * u * u * (1 - u) + p3 * u ** 3
rnd = random.Random(7)
def mk(name, col, es):
    m, b = mat(name, col, 0, 0.5, emis=col, es=es); return m
hot_m = mk("hot", (1.0, 0.25, 0.03), 3.5); cold_m = mk("cold", (0.1, 0.45, 1.0), 3.5)
LIFE = 1.5
hot = []
for i in range(64):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.042); o = bpy.context.object; finish(o, hot_m)
    src = rnd.random()
    if src < 0.55:   # off the hot exhaust manifold
        p0 = Vector((rnd.uniform(-0.75, 0.75), rnd.uniform(-0.8, -0.65), rnd.uniform(0.45, 1.05)))
    else:            # radiator air pushed back by the fan
        p0 = Vector((rnd.uniform(-0.6, 0.5), -1.5, rnd.uniform(0.15, 0.95)))
    ang = rnd.uniform(0, 2 * math.pi); end = FC + Vector((0.22 * math.cos(ang), rnd.uniform(-0.25, 0.25), 0.22 * math.sin(ang)))
    up = p0 + Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.1, 0.25), rnd.uniform(1.4, 2.0)))
    hot.append(dict(o=o, p0=p0, end=end, up=up, ph=rnd.random() * LIFE, j=rnd.uniform(0.8, 1.2)))
cold = []
for i in range(40):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.042); o = bpy.context.object; finish(o, cold_m)
    off = Vector((rnd.uniform(-0.06, 0.06), 0, rnd.uniform(-0.06, 0.06)))
    ang = rnd.uniform(0, 2 * math.pi); end = FC + Vector((0.22 * math.cos(ang), rnd.uniform(-0.25, 0.25), 0.22 * math.sin(ang)))
    cold.append(dict(o=o, off=off, end=end, ph=rnd.random() * LIFE))
def hot_pos(p, s):
    age = (s + p["ph"]) % LIFE; born = s - age; u = age / LIFE * p["j"]
    if u > 1: return None
    if born < S_SWITCH:   # sucked into the open filter
        mid = p["p0"] + Vector((0, 0, 0.25)); return bez(p["p0"], mid, p["end"] + Vector((0.25, 0, 0.15)), p["end"], u), u
    return bez(p["p0"], p["p0"] + Vector((0, 0, 0.5)), p["up"] - Vector((0, 0, 0.4)), p["up"], u), u
def cold_pos(p, s):
    age = (s + p["ph"]) % LIFE; born = s - age; u = age / LIFE
    if born < S_SWITCH + 0.25: return None
    a, b, c = (Vector(x) + p["off"] for x in duct_pts)
    if u < 0.75: q = u / 0.75; pos = a + (b - a) * q if q < 0.8 else b + (c - b) * ((q - 0.8) / 0.2)
    else: q = (u - 0.75) / 0.25; pos = c + (p["end"] - c) * q
    return pos, u

# ---------------- world, lights, camera ----------------
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.003, 0.004, 0.007, 1)
def light(loc, energy, color, size, tgt=(-0.5, -0.5, 0.9)):
    bpy.ops.object.light_add(type="AREA", location=loc); l = bpy.context.object
    l.data.energy = energy; l.data.color = color; l.data.size = size
    l.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler(); return l
light((-3.0, -6.0, 6.0), 1500, (1.0, 0.96, 0.92), 4.0)
light((-6.0, 3.0, 3.0), 1700, (0.25, 0.5, 1.0), 2.0)
light((5.0, 2.0, 2.0), 1400, (1.0, 0.45, 0.12), 1.5)
sweep = light((-4, -5, 4), 0, (0.8, 0.9, 1.0), 1.0)
bpy.ops.object.light_add(type="POINT", location=(0.1, -0.95, 0.75)); mani_l = bpy.context.object
mani_l.data.color = (1.0, 0.35, 0.08); mani_l.data.shadow_soft_size = 0.3
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 35; cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 4.0
log = []
for f in range(1, N + 1):
    t = (f - 1) / FPS; s = simt(t)
    fan.rotation_euler = (0, s * 2 * math.pi * 2.2, 0); fan.keyframe_insert("rotation_euler", frame=f)
    b = ease((t - T_SWITCH) / T_BUILD)
    shield.location = (FC.x, -0.72, 0.6 - 2.2 * (1 - b)); shield.keyframe_insert("location", frame=f)
    shield.scale = (1, 1, 1) if b > 0.001 else (0.001, 0.001, 0.001); shield.keyframe_insert("scale", frame=f)
    glow = 0.9 + 0.25 * math.sin(t * 5.0)
    mani_b.inputs["Emission Strength"].default_value = glow; mani_b.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
    mani_l.data.energy = 120 * glow; mani_l.data.keyframe_insert("energy", frame=f)
    for group in (hot, cold):
        for p in group:
            r = hot_pos(p, s) if group is hot else cold_pos(p, s)
            if r is None: p["o"].scale = (0.001,) * 3
            else:
                pos, u = r; p["o"].location = pos; k = min(1, u / 0.12, (1 - u) / 0.12 + 0.2); p["o"].scale = (max(0.001, k),) * 3
            p["o"].keyframe_insert("location", frame=f); p["o"].keyframe_insert("scale", frame=f)
    # camera
    target = Vector((-0.75, -0.6, 0.95)).lerp(Vector((-0.9, -1.0, 0.85)), ease((t - 8.0) / 2.0))
    ang = math.radians(-162 + 26 * (t / DUR))
    dist = 3.2 + 3.0 * ease(t / 2.4) - 1.4 * ease((t - 4.4) / 2.0) + 0.9 * ease((t - 7.2) / 1.6)
    hgt = 1.3 + 2.0 * ease(t / 2.4) - 0.4 * ease((t - 4.4) / 2.0)
    cam.location = target + Vector((dist * math.cos(ang), dist * math.sin(ang), hgt))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.dof.focus_distance = (FC - cam.location).length
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f); cam.data.keyframe_insert("dof.focus_distance", frame=f)
    sw = max(0.0, 1 - abs(t - 0.4) / 0.4) + max(0.0, 1 - abs(t - 8.7) / 0.5) + max(0.0, 1 - abs(t - 11.9) / 0.5)
    sweep.location = (-5 + 9 * ((t % 3) / 3), -5, 4); sweep.data.energy = 2600 * sw
    sweep.keyframe_insert("location", frame=f); sweep.data.keyframe_insert("energy", frame=f)
    log.append(dict(f=f, t=round(t, 3), s=round(s, 3), shield=round(b, 3)))
import os; os.makedirs(f"{OUTD}/frames", exist_ok=True)
json.dump(log, open(f"{OUTD}/events.json", "w"))

from bpy_extras.object_utils import world_to_camera_view
if F0 == 1:
    pts = {"filter": (FC.x, -0.95, FC.z + 0.2), "manifold": (0.35, -0.72, 0.8), "radiator": (0.9, -1.75, 1.0),
           "maf": (-1.38, 0.08, 1.2), "duct": (-1.38, -2.0, 0.75), "fan": (0.15, -1.6, 0.9)}
    proj = []
    for f in range(1, N + 1):
        sc.frame_set(f); row = {}
        for n_, p in pts.items():
            v = world_to_camera_view(sc, cam, Vector(p)); row[n_] = [round(v.x, 4), round(1 - v.y, 4)]
        proj.append(row)
    json.dump(proj, open(f"{OUTD}/proj.json", "w"))
sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 92
for f in range(F0, F1 + 1):
    sc.frame_set(f)
    sc.render.filepath = f"{OUTD}/frames/f{f:04d}.jpg"
    t0 = time.time(); bpy.ops.render.render(write_still=True)
    print(f"frame {f} {time.time() - t0:.1f}s", flush=True)
