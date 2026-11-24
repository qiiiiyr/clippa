# Plan: automatic clipping bot

Goal: long videos and streams in, 15-60 second vertical clips out, posted to YouTube Shorts and Instagram Reels,
with a human approving every batch. Same shape as the Cutaway repo: GitHub Actions do the work, Claude reviews weekly.

## Pipeline

| Step | What | Tool | Model |
|---|---|---|---|
| 1. Find | new videos and top Twitch clips from `sources.json` | `yt-dlp`, Twitch API | none |
| 2. Download | best quality video and audio | `yt-dlp` | none |
| 3. Transcribe | word-level timestamps | OpenAI Whisper API | `whisper-1` |
| 4. Pick highlights | score windows of the transcript for hook, payoff, standalone sense; return start/end | Claude | `claude-opus-5-5`, effort `xhigh` |
| 4b. Scan Instagram | pull the latest 50 Reels of the reference accounts in `sources.json` (`instagram` list); keep the top 10 by likes + comments per follower as the winner set | Graph API `business_discovery` | none |
| 4c. Rank clips | compare each candidate clip (hook line, topic, length, pacing) with the winner set; give a 0-100 predicted-views score and one line of why; post highest first and drop the lowest | Claude | `claude-opus-5-5`, effort `xhigh` |
| 5. Cut and reframe | trim, 9:16 crop (face or speaker centred), loudness normalise | `ffmpeg` | none |
| 6. Captions | burned-in word captions from the Whisper timestamps | `ffmpeg` / Remotion | none |
| 7. Package | title, description with source credit, hashtags, thumbnail frame | Claude | `claude-sonnet-5-5`, effort `high` |
| 8. Review | previews in one pull request; untick what is wrong, merge to approve | GitHub | none |
| 9. Post | YouTube Shorts and Instagram Reels on a schedule | YouTube and Graph APIs | none |
| 10. Learn | views, % watched, saves per clip; weekly report and changes to scoring rules | Claude session | `claude-opus-5-5` |

## Repo layout

```
sources.json          channels and videos to clip (only with permission)
strategy.json         scoring rules, lessons, posting counts
clips/<week>/<n>/     meta.json (source, start, end, title, post flags), preview.mp4
scripts/              find.ts, transcribe.ts, pick.ts, cut.ts, caption.ts, package.ts, publish.ts
.github/workflows/    clip.yml, render.yml, publish.yml, collect.yml
docs/SETUP.md         one-time setup
docs/PLAN.md          this file
```

## Milestones

1. **One clip by hand:** URL in, one captioned 9:16 file out, no AI. Checks `ffmpeg` and `yt-dlp` in CI.
2. **AI pick:** transcript to Claude to start/end times. Test on 3 videos and compare with what you would pick.
3. **Package and review:** titles and the weekly pull request with previews.
4. **Posting:** YouTube first, then Instagram, dry run before public.
5. **Learning loop:** stats collector and the weekly Claude review, as in Cutaway.
6. **Later:** TikTok after its audit, Twitch auto-watch, face-tracking crop.

## Instagram scan (which clip gets the most views)

- Same method as `scripts/stats/instagram.ts` in the Cutaway repo: `business_discovery.username(<handle>){media.limit(50){caption,like_count,comments_count,timestamp,permalink,thumbnail_url}}`, using the `IG_USER_ID` and `IG_TOKEN` from SETUP part 4.
- **Limit:** Instagram does not give other accounts' view counts, and only Business or Creator accounts can be scanned. Likes and comments stand in for views, so the score is a prediction, not a count.
- Output: `data/ig-scan.json` (winners with hook, length, theme, likes per follower) and `clips/<week>/ranking.json` (score and reason per clip). Both appear in the weekly pull request, so you see why a clip was ranked first.
- The own-account side closes the loop: `collect` stores each posted clip's real views, and the weekly review compares predicted rank with real rank, then adjusts the scoring rules in `strategy.json`.
- Milestone: build it in milestone 2 right after the AI pick, and check that the ranking agrees with your own guess on 3 videos.

## Guide from the Instagram link (to fill in)

Paste the guide here or send it to me and I will turn it into rules for steps 4-7 (hook length, caption style, clip
length, posting times). Until then these are placeholders:

- Hook in the first 3 seconds:
- Clip length:
- Caption style:
- Posting times:
- Other tips:

## Risks

- **Rights:** clip only permitted channels, credit the source, keep a `sources.json` note per channel.
- **YouTube blocking runners:** may need a self-hosted runner or cookies.
- **Cost:** Opus at `xhigh` on long transcripts is the big cost. Pre-filter windows with Sonnet and cap clips per video.
- **Platform audits:** YouTube and TikTok may force private uploads until audited.
