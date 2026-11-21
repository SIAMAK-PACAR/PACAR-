
if __name__ == "__main__":
    if sys.argv[1] == "stills":
        shots = [(i, tt) for i, tt in enumerate(STILL_T)] + EXTRA_STILLS
        for k, (i, tt) in enumerate(shots):
            SCENES[i][0](tt).convert("RGB").save(f"{OUT}/still{k}.jpg", quality=85)
    else:
        for i in [int(x) for x in sys.argv[1:]]:
            fn, dur = SCENES[i]
            render_scene(i, fn, dur)
