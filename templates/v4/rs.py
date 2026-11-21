def render_scene(i, fn, dur):
    final = f"{OUT}/scene{i}.mp4"
    tmp = f"{OUT}/scene{i}.tmp.mp4"
    n = int(round(dur * FPS))
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18",
                          "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for f in range(n):
        p.stdin.write(fn(f / FPS).convert("RGB").tobytes())
    p.stdin.close()
    if p.wait() == 0:
        os.replace(tmp, final)

