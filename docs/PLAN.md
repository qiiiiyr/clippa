# Plan: automatic clipping bot

Goal: long videos and streams in, 15-60 second vertical clips out, posted to YouTube Shorts,
with a human approving every batch. Same shape as the Cutaway repo: GitHub Actions do the work, Claude reviews weekly.

## Pipeline (built: `clippa.py`, run daily by `.github/workflows/clip.yml`)

| Step | What | Tool | Model |
|---|---|---|---|
| 1. Scan niches | top 100 clips this week of each of the 20 biggest Twitch categories; niches ranked by total views, top 10 clips kept as inspiration (`data/scan.json`) | Twitch API | none |
| 2. Find moments | in the `sources.json` channels: moments viewers clipped on Twitch (located in the VOD), "most replayed" peaks of the last 3 YouTube streams and last 3 videos; ordered hottest niche first, then views; moments already in `data/seen.json` skipped | Twitch API, `yt-dlp` | none |
| 3. Download | only the moment plus 30 s each side | `yt-dlp` | none |
| 4. Transcribe | word-level timestamps | OpenAI Whisper API | `whisper-1` |
| 5. Pick and package | exact 15-60 s cut with a hook, title in the style of the niche's top clips, description, hashtags, or skip | Claude (structured output) | `claude-opus-5-5`, effort `xhigh` |
| 6. Edit | 9:16 with the stream full width over a blurred copy, burned-in 3-word captions, -14 LUFS | `ffmpeg` | none |
| 7. Post | YouTube Shorts with source credit; dry run keeps the clips as a workflow artifact | YouTube API | none |

## Repo layout

```
clippa.py             the whole pipeline
test_clippa.py        offline self-check (runs before every clip run)
sources.json          channels to clip (only with permission)
data/scan.json        latest niche ranking with top clips
data/seen.json        clipped moments and where they were posted
.github/workflows/    clip.yml
docs/SETUP.md         one-time setup
docs/PLAN.md          this file
```

## Later

- Learning loop: collect each posted clip's views and feed the winners back into the prompt next to the niche scan.
- Instagram Reels upload, and a YouTube Shorts scan as a second inspiration source (about 2,000 YouTube quota units a day).
- Review step: previews in a pull request, merge to approve, before posting.
- TikTok after its API audit; face-tracking crop for facecam streams.

## Risks

- **Rights:** clip only permitted channels, credit the source, keep a `sources.json` note per channel.
- **YouTube blocking runners:** needs the `YTDLP_COOKIES` secret or a self-hosted runner.
- **Cost:** only a ~2 minute excerpt per moment is downloaded, transcribed and sent to Claude; `CLIPS_PER_RUN` caps it. Skipped moments still cost one call.
- **Platform audits:** YouTube and TikTok may force private uploads until audited.
