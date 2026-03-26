# Loominary

Transform podcast episodes into searchable text transcripts — or record and transcribe your meetings. Find a podcast on Spotify, or join a meeting, and Loominary handles the rest: RSS discovery, audio download or screen recording, transcription, local database storage, and optional Google Drive upload.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Package manager | uv |
| Spotify | Spotipy (Spotify Web API) |
| Transcription | faster-whisper (default) · OpenAI Whisper (alternative) |
| Screen/audio capture | ffmpeg (gdigrab + WASAPI loopback) |
| Database | DuckDB |
| CLI | rich · questionary |
| Google Drive | Google Drive API v3 |

---

## Prerequisites

### 1. Python and uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. ffmpeg

Required for audio processing and (in meeting mode) screen/audio capture.

```bash
# Windows
winget install ffmpeg

# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### 3. Spotify Developer App

Only required for podcast mode.

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click **Create app**
3. Set **Redirect URI** to `http://127.0.0.1:8888/callback`
4. Copy your **Client ID** and **Client Secret**

### 4. Google Drive (optional)

Only needed if you want to upload transcripts to Drive.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Google Drive API**
3. Create **OAuth 2.0 credentials** (Desktop app type)
4. Download the `client_secrets.json` file

---

## Setup

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd Loominary

# 2. Install all dependencies
uv sync

# 3. Configure environment
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```ini
SPOTIPY_CLIENT_ID=your_client_id_here
SPOTIPY_CLIENT_SECRET=your_client_secret_here
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

```bash
# 4. Run
uv run main.py
```

On first run (podcast mode), a browser window opens for Spotify OAuth. After login, the token is cached at `.cache` so subsequent runs skip the browser step.

---

## Usage

### Starting the app

```bash
uv run main.py
```

You are first asked what you want to do:

```
? What would you like to do?
  > Transcribe a podcast
    Record a meeting
```

---

## Podcast Mode

Select **Transcribe a podcast** to enter the podcast workflow.

### Option 1 — Search for a podcast

Type any keyword (show name, topic, host name). Loominary queries the Spotify catalog and shows up to 8 matching shows. Select one, then select an episode from the 20 most recent.

### Option 2 — Paste a Spotify link

Paste any Spotify share URL or URI directly. Supported formats:

```
https://open.spotify.com/episode/4rOoJ6Egrf8K2IrywzwOMk
https://open.spotify.com/show/4rOoJ6Egrf8K2IrywzwOMk
spotify:episode:4rOoJ6Egrf8K2IrywzwOMk
```

If you paste a show link, you are taken to the episode selection menu. If you paste an episode link directly, transcription begins immediately.

### What happens next

Once an episode is selected:

1. **RSS discovery** — Loominary finds the podcast's RSS feed automatically (no manual input needed)
2. **Download** — the MP3 is streamed to `tmp/audio/` with a live progress bar
3. **Transcription** — Whisper processes the audio; a spinner shows progress
4. **Save** — the transcript is written to `data/transcripts/` as a `.txt` file
5. **Database** — show, episode, and transcript metadata are stored in `data/loominary.duckdb`
6. **Drive upload** *(optional)* — you are asked whether to upload to Google Drive

### Output files

Podcast transcripts are named using this pattern:

```
podcast_{YYYY-MM-DD}_{show_name}_{episode_name}.txt
```

Example:
```
data/transcripts/podcast_2024-12-15_lex_fridman_podcast_sam_altman_openai_and_gpt-5.txt
```

---

## Meeting Mode

Select **Record a meeting** to enter the meeting recorder. This mode is **Windows-only** — it uses ffmpeg's `gdigrab` for screen capture and WASAPI loopback for system audio.

You will be asked to choose between two sub-modes:

```
? Select recording mode:
  > Automatic (scheduled from YAML config)
    Manual (start now, stop on command)
```

### Automatic mode

Reads a YAML config file from the `meetings/` folder, waits until the scheduled start time, opens the meeting URL in your browser, records for the specified duration, then transcribes.

**Create a config file** at `meetings/my-meeting.yaml`:

```yaml
name: "quarterly-review"
url: "https://meet.google.com/xyz-abc-def"
platform: generic          # zoom | teams | generic | goldcast
start_time: "2026-04-01 10:00:00"
duration_minutes: 60
```

Loominary scans all `.yaml` / `.yml` files in `meetings/` and lets you pick one interactively. After recording it will optionally shut down the computer.

### Manual mode

Prompts you for the meeting name, URL, and platform, then starts recording immediately. Type `stop` and press Enter in the terminal to stop the recording and begin transcription.

```
Meeting name: weekly-standup
Meeting URL (leave blank to skip opening browser): https://zoom.us/j/123456789
Platform: zoom

Recording... Type stop and press Enter to stop recording.
stop
Stop command received. Finishing recording...
```

### Meeting prerequisites

Meeting mode requires a WASAPI loopback audio device to capture system audio. On most Windows machines this works automatically. If you see an `AudioDeviceError`:

1. Right-click the speaker icon in the taskbar → **Sounds**
2. Go to the **Recording** tab
3. Right-click in the device list → **Show Disabled Devices**
4. Enable **Stereo Mix** if available, then retry

Alternatively, install a virtual audio cable such as [VB-Audio VoiceMeeter](https://vb-audio.com/Voicemeeter/).

### Meeting pipeline

1. **Pre-flight** — verifies ffmpeg is on PATH and detects the loopback audio device
2. **Browser** — opens the meeting URL in your default browser
3. **Record** — captures screen + system audio to `data/recordings/YYYY-MM-DD_name/recording.mp4`
4. **Extract audio** — converts MP4 to 16kHz mono WAV for Whisper
5. **Transcription** — same Whisper engine used for podcasts
6. **Save** — writes `data/transcripts/meeting_YYYY-MM-DD_name.txt` and a `.srt` subtitle file
7. **Database** — meeting and transcript metadata stored in `data/loominary.duckdb`

### Meeting output files

```
data/recordings/2026-04-01_quarterly-review/
├── recording.mp4     # full screen + audio
├── audio.wav         # extracted audio (16kHz mono)
├── ffmpeg.log        # ffmpeg debug output
└── recorder.log      # application debug log

data/transcripts/
├── meeting_2026-04-01_quarterly-review.txt   # plain text with timestamps
└── meeting_2026-04-01_quarterly-review.srt   # SRT subtitle format
```

The plain-text transcript includes per-segment timestamps:

```
Meeting: quarterly-review
Date: 2026-04-01 10:00:00
Segments: 142
------------------------------------------------------------
[00:00:00 --> 00:00:04] Good morning everyone, let's get started.
[00:00:04 --> 00:00:09] Today we'll be reviewing Q1 performance.
```

---

## Configuration

All settings live in `.env`. Copy `.env.example` to get started.

### Required (podcast mode only)

| Variable | Description |
|---|---|
| `SPOTIPY_CLIENT_ID` | Spotify app Client ID |
| `SPOTIPY_CLIENT_SECRET` | Spotify app Client Secret |
| `SPOTIPY_REDIRECT_URI` | Must match the redirect URI set in your Spotify app (default: `http://127.0.0.1:8888/callback`) |

### Transcription

| Variable | Default | Options | Description |
|---|---|---|---|
| `WHISPER_BACKEND` | `faster-whisper` | `faster-whisper`, `openai-whisper` | Which transcription engine to use |
| `WHISPER_MODEL` | `small` | `tiny`, `base`, `small`, `medium`, `large-v3` | Model size — larger = more accurate, slower, more RAM |
| `SAVE_SEGMENTS` | `false` | `true`, `false` | Also save a `{filename}.segments.json` with per-segment timestamps (podcast mode only) |

### RSS Discovery (optional)

| Variable | Description |
|---|---|
| `PODCAST_INDEX_API_KEY` | Podcast Index API key — improves RSS discovery coverage |
| `PODCAST_INDEX_API_SECRET` | Podcast Index API secret |

Get a free key at [podcastindex.org](https://podcastindex.org/login).

### Google Drive (optional)

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_CLIENT_SECRETS_FILE` | *(none)* | Path to your downloaded `client_secrets.json` |
| `GOOGLE_DRIVE_FOLDER_NAME` | `Loominary` | Root folder name in Drive. Show subfolders are created automatically |

### Paths

| Variable | Default | Description |
|---|---|---|
| `LOOMINARY_DB_PATH` | `./data/loominary.duckdb` | Location of the local DuckDB database |
| `LOOMINARY_TRANSCRIPTS_DIR` | `./data/transcripts` | Where transcript `.txt` files are saved |
| `LOOMINARY_TMP_DIR` | `./tmp` | Temporary folder for MP3 downloads (auto-cleaned after transcription) |

---

## Customisation

### Choosing a transcription backend

**faster-whisper** (default) is recommended for most users:
- ~4x faster than OpenAI Whisper on CPU
- Uses significantly less RAM — can handle 3+ hour episodes without chunking
- No PyTorch dependency

**openai-whisper** is available as an alternative:
- Slightly more mature ecosystem
- Automatically chunks episodes longer than 20 minutes to avoid out-of-memory errors
- Requires PyTorch (installed automatically)

```ini
# .env
WHISPER_BACKEND=faster-whisper   # recommended
WHISPER_BACKEND=openai-whisper   # alternative
```

### Choosing a model size

Larger models produce more accurate transcripts but are slower and use more RAM. The `small` model is a good default for most content in English.

| Model | RAM (approx.) | Speed | Best for |
|---|---|---|---|
| `tiny` | ~400 MB | Fastest | Quick drafts, low-memory machines |
| `base` | ~550 MB | Fast | General use |
| `small` | ~1 GB | Balanced | **Default — good accuracy** |
| `medium` | ~2.5 GB | Slow | High accuracy, technical content |
| `large-v3` | ~5 GB | Slowest | Best possible accuracy |

```ini
# .env
WHISPER_MODEL=small
```

### Saving timestamped segments (podcast mode)

Set `SAVE_SEGMENTS=true` to save a JSON file alongside every podcast transcript containing start/end timestamps for each spoken segment:

```ini
SAVE_SEGMENTS=true
```

Output: `data/transcripts/podcast_2024-12-15_show_episode.segments.json`

```json
[
  { "start": 0.0, "end": 4.2, "text": " Welcome to the show." },
  { "start": 4.2, "end": 9.8, "text": " Today we're talking about..." }
]
```

### Improving RSS discovery

Loominary uses a 4-layer fallback to find podcast RSS feeds:

1. Spotify `external_urls` field (instant, rarely populated)
2. iTunes Search API (no key needed, covers most major podcasts)
3. Podcast Index API (free key, broader independent podcast coverage)
4. Spotify web page scrape (last resort)

If a podcast isn't found via iTunes, adding a Podcast Index key usually resolves it:

```ini
PODCAST_INDEX_API_KEY=your_key
PODCAST_INDEX_API_SECRET=your_secret
```

---

## Inspecting the database

Loominary stores all metadata locally in DuckDB. You can query it directly:

```bash
# List all podcast transcripts
uv run python -c "
import duckdb
c = duckdb.connect('./data/loominary.duckdb')
print(c.execute('SELECT file_name, word_count, whisper_model, transcribed_at FROM transcripts').df())
"

# List all meeting transcripts
uv run python -c "
import duckdb
c = duckdb.connect('./data/loominary.duckdb')
print(c.execute('SELECT m.name, mt.transcript_path, mt.word_count, mt.created_at FROM meeting_transcripts mt JOIN meetings m ON mt.meeting_id = m.id').df())
"

# List all shows
uv run python -c "
import duckdb
c = duckdb.connect('./data/loominary.duckdb')
print(c.execute('SELECT name, publisher, total_episodes FROM shows').df())
"
```

---

## Project Structure

```
Loominary/
├── main.py                        # Entry point — mode selector (podcast / meeting)
├── pyproject.toml                 # Dependencies (uv-managed)
├── .env                           # Your secrets (gitignored)
├── .env.example                   # Template
├── meetings/                      # YAML configs for automatic meeting mode
│   └── my-meeting.yaml
│
├── loominary/
│   ├── config.py                  # Environment loading + validation
│   ├── cli.py                     # Podcast interactive menus + workflow
│   │
│   ├── meeting/                   # Meeting recorder pipeline
│   │   ├── pipeline.py            # Automatic + manual mode orchestrators
│   │   ├── recorder.py            # ffmpeg screen + audio capture
│   │   ├── audio_devices.py       # WASAPI loopback device detection
│   │   ├── scheduler.py           # Countdown wait + browser open
│   │   ├── transcriber.py         # Audio extraction + transcript file writing
│   │   ├── config.py              # YAML config loading (MeetingConfig)
│   │   ├── shutdown.py            # Post-meeting wait + Windows shutdown
│   │   └── errors.py              # Exception hierarchy
│   │
│   ├── auth/
│   │   ├── spotify_auth.py        # Spotify OAuth + token cache
│   │   └── google_auth.py         # Google OAuth2
│   │
│   ├── spotify/
│   │   ├── search.py              # Show search + episode listing
│   │   ├── link_parser.py         # Parse Spotify URLs → IDs
│   │   └── metadata.py            # Dataclasses + normalizers
│   │
│   ├── rss/
│   │   ├── discovery.py           # 4-layer RSS feed discovery
│   │   └── downloader.py          # Streaming MP3 download
│   │
│   ├── transcription/
│   │   ├── base.py                # Abstract engine + TranscriptResult
│   │   ├── faster_whisper_engine.py
│   │   └── whisper_engine.py
│   │
│   ├── database/
│   │   ├── schema.py              # CREATE TABLE statements (shows, episodes, transcripts, meetings, meeting_transcripts)
│   │   └── repository.py          # upsert/insert/query functions
│   │
│   ├── drive/
│   │   └── uploader.py            # Drive folder creation + upload
│   │
│   └── utils/
│       ├── file_naming.py         # Slug builder + collision handling
│       └── progress.py            # Shared rich console + progress bars
│
├── data/
│   ├── loominary.duckdb           # Local database (gitignored)
│   ├── transcripts/               # Output .txt files — podcast_ and meeting_ prefixed (gitignored)
│   └── recordings/                # Meeting screen recordings (gitignored)
│       └── YYYY-MM-DD_name/
│           ├── recording.mp4
│           ├── audio.wav
│           ├── ffmpeg.log
│           └── recorder.log
│
└── tmp/audio/                     # Temp MP3 downloads (gitignored)
```

---

## Troubleshooting

**`Missing required environment variable: SPOTIPY_CLIENT_ID`**
This only applies to podcast mode. Copy `.env.example` to `.env` and fill in your Spotify credentials.

**`Could not find RSS feed for this podcast`**
The podcast may be Spotify-exclusive (no public RSS feed). Add a Podcast Index API key to `.env` for broader coverage.

**`Transcription failed: Out of memory`** (openai-whisper only)
Switch to `WHISPER_BACKEND=faster-whisper` or use a smaller model (`WHISPER_MODEL=tiny`). If you must use openai-whisper, the engine will automatically chunk files longer than 20 minutes.

**Spotify login doesn't redirect back**
Ensure the redirect URI in your `.env` exactly matches the one set in your Spotify Developer Dashboard, including the port.

**`AudioDeviceError: Could not find a WASAPI loopback audio device`** (meeting mode)
Enable Stereo Mix in Windows Sound settings: right-click the speaker icon → Sounds → Recording tab → right-click → Show Disabled Devices → enable Stereo Mix. Alternatively, install [VB-Audio VoiceMeeter](https://vb-audio.com/Voicemeeter/).

**`RecorderError: ffmpeg not found on PATH`** (meeting mode)
Install ffmpeg via `winget install ffmpeg` and restart your terminal.

---

## Legal Disclaimer

This project is unofficial and is not affiliated with, authorized by, or endorsed by Spotify or Google. It is intended for personal, non-commercial educational use only. Users are responsible for complying with the Terms of Service of all platforms used and for respecting the intellectual property rights of podcast creators and meeting participants.
