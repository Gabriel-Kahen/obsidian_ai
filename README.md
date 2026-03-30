# Obsidian AI Discord Ingest

Small Python service for a Raspberry Pi that:

1. listens for messages in your Discord server,
2. extracts links plus any surrounding text,
3. fetches page context for each link,
4. asks Gemini to turn that into an Obsidian-friendly note,
5. writes a `.md` file with frontmatter into a local staging folder on the Pi,
6. uploads that note to iCloud Drive using `rclone`,
7. moves it into your Obsidian iCloud app folder.

## What It Does

- One Discord message with one URL becomes one markdown note.
- One Discord message with multiple URLs becomes multiple markdown notes.
- One Discord message with only text becomes one markdown note.
- Processed Discord message IDs are stored so the bot does not re-import the same message after a restart.
- Failed iCloud uploads stay queued on disk and retry in the background.

## Setup

### 1. Create the Discord bot

- Go to the Discord developer portal and create a bot.
- Enable the `Message Content Intent`.
- Invite the bot to your server.
- Copy the bot token into `.env`.

### 2. Create your Gemini API config

- Put your Gemini API key in `GEMINI_API_KEY`.
- Set `GEMINI_MODEL` to the model you want to use.

### 3. Configure the local staging path

- Set `OBSIDIAN_OUTPUT_DIR` to a local folder on the Pi.

### 4. Configure `rclone` for iCloud Drive

- Install `rclone` on the Pi.
- Run `rclone config`.
- Create an iCloud Drive remote, for example `icloud`.
- Choose the destination folder you want this bot to move notes into and set `RCLONE_DESTINATION`, for example `icloud:Obsidian/gabenotes/auto`.

This project assumes `rclone` is the only sync mechanism. Your Mac should just receive the resulting files through normal iCloud Drive sync.

### 5. Install and run

```bash
mkdir -p /home/pi/obsidian_ai
cd /home/pi/obsidian_ai
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
obsidian-ai-bot
```

## Environment Variables

- `DISCORD_BOT_TOKEN`: required.
- `DISCORD_ALLOWED_GUILD_IDS`: optional comma-separated allowlist.
- `DISCORD_ALLOWED_CHANNEL_IDS`: optional comma-separated allowlist.
- `DISCORD_ALLOWED_USER_IDS`: optional comma-separated allowlist.
- `GEMINI_API_KEY`: required.
- `GEMINI_MODEL`: required in practice; example is provided in `.env.example`.
- `OBSIDIAN_OUTPUT_DIR`: required local staging folder on the Pi, for example `/home/gabe/obsidian_ai/staging`.
- `STATE_PATH`: where processed Discord message IDs are stored.
- `SYNC_STATE_PATH`: where pending `rclone` uploads are stored.
- `STATIC_TAGS`: comma-separated tags added to every note.
- `HTTP_TIMEOUT_SECONDS`: timeout for page fetches and Gemini API calls.
- `RCLONE_COMMAND`: defaults to `rclone`.
- `RCLONE_CONFIG_PATH`: optional explicit path to `rclone.conf`.
- `RCLONE_DESTINATION`: required remote destination such as `icloud:Obsidian/gabenotes/auto`.
- `RCLONE_SYNC_INTERVAL_SECONDS`: how often the background retry loop runs.
- `RCLONE_SYNC_TIMEOUT_SECONDS`: timeout for each `rclone copyto` attempt.

## Example systemd service

```ini
[Unit]
Description=Obsidian AI Discord Ingest
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pi/obsidian_ai
EnvironmentFile=/home/pi/obsidian_ai/.env
ExecStart=/home/pi/obsidian_ai/.venv/bin/obsidian-ai-bot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Sync Behavior

- Notes are always written locally first.
- The bot then uploads each note to a temporary root-level iCloud path.
- After that upload succeeds, the bot moves the uploaded file into `RCLONE_DESTINATION`.
- If that upload fails, the note remains in the local staging folder and is recorded in `SYNC_STATE_PATH`.
- A background loop retries pending uploads on a fixed interval.
- A Discord `✅` reaction means local write plus immediate sync succeeded.
- A Discord `🕒` reaction means local write succeeded but iCloud upload is still pending retry.

## Current Limits

- Link fetching is HTML-focused. Some sites with aggressive bot protection will return weak or empty content.
- PDFs, private pages, and login-gated pages are not deeply parsed here.
- The Gemini output is constrained to JSON, but the note quality still depends on the source material.
- This design depends on `rclone`'s iCloud Drive backend. It is the best Pi-only fit here, but it is still less predictable than mainstream backends like S3 or Dropbox.
- X/Twitter support relies on metadata available in the public page response. It works best for public posts and may weaken when X changes its page metadata format.
