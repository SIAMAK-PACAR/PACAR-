#!/usr/bin/env python3
"""ENGINE DNA audio library tool (free: Python stdlib + numpy + ffmpeg).

  python3 edna_audio.py init
  python3 edna_audio.py add FILE --class CUSTOM --config V8 --category IDLE --name "..." [--project-json p.json]
  python3 edna_audio.py add FILE --class REAL --manufacturer BMW --model "M3" --year 2021 --engine-code S58 \
        --config INLINE_6 --category COLD_START --source-url URL --creator NAME --license CC-BY-4.0 --attribution "..."
  python3 edna_audio.py search "V12 high rpm custom"      (free text: brand, model, code, config, category, REAL/CUSTOM)
  python3 edna_audio.py qc [ASSET_ID|all]                 (peak, RMS, LUFS, clipping, silence, noise floor -> quality_reports)
  python3 edna_audio.py dedupe                            (exact hash + near-duplicate envelope match)
  python3 edna_audio.py process ASSET_ID [--lufs -16] [--trim] [--fade 0.05] [--segment 5]   (non-destructive -> PROCESSED/)
  python3 edna_audio.py preview ASSET_ID                  (mp3 preview -> PREVIEWS/)
  python3 edna_audio.py licenses                          (writes LICENSES/license_register.csv)
  python3 edna_audio.py pick --config V8 --category ACCELERATION [--class REAL]   (for video assembly)
"""
import argparse, csv, datetime, hashlib, json, os, re, shutil, sqlite3, subprocess, sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIB = os.path.join(ROOT, "AUDIO_LIBRARY")
DB = os.path.join(LIB, "METADATA", "engine_dna_audio.sqlite")
NOW = lambda: datetime.datetime.now().isoformat(timespec="seconds")

LICENSES = [  # code, url, commercial, modification, attribution
    ("ORIGINAL", "", 1, 1, 0),                       # made by ENGINE DNA itself
    ("CC0", "https://creativecommons.org/publicdomain/zero/1.0/", 1, 1, 0),
    ("CC-BY-4.0", "https://creativecommons.org/licenses/by/4.0/", 1, 1, 1),
    ("CC-BY-3.0", "https://creativecommons.org/licenses/by/3.0/", 1, 1, 1),
    ("CC-BY-SA-4.0", "https://creativecommons.org/licenses/by-sa/4.0/", 1, 1, 1),
    ("CC-BY-NC-4.0", "https://creativecommons.org/licenses/by-nc/4.0/", 0, 1, 1),
    ("CC-BY-ND-4.0", "https://creativecommons.org/licenses/by-nd/4.0/", 1, 0, 1),
    ("CC-BY-NC-ND-4.0", "https://creativecommons.org/licenses/by-nc-nd/4.0/", 0, 0, 1),
    ("UNKNOWN", "", 0, 0, 1),
]
MANUFACTURERS = ["BMW", "Mercedes-Benz", "Mercedes-AMG", "Audi", "Porsche", "Volkswagen", "Volvo", "Koenigsegg",
                 "Lamborghini", "Ferrari", "McLaren", "Bugatti", "Pagani", "Aston Martin", "Bentley", "Rolls-Royce",
                 "Honda", "Toyota", "Nissan", "Mazda", "Subaru", "Mitsubishi", "Lexus", "Hyundai", "Kia", "Ford",
                 "Chevrolet", "Dodge", "Cadillac", "Tesla", "BYD"]
FOLDER = {"Mercedes-Benz": "MERCEDES_BENZ", "Mercedes-AMG": "MERCEDES_BENZ"}
KNOWN_FOLDERS = {"BMW", "MERCEDES_BENZ", "AUDI", "PORSCHE", "VOLVO", "KOENIGSEGG", "LAMBORGHINI", "FERRARI",
                 "HONDA", "TOYOTA", "NISSAN", "SUBARU", "FORD"}
CATEGORIES = ['COLD_START', 'WARM_START', 'IDLE', 'LOW_RPM', 'MID_RPM', 'HIGH_RPM', 'REVVING', 'ACCELERATION',
              'DECELERATION', 'GEAR_SHIFT', 'EXHAUST', 'INTAKE', 'TURBO_SPOOL', 'SUPERCHARGER_WHINE', 'FLYBY',
              'LAUNCH', 'HYBRID_START_STOP', 'EV_ACCELERATION']
CONFIGS = ["V8", "V10", "V12", "INLINE_3", "INLINE_4", "INLINE_5", "INLINE_6", "V6", "BOXER", "W12", "W16",
           "ROTARY", "HYBRID", "ELECTRIC"]

def con():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c

def manu_folder(name):
    f = FOLDER.get(name, re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_"))
    return f if f in KNOWN_FOLDERS else "OTHER"

# ---------------- init ----------------
def cmd_init(a):
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = con()
    c.executescript(open(os.path.join(ROOT, "09_Scripts", "schema.sql")).read())
    c.executemany("INSERT OR IGNORE INTO licenses(code,url,commercial_ok,modification_ok,attribution_required) VALUES(?,?,?,?,?)", LICENSES)
    c.executemany("INSERT OR IGNORE INTO manufacturers(name,folder) VALUES(?,?)", [(m, manu_folder(m)) for m in MANUFACTURERS])
    c.commit(); print("database ready:", DB)

# ---------------- audio helpers ----------------
def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels:format=duration,format_name",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    j = json.loads(out); s = j["streams"][0]
    return float(j["format"]["duration"]), int(s["sample_rate"]), int(s["channels"]), j["format"]["format_name"].split(",")[0]

def load_all(path):
    """all channels interleaved at the native rate (for true sample peaks)"""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)

def load_mono(path, sr=22050):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-af", "pan=mono|c0=0.5*c0+0.5*c1" if probe(path)[2] == 2 else "anull",
                          "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32), sr

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def next_id(c, prefix):
    n = c.execute("SELECT COUNT(*) FROM audio_assets WHERE id LIKE ?", (prefix + "%",)).fetchone()[0]
    return f"{prefix}{n + 1:04d}"

# ---------------- add ----------------
def cmd_add(a):
    c = con()
    if a.category not in CATEGORIES: sys.exit(f"category must be one of {CATEGORIES}")
    if a.config not in CONFIGS: sys.exit(f"config must be one of {CONFIGS}")
    dur, sr, ch, fmt = probe(a.file)
    if a.cls == "CUSTOM":
        dest_dir = os.path.join(LIB, "CUSTOM", a.config if os.path.isdir(os.path.join(LIB, "CUSTOM", a.config)) else "V8")
        aid = next_id(c, f"CUS-{a.config}-")
        lic = ("ORIGINAL", "YES", "YES", "SYNTHETIC", "ENGINE DNA (procedural)")
        proj = None
        if a.project_json:
            p = json.load(open(a.project_json))
            cur = c.execute("INSERT INTO custom_sound_projects(name,generator,parameters_json,created) VALUES(?,?,?,?)",
                            (a.name, p.get("generator", "synth_engine.py"), json.dumps(p), NOW()))
            proj = cur.lastrowid
        src_id = None
    else:
        if not a.manufacturer: sys.exit("REAL assets need --manufacturer")
        lr = c.execute("SELECT * FROM licenses WHERE code=?", (a.license or "UNKNOWN",)).fetchone()
        if lr is None: sys.exit("unknown license code; add it to the licenses table first")
        # unknown license or missing source -> QUARANTINED, never VERIFIED automatically
        status = "QUARANTINED" if (lr["code"] == "UNKNOWN" or not a.source_url) else ("VERIFIED" if a.verified else "UNVERIFIED")
        lic = (lr["code"], "YES" if lr["commercial_ok"] else "NO", "YES" if lr["modification_ok"] else "NO", status, a.creator)
        dest_dir = os.path.join(LIB, "REAL", manu_folder(a.manufacturer))
        aid = next_id(c, f"REA-{manu_folder(a.manufacturer)[:4]}-")
        # keep an untouched original copy
        orig = os.path.join(LIB, "ORIGINALS", aid + os.path.splitext(a.file)[1])
        shutil.copy2(a.file, orig)
        src_id = c.execute("INSERT INTO audio_sources(source_url,creator,license_id,attribution_text,download_date,original_file) VALUES(?,?,?,?,?,?)",
                           (a.source_url, a.creator, lr["id"], a.attribution, a.download_date or NOW()[:10], orig)).lastrowid
        proj = None
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{aid}_{re.sub(r'[^A-Za-z0-9]+', '_', a.name)}{os.path.splitext(a.file)[1]}")
    if os.path.exists(dest): sys.exit("refusing to overwrite " + dest)
    shutil.copy2(a.file, dest)
    c.execute("""INSERT INTO audio_assets(id,asset_name,classification,manufacturer,model,model_year,engine_code,engine_configuration,
                 sound_category,file_path,file_format,duration_s,sample_rate,channels,sha256,source_id,custom_project_id,source_url,creator,
                 license,attribution_text,commercial_ok,modification_ok,verification_status,notes,added)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (aid, a.name, a.cls, a.manufacturer, a.model, a.year, a.engine_code, a.config, a.category,
               os.path.relpath(dest, LIB), fmt, round(dur, 3), sr, ch, sha256(dest), src_id, proj, a.source_url, lic[4],
               lic[0], a.attribution, lic[1], lic[2], lic[3], a.notes, NOW()))
    c.commit(); print(aid, "->", os.path.relpath(dest, ROOT), f"[{lic[3]}]")

# ---------------- search ----------------
def cmd_search(a):
    c = con(); words = a.query.upper().split()
    where, args = [], []
    for w in words:
        if w in ("REAL", "CUSTOM"): where.append("classification=?"); args.append(w); continue
        if w in ("VERIFIED", "UNVERIFIED", "QUARANTINED", "SYNTHETIC"): where.append("verification_status=?"); args.append(w); continue
        if w in ("COMMERCIAL",): where.append("commercial_ok='YES'"); continue
        w2 = {"RPM": None, "HIGH": "HIGH", "LOW": "LOW", "MID": "MID", "COLD": "COLD", "START": "START",
              "INLINE-4": "INLINE_4", "I4": "INLINE_4", "I6": "INLINE_6", "INLINE-6": "INLINE_6"}.get(w, w)
        if w2 is None: continue
        where.append("(UPPER(asset_name) LIKE ? OR UPPER(IFNULL(manufacturer,'')) LIKE ? OR UPPER(IFNULL(model,'')) LIKE ? OR "
                     "UPPER(IFNULL(engine_code,'')) LIKE ? OR engine_configuration LIKE ? OR sound_category LIKE ? OR UPPER(IFNULL(license,'')) LIKE ?)")
        args += [f"%{w2}%"] * 7
    q = "SELECT * FROM audio_assets" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY quality_score DESC NULLS LAST, id"
    rows = c.execute(q, args).fetchall()
    if not rows: print("no matches"); return
    for r in rows:
        print(f"{r['id']:<16} {r['classification']:<6} {r['verification_status']:<11} {r['engine_configuration']:<9} "
              f"{r['sound_category']:<13} {r['duration_s']:>6.1f}s  q={r['quality_score'] if r['quality_score'] is not None else '-':<5} "
              f"lic={r['license']:<10} commercial={r['commercial_ok']:<4} {r['asset_name']}")

# ---------------- quality check ----------------
def analyse(path):
    x, sr = load_mono(path, probe(path)[1])
    allc = load_all(path)
    peak = float(np.max(np.abs(allc))) if len(allc) else 0
    rms = float(np.sqrt(np.mean(x ** 2))) if len(x) else 0
    db = lambda v: 20 * np.log10(max(v, 1e-9))
    clipped = int(np.sum(np.abs(allc) >= 0.999))
    fr = int(0.05 * sr); env = np.array([np.sqrt(np.mean(x[i:i + fr] ** 2)) for i in range(0, max(1, len(x) - fr), fr)])
    thr = 10 ** (-50 / 20)
    loud = np.where(env > thr)[0]
    lead = loud[0] * 0.05 if len(loud) else len(x) / sr
    trail = (len(env) - 1 - loud[-1]) * 0.05 if len(loud) else len(x) / sr
    quiet = env[env < 10 ** (-40 / 20)]
    noise = db(float(np.median(quiet))) if len(quiet) > 5 else None   # only measurable where the file has quiet parts
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", r); LRA = re.findall(r"LRA:\s+([\d.]+) LU", r)
    lufs = float(I[-1]) if I else None; lra = float(LRA[-1]) if LRA else None
    issues, score = [], 10.0
    if clipped: issues.append(f"{clipped} clipped samples"); score -= min(4, clipped / 200)
    if db(peak) > -0.3: issues.append("peak above -0.3 dBFS"); score -= 1
    if lufs is not None and lufs < -30: issues.append("very quiet"); score -= 2
    if lead > 0.5: issues.append(f"{lead:.1f}s leading silence"); score -= 0.5
    if trail > 0.5: issues.append(f"{trail:.1f}s trailing silence"); score -= 0.5
    if noise is not None and noise > -55: issues.append("audible noise in quiet parts"); score -= 2
    return dict(peak_dbfs=round(db(peak), 2), rms_dbfs=round(db(rms), 2), integrated_lufs=lufs, loudness_range_lu=lra,
                clipped_samples=clipped, leading_silence_s=round(lead, 2), trailing_silence_s=round(trail, 2),
                noise_floor_dbfs=None if noise is None else round(noise, 1), score=round(max(score, 0), 1), issues="; ".join(issues) or "ok")

def cmd_qc(a):
    c = con()
    rows = c.execute("SELECT id,file_path FROM audio_assets" + ("" if a.asset == "all" else " WHERE id=?"),
                     () if a.asset == "all" else (a.asset,)).fetchall()
    os.makedirs(os.path.join(LIB, "QUALITY_REPORTS"), exist_ok=True)
    for r in rows:
        rep = analyse(os.path.join(LIB, r["file_path"]))
        c.execute("""INSERT INTO quality_reports(asset_id,checked,peak_dbfs,rms_dbfs,integrated_lufs,loudness_range_lu,clipped_samples,
                     leading_silence_s,trailing_silence_s,noise_floor_dbfs,score,issues) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (r["id"], NOW(), *[rep[k] for k in ["peak_dbfs", "rms_dbfs", "integrated_lufs", "loudness_range_lu", "clipped_samples",
                                                       "leading_silence_s", "trailing_silence_s", "noise_floor_dbfs", "score", "issues"]]))
        c.execute("UPDATE audio_assets SET quality_score=? WHERE id=?", (rep["score"], r["id"]))
        json.dump(rep, open(os.path.join(LIB, "QUALITY_REPORTS", r["id"] + ".json"), "w"), indent=2)
        print(f"{r['id']:<16} score {rep['score']:>4}  peak {rep['peak_dbfs']:>6} dBFS  {rep['integrated_lufs']} LUFS  {rep['issues']}")
    c.commit()

# ---------------- duplicates ----------------
def cmd_dedupe(a):
    c = con(); rows = c.execute("SELECT id,file_path,sha256 FROM audio_assets").fetchall()
    seen = {}
    for r in rows:
        if r["sha256"] in seen: print(f"EXACT DUPLICATE: {r['id']} == {seen[r['sha256']]}")
        seen.setdefault(r["sha256"], r["id"])
    sigs = {}
    for r in rows:
        x, sr = load_mono(os.path.join(LIB, r["file_path"]), 8000)
        env = np.array([np.sqrt(np.mean(x[i:i + 400] ** 2)) for i in range(0, len(x) - 400, 400)])
        if len(env) > 5: sigs[r["id"]] = (env - env.mean()) / (env.std() + 1e-9)
    ids = list(sigs)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            A, B = sigs[ids[i]], sigs[ids[j]]; n = min(len(A), len(B))
            if n < 20: continue
            corr = float(np.max(np.correlate(A[:n], B[:n], "full")) / n)
            if corr > 0.95: print(f"NEAR DUPLICATE ({corr:.2f}): {ids[i]} ~ {ids[j]}")
    print("dedupe done")

# ---------------- processing (non-destructive) ----------------
def cmd_process(a):
    c = con(); r = c.execute("SELECT * FROM audio_assets WHERE id=?", (a.asset,)).fetchone()
    if not r: sys.exit("no such asset")
    src = os.path.join(LIB, r["file_path"]); outdir = os.path.join(LIB, "PROCESSED"); os.makedirs(outdir, exist_ok=True)
    filters = []
    if a.trim: filters.append("silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse")
    filters.append(f"loudnorm=I={a.lufs}:TP=-1.0:LRA=11")
    dur = probe(src)[0]
    if a.fade: filters.append(f"afade=t=in:d={a.fade},afade=t=out:st={max(0, dur - a.fade)}:d={a.fade}")
    out = os.path.join(outdir, f"{r['id']}_norm{abs(int(a.lufs))}.wav")
    if os.path.exists(out): sys.exit("refusing to overwrite " + out)
    subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-af", ",".join(filters), "-ar", "48000", out], check=True)
    print("processed ->", os.path.relpath(out, ROOT))
    if a.segment:
        pat = os.path.join(outdir, f"{r['id']}_seg%03d.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-i", out, "-f", "segment", "-segment_time", str(a.segment), "-c", "copy", pat], check=True)
        print("segments ->", os.path.relpath(outdir, ROOT))

def cmd_preview(a):
    c = con(); r = c.execute("SELECT * FROM audio_assets WHERE id=?", (a.asset,)).fetchone()
    out = os.path.join(LIB, "PREVIEWS", r["id"] + ".mp3"); os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(LIB, r["file_path"]), "-b:a", "128k", out], check=True)
    print("preview ->", os.path.relpath(out, ROOT))

# ---------------- license register ----------------
def cmd_licenses(a):
    c = con(); rows = c.execute("SELECT id,classification,asset_name,manufacturer,model,source_url,creator,license,attribution_text,"
                                "commercial_ok,modification_ok,verification_status FROM audio_assets ORDER BY id").fetchall()
    out = os.path.join(LIB, "LICENSES", "license_register.csv"); os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(rows[0].keys() if rows else ["id"])
        for r in rows: w.writerow(list(r))
    print("license register ->", os.path.relpath(out, ROOT), f"({len(rows)} assets)")

# ---------------- pick for video ----------------
def cmd_pick(a):
    c = con(); q = "SELECT * FROM publishable_assets WHERE engine_configuration=? AND sound_category=?"; args = [a.config, a.category]
    if a.cls: q += " AND classification=?"; args.append(a.cls)
    r = c.execute(q + " ORDER BY classification='REAL' DESC, quality_score DESC LIMIT 1", args).fetchone()
    if not r: sys.exit("nothing publishable matches (REAL sounds are never silently replaced by CUSTOM: ask with --class CUSTOM)")
    print(json.dumps(dict(r), indent=2))

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("init")
    ad = s.add_parser("add"); ad.add_argument("file"); ad.add_argument("--class", dest="cls", required=True, choices=["REAL", "CUSTOM"])
    for k in ["manufacturer", "model", "year", "engine-code", "source-url", "creator", "license", "attribution", "download-date", "notes", "project-json"]:
        ad.add_argument("--" + k)
    ad.add_argument("--config", required=True); ad.add_argument("--category", required=True); ad.add_argument("--name", required=True)
    ad.add_argument("--verified", action="store_true", help="only after source, vehicle identity and license were checked by a person")
    se = s.add_parser("search"); se.add_argument("query")
    q = s.add_parser("qc"); q.add_argument("asset", nargs="?", default="all")
    s.add_parser("dedupe")
    pr = s.add_parser("process"); pr.add_argument("asset"); pr.add_argument("--lufs", type=float, default=-16)
    pr.add_argument("--trim", action="store_true"); pr.add_argument("--fade", type=float, default=0.05); pr.add_argument("--segment", type=float)
    pv = s.add_parser("preview"); pv.add_argument("asset")
    s.add_parser("licenses")
    pk = s.add_parser("pick"); pk.add_argument("--config", required=True); pk.add_argument("--category", required=True); pk.add_argument("--class", dest="cls")
    a = p.parse_args()
    {"init": cmd_init, "add": cmd_add, "search": cmd_search, "qc": cmd_qc, "dedupe": cmd_dedupe, "process": cmd_process,
     "preview": cmd_preview, "licenses": cmd_licenses, "pick": cmd_pick}[a.cmd](a)

if __name__ == "__main__":
    main()
