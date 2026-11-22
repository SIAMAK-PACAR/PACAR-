# ENGINE DNA

Zero-budget (0 SEK/month) production system for cinematic engine-explainer Shorts (YouTube Shorts, TikTok, Reels), 1080x1920, 30 fps, ~30 s.

## Status (2026-11-22)

| Part | Status |
|---|---|
| Folder structure (video + audio library) | Done |
| SQLite audio database + schema | Done: `AUDIO_LIBRARY/METADATA/engine_dna_audio.sqlite`, `09_Scripts/schema.sql` |
| Audio tool: add / search / quality check / duplicates / processing / previews / license register / pick-for-video | Done: `09_Scripts/edna_audio.py` |
| Procedural engine-sound generator (CUSTOM / SYNTHETIC) | Done: `09_Scripts/synth_engine.py` |
| First CUSTOM collection: V8 (cross-plane), V10, V12: idle, revving, high RPM, warm start | Done: 12 assets, all quality-checked |
| REAL recordings | None yet. The work environment cannot reach Freesound or other sound sites; nothing has been downloaded. |
| Blender 3D engines | Not started: needs approval to install `bpy` (Blender as a Python module, free, ~300 MB). |
| Episode 01 video (V8 vs V10 vs V12) | Not started (needs the 3D stage). |

## Folders

```
01_Engine_Models/  02_Blender_Projects/  03_Engine_Sounds/  04_Animations/  05_Video_Editing/
06_Thumbnails/     07_YouTube_Exports/   08_Licenses/       09_Scripts/      10_Project_Documentation/
AUDIO_LIBRARY/
  REAL/<BRAND>/      authentic recordings only (source + license required)
  CUSTOM/<CONFIG>/   procedural sounds, always labelled CUSTOM / SYNTHETIC
  ORIGINALS/         untouched copies of every downloaded file (never modified)
  PROCESSED/         normalised / trimmed / segmented copies
  PREVIEWS/          mp3 previews
  METADATA/          SQLite database, metadata template
  LICENSES/          license_register.csv
  QUALITY_REPORTS/   one JSON report per asset
```

## Rules built into the system

- `CUSTOM` assets are forced to `SYNTHETIC` status by the database; a `REAL` asset can never be `SYNTHETIC`.
- A `REAL` asset with unknown license or no source URL is stored as `QUARANTINED`.
- `REAL` assets become `VERIFIED` only with `--verified`, after a person has checked source, vehicle identity and license.
- The view `publishable_assets` only contains `VERIFIED`/`SYNTHETIC` assets with commercial use allowed (so CC BY-NC and unknown licenses are excluded).
- `pick` never silently swaps a missing REAL sound for a CUSTOM one: you must ask for `--class CUSTOM`.
- Processing never overwrites: originals stay in `ORIGINALS/`, results go to `PROCESSED/` with new names.

See `10_Project_Documentation/ADD_SOUNDS.md` for day-to-day use.
