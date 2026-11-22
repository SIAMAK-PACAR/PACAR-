-- ENGINE DNA audio library schema (SQLite). Portable: plain SQL, no extensions.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS manufacturers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,            -- e.g. 'BMW', 'Mercedes-Benz', 'Mercedes-AMG'
  folder TEXT NOT NULL,                 -- folder under AUDIO_LIBRARY/REAL
  country TEXT
);

CREATE TABLE IF NOT EXISTS engine_specs (
  id INTEGER PRIMARY KEY,
  engine_code TEXT,                     -- e.g. 'S58' (only if verified)
  configuration TEXT NOT NULL,          -- V8, V10, V12, INLINE_4, INLINE_6, V6, BOXER, ROTARY, HYBRID, ELECTRIC ...
  displacement_cc INTEGER,
  aspiration TEXT,                      -- NA, TURBO, TWIN_TURBO, SUPERCHARGED, ELECTRIC, HYBRID
  crankshaft TEXT,                      -- cross-plane, flat-plane, even-fire ... (only if verified)
  firing_order TEXT,
  rpm_idle INTEGER, rpm_redline INTEGER,
  verified INTEGER NOT NULL DEFAULT 0,  -- 1 only when every field above has a cited source
  spec_source TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS vehicle_models (
  id INTEGER PRIMARY KEY,
  manufacturer_id INTEGER NOT NULL REFERENCES manufacturers(id),
  model TEXT NOT NULL,
  model_year TEXT,
  segment TEXT,                         -- ordinary, sports, supercar, hypercar, classic, performance, hybrid, ev
  engine_spec_id INTEGER REFERENCES engine_specs(id)
);

CREATE TABLE IF NOT EXISTS licenses (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,            -- CC0, CC-BY-4.0, CC-BY-NC-4.0, CC-BY-ND-4.0, ORIGINAL, UNKNOWN ...
  url TEXT,
  commercial_ok INTEGER NOT NULL,       -- 1 yes, 0 no
  modification_ok INTEGER NOT NULL,
  attribution_required INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS audio_sources (
  id INTEGER PRIMARY KEY,
  source_url TEXT,
  creator TEXT,
  license_id INTEGER NOT NULL REFERENCES licenses(id),
  attribution_text TEXT,
  download_date TEXT,
  original_file TEXT,                   -- path under ORIGINALS (never modified)
  notes TEXT
);

CREATE TABLE IF NOT EXISTS recording_sessions (
  id INTEGER PRIMARY KEY,
  source_id INTEGER REFERENCES audio_sources(id),
  location TEXT, date TEXT, microphone TEXT, conditions TEXT, notes TEXT
);

CREATE TABLE IF NOT EXISTS custom_sound_projects (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  generator TEXT NOT NULL,              -- script + version used
  parameters_json TEXT NOT NULL,        -- full parameters so the sound can be regenerated
  created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audio_assets (
  id TEXT PRIMARY KEY,                  -- unique id, e.g. CUS-V8-0001 / REA-BMW-0001
  asset_name TEXT NOT NULL,
  classification TEXT NOT NULL CHECK (classification IN ('REAL','CUSTOM')),
  manufacturer TEXT,                    -- NULL for CUSTOM generic sounds
  model TEXT,
  model_year TEXT,
  engine_code TEXT,
  engine_configuration TEXT NOT NULL,
  sound_category TEXT NOT NULL CHECK (sound_category IN (
    'COLD_START','WARM_START','IDLE','LOW_RPM','MID_RPM','HIGH_RPM','REVVING','ACCELERATION',
    'DECELERATION','GEAR_SHIFT','EXHAUST','INTAKE','TURBO_SPOOL','SUPERCHARGER_WHINE','FLYBY',
    'LAUNCH','HYBRID_START_STOP','EV_ACCELERATION')),
  file_path TEXT NOT NULL UNIQUE,
  file_format TEXT, duration_s REAL, sample_rate INTEGER, channels INTEGER,
  sha256 TEXT,
  source_id INTEGER REFERENCES audio_sources(id),
  custom_project_id INTEGER REFERENCES custom_sound_projects(id),
  source_url TEXT, creator TEXT, license TEXT, attribution_text TEXT,
  commercial_ok TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (commercial_ok IN ('YES','NO','UNKNOWN')),
  modification_ok TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (modification_ok IN ('YES','NO','UNKNOWN')),
  verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
    CHECK (verification_status IN ('VERIFIED','UNVERIFIED','QUARANTINED','SYNTHETIC')),
  quality_score REAL,
  notes TEXT,
  added TEXT NOT NULL,
  -- a REAL asset must have a source; a CUSTOM asset must be SYNTHETIC
  CHECK (classification <> 'CUSTOM' OR verification_status = 'SYNTHETIC'),
  CHECK (classification <> 'REAL' OR verification_status <> 'SYNTHETIC')
);

CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS asset_tags (
  asset_id TEXT REFERENCES audio_assets(id), tag_id INTEGER REFERENCES tags(id),
  PRIMARY KEY (asset_id, tag_id));

CREATE TABLE IF NOT EXISTS quality_reports (
  id INTEGER PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES audio_assets(id),
  checked TEXT NOT NULL,
  peak_dbfs REAL, rms_dbfs REAL, integrated_lufs REAL, loudness_range_lu REAL,
  clipped_samples INTEGER, leading_silence_s REAL, trailing_silence_s REAL,
  noise_floor_dbfs REAL, score REAL, issues TEXT
);

CREATE TABLE IF NOT EXISTS video_usage (
  id INTEGER PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES audio_assets(id),
  episode TEXT NOT NULL, platform TEXT, used_on TEXT, attribution_shown INTEGER, notes TEXT
);

-- Never return unverified REAL recordings as verified: views make the rule explicit.
CREATE VIEW IF NOT EXISTS publishable_assets AS
  SELECT * FROM audio_assets
  WHERE verification_status IN ('VERIFIED','SYNTHETIC') AND commercial_ok = 'YES';
