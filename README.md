# clippa

Clipping bot: scans which Twitch clip niches get the most views, then cuts, edits (9:16, captions)
and uploads new clips from the Twitch and YouTube streams in `sources.json` to YouTube Shorts.

- Dashboard: `docs/index.html`, rebuilt by every run (see SETUP part 4)
- Setup: [docs/SETUP.md](docs/SETUP.md)
- How it works: [docs/PLAN.md](docs/PLAN.md)
- Local run: `pip install -r requirements.txt`, set the secrets from SETUP as environment variables, `python clippa.py`
  (dry run unless `DRY_RUN=false`). Self-check: `python test_clippa.py`.

Captions follow the language spoken in each clip (Whisper detects it), including Hindi and mixed Hindi/English. With no
API keys the whole bot is free and can run on your own machine, with nothing uploaded anywhere except the finished clips.
