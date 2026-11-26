"""PACAR engine showcase: Toyota GT86 / Subaru FA20 flat-four (boxer) cutaway.
Exact slider-crank motion, firing order 1-3-2-4, cams at half crank speed.
Crank axis = X (front at -X). Right bank (+Y): cyl 1 (front), 3. Left bank (-Y): cyl 2 (front), 4.
usage: python3 boxer_scene.py <samples> <percent> <frame_start> <frame_end>"""
import bpy, bmesh, math, sys, time, json
from mathutils import Vector

SAMPLES, PCT, F0, F1 = [int(v) for v in sys.argv[-4:]]
FPS, N = 24, 300
DUR = N / FPS

# ---------------- crank schedule (visual, degrees) ----------------
def omega(t):  # visual deg/s
    segs = [(0.0, 300), (1.0, 300), (1.4, 900), (2.35, 900), (2.6, 180), (6.4, 180), (6.7, 900),
            (7.4, 900), (8.2, 1500), (8.6, 1500), (9.6, 900), (DUR + 1, 900)]
    for (a, wa), (b, wb) in zip(segs, segs[1:]):
        if a <= t < b: return wa + (wb - wa) * (t - a) / (b - a)
    return 900
STEP = 1 / 240
def theta_raw(t):
    s, x = 0.0, 0.0
    while x < t:
        h = min(STEP, t - x); s += omega(x + h / 2) * h; x += h
    return s
OFFSET = -theta_raw(3.0) % 720          # cylinder 1 fires (TDC compression) exactly at t = 3.0 s
def theta(t): return theta_raw(t) + OFFSET
ORDER = [1, 3, 2, 4]
FIRST_FIRE_T = 1.0                       # engine catches here (cranking before)

R, L, BORE = 0.43, 1.30, 0.86            # stroke = 2R = bore (FA20 is square: 86 x 86 mm)
COMP_H = 0.26                            # wrist pin to crown
XPOS = {1: -0.9, 2: -0.3, 3: 0.3, 4: 0.9}
SIDE = {1: 1, 3: 1, 2: -1, 4: -1}
PHI = {1: 0.0, 4: 0.0, 2: math.pi, 3: math.pi}   # crankpin angle (from +Y) at theta = 0
# check: cyl c is at TDC when pin points along its own side: side +1 -> pin angle 0, side -1 -> pin angle 180
# cyl1 TDC at th=0, cyl3 at 180, cyl2 at 0/360, cyl4 at 180/540 -> firing 1(0) 3(180) 2(360) 4(540)
FIRE_ANG = {1: 0, 3: 180, 2: 360, 4: 540}

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True; sc.cycles.max_bounces = 5
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
steel, _ = mat("steel", (0.75, 0.76, 0.78), 1.0, 0.18)
forged, _ = mat("forged", (0.42, 0.43, 0.45), 1.0, 0.3)
alu, _ = mat("alu", (0.82, 0.83, 0.85), 1.0, 0.32)
block_m, _ = mat("block", (0.30, 0.31, 0.33), 1.0, 0.45)
red, _ = mat("cover", (0.6, 0.02, 0.015), 0.0, 0.2, coat=1.0)
liner, _ = mat("liner", (0.5, 0.5, 0.52), 1.0, 0.25)
dark, _ = mat("dark", (0.03, 0.03, 0.035), 0.3, 0.5)
floor, _ = mat("floor", (0.006, 0.006, 0.008), 0.0, 0.42)

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
def cyl_y(radius, length, loc, verts=64):   # cylinder whose axis is Y
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=length, location=loc, rotation=(math.pi / 2, 0, 0))
    return bpy.context.object
def cyl_x(radius, length, loc, verts=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=length, location=loc, rotation=(0, math.pi / 2, 0))
    return bpy.context.object
def box(loc, scale, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot); o = bpy.context.object; o.scale = scale
    bpy.ops.object.transform_apply(scale=True, rotation=True); return o
def cut_top(o, z=0.0):                       # cutaway: remove everything above z
    boolean(o, box((0, 0, z + 5), (20, 20, 10)))

# ---------------- crankshaft (rotates about X) ----------------
bpy.ops.object.empty_add(); crank = bpy.context.object; crank.name = "crank"
parts = []
xs = [-1.2, -0.6, 0.0, 0.6, 1.2]                         # 5 main journals
for x in xs: parts.append(finish(cyl_x(0.24, 0.16, (x, 0, 0)), steel))
parts.append(finish(cyl_x(0.16, 0.9, (-1.65, 0, 0)), steel))         # snout
parts.append(finish(cyl_x(0.75, 0.08, (-2.05, 0, 0), 96), forged))    # pulley / damper (front)
parts.append(finish(cyl_x(0.95, 0.07, (1.55, 0, 0), 128), forged))    # flywheel (rear)
for c, x in XPOS.items():
    a = PHI[c]; py, pz = R * math.cos(a), R * math.sin(a)
    parts.append(finish(cyl_x(0.2, 0.2, (x, py, pz)), steel))          # crankpin
    for dx in (-0.14, 0.14):                                            # webs + counterweights
        w = box((x + dx, py * 0.5, pz * 0.5), (0.07, 0.36, R + 0.3), (a - math.pi / 2, 0, 0)); parts.append(finish(w, forged, False))
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.5, depth=0.07, location=(x + dx, 0, 0), rotation=(0, math.pi / 2, 0))
        cw = bpy.context.object
        boolean(cw, box((x + dx, 0.6 * math.cos(a), 0.6 * math.sin(a)), (0.3, 1.2, 1.2), (a, 0, 0)))  # keep half opposite pin
        parts.append(finish(cw, forged))
for o in parts: o.parent = crank

# ---------------- pistons + rods ----------------
pistons, rods = {}, {}
for c, x in XPOS.items():
    s = SIDE[c]
    bpy.ops.object.empty_add(); pe = bpy.context.object; pe.name = f"piston{c}"
    body = finish(cyl_y(BORE / 2 - 0.01, 0.42, (x, s * (COMP_H - 0.21), 0)), alu); body.parent = pe
    for k in range(3):
        g = finish(cyl_y(BORE / 2 - 0.005, 0.018, (x, s * (COMP_H - 0.05 - 0.05 * k), 0)), dark); g.parent = pe
    pin = finish(cyl_x(0.09, 0.62, (x, 0, 0)), steel); pin.parent = pe
    pistons[c] = pe
    bpy.ops.object.empty_add(); re = bpy.context.object; re.name = f"rod{c}"
    beam = box((x, s * L / 2, 0), (0.12, L, 0.16)); finish(beam, forged, False); beam.parent = re
    big = finish(cyl_x(0.26, 0.18, (x, 0, 0)), forged); big.parent = re
    small = finish(cyl_x(0.14, 0.16, (x, s * L, 0)), forged); small.parent = re
    rods[c] = re

# ---------------- cylinders, block, heads (cutaway: top removed) ----------------
TDC_CROWN = R + L + COMP_H            # 1.99
HEAD_FACE = TDC_CROWN + 0.14
flash_mats = {}
for c, x in XPOS.items():
    s = SIDE[c]
    y0, y1 = 0.62, HEAD_FACE
    t = cyl_y(BORE / 2 + 0.07, y1 - y0, (x, s * (y0 + y1) / 2, 0), 72)
    boolean(t, cyl_y(BORE / 2, y1 - y0 + 0.2, (x, s * (y0 + y1) / 2, 0), 72)); cut_top(t, 0.0); finish(t, liner)
    # combustion glow disc in the chamber
    m, b = mat(f"flash{c}", (0.35, 0.34, 0.33), 1.0, 0.4)
    b.inputs["Emission Color"].default_value = (1.0, 0.42, 0.08, 1); b.inputs["Emission Strength"].default_value = 0
    flash_mats[c] = b
    fl = cyl_y(BORE / 2 - 0.02, 0.12, (x, s * (HEAD_FACE - 0.065), 0), 48); finish(fl, m)
for s in (1, -1):
    xb = [XPOS[c] for c in XPOS if SIDE[c] == s]
    # crankcase half
    cc = box((0, s * 0.32, -0.05), (3.0, 0.6, 1.7)); boolean(cc, cyl_x(0.8, 3.2, (0, 0, 0))); cut_top(cc, -0.1); finish(cc, block_m)
    # cylinder head
    hd = box((sum(xb) / 2, s * (HEAD_FACE + 0.35), -0.15), (1.9, 0.7, 1.35)); cut_top(hd, 0.2); finish(hd, block_m)
    cv = box((sum(xb) / 2, s * (HEAD_FACE + 0.78), -0.32), (1.95, 0.14, 1.05)); finish(cv, red)
cams = []
for s in (1, -1):
    for zc in (0.2,):   # upper (visible) camshaft of each head; lower cam is inside the head
        bpy.ops.object.empty_add(location=(0, s * (HEAD_FACE + 0.35), zc)); ce = bpy.context.object
        sh = finish(cyl_x(0.08, 1.9, (0, s * (HEAD_FACE + 0.35), zc)), steel); sh.parent = ce
        for c in XPOS:
            if SIDE[c] != s: continue
            for dx in (-0.16, 0.16):
                lobe = box((XPOS[c] + dx, s * (HEAD_FACE + 0.35), zc + 0.05), (0.1, 0.22, 0.3)); finish(lobe, steel, False); lobe.parent = ce
        sh.location -= ce.location; [ch.__setattr__("location", ch.location - ce.location) for ch in ce.children if ch is not sh]
        cams.append(ce)
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -1.0)); finish(bpy.context.object, floor, False)

# ---------------- animation ----------------
fl_lights = {}
for c, x in XPOS.items():
    bpy.ops.object.light_add(type="POINT", location=(x, SIDE[c] * (HEAD_FACE - 0.07), 0.5)); l = bpy.context.object
    l.data.color = (1.0, 0.45, 0.12); l.data.shadow_soft_size = 0.2; l.data.energy = 0; fl_lights[c] = l
def flash_level(c, th, t):
    if t < FIRST_FIRE_T: return 0.0
    d = (th - FIRE_ANG[c] + 0.01) % 720
    return math.exp(-d / 45.0) if d < 150 else 0.0
log = []
for f in range(1, N + 1):
    t = (f - 1) / FPS; th = theta(t); thr = math.radians(th)
    crank.rotation_euler = (thr, 0, 0); crank.keyframe_insert("rotation_euler", frame=f)
    for ce in cams:
        ce.rotation_euler = (thr / 2, 0, 0); ce.keyframe_insert("rotation_euler", frame=f)
    for c, x in XPOS.items():
        s = SIDE[c]; a = thr + PHI[c]
        py, pz = R * math.cos(a), R * math.sin(a)
        yp = py + s * math.sqrt(L * L - pz * pz)
        pistons[c].location = (0, yp, 0); pistons[c].keyframe_insert("location", frame=f)
        rods[c].location = (0, py, pz)
        rods[c].rotation_euler = (-s * math.asin(pz / L) if s > 0 else math.asin(pz / L), 0, 0)
        rods[c].keyframe_insert("location", frame=f); rods[c].keyframe_insert("rotation_euler", frame=f)
        lv = flash_level(c, th, t)
        flash_mats[c].inputs["Emission Strength"].default_value = 180 * lv
        flash_mats[c].inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
        fl_lights[c].data.energy = 1500 * lv; fl_lights[c].data.keyframe_insert("energy", frame=f)
    log.append(dict(f=f, t=round(t, 3), theta=round(th, 2)))
json.dump(log, open("/home/claude/blender/boxer_theta.json", "w"))
# interpolation: constant keys per frame, linear is fine because a key exists on every frame

# ---------------- world, lights, camera ----------------
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.003, 0.004, 0.007, 1)
def light(loc, energy, color, size):
    bpy.ops.object.light_add(type="AREA", location=loc); l = bpy.context.object
    l.data.energy = energy; l.data.color = color; l.data.size = size
    l.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return l
light((3.0, -4.0, 7.0), 1400, (1.0, 0.96, 0.92), 4.0)
light((-6.0, 4.0, 2.5), 1800, (0.25, 0.5, 1.0), 2.0)
light((6.0, 4.0, 1.5), 1300, (1.0, 0.45, 0.12), 1.5)
sweep = light((-6, -6, 3), 0, (0.8, 0.9, 1.0), 1.0)          # light sweep across the metal
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 28; cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 4.0
target = Vector((0.0, 0.0, -0.1))
for f in range(1, N + 1):
    t = (f - 1) / FPS; k = t / DUR
    ang = math.radians(-60 + 50 * k)                 # slow orbit around the engine
    dist = 10.5 - 2.2 * min(1, t / 3.0)              # push-in during the first 3 s
    hgt = 7.6 - 1.2 * k
    cam.location = Vector((dist * math.cos(ang) * 0.55, dist * math.sin(ang) * 0.55, hgt))
    tgt = target + Vector((0, 0, -0.9))               # aim slightly high: engine in the upper part of the frame
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.dof.focus_distance = (target - cam.location).length
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)
    cam.data.keyframe_insert("dof.focus_distance", frame=f)
    sw = max(0.0, 1 - abs(t - 0.6) / 0.6) + max(0.0, 1 - abs(t - 6.6) / 0.5)
    sweep.location = (-6 + 12 * ((t % 6) / 6), -6, 3); sweep.data.energy = 2500 * sw
    sweep.keyframe_insert("location", frame=f); sweep.data.keyframe_insert("energy", frame=f)

from bpy_extras.object_utils import world_to_camera_view
if F0 == 1:
    proj = []
    for f in range(1, N + 1):
        sc.frame_set(f); t = (f - 1) / FPS; th = theta(t); row = {}
        for c, x in XPOS.items():
            v = world_to_camera_view(sc, cam, Vector((x, SIDE[c] * (HEAD_FACE - 0.1), 0.15)))
            row[c] = [v.x, 1 - v.y, flash_level(c, th, t)]
        proj.append(row)
    json.dump(proj, open("/home/claude/blender/boxer_flash2d.json", "w"))
sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 92
for f in range(F0, F1 + 1):
    sc.frame_set(f)
    sc.render.filepath = f"/home/claude/blender/frames/f{f:04d}.jpg"
    t0 = time.time(); bpy.ops.render.render(write_still=True)
    print(f"frame {f} {time.time() - t0:.1f}s", flush=True)
