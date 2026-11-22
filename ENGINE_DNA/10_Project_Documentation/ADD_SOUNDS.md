# How to add engine sounds

All commands run from `ENGINE_DNA/09_Scripts/`. Tools: Python 3 (numpy, scipy), ffmpeg. All free.

## 1. First time only
```
python3 edna_audio.py init
```

## 2. Adding a REAL recording
1. Find the candidate (e.g. Freesound). Before downloading, write down: page URL, creator, license, and what the page says about the vehicle.
2. Check the license of that single file: CC0 or CC BY are fine for commercial videos; CC BY-NC is not; ND means you may not edit it.
3. Get approval, then download the file (only that file).
4. Add it:
```
python3 edna_audio.py add file.wav --class REAL --manufacturer "BMW" --model "M3" --year 2021 --engine-code S58 \
  --config INLINE_6 --category COLD_START --name "BMW M3 cold start" \
  --source-url "https://..." --creator "name" --license CC-BY-4.0 --attribution "Sound by name (CC BY 4.0)"
```
The tool keeps an untouched copy in `ORIGINALS/` and stores the asset as `UNVERIFIED`.
Only when you have checked that the recording really is that vehicle, add `--verified` (or update the row).
Engine codes, displacement etc. go in only if a source confirms them.

## 3. Adding a CUSTOM (synthetic) sound
```
python3 synth_engine.py --config V12 --profile rev --dur 6 --out v12_rev.wav --json v12_rev.json
python3 edna_audio.py add v12_rev.wav --class CUSTOM --config V12 --category REVVING --name "V12 rev synthetic" --project-json v12_rev.json
```
Configs: INLINE_4, INLINE_6, V8_CROSSPLANE, V8_FLATPLANE, V10, V12, BOXER_4. Profiles: idle, rev, high, accel, startup.
The parameters are saved, so any sound can be regenerated exactly.

## 4. Check, clean, find
```
python3 edna_audio.py qc all            # peak, loudness (LUFS), clipping, silence, noise -> QUALITY_REPORTS/
python3 edna_audio.py dedupe            # exact and near duplicates
python3 edna_audio.py process CUS-V12-0002 --lufs -16 --trim --fade 0.05     # non-destructive
python3 edna_audio.py preview CUS-V12-0002
python3 edna_audio.py search "V12 high rpm custom"
python3 edna_audio.py licenses          # LICENSES/license_register.csv
```

## 5. Picking sounds for a video
```
python3 edna_audio.py pick --config V8 --category ACCELERATION              # prefers REAL, never swaps silently
python3 edna_audio.py pick --config V8 --category ACCELERATION --class CUSTOM
```
For comparison videos, process every chosen clip to the same loudness (`--lufs -16`) so they are fair to compare.

## Honesty rules for videos
- Synthetic sounds are shown as "CUSTOM / SYNTHETIC SOUND" and never with a brand or model name.
- Never claim every V8/V10/V12 sounds the same: sound also depends on crankshaft, firing order, RPM, intake, exhaust and turbocharging.
