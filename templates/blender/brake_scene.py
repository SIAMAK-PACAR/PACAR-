"""PACAR: correct disc-brake animation. Caliper is fixed; only the disc + hub spin.
Pads clamp at T_CLAMP, disc decelerates, friction rings heat up (emission).
usage: python3 brake_scene.py <samples> <percent> <frame_start> <frame_end>"""
import bpy, bmesh, math, sys, time
from mathutils import Vector

SAMPLES, PCT, F0, F1 = [int(v) for v in sys.argv[-4:]]
FPS, DUR = 24, 11.0
N = int(FPS * DUR)
T_CLAMP, T_STOP = 4.6, 8.4

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True; sc.cycles.max_bounces = 6
sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920; sc.render.resolution_percentage = PCT
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, N
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Punchy"

def mat(name, color, metal=0.0, rough=0.4, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough; b.inputs["Coat Weight"].default_value = coat
    return m, b

steel, _ = mat("steel", (0.62, 0.63, 0.65), 1.0, 0.22)
face_m, steel_b = mat("disc", (0.6, 0.61, 0.63), 1.0, 0.3)
steel_b.inputs["Emission Color"].default_value = (1.0, 0.22, 0.03, 1)
dark, _ = mat("hub", (0.06, 0.06, 0.07), 1.0, 0.35)
vane, _ = mat("vane", (0.18, 0.18, 0.19), 1.0, 0.5)
red, _ = mat("caliper", (0.55, 0.015, 0.01), 0.0, 0.18, coat=1.0)
pad, _ = mat("pad", (0.04, 0.04, 0.045), 0.1, 0.8)
backing, _ = mat("backing", (0.25, 0.26, 0.28), 1.0, 0.4)
floor, _ = mat("floor", (0.008, 0.008, 0.01), 0.0, 0.2)

def finish(o, m, smooth=True):
    o.data.materials.clear(); o.data.materials.append(m)
    for p in o.data.polygons: p.material_index = 0
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    if smooth:
        try: bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
        except Exception: bpy.ops.object.shade_smooth()
    o.select_set(False); return o

def boolean(target, cutter, op="DIFFERENCE"):
    m = target.modifiers.new("b", "BOOLEAN"); m.object = cutter; m.operation = op; m.solver = "EXACT"
    bpy.context.view_layer.objects.active = target; bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter)

# ---------------- disc (axis = Z) ----------------
R_DISC, T_FACE, GAP = 1.6, 0.085, 0.13
faces = []
for z in (GAP / 2 + T_FACE / 2, -(GAP / 2 + T_FACE / 2)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=160, radius=R_DISC, depth=T_FACE, location=(0, 0, z)); f = bpy.context.object
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.9, depth=T_FACE * 3, location=(0, 0, z)); boolean(f, bpy.context.object)
    for ring, r in enumerate((1.12, 1.4)):
        for i in range(20):
            a = i * 2 * math.pi / 20 + ring * math.pi / 20
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.042, depth=0.5, location=(r * math.cos(a), r * math.sin(a), z))
            boolean(f, bpy.context.object)
    faces.append(finish(f, face_m))
for i in range(40):
    a = i * 2 * math.pi / 40
    bpy.ops.mesh.primitive_cube_add(size=1, location=(1.25 * math.cos(a), 1.25 * math.sin(a), 0), rotation=(0, 0, a + 0.35))
    v = bpy.context.object; v.scale = (0.66, 0.03, GAP); finish(v, vane, smooth=False)
# hat, hub, studs
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=0.92, depth=0.5, location=(0, 0, 0.32)); finish(bpy.context.object, steel)
bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.42, depth=0.55, location=(0, 0, 0.6)); finish(bpy.context.object, dark)
for i in range(5):
    a = i * 2 * math.pi / 5
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.055, depth=0.45, location=(0.65 * math.cos(a), 0.65 * math.sin(a), 0.75))
    finish(bpy.context.object, steel)
spin_parts = list(bpy.data.objects)
bpy.ops.object.empty_add(); spin = bpy.context.object; spin.name = "spin"
for o in spin_parts: o.parent = spin

# ---------------- caliper (fixed) ----------------
def ring_sector(r_in, r_out, depth, a0, a1, z=0.0, segs=48):
    bm = bmesh.new(); verts = []
    for k in range(segs + 1):
        a = a0 + (a1 - a0) * k / segs
        for r in (r_in, r_out):
            for zz in (z - depth / 2, z + depth / 2):
                verts.append(bm.verts.new((r * math.cos(a), r * math.sin(a), zz)))
    for k in range(segs):
        i, j = 4 * k, 4 * (k + 1)
        q = [(0, 1, 3, 2), (0, 2, 2, 0)]
        bm.faces.new([verts[i + 0], verts[i + 2], verts[j + 2], verts[j + 0]])   # bottom
        bm.faces.new([verts[i + 1], verts[j + 1], verts[j + 3], verts[i + 3]])   # top
        bm.faces.new([verts[i + 0], verts[j + 0], verts[j + 1], verts[i + 1]])   # inner
        bm.faces.new([verts[i + 2], verts[i + 3], verts[j + 3], verts[j + 2]])   # outer
    for i in (0, 4 * segs):
        bm.faces.new([verts[i + 0], verts[i + 1], verts[i + 3], verts[i + 2]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("sector"); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("sector", me); bpy.context.collection.objects.link(o); return o

A0, A1 = math.radians(55), math.radians(125)
cal = ring_sector(1.05, 1.95, 0.78, A0, A1)
bev = cal.modifiers.new("bev", "BEVEL"); bev.width = 0.08; bev.segments = 5
bpy.context.view_layer.objects.active = cal; bpy.ops.object.modifier_apply(modifier="bev")
slot = ring_sector(0.0, R_DISC + 0.12, GAP + 2 * T_FACE + 0.12, A0 - 0.3, A1 + 0.3)
boolean(cal, slot)
finish(cal, red)
# pads (fixed in rotation, move along Z to clamp)
pads = []
for sgn in (1, -1):
    p = ring_sector(1.08, 1.58, 0.06, A0 + 0.1, A1 - 0.1, z=sgn * (GAP / 2 + T_FACE + 0.03 + 0.05)); finish(p, pad)
    b = ring_sector(1.08, 1.58, 0.03, A0 + 0.08, A1 - 0.08, z=sgn * (GAP / 2 + T_FACE + 0.03 + 0.05 + 0.045)); finish(b, backing)
    b.parent = p; pads.append((p, sgn))
# bolt heads on caliper face (fixed)
for a in (A0 + 0.12, A1 - 0.12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.07, depth=0.08, location=(1.8 * math.cos(a), 1.8 * math.sin(a), 0.42)); finish(bpy.context.object, steel, False)
    bpy.context.object.parent = cal

# ---------------- assembly orientation ----------------
bpy.ops.object.empty_add(); root = bpy.context.object
for o in [spin, cal] + [p for p, _ in pads]: o.parent = root
root.rotation_euler = (math.radians(90), 0, math.radians(-28))
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -2.05)); finish(bpy.context.object, floor, False)

# ---------------- animation ----------------
def spin_angle(t):
    w0 = 2 * math.pi * 0.55                    # rad/s (visual speed)
    if t <= T_CLAMP: return w0 * t
    if t <= T_STOP:
        d = T_STOP - T_CLAMP; x = t - T_CLAMP
        return w0 * T_CLAMP + w0 * (x - x * x / (2 * d))
    return w0 * T_CLAMP + w0 * (T_STOP - T_CLAMP) / 2
for f in range(1, N + 1):
    t = (f - 1) / FPS
    spin.rotation_euler = (0, 0, -spin_angle(t)); spin.keyframe_insert("rotation_euler", frame=f)
    k = min(1.0, max(0.0, (t - (T_CLAMP - 0.35)) / 0.35))   # pads move 0.35 s before clamp
    rel = max(0.0, (t - 9.6) / 0.5)                          # pads release at the end
    k = k * (1 - min(1.0, rel))
    for p, sgn in pads:
        p.location = (0, 0, -sgn * 0.05 * k); p.keyframe_insert("location", frame=f)
    heat = 0.0 if t < T_CLAMP else min(1.0, (t - T_CLAMP) / (T_STOP - T_CLAMP)) ** 1.5
    if t > T_STOP: heat = max(0.0, 1.0 - (t - T_STOP) / 6.0)
    steel_b.inputs["Emission Strength"].default_value = 1.1 * heat
    steel_b.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
for fc in list(spin.animation_data.action.fcurves) if spin.animation_data and hasattr(spin.animation_data.action, "fcurves") else []:
    for kp in fc.keyframe_points: kp.interpolation = "LINEAR"

# ---------------- world, lights, camera ----------------
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.003, 0.004, 0.007, 1)
def light(loc, energy, color, size):
    bpy.ops.object.light_add(type="AREA", location=loc); l = bpy.context.object
    l.data.energy = energy; l.data.color = color; l.data.size = size
    l.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
light((4.0, -5.0, 4.5), 1100, (1.0, 0.96, 0.92), 3.0)
light((-5.0, 2.5, 3.0), 1600, (0.25, 0.5, 1.0), 1.5)
light((5.0, 3.0, 0.5), 1100, (1.0, 0.45, 0.12), 1.2)
light((0, -2, 6), 300, (1, 1, 1), 4)

bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 55; cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 5.6
target = Vector((0.0, 0.0, 0.45))
for f in range(1, N + 1):
    t = (f - 1) / FPS; k = t / DUR
    cam.location = Vector((2.2 - 0.8 * k, -8.6 + 1.6 * k, 1.1 + 0.3 * k))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.dof.focus_distance = (target - cam.location).length
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)
    cam.data.keyframe_insert("dof.focus_distance", frame=f)

sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 92
for f in range(F0, F1 + 1):
    sc.frame_set(f)
    sc.render.filepath = f"/home/claude/blender/frames/f{f:04d}.jpg"
    t0 = time.time(); bpy.ops.render.render(write_still=True)
    print(f"frame {f} {time.time() - t0:.1f}s", flush=True)
