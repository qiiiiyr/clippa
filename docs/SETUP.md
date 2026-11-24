# One-time setup

You connect the clipping bot to the accounts it posts to and to the AI services it uses, then test. Done once.
This mirrors the setup of the Cutaway / Bongkar Pasang repo: keys live in GitHub, GitHub Actions does the work, you approve.

**Golden rule:** keys and tokens go only into GitHub (Settings → Secrets and variables → Actions → **Repository
secrets**), never into a chat or a screenshot.

| Part | What you get | Secrets |
|---|---|---|
| 1. AI keys | highlight picking, titles, transcription | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` |
| 2. Sources | niche scan and where clips are cut from | `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, optional `YTDLP_COOKIES` |
| 3. YouTube (Shorts) | upload and the YouTube side of the scan | `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` |
| 4. Instagram (Reels) | upload and stats | `IG_USER_ID`, `IG_TOKEN` |
| 5. TikTok (optional, later) | upload | `TT_CLIENT_KEY`, `TT_CLIENT_SECRET`, `TT_REFRESH_TOKEN` |
| 6. GitHub settings and tests | switch it on | variables `POSTING`, `PRIVACY` |

## 1. AI keys

1. Claude: <https://console.anthropic.com> → API Keys → create a key for this bot only, add a small credit and set a
   monthly spend limit. Save as `ANTHROPIC_API_KEY`.
2. Transcription (Whisper): <https://platform.openai.com> → API keys → create one. Save as `OPENAI_API_KEY`.
3. Optional repository **variables** (not secrets); the defaults are shown: `CLIP_MODEL=claude-opus-5-5`,
   `CLIP_EFFORT=xhigh` (one call per clip picks the cut and writes title, description and hashtags),
   `WHISPER_MODEL=whisper-1`, `CLIP_MIN_SECONDS=15`, `CLIP_MAX_SECONDS=60`, `CLIPS_PER_RUN=3`.

## 2. Sources

- **Twitch:** <https://dev.twitch.tv/console> → Register Your Application (category "Application Integration",
  redirect `http://localhost`) → copy the Client ID and a new Client Secret into `TWITCH_CLIENT_ID` and
  `TWITCH_CLIENT_SECRET`. Needed for every run: the niche scan reads the top clips of the 20 biggest Twitch categories.
- **`sources.json`:** the channels clips are cut from: `"twitch"` takes channel logins (`"xqc"`), `"youtube"` takes
  @handles (`"@somechannel"`). The bot cuts the moments viewers clipped on Twitch and the "most replayed" parts of
  YouTube streams, hottest niche from the scan first.
- **YouTube downloads:** `yt-dlp`, no key. YouTube often blocks cloud machines with "Sign in to confirm you're not a
  bot". Fix: in a private browser window sign in with a spare Google account, export youtube.com cookies with a
  "cookies.txt" extension, and paste the whole file into the secret `YTDLP_COOKIES`.
- **Rights:** only add channels that agreed to be clipped (or your own). Every clip credits the source in the
  description. Un-permitted re-uploads get claimed or struck and can end the account.

## 3. YouTube (Shorts)

1. Sign in to YouTube and create the channel for the clips.
2. <https://console.cloud.google.com> → new project → enable **YouTube Data API v3** and **YouTube Analytics API**.
3. OAuth consent screen: External, fill the app name and links, then press **Publish app** (in "Testing" the login
   expires every 7 days). Credentials → OAuth client ID → Web application, redirect URI
   `https://developers.google.com/oauthplayground`. Save `YT_CLIENT_ID`, `YT_CLIENT_SECRET`.
4. <https://developers.google.com/oauthplayground> → gear → "Use your own OAuth credentials" → scopes
   `https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/yt-analytics.readonly`
   → authorize with the clips channel → exchange the code → copy the **refresh token** into `YT_REFRESH_TOKEN`.
5. New API projects may be forced to private until YouTube audits them: <https://support.google.com/youtube/contact/yt_api_form>.
6. Quota: 10,000 units a day. The scan uses about 2,000 (20 searches), each upload about 1,600, so keep
   `CLIPS_PER_RUN` at 4 or less. Without `YT_REFRESH_TOKEN` the bot scans Twitch only and skips YouTube uploads.

## 4. Instagram (Reels)

1. Make the Instagram account a **Creator** account (Settings and privacy → Account type and tools) and link it to a
   Facebook Page (Edit profile → Page).
2. <https://developers.facebook.com> → Create app (use case "Manage messaging & content on Instagram"), keep it in
   Development mode.
3. Graph API Explorer: user token with `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`,
   `pages_show_list`, `pages_read_engagement`, `business_management` → make it long-lived in the Access Token Debugger →
   `GET me/accounts` gives the Page token (never expires). Save it as `IG_TOKEN`.
4. `GET <page id>?fields=instagram_business_account` → the `id` is `IG_USER_ID`.

## 5. TikTok (optional, later)

Register an app at <https://developers.tiktok.com>, add the Content Posting API, and complete its audit. Until the audit
passes, uploads are private only, so start with YouTube and Instagram.

## 6. GitHub settings and tests

1. Settings → General → `main` is the default branch.
2. Settings → Actions → General → Workflow permissions **Read and write**, and tick "Allow GitHub Actions to create
   and approve pull requests".
3. Add the secrets from parts 1-4.
4. **Dry run:** add channels to `sources.json`, then Actions → **clip** → Run workflow with dry run ticked. The log
   shows the most viewed niches; `data/scan.json` (committed by the run) has the full ranking and each niche's top
   clips. Download the **clips** artifact: one `.mp4` and `.json` per clip. Check captions, crop and the first 3 seconds.
5. **First real post:** set the variable `PRIVACY=private`, run **clip** with dry run unticked, check the uploads.
6. **Go live:** remove `PRIVACY` (or set `public`) and set the variable `POSTING=on`. The daily run then posts. Delete
   `POSTING` or set it to `off` to pause. `data/seen.json` remembers clipped moments so nothing is posted twice.

## If something fails

| Message | Meaning and fix |
|---|---|
| `Sign in to confirm you're not a bot` (yt-dlp) | YouTube blocked the runner. Add the `YTDLP_COOKIES` secret (part 2) or use a self-hosted runner. |
| `0 clip(s)` | No new moments: add channels to `sources.json`, or their VODs are subscriber-only. |
| `invalid_grant` (YouTube) | Refresh token expired. Publish the app, then redo the token. |
| Instagram `code 190` | Token expired. Redo part 4 step 3. |
| Instagram `code 100` | Wrong user ID or wrong Page. Redo part 4 step 4. |
| Claude `429` or spend limit | Raise the limit in the Anthropic console or lower `CLIP_EFFORT`. |
