"""Self-check for the offline parts of clippa: python test_clippa.py (needs ffmpeg; no keys, no network)."""
import subprocess
import tempfile
from pathlib import Path

import clippa
import dashboard

# peaks: highest first, never two inside one moment
heat = [{"start_time": t, "end_time": t + 10, "value": v} for t, v in [(0, .1), (100, 1), (110, .9), (500, .8)]]
assert [round(p) for p, _ in clippa.peaks(heat)] == [105, 505]

# rank: hottest niche first, by Twitch category or by name in the YouTube title; unknown niche last
niches = [{"id": "1", "name": "Minecraft"}, {"id": "2", "name": "Chess"}]
moments = [{"title": "random", "views": 9e9}, {"title": "x", "game_id": "2", "views": 5},
           {"title": "MINECRAFT hardcore", "views": 1}]
assert [m.get("niche") for m in clippa.rank(moments, niches)] == ["1", "2", None]

# seen_before: same stream within 90 s counts as the same moment
seen = [{"url": "a", "start": 100}]
assert clippa.seen_before({"url": "a", "start": 150}, seen)
assert not clippa.seen_before({"url": "a", "start": 300}, seen)
assert not clippa.seen_before({"url": "b", "start": 100}, seen)

# clamp: model boundaries forced into the file and into 15-60 s
assert clippa.clamp(-5, 200, 120) == (0, 60)
assert clippa.clamp(110, 112, 120) == (105, 120)
assert clippa.clamp(10, 12, 120) == (10, 25)

# captions: words inside the clip only, timed from the clip start, braces escaped
words = [{"word": w, "start": s, "end": s + .4} for w, s in [("skip", 1), ("no", 5), ("{way}", 5.5), ("bro", 6)]]
ass = clippa.captions(words, 4, 10)
assert "SKIP" not in ass and "Dialogue: 0,0:00:01.00,0:00:02.90,Default,,0,0,0,,NO (WAY) BRO" in ass

# render: a real 9:16 file comes out of a 16:9 source
with tempfile.TemporaryDirectory() as tmp:
    work = Path(tmp)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                    "-f", "lavfi", "-i", "sine", "-t", "12", work / "src.mp4"], check=True)
    clippa.render(work / "src.mp4", 4, 10, words, work, work / "out.mp4")
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", work / "out.mp4"], capture_output=True, text=True).stdout.strip()
    assert probe == "1080,1920", probe
    assert 5.9 < clippa.duration(work / "out.mp4") < 6.2

# dashboard: titles are escaped, only https links become buttons, empty data still renders
page = dashboard.build({"date": "d", "niches": [{"name": "A<b>", "views": 5, "top": [{"title": "t", "views": 5}]}]},
                       [{"keep": True, "title": "<script>x</script>", "date": "d", "youtube": 'javascript:"'}])
assert "<script>x" not in page and "A&lt;b&gt;" in page and "javascript" not in page.split("<tr>", 2)[-1].split("href")[0]
assert "No scan yet" in dashboard.build({}, [])

# top_channels: summed across niches, most viewed first
scanned = [{"top": [{"channel_id": "a", "views": 5}, {"channel_id": "b", "views": 7}]},
           {"top": [{"channel_id": "a", "views": 4}, {"channel_id": "c", "views": 1}]}]
assert clippa.top_channels(scanned, n=2) == ["a", "b"]

# free_pick: no Claude key keeps the marked moment, source title and a niche hashtag
fp = clippa.free_pick({"start": 100, "end": 120, "title": "wow"}, {"name": "Grand Theft Auto V"}, 30)
assert fp == {"keep": True, "start": 30, "end": 50, "title": "wow", "description": "", "hashtags": ["GrandTheftAutoV", "shorts"]}

print("ok")
