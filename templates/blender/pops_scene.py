"""PACAR Tuning Truth: pops & bangs map. Single-cylinder 4-stroke cutaway + exhaust downpipe + catalytic converter.
Crank axis = Y (camera looks along +Y, front half y<0 of static parts removed). Exact slider-crank, cams at half speed.
Cycle angle phi (crank deg): 0 = TDC start of intake, 360 = TDC compression.
Normal spark phi=345 (15 BTDC). Pop map: fuel on overrun + spark retarded to phi=400 (40 ATDC): still burning at EVO (490)
-> flame enters exhaust, ignites in the hot downpipe.
usage: python3 pops_scene.py <samples> <percent> <frame_start> <frame_end>"""
import bpy, math, sys, time, json
from mathutils import Vector

SAMPLES, PCT, F0, F1 = [int(v) for v in sys.argv[-4:]]
FPS, N = 24, 312
DUR = N / FPS
OUTD = "/home/claude/blender/pops"

def omega(t):  # visual crank deg/s
    segs = [(0, 720), (4.3, 720), (4.6, 240), (8.5, 240), (8.9, 1440), (11.5, 1440), (11.9, 540), (DUR + 1, 540)]
    for (a, wa), (b, wb) in zip(segs, segs[1:]):
        if a <= t < b: return wa + (wb - wa) * (t - a) / (b - a)
    return 540
_DT = 1 / 960
_TH = [0.0]
for _i in range(int((DUR + 3) / _DT)): _TH.append(_TH[-1] + omega((_i + 0.5) * _DT) * _DT)
def theta_raw(t):
    x = t / _DT; i = min(int(x), len(_TH) - 2); return _TH[i] + (_TH[i + 1] - _TH[i]) * (x - i)
# the slow-motion pop cycle: retarded spark (phi 400) exactly at t = 6.0 s
OFFSET = (400 - theta_raw(6.0)) % 720
def theta(t): return theta_raw(t) + OFFSET
import bisect
def t_of_theta(th):
    i = bisect.bisect_left(_TH, th - OFFSET); return max(0, i) * _DT
_MODE = {}
def mode(k):     # cycle k starts at theta = 720k
    if k not in _MODE:
        ts = t_of_theta(720 * k)
        _MODE[k] = "fire" if ts < 1.9 else ("cut" if ts < 4.1 else "pop")
    return _MODE[k]
SPARK = {"fire": 345, "pop": 400}
EVO, EVC, IVO, IVC = 490, 730, -10, 230

R, L, BORE, COMP_H = 0.45, 1.5, 1.0, 0.3
TDC_CROWN = R + L + COMP_H          # 2.25
DECK = 2.36                          # head face

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True; sc.cycles.max_bounces = 5
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920; sc.render.resolution_percentage = PCT
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, N
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Punchy"

def mat(name, color, metal=0.0, rough=0.4, coat=0.0, emis=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough; b.inputs["Coat Weight"].default_value = coat
    if emis:
        b.inputs["Emission Color"].default_value = (*emis, 1); b.inputs["Emission Strength"].default_value = 0
    return m, b
steel, _ = mat("steel", (0.78, 0.79, 0.81), 1.0, 0.16)
forged, _ = mat("forged", (0.42, 0.43, 0.45), 1.0, 0.3)
alu, _ = mat("alu", (0.83, 0.84, 0.86), 1.0, 0.3)
block_m, _ = mat("block", (0.32, 0.33, 0.35), 1.0, 0.42)
cover, _ = mat("cover", (0.55, 0.02, 0.015), 0.0, 0.2, coat=1.0)
liner, _ = mat("liner", (0.52, 0.52, 0.54), 1.0, 0.24)
pipe_m, _ = mat("pipe", (0.80, 0.72, 0.62), 1.0, 0.22)      # stainless, slight heat tint
dark, _ = mat("dark", (0.03, 0.03, 0.035), 0.3, 0.5)
ceramic, _ = mat("ceramic", (0.85, 0.85, 0.82), 0.0, 0.6)
floor, _ = mat("floor", (0.006, 0.006, 0.008), 0.0, 0.4)
plug_tip, plug_b = mat("plugtip", (0.6, 0.6, 0.6), 1.0, 0.3, emis=(0.55, 0.75, 1.0))
chamber_m, chamber_b = mat("chamber", (0.3, 0.3, 0.3), 1.0, 0.4, emis=(1.0, 0.45, 0.1))
spray_m, spray_b = mat("spray", (0.6, 0.8, 1.0), 0.0, 0.3, emis=(0.55, 0.8, 1.0))
spray_b.inputs["Alpha"].default_value = 0.0

# catalytic converter substrate: longitudinal channel walls (wave bands) + heat glow
cat_m = bpy.data.materials.new("cat"); cat_m.use_nodes = True
nt = cat_m.node_tree; cb = nt.nodes["Principled BSDF"]
wave = nt.nodes.new("ShaderNodeTexWave"); wave.inputs["Scale"].default_value = 14; wave.bands_direction = "X"
wave.inputs["Distortion"].default_value = 0; wave.wave_profile = "SAW"
ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (0.05, 0.05, 0.05, 1)
ramp.color_ramp.elements[1].position = 0.15; ramp.color_ramp.elements[1].color = (0.75, 0.73, 0.68, 1)
nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], cb.inputs["Base Color"])
cb.inputs["Roughness"].default_value = 0.7
cb.inputs["Emission Color"].default_value = (1.0, 0.22, 0.03, 1); cb.inputs["Emission Strength"].default_value = 0
nt.links.new(ramp.outputs["Color"], cb.inputs["Emission Color"]) if False else None

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
def cyl(radius, depth, loc, rot=(0, 0, 0), verts=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot)
    return bpy.context.object
def cyl_y(r, d, loc, v=64): return cyl(r, d, loc, (math.pi / 2, 0, 0), v)
def cyl_x(r, d, loc, v=64): return cyl(r, d, loc, (0, math.pi / 2, 0), v)
def cyl_between(r, a, b, v=48):
    a, b = Vector(a), Vector(b); d = b - a
    o = cyl(r, d.length, (a + b) / 2, (0, 0, 0), v)
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler(); return o
def box(loc, scale, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot); o = bpy.context.object; o.scale = scale
    bpy.ops.object.transform_apply(scale=True, rotation=True); return o
def cut_front(o, y=0.0): boolean(o, box((0, y - 10, 0), (40, 20, 40)))
def apply_tf(o):
    bpy.context.view_layer.objects.active = o; o.select_set(True); bpy.ops.object.transform_apply(location=False, rotation=True, scale=True); o.select_set(False)

# ---------------- crankshaft (rotates about Y) ----------------
bpy.ops.object.empty_add(); crank = bpy.context.object
parts = [finish(cyl_y(0.22, 1.5, (0, 0, 0)), steel)]
parts.append(finish(cyl_y(0.17, 0.42, (0, 0, R)), steel))                               # crankpin
for dy in (-0.27, 0.27):
    w = box((0, dy, R / 2), (0.42, 0.1, R + 0.32)); parts.append(finish(w, forged, False))
    cw = cyl_y(0.72, 0.1, (0, dy, 0), 96); boolean(cw, box((0, dy, 0.75), (2, 0.4, 1.5))); parts.append(finish(cw, forged))
for o in parts: o.parent = crank

# ---------------- piston + rod ----------------
bpy.ops.object.empty_add(); piston = bpy.context.object
finish(cyl(BORE / 2 - 0.012, 0.5, (0, 0, COMP_H - 0.25), verts=96), alu).parent = piston
for k in range(3): finish(cyl(BORE / 2 - 0.006, 0.02, (0, 0, COMP_H - 0.06 - 0.06 * k), verts=96), dark).parent = piston
finish(cyl_y(0.1, 0.7, (0, 0, 0)), steel).parent = piston
bpy.ops.object.empty_add(); rod = bpy.context.object
finish(box((0, 0, L / 2), (0.16, 0.13, L)), forged, False).parent = rod
finish(cyl_y(0.27, 0.2, (0, 0, 0)), forged).parent = rod
finish(cyl_y(0.15, 0.18, (0, 0, L)), forged).parent = rod

# ---------------- block, liner, crankcase (cut) ----------------
lin = cyl(BORE / 2 + 0.06, DECK - 0.55, (0, 0, (DECK + 0.55) / 2), verts=96)
boolean(lin, cyl(BORE / 2, DECK, (0, 0, (DECK + 0.55) / 2), verts=96)); cut_front(lin); finish(lin, liner)
blk = box((0, 0, (DECK + 0.55) / 2), (1.5, 1.3, DECK - 0.55)); boolean(blk, cyl(BORE / 2 + 0.05, DECK, (0, 0, (DECK + 0.55) / 2), verts=96))
cut_front(blk); finish(blk, block_m)
cc = box((0, 0, -0.15), (1.9, 1.3, 1.5)); boolean(cc, cyl_y(0.86, 2, (0, 0, 0), 96)); boolean(cc, box((0, 0, 0.8), (1.0, 1.0, 0.6)))
cut_front(cc); finish(cc, block_m)

# ---------------- head with ports (cut) ----------------
VX = {"in": -0.24, "ex": 0.24}
SEAT = DECK + 0.04
hd = box((0, 0, DECK + 0.4), (1.7, 1.3, 0.8))
boolean(hd, cyl(BORE / 2, 0.16, (0, 0, DECK + 0.02), verts=96))                       # chamber
for k, s in (("in", -1), ("ex", 1)):
    boolean(hd, cyl(0.19, 0.2, (VX[k], 0, SEAT + 0.08)))                             # valve throat
    boolean(hd, cyl_between(0.17, (VX[k], 0, SEAT + 0.1), (s * 0.95, 0, DECK + 0.48)))  # port
    boolean(hd, cyl(0.045, 1.0, (VX[k], 0, DECK + 0.7)))                              # valve guide
boolean(hd, cyl(0.07, 1.0, (0, 0, DECK + 0.5)))                                      # plug hole
cut_front(hd); finish(hd, block_m)
cam_cover = box((0, 0.0, DECK + 1.15), (1.7, 1.3, 0.7)); boolean(cam_cover, box((0, 0, DECK + 1.05), (1.5, 1.1, 0.7)))
cut_front(cam_cover); finish(cam_cover, cover)

# valves + followers
valves = {}
for k in VX:
    bpy.ops.object.empty_add(); ve = bpy.context.object
    finish(cyl(0.18, 0.05, (VX[k], 0, SEAT + 0.025)), steel).parent = ve
    finish(cyl(0.03, 0.62, (VX[k], 0, SEAT + 0.36)), steel).parent = ve
    finish(cyl(0.11, 0.07, (VX[k], 0, SEAT + 0.705)), forged).parent = ve         # bucket follower
    for j in range(6):                                                              # spring coils
        t_ = bpy.ops.mesh.primitive_torus_add(major_radius=0.08, minor_radius=0.014, location=(VX[k], 0, SEAT + 0.3 + j * 0.06))
        finish(bpy.context.object, steel).parent = ve
    valves[k] = ve
CAMZ = SEAT + 0.74 + 0.11
cams = {}
for k in VX:
    bpy.ops.object.empty_add(location=(VX[k], 0, CAMZ)); ce = bpy.context.object
    for o in (cyl_y(0.11, 0.18, (VX[k], 0, CAMZ)), cyl_y(0.075, 0.18, (VX[k], 0, CAMZ - 0.155)), cyl_y(0.05, 1.2, (VX[k], 0, CAMZ))):
        finish(o, steel); o.parent = ce; o.location -= ce.location
    hull = box((VX[k], 0, CAMZ - 0.08), (0.15, 0.18, 0.16)); finish(hull, steel, False); hull.parent = ce; hull.location -= ce.location
    cams[k] = ce

# spark plug + injector
finish(cyl(0.06, 0.55, (0, 0, DECK + 0.33)), ceramic)
tip = cyl(0.025, 0.06, (0, 0, DECK + 0.03)); finish(tip, plug_tip)
inj = cyl_between(0.05, (-1.05, 0, DECK + 0.95), (-0.55, 0, DECK + 0.45)); finish(inj, dark)
bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.12, radius2=0.01, depth=0.32, location=(-0.42, 0, DECK + 0.32))
spray = bpy.context.object; spray.rotation_euler = (Vector((0.35, 0, -0.35))).to_track_quat("-Z", "Y").to_euler(); finish(spray, spray_m)

# chamber glow disc
cg = cyl(BORE / 2 - 0.02, 0.06, (0, 0, DECK - 0.03), verts=64); finish(cg, chamber_m)
# hide chamber disc when piston is near: it sits just under the head face (crown max 2.25 < 2.30)

# ---------------- exhaust: runner, downpipe, catalytic converter ----------------
PZ = DECK + 0.48; PX0, PX1 = 0.85, 1.75; PR = 0.2
def tube(a, b, r, th=0.03):
    o = cyl_between(r, a, b, 64); boolean(o, cyl_between(r - th, Vector(a) - (Vector(b) - Vector(a)) * 0.05, Vector(b) + (Vector(b) - Vector(a)) * 0.05, 64))
    cut_front(o); return finish(o, pipe_m)
tube((PX0, 0, PZ), (PX1, 0, PZ), PR)
bpy.ops.mesh.primitive_uv_sphere_add(radius=PR, location=(PX1, 0, PZ), segments=48, ring_count=24); el = bpy.context.object
boolean(el, cyl_between(PR - 0.03, (PX1 - 0.4, 0, PZ), (PX1 + 0.01, 0, PZ))); boolean(el, cyl_between(PR - 0.03, (PX1, 0, PZ + 0.01), (PX1, 0, PZ - 0.4)))
boolean(el, box((PX1 + 0.1, 0, PZ + 0.1), (0.2, 0.7, 0.2)) if False else box((PX1, -1, PZ), (2, 2, 2)))
finish(el, pipe_m)
CAT_TOP, CAT_BOT = 1.35, 0.05
tube((PX1, 0, PZ), (PX1, 0, CAT_TOP + 0.15), PR)
cone_t = cyl_between(0.36, (PX1, 0, CAT_TOP), (PX1, 0, CAT_BOT), 64)
boolean(cone_t, cyl_between(0.33, (PX1, 0, CAT_TOP + 0.1), (PX1, 0, CAT_BOT - 0.1), 64)); cut_front(cone_t); finish(cone_t, pipe_m)
for z0, z1 in ((CAT_TOP + 0.15, CAT_TOP), (CAT_BOT, CAT_BOT - 0.15)):
    bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=0.36 if z0 > z1 else PR, radius2=PR if z0 > z1 else 0.36, depth=0.15,
                                    location=(PX1, 0, (z0 + z1) / 2))
    cn = bpy.context.object
    if z0 > z1: cn.rotation_euler = (math.pi, 0, 0)
    boolean(cn, cyl(PR - 0.03, 0.3, (PX1, 0, (z0 + z1) / 2))); cut_front(cn); finish(cn, pipe_m)
sub = cyl(0.33, CAT_TOP - CAT_BOT - 0.04, (PX1, 0, (CAT_TOP + CAT_BOT) / 2)); cut_front(sub, 0.02); finish(sub, cat_m, False)
tube((PX1, 0, CAT_BOT - 0.15), (PX1, 0, -1.7), PR)
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -1.75)); finish(bpy.context.object, floor, False)

# flame path: exhaust valve throat -> port -> runner -> elbow -> downpipe -> cat face
path = [Vector((0.24, 0, SEAT + 0.08)), Vector((0.95, 0, PZ)), Vector((PX1, 0, PZ)), Vector((PX1, 0, CAT_TOP + 0.05))]
seglen = [(b - a).length for a, b in zip(path, path[1:])]; PL = sum(seglen)
def path_pt(s):
    d = s * PL
    for (a, b), l in zip(zip(path, path[1:]), seglen):
        if d <= l: return a + (b - a) * (d / l)
        d -= l
    return path[-1]
NB = 28
balls = []
for i in range(NB):
    s = (i + 0.5) / NB
    m, b = mat(f"fl{i}", (1.0, 0.4, 0.08), 0.0, 0.5, emis=(1.0, 0.32, 0.04))
    b.inputs["Alpha"].default_value = 1.0
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=0.15, location=path_pt(s)); o = bpy.context.object
    finish(o, m); balls.append((s, o, b))
lights_fl = []
for s in (0.2, 0.5, 0.8):
    bpy.ops.object.light_add(type="POINT", location=path_pt(s) + Vector((0, -0.05, 0))); l = bpy.context.object
    l.data.color = (1.0, 0.5, 0.15); l.data.shadow_soft_size = 0.15; l.data.energy = 0; lights_fl.append((s, l))
bpy.ops.object.light_add(type="POINT", location=(0, -0.1, DECK - 0.15)); ch_l = bpy.context.object
ch_l.data.color = (1.0, 0.5, 0.15); ch_l.data.shadow_soft_size = 0.2; ch_l.data.energy = 0
bpy.ops.object.light_add(type="POINT", location=(PX1, -0.6, (CAT_TOP + CAT_BOT) / 2)); cat_l = bpy.context.object
cat_l.data.color = (1.0, 0.3, 0.06); cat_l.data.energy = 0

# ---------------- event model ----------------
def lift(phi, open_, close_):
    d = close_ - open_; x = (phi - open_) % 720
    return math.sin(math.pi * x / d) ** 1.3 if x < d else 0.0
def events(t):
    th = theta(t); k = int(th // 720); phi = th - 720 * k
    out = dict(th=th, phi=phi, k=k, mode=mode(k), spray=0.0, spark=0.0, chamber=0.0, front=None, bang=0.0)
    md = mode(k)
    if md in ("fire", "pop") and 10 < phi < 200: out["spray"] = math.sin(math.pi * (phi - 10) / 190)
    if md in SPARK:
        sp = SPARK[md]; d = phi - sp
        if 0 <= d < 14: out["spark"] = 1 - d / 14
        if md == "fire" and 0 <= d < 150: out["chamber"] = min(1, d / 12) * math.exp(-max(0, d - 12) / 40)
        if md == "pop" and 0 <= d < 140: out["chamber"] = 0.55 * min(1, d / 25) * (1 if phi < EVO else math.exp(-(phi - EVO) / 25))
    for kk in (k, k - 1):                  # pipe flame of a pop cycle (may extend into next cycle)
        if mode(kk) != "pop": continue
        p = (th - (720 * kk + EVO)) / 230.0
        if 0 <= p < 1.25: out["front"] = p; out["bang"] = max(0.0, 1 - abs(p - 0.45) / 0.22) if 0.23 < p < 0.67 else 0.0
    return out
BANGS = [t_of_theta(720 * k + EVO + 0.45 * 230) for k in range(0, 40) if mode(k) == "pop"]
BANGS = [b for b in BANGS if 0 < b < DUR]
def heat(t):
    return min(1.0, sum((0.2 if b < 8 else 0.13) * math.exp(-(t - b) / 8.0) * min(1, (t - b) / 0.3) for b in BANGS if b <= t))
json.dump(BANGS, open(f"{OUTD}/bangs.json", "w"))

log = []
for f in range(1, N + 1):
    t = (f - 1) / FPS; e = events(t); th = math.radians(e["th"])
    crank.rotation_euler = (0, th, 0); crank.keyframe_insert("rotation_euler", frame=f)
    xp, zp = R * math.sin(th), R * math.cos(th)
    zw = zp + math.sqrt(L * L - xp * xp)
    piston.location = (0, 0, zw); piston.keyframe_insert("location", frame=f)
    rod.location = (xp, 0, zp); rod.rotation_euler = (0, math.asin(-xp / L), 0)
    rod.keyframe_insert("location", frame=f); rod.keyframe_insert("rotation_euler", frame=f)
    phi = e["phi"]
    for kname, (o, c, pk) in (("in", (IVO, IVC, 110)), ("ex", (EVO, EVC, 610))):
        lv = lift(phi, o, c) * 0.12
        valves[kname].location = (0, 0, -lv); valves[kname].keyframe_insert("location", frame=f)
        cams[kname].rotation_euler = (0, math.radians((e["th"] - pk) / 2), 0); cams[kname].keyframe_insert("rotation_euler", frame=f)
    spray_b.inputs["Alpha"].default_value = 0.55 * e["spray"]; spray_b.inputs["Emission Strength"].default_value = 6 * e["spray"]
    spray_b.inputs["Alpha"].keyframe_insert("default_value", frame=f); spray_b.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
    plug_b.inputs["Emission Strength"].default_value = 300 * e["spark"]; plug_b.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
    chamber_b.inputs["Emission Strength"].default_value = 120 * e["chamber"]; chamber_b.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
    ch_l.data.energy = 900 * e["chamber"] + 150 * e["spark"]; ch_l.data.keyframe_insert("energy", frame=f)
    p = e["front"]; inten = {}
    for s, o, b in balls:
        if p is None: v = 0.0
        else:
            front = min(1.0, p * 1.3)
            v = (math.exp(-((s - front) / 0.13) ** 2) * (1 - min(1, max(0, p - 0.9) / 0.35)) * (0.5 if s < front - 0.05 or True else 1)
                 + 2.2 * e["bang"] * math.exp(-((s - 0.55) / 0.28) ** 2))
            v *= 1 - min(1, max(0, p - 1.0) / 0.25)
        v = min(v, 2.5); inten[s] = v
        b.inputs["Emission Strength"].default_value = 18 * v; b.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
        sz = 0.001 if v < 0.02 else min(1.25, 0.55 + 0.5 * v)
        o.scale = (sz, sz, sz); o.keyframe_insert("scale", frame=f)
    for s, l in lights_fl:
        v = max(inten[bs] for bs, _, _ in balls if abs(bs - s) < 0.12)
        l.data.energy = 700 * v; l.data.keyframe_insert("energy", frame=f)
    h = heat(t)
    cb.inputs["Emission Strength"].default_value = 2.2 * h ** 1.5; cb.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
    cat_l.data.energy = 250 * h ** 1.5; cat_l.data.keyframe_insert("energy", frame=f)
    log.append(dict(f=f, t=round(t, 3), phi=round(phi, 1), mode=e["mode"], spark=round(e["spark"], 2), bang=round(e["bang"], 3),
                    front=None if p is None else round(p, 3), chamber=round(e["chamber"], 3), heat=round(h, 3)))
json.dump(log, open(f"{OUTD}/events.json", "w"))

# ---------------- world, lights, camera ----------------
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.003, 0.004, 0.007, 1)
def light(loc, energy, color, size, tgt=(0.4, 0, 1.0)):
    bpy.ops.object.light_add(type="AREA", location=loc); l = bpy.context.object
    l.data.energy = energy; l.data.color = color; l.data.size = size
    l.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler(); return l
light((2.5, -7.0, 6.0), 1300, (1.0, 0.96, 0.92), 4.0)
light((-5.5, 3.0, 3.0), 1600, (0.25, 0.5, 1.0), 2.0)
light((6.0, 3.0, 1.0), 1300, (1.0, 0.45, 0.12), 1.5)
sweep = light((-4, -5, 4), 0, (0.8, 0.9, 1.0), 1.0)
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 50; cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 5.6
target = Vector((0.55, 0, 1.75))
for f in range(1, N + 1):
    t = (f - 1) / FPS; k = t / DUR
    ang = math.radians(-112 + 32 * k)                    # slow orbit, front-left to front-right
    dist = 12.2 - 2.0 * min(1, t / 3.0) - 0.6 * max(0, min(1, (t - 5.0) / 2.5))   # push-in, extra during slow-mo
    hgt = 1.9 - 0.8 * k
    cam.location = target + Vector((dist * math.cos(ang), dist * math.sin(ang), hgt))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.dof.focus_distance = (target - cam.location).length
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f); cam.data.keyframe_insert("dof.focus_distance", frame=f)
    sw = max(0.0, 1 - abs(t - 0.5) / 0.5) + max(0.0, 1 - abs(t - 4.6) / 0.5) + max(0.0, 1 - abs(t - 11.8) / 0.5)
    sweep.location = (-4 + 10 * ((t % 4) / 4), -5, 4); sweep.data.energy = 2500 * sw
    sweep.keyframe_insert("location", frame=f); sweep.data.keyframe_insert("energy", frame=f)

from bpy_extras.object_utils import world_to_camera_view
if F0 == 1:
    pts = {"plug": (0, 0, DECK + 0.6), "exvalve": (0.24, 0, SEAT + 0.4), "injector": (-0.8, 0, DECK + 0.72),
           "cat": (PX1 + 0.36, 0, 0.7), "piston": (-0.5, 0, 1.6), "pipe": (PX1, 0, PZ), "chamber": (0, 0, DECK - 0.05)}
    proj = []
    for f in range(1, N + 1):
        sc.frame_set(f); row = {}
        for n_, p in pts.items():
            v = world_to_camera_view(sc, cam, Vector(p)); row[n_] = [round(v.x, 4), round(1 - v.y, 4)]
        proj.append(row)
    json.dump(proj, open(f"{OUTD}/proj.json", "w"))
sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 92
frames = range(F0, F1 + 1)
for f in frames:
    sc.frame_set(f)
    sc.render.filepath = f"{OUTD}/frames/f{f:04d}.jpg"
    t0 = time.time(); bpy.ops.render.render(write_still=True)
    print(f"frame {f} {time.time() - t0:.1f}s", flush=True)
