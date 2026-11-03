# Render tools (all local, no watermark)
- make_series.py  : "Seen Just Now" chat reels (spec json -> mp4). Current renderer. Usage: python3 make_series.py specs-series/ep3.json out.mp4
- make_dm.py      : first-generation chat reels (no episode badge)
- make_reel.py    : Dream Note poem reels (styles W/D)
Needs: python3, numpy, Pillow, ffmpeg; fonts Inter (opentype/inter) and Latin Modern Roman (texmf lm). Script font paths are at the top of each file.
Spec fields (series): name (chat header), couple, ep, stamp, msgs [["R"|"S", text]...] (R = other person, S = you; end on S), closer, follow.
