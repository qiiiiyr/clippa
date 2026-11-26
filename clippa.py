"""Clippa: scan which clip niches get the most views, then cut, edit and upload new clips from Twitch and YouTube streams.

    python clippa.py          # DRY_RUN is on unless DRY_RUN=false: renders to out/ and uploads nothing

Steps: 1. scan this week's top clips of the biggest Twitch categories and rank the niches by views,
2. find highlight moments in the streams of the channels in sources.json (Twitch clips viewers made, YouTube
"most replayed" peaks), hottest niche first, 3. cut each moment, transcribe it, let Claude pick the exact clip and
write the title using the niche's top clips as inspiration, render a captioned 9:16 video, 4. upload to YouTube Shorts.
"""
import functools
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
import requests
import yt_dlp

import dashboard

ROOT = Path(__file__).resolve().parent
DATA, OUT = ROOT / "data", ROOT / "out"
env = os.environ.get
DRY_RUN = env("DRY_RUN", "true").lower() != "false"
PRIVACY = env("PRIVACY") or "public"
CLIPS_PER_RUN = int(env("CLIPS_PER_RUN") or 3)
MIN_S, MAX_S = int(env("CLIP_MIN_SECONDS") or 15), int(env("CLIP_MAX_SECONDS") or 60)
NICHES, PAD = 20, 30  # categories scanned (top 100 clips each), seconds kept around a moment
WEEK_AGO = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")


def ok(r):
    """Raise with the response body, but never the query string (it can hold access tokens)."""
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.url.split('?')[0]}: {r.text[:500]}")
    return r


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save(path, data):
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


# ---------- sources ----------

def ydl(**opts):
    """yt-dlp using Node (preinstalled on GitHub runners) for YouTube's JS checks, plus the optional YTDLP_COOKIES
    secret (a cookies.txt export) for when YouTube asks the runner to sign in."""
    if env("YTDLP_COOKIES"):
        cookies = Path(tempfile.gettempdir()) / "clippa-cookies.txt"  # outside the repo so it is never committed
        cookies.write_text(env("YTDLP_COOKIES"))
        opts["cookiefile"] = str(cookies)
    return yt_dlp.YoutubeDL({"quiet": True, "js_runtimes": {"node": {}, "deno": {}}, **opts})


def twitch():
    """GET helper for the Twitch Helix API with an app token."""
    cid = env("TWITCH_CLIENT_ID")
    tok = ok(requests.post("https://id.twitch.tv/oauth2/token", timeout=30, params={
        "client_id": cid, "client_secret": env("TWITCH_CLIENT_SECRET"), "grant_type": "client_credentials"})).json()
    headers = {"Client-Id": cid, "Authorization": "Bearer " + tok["access_token"]}
    return lambda path, **p: ok(requests.get("https://api.twitch.tv/helix/" + path, headers=headers, params=p,
                                             timeout=30)).json()


def youtube_token():
    return ok(requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": env("YT_CLIENT_ID"), "client_secret": env("YT_CLIENT_SECRET"),
        "refresh_token": env("YT_REFRESH_TOKEN"), "grant_type": "refresh_token"})).json()["access_token"]


# ---------- 1. scan ----------

def scan(tw):
    """Rank the biggest Twitch categories (niches) by the total views of their top 100 clips this week."""
    niches = []
    for g in tw("games/top", first=NICHES)["data"]:
        clips = [{"title": c["title"], "views": c["view_count"], "channel": c["broadcaster_name"],
                  "channel_id": c["broadcaster_id"]}
                 for c in tw("clips", game_id=g["id"], started_at=WEEK_AGO, first=100)["data"]]
        niches.append({"id": g["id"], "name": g["name"], "clips_scanned": len(clips),
                       "views": sum(c["views"] for c in clips),
                       "top": sorted(clips, key=lambda c: -c["views"])[:10]})
        print(f"scanned {g['name']}: {len(clips)} clips, {niches[-1]['views']:,} views")
    return sorted(niches, key=lambda n: -n["views"])


# ---------- 2. find moments ----------

def top_channels(niches, n=3):
    """Ids of the channels whose clips got the most views across all scanned niches."""
    views = {}
    for niche in niches:
        for c in niche["top"]:
            views[c["channel_id"]] = views.get(c["channel_id"], 0) + c["views"]
    return sorted(views, key=lambda i: -views[i])[:n]


def twitch_moments(tw, users):
    """Highlights viewers clipped this week on these channels, located in the stream VOD when it exists."""
    moments = []
    for u in users:
        for c in tw("clips", broadcaster_id=u["id"], started_at=WEEK_AGO, first=20)["data"]:
            vod = c["video_id"] and c["vod_offset"] is not None
            start = c["vod_offset"] if vod else 0
            moments.append({"url": f"https://www.twitch.tv/videos/{c['video_id']}" if vod else c["url"],
                            "start": start, "end": start + c["duration"], "game_id": c["game_id"],
                            "views": c["view_count"], "channel": c["broadcaster_name"], "title": c["title"]})
    return moments


def peaks(heatmap, n=2, half=45):
    """Centres and values of the n most replayed heatmap segments that are at least a moment apart."""
    picked = []
    for seg in sorted(heatmap, key=lambda s: -s["value"]):
        mid = (seg["start_time"] + seg["end_time"]) / 2
        if all(abs(mid - p) > 2 * half for p, _ in picked):
            picked.append((mid, seg["value"]))
        if len(picked) == n:
            break
    return picked


def youtube_moments(handles, half=45):
    """The most replayed parts of the last 3 finished live streams and last 3 videos of the allowed YouTube channels."""
    moments = []
    # ignoreerrors: a blocked, upcoming or members-only video comes back as None and only that video is skipped
    with ydl(extract_flat=True, playlistend=3, ignoreerrors=True) as flat, ydl(ignoreerrors=True) as full:
        for h, kind in ((h, kind) for h in handles for kind in ("streams", "videos")):
            tab = flat.extract_info(f"https://www.youtube.com/{h}/{kind}", download=False) or {}
            for e in tab.get("entries") or []:
                info = e and full.extract_info(e["url"], download=False)
                if not info or info.get("live_status") not in ("was_live", "not_live"):  # skip live and upcoming
                    continue
                for mid, value in peaks(info.get("heatmap") or [], half=half):
                    moments.append({"url": info["webpage_url"], "start": max(0, mid - half), "end": mid + half,
                                    "views": int(value * (info.get("view_count") or 0)), "channel": info["channel"],
                                    "title": info["title"], "tags": info.get("tags") or []})
    return moments


def rank(moments, niches):
    """Tag each moment with its niche and order: most viewed niche first, then the moment's own views."""
    order = {n["id"]: i for i, n in enumerate(niches)}
    for m in moments:
        text = " ".join([m["title"], *m.get("tags", [])])
        m["niche"] = m.get("game_id") if m.get("game_id") in order else next(
            (n["id"] for n in niches if re.search(rf"\b{re.escape(n['name'])}\b", text, re.I)), None)
    return sorted(moments, key=lambda m: (order.get(m["niche"], len(order)), -m["views"]))


# titles that get Shorts age-restricted, limited or struck; matched as whole words, any case
BLOCKED = re.compile(r"\b(nudes?|naked|nsfw|porn\w*|sex\w*|horny|boobs?|tits|titties|dick|pussy|onlyfans|rape|kys|"
                     r"fuck\w*|(bull)?shit(s|ty)?|bitch\w*|n[i1]gg\w*|f[a4]gg?\w*|retard\w*)\b", re.I)


def blocked(m):
    """True when the moment's title, or the title written for it, has a word that should never be posted."""
    return bool(BLOCKED.search(m["title"]))


def seen_before(m, seen):
    """True when the same part of the same stream was already clipped (viewers often clip one moment many times)."""
    return any(s["url"] == m["url"] and abs(s["start"] - m["start"]) < 90 for s in seen)


# ---------- 3. clip and edit ----------

def download(m, work):
    s = max(0, m["start"] - PAD)
    # a deleted or subscriber-only video stalled for 8 minutes in a real run: give up after 30 s without data
    # (ffmpeg does the section download and takes its own timeout, in microseconds)
    with ydl(format="bv*[height<=1080]+ba/b", merge_output_format="mp4", outtmpl=str(work / "src.%(ext)s"),
             socket_timeout=30, external_downloader_args={"ffmpeg_i": ["-rw_timeout", "30000000"]},
             download_ranges=yt_dlp.utils.download_range_func(None, [(s, m["end"] + PAD)])) as y:
        y.download([m["url"]])
    return next(work.glob("src.*")), m["start"] - s


def duration(path):
    """Length in seconds, or 0.0 when the file does not say (ffprobe prints N/A for some Twitch downloads)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out) if out not in ("", "N/A") else 0.0


@functools.cache
def whisper():
    from faster_whisper import WhisperModel
    return WhisperModel("base", compute_type="int8")


def transcribe_local(src):
    """Free captions: open-source Whisper on the runner's CPU, used when there is no OPENAI_API_KEY."""
    segments, _ = whisper().transcribe(str(src), word_timestamps=True)
    return [{"word": w.word, "start": w.start, "end": w.end} for seg in segments for w in seg.words]


def transcribe(src, work):
    if not env("OPENAI_API_KEY"):
        return transcribe_local(src)
    mp3 = work / "audio.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k",
                    mp3], check=True)
    with open(mp3, "rb") as f:
        r = ok(requests.post("https://api.openai.com/v1/audio/transcriptions", timeout=300, files={"file": f},
                             headers={"Authorization": "Bearer " + env("OPENAI_API_KEY", "")},
                             data={"model": env("WHISPER_MODEL") or "whisper-1", "response_format": "verbose_json",
                                   "timestamp_granularities[]": "word"}))
    return r.json().get("words") or []


PICK_SCHEMA = {"type": "object", "additionalProperties": False,
               "required": ["keep", "start", "end", "title", "description", "hashtags"],
               "properties": {"keep": {"type": "boolean"}, "start": {"type": "number"}, "end": {"type": "number"},
                              "title": {"type": "string"}, "description": {"type": "string"},
                              "hashtags": {"type": "array", "items": {"type": "string"}}}}


def free_pick(m, niche, marked_at):
    """No Claude key: keep the moment viewers marked, the source's own title, and the niche as hashtag."""
    tag = "".join(c for c in (niche or {}).get("name", "") if c.isalnum())
    return {"keep": True, "start": marked_at, "end": marked_at + m["end"] - m["start"], "title": m["title"],
            "description": "", "hashtags": [t for t in (tag, "shorts") if t]}


def pick(m, niche, words, marked_at, length):
    """Claude chooses the clip boundaries and writes the post, inspired by the niche's most viewed clips."""
    if not env("ANTHROPIC_API_KEY"):
        return free_pick(m, niche, marked_at)
    inspo = "\n".join(f'- "{c["title"]}" ({c["views"]:,} views)' for c in (niche or {}).get("top", []))
    prompt = f"""You cut short vertical clips (YouTube Shorts) from livestreams.
Stream: "{m['title']}" by {m['channel']}. This excerpt is {length:.0f} s long; viewers marked a highlight at about \
{marked_at:.0f}-{marked_at + m['end'] - m['start']:.0f} s.
Niche: {(niche or {}).get('name', 'unknown')}. The most viewed clips in this niche this week, as inspiration for which \
moments and titles work:
{inspo or '- none found'}

Transcript, each word after its start time in seconds:
{' '.join(f"[{w['start']:.1f}]{w['word']}" for w in words) or '(no speech)'}

Pick one {MIN_S}-{MAX_S} second clip that opens on a hook within the first 2 seconds, ends right after the payoff, and \
makes sense with no context. If there is no speech, keep the marked highlight. Write a short, punchy title in the style \
of the examples (never promise something the clip does not show), a one-line description and 3-5 hashtags. Set keep to \
false if nothing here would work as a standalone clip."""
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
            model=env("CLIP_MODEL") or "claude-opus-5-5", max_tokens=64000,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            output_config={"effort": env("CLIP_EFFORT") or "xhigh",
                           "format": {"type": "json_schema", "schema": PICK_SCHEMA}},
            messages=[{"role": "user", "content": prompt}]) as stream:
        r = stream.get_final_message()
    if r.stop_reason != "end_turn":
        raise RuntimeError(f"Claude stopped with {r.stop_reason}")
    return json.loads(next(b.text for b in r.content if b.type == "text"))


def clamp(start, end, length):
    """Fit model-chosen boundaries inside the file and the MIN_S-MAX_S length."""
    start = min(max(0.0, start), max(0.0, length - MIN_S))
    end = min(max(end, start + MIN_S), start + MAX_S, length)
    return start, end


def ts(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02}:{t % 60:05.2f}"


def captions(words, start, end, per=3):
    """ASS subtitles: the words inside the clip, `per` at a time, timed from the clip start."""
    words = [w for w in words if start <= w["start"] < end]
    lines = []
    for i in range(0, len(words), per):
        g = words[i:i + per]
        stop = min(words[i + per]["start"] if i + per < len(words) else end, g[-1]["end"] + 0.5, end)
        text = " ".join(w["word"].strip() for w in g).upper().replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{ts(g[0]['start'] - start)},{ts(stop - start)},Default,,0,0,0,,{text}")
    return """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, \
StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,0,2,60,60,460,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(lines) + "\n"


def render(src, start, end, words, work, out):
    """9:16: the stream full width in the middle over a blurred copy, burned-in captions, loudness at -14 LUFS."""
    (work / "caps.ass").write_text(captions(words, start, end))
    graph = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[bg];"
             "[b]scale=1080:-2[fg];[bg][fg]overlay=0:(H-h)/2,ass=caps.ass[v]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}",
                    "-i", Path(src).resolve(), "-filter_complex", graph, "-map", "[v]", "-map", "0:a:0?",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", Path(out).resolve()],
                   check=True, cwd=work)


# ---------- 4. upload ----------

def upload_youtube(token, path, title, description, tags):
    meta = {"snippet": {"title": title.replace("<", "").replace(">", "")[:100], "description": description,
                        "tags": tags, "categoryId": "20"},
            "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": False}}
    auth = {"Authorization": "Bearer " + token}
    session = ok(requests.post("https://www.googleapis.com/upload/youtube/v3/videos", json=meta, timeout=60,
                               params={"uploadType": "resumable", "part": "snippet,status"},
                               headers={**auth, "X-Upload-Content-Type": "video/mp4"}))
    with open(path, "rb") as f:
        video = ok(requests.put(session.headers["Location"], data=f, timeout=600,
                                headers={**auth, "Content-Type": "video/mp4"})).json()
    return "https://youtube.com/shorts/" + video["id"]


# ---------- run ----------

def make_clip(m, niche, yt_token):
    """Cut, edit and (unless dry run) upload one moment. Returns what to remember about it."""
    channel = "".join(c if c.isalnum() else "_" for c in m["channel"])
    name = f"{datetime.now(timezone.utc):%Y%m%d}-{channel}-{int(m['start'])}"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        src, marked_at = download(m, work)
        length = duration(src) or marked_at + m["end"] - m["start"] + PAD  # unknown: the section we asked for
        words = transcribe(src, work)
        p = pick(m, niche, words, marked_at, length)
        record = {"url": m["url"], "start": m["start"], "niche": (niche or {}).get("name"), "keep": p["keep"],
                  "title": p["title"], "date": f"{datetime.now(timezone.utc):%Y-%m-%d}"}
        if not p["keep"] or blocked(p):  # Claude's own title is checked too
            print(f"  skipped: {p['title']}")
            record["keep"] = False
            return record
        start, end = clamp(p["start"], p["end"], length)
        out = OUT / f"{name}.mp4"
        render(src, start, end, words, work, out)
    tags = [t.lstrip("#").replace(" ", "") for t in p["hashtags"]]
    caption = f"{p['description']}\n\nCredit: {m['channel']} ({m['url']})\n" + " ".join("#" + t for t in tags)
    save(OUT / f"{name}.json", {**record, "clip": [start, end], "caption": caption})
    print(f"  rendered {out.name} ({end - start:.0f} s): {p['title']}")
    if yt_token and not DRY_RUN:  # a failed upload raises, so the moment is not recorded and is retried next run
        record["youtube"] = upload_youtube(yt_token, out, p["title"], caption + " #Shorts", tags)
        print(f"  YouTube: {record['youtube']}")
    return record


def main():
    DATA.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    sources = load(ROOT / "sources.json", {})
    seen = load(DATA / "seen.json", [])
    tw = twitch()
    yt_token = youtube_token() if env("YT_REFRESH_TOKEN") else None
    if not DRY_RUN and not yt_token:  # else moments would be marked done without ever being uploaded
        raise SystemExit("Posting is on but YT_REFRESH_TOKEN is missing; add it or turn POSTING off.")

    niches = scan(tw)
    save(DATA / "scan.json", {"date": f"{datetime.now(timezone.utc):%Y-%m-%d}", "niches": niches})
    print("Most viewed niches:", ", ".join(f"{n['name']} ({n['views']:,})" for n in niches[:5]))

    logins = sources.get("twitch", [])
    # no channels listed: clip the most viewed channels from the scan (check they allow clipping)
    users = tw("users", login=logins)["data"] if logins else tw("users", id=top_channels(niches))["data"]
    print("Clipping Twitch channels:", ", ".join(u["display_name"] for u in users) or "none")
    moments = rank(twitch_moments(tw, users) + youtube_moments(sources.get("youtube", [])), niches)
    by_id = {n["id"]: n for n in niches}
    done, made = list(seen), 0
    for m in moments:
        if made >= CLIPS_PER_RUN:
            break
        if seen_before(m, done):
            continue
        if blocked(m):
            print(f"skipped (blocked word in title): {m['channel']} @ {m['start']:.0f}s")
            continue
        print(f"{m['channel']} @ {m['start']:.0f}s, niche {by_id.get(m['niche'], {}).get('name', 'other')}: {m['title'][:60]}")
        try:
            record = make_clip(m, by_id.get(m["niche"]), yt_token)
        except Exception as e:  # one bad stream must not stop the run
            print(f"  failed: {e}")
            continue
        done.append(record)
        made += record["keep"]
        if not DRY_RUN:
            save(DATA / "seen.json", done)
    dashboard.write(load(DATA / "scan.json", {}), load(DATA / "seen.json", []), ROOT / "docs" / "index.html")
    print(f"{made} clip(s) {'rendered (dry run, nothing uploaded)' if DRY_RUN else 'posted'}; see out/")


if __name__ == "__main__":
    main()
