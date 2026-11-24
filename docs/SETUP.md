# One-time setup

You connect the clipping bot to the accounts it posts to and to the AI services it uses, then test. Done once.
This mirrors the setup of the Cutaway / Bongkar Pasang repo: keys live in GitHub, GitHub Actions does the work, you approve.

**Golden rule:** keys and tokens go only into GitHub (Settings → Secrets and variables → Actions → **Repository
secrets**), never into a chat or a screenshot.

| Part | What you get | Secrets |
|---|---|---|
| 1. AI keys | highlight picking, titles, transcription | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` |
| 2. Sources | where clips are cut from | `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` (YouTube sources need none) |
| 3. YouTube (Shorts) | upload and stats | `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` |
| 4. Instagram (Reels) | upload and stats | `IG_USER_ID`, `IG_TOKEN` |
| 5. TikTok (optional, later) | upload | `TT_CLIENT_KEY`, `TT_CLIENT_SECRET`, `TT_REFRESH_TOKEN` |
| 6. GitHub settings and tests | switch it on | variables `POSTING`, `PRIVACY` |

## 1. AI keys

1. Claude: <https://console.anthropic.com> → API Keys → create a key for this bot only, add a small credit and set a
   monthly spend limit. Save as `ANTHROPIC_API_KEY`.
2. Transcription (Whisper): <https://platform.openai.com> → API keys → create one. Save as `OPENAI_API_KEY`.
3. Models (repository **variables**, not secrets): `CLIP_MODEL=claude-opus-5-5`, `CLIP_EFFORT=xhigh` (finding the
   highlights), `SMALL_TASK_MODEL=claude-sonnet-5-5`, `SMALL_TASK_EFFORT=high` (titles, captions, hashtags),
   `WHISPER_MODEL=whisper-1`, `CLIP_MIN_SECONDS=15`, `CLIP_MAX_SECONDS=60`.

## 2. Sources

- **YouTube videos:** the bot downloads with `yt-dlp`. No key. GitHub runners are sometimes blocked by YouTube; if a
  download fails with "sign in to confirm", see "If something fails".
- **Twitch:** <https://dev.twitch.tv/console> → Register Your Application (category "Application Integration",
  redirect `http://localhost`) → copy the Client ID and a new Client Secret into `TWITCH_CLIENT_ID` and
  `TWITCH_CLIENT_SECRET`. The bot lists the top clips of the channels in `sources.json`.
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

## 4. Instagram (Reels)

1. Make the Instagram account a **Creator** account (Settings and privacy → Account type and tools) and link it to a
   Facebook Page (Edit profile → Page).
2. <https://developers.facebook.com> → Create app (use case "Manage messaging & content on Instagram"), keep it in
   Development mode.
3. Graph API Explorer: user token with `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`,
   `pages_show_list`, `pages_read_engagement`, `business_management` → make it long-lived in the Access Token Debugger →
   `GET me/accounts` gives the Page token (never expires). Save it as `IG_TOKEN`.
4. `GET <page id>?fields=instagram_business_account` → the `id` is `IG_USER_ID`.
5. **Scan list:** in `sources.json` add `"instagram": ["handle1", "handle2"]` with 5-10 Business or Creator accounts in your niche. The bot scans them daily to learn what gets the most views. Personal accounts return an error and are skipped.

## 5. TikTok (optional, later)

Register an app at <https://developers.tiktok.com>, add the Content Posting API, and complete its audit. Until the audit
passes, uploads are private only, so start with YouTube and Instagram.

## 6. GitHub settings and tests

1. Settings → General → `main` is the default branch.
2. Settings → Actions → General → Workflow permissions **Read and write**, and tick "Allow GitHub Actions to create
   and approve pull requests".
3. Add the secrets from parts 1-4.
4. **Check logins:** Actions → **publish** → Run workflow, dry run ticked. Each account prints `login OK` or what to fix.
5. **Test one clip:** Actions → **clip** → Run workflow with one video URL and dry run ticked. Open the preview, check
   captions, crop, and the first 3 seconds. Then run it again with dry run off and `PRIVACY=private`.
6. Variables: `POSTING=off` pauses all posting; `PRIVACY=private` uploads YouTube as private.

## If something fails

| Message | Meaning and fix |
|---|---|
| `Sign in to confirm you're not a bot` (yt-dlp) | YouTube blocked the runner. Use a self-hosted runner or the cookies option in `docs/PLAN.md`. |
| `invalid_grant` (YouTube) | Refresh token expired. Publish the app, then redo the token. |
| Instagram `code 190` | Token expired. Redo part 4 step 3. |
| Instagram `code 100` | Wrong user ID or wrong Page. Redo part 4 step 4. |
| Claude `429` or spend limit | Raise the limit in the Anthropic console or lower `CLIP_EFFORT`. |
