#!/usr/bin/env python3
"""Rescale presets.json from the original 1196-LED strip to YOUR LED count.

    py adjust_led_count.py 600                 -> writes presets_600.json  (restore that one into WLED)
    py adjust_led_count.py 600 presets.json out.json

Only the segment lengths change (every look spans the whole strip; the 3-LED white sparkle overlay
segments are re-fitted to the new end). Colours, effects, speeds and playlists are untouched.
"""
import json
import sys

OLD = 1196
if len(sys.argv) < 2 or not sys.argv[1].isdigit() or int(sys.argv[1]) < 10:
    sys.exit("usage: py adjust_led_count.py <your total LED count> [in.json] [out.json]")
n = int(sys.argv[1])
src = sys.argv[2] if len(sys.argv) > 2 else "presets.json"
dst = sys.argv[3] if len(sys.argv) > 3 else f"presets_{n}.json"
fix = {OLD: n, OLD - 1: n - 1, OLD - 2: n - 2}
data = json.load(open(src, encoding="utf-8"))
changed = 0
for p in data.values():
    for s in p.get("seg", []):
        if s.get("stop") in fix:
            s["stop"] = fix[s["stop"]]
            changed += 1
json.dump(data, open(dst, "w", encoding="utf-8"), separators=(",", ":"))
print(f"Rewrote {changed} segments for {n} LEDs -> {dst}")
