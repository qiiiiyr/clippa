# clippa

Clipping bot: scans which clip niches get the most views on Twitch and YouTube, then cuts, edits (9:16, captions)
and uploads new clips from the Twitch and YouTube streams in `sources.json` to YouTube Shorts and Instagram Reels.

- Setup: [docs/SETUP.md](docs/SETUP.md)
- How it works: [docs/PLAN.md](docs/PLAN.md)
- Local run: `pip install -r requirements.txt`, set the secrets from SETUP as environment variables, `python clippa.py`
  (dry run unless `DRY_RUN=false`). Self-check: `python test_clippa.py`.
