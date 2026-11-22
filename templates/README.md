PACAR motion-graphic Short templates (1080x1920, 30 fps, ~33 s, Python + PIL + numpy + ffmpeg).
v1 spark plugs (render.py + audio.py: `python3 render.py stills`, `python3 render.py 0 1 2 ...` renders scenes, then concat + music.wav)
v2 turbo, v3 engine oil, v4 real vs fake carbon, v5 PPF vs ceramic.
Copy one folder, change the scene functions/texts/sprites for the new topic, render stills, check them, render scenes (2-3 at a time), concat, add music.
Fonts: /usr/share/fonts/opentype/inter/ (Inter-*.otf); fall back to DejaVu Sans if missing.

engine_lab/engine4.py: physics-based inline-4 explainer (slider-crank kinematics, firing order 1-3-4-2, slow-mo -> real speed -> floor it,
tachometer, captions) with synced synthesized sound. `python3 engine4.py stills` then `python3 engine4.py render`.
Adapt the cylinder layout (V / boxer / inline-6 ...) and firing order per engine; ENGINE_DNA/09_Scripts/synth_engine.py has firing orders.
