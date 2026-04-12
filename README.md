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
| Vector store | Qdrant (server or embedded local) |
| Embeddings | BGE-M3 (1024-dim dense + BM25 sparse) |
| LLM | Qwen3.5-35B-A3B via llama.cpp server |
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
    Chat with library
    Reindex all transcripts
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

## RAG Chat — Chat with Your Library

Loominary includes a built-in RAG (retrieval-augmented generation) chatbot that lets you ask questions across all your transcribed podcasts and meetings. It uses:

- **BGE-M3** for dense embeddings (1024-dim)
- **BM25** for sparse keyword matching
- **Qdrant** for hybrid vector search (dense + sparse fused with Reciprocal Rank Fusion)
- **Qwen3.5-35B-A3B** (3B active params, MoE) via llama.cpp for answer generation

### How it works

1. Transcripts are split into 512-token chunks (with 64-token overlap)
2. Each chunk is embedded with BGE-M3 (dense) and BM25 (sparse), then stored in Qdrant with metadata (show name, episode title, dates, etc.)
3. When you ask a question, both embedding types are searched and results are fused with RRF
4. The top 5 relevant chunks are injected into a grounded prompt sent to the LLM
5. The LLM answers using only the provided excerpts and cites its sources with `[1]`, `[2]`, etc.

### Indexing

Transcripts are **automatically indexed** after each transcription (both podcast and meeting modes). You can also manually reindex everything via the main menu:

```
? What would you like to do? Reindex all transcripts
? Force re-index even if files are unchanged? No
```

Reindexing is idempotent — files whose content hash hasn't changed are skipped.

### Two ways to run it

The RAG chatbot requires two backend services: a **vector database** (Qdrant) and an **LLM server** (llama.cpp). You can run these locally or via Docker — choose the option that fits your situation:

---

#### Option A — Local development (no Docker required)

**When to use:** Day-to-day development, quick testing, single-machine use. No server processes to manage. The vector database runs embedded (no Qdrant server needed), but you still need a local llama.cpp server for the LLM.

In this mode, Qdrant runs as an **embedded local database** stored at `data/qdrant_local/`. The fallback activates automatically when no Qdrant server is reachable — no Docker or separate Qdrant process needed.

##### Step 1 — Install Loominary dependencies

```bash
cd Loominary
uv sync
```

##### Step 2 — Download llama.cpp (pre-built binary)

llama.cpp is the inference engine that runs the Qwen3.5 LLM locally. You need to download the correct pre-built binary for your system.

**How to choose the right binary:**

First, identify your system:

```bash
# Check your CPU (to determine AVX support)
wmic cpu get Name

# Check available RAM
systeminfo | findstr "Total Physical Memory"
```

Then go to the [llama.cpp releases page](https://github.com/ggml-org/llama.cpp/releases/) and download the latest release zip that matches your system:

| Your system | Download file to look for |
|---|---|
| Windows, modern CPU (Intel Haswell+ / AMD Zen+) | `llama-<version>-bin-win-avx2-x64.zip` |
| Windows, older CPU (no AVX2) | `llama-<version>-bin-win-avx-x64.zip` |
| Windows, NVIDIA GPU | `llama-<version>-bin-win-cuda-cu12.4.1-x64.zip` |
| macOS, Apple Silicon (M1/M2/M3/M4) | `llama-<version>-bin-macos-arm64.zip` |
| macOS, Intel | `llama-<version>-bin-macos-x64.zip` |
| Linux, x64 | `llama-<version>-bin-ubuntu-x64.zip` |
| Linux, NVIDIA GPU | `llama-<version>-bin-ubuntu-x64-cuda-cu12.4.1.zip` |

> **How to check AVX2 support (Windows):** Most CPUs from 2014 onward support AVX2. If unsure, open PowerShell and run: `(Get-CimInstance Win32_Processor).Name` — then look up your CPU model. AMD Ryzen and Intel 4th-gen Core or newer all support AVX2.

> **Why AVX2 matters:** AVX2 enables SIMD (Single Instruction, Multiple Data) vector operations that dramatically speed up the matrix multiplications in LLM inference. The AVX2 build will be significantly faster than the plain AVX build on supported CPUs.

Extract the zip to a location of your choice, for example:

```powershell
# Windows example
mkdir C:\llama-cpp
# Extract the downloaded zip into C:\llama-cpp
# You should see llama-server.exe (or llama-server on macOS/Linux) inside
```

```bash
# macOS / Linux example
mkdir -p ~/llama-cpp
cd ~/llama-cpp
unzip ~/Downloads/llama-*.zip
```

##### Step 3 — Download the model weights (one-time, ~21.6 GB)

The chatbot uses [Qwen3.5-35B-A3B](https://huggingface.co/Qwen/Qwen3.5-35B-A3B), a Mixture-of-Experts model with 35B total parameters but only 3B active per token — making it feasible to run on CPU with ~28 GB RAM. We use the [MXFP4 quantized GGUF](https://huggingface.co/unsloth/Qwen3.5-35B-A3B-GGUF) from Unsloth.

```bash
mkdir -p models

# This will take a while depending on your connection (~21.6 GB)
curl -L -o models/qwen3.5-35b-a3b.gguf \
  "https://huggingface.co/unsloth/Qwen3.5-35B-A3B-GGUF/resolve/main/Qwen3.5-35B-A3B-MXFP4_MOE.gguf?download=true"
```

Verify the download completed (should be ~21.6 GB):

```bash
ls -lh models/qwen3.5-35b-a3b.gguf
```

##### Step 4 — Start the llama.cpp server

Open a **separate terminal** (this server needs to stay running while you use Loominary):

```bash
# Adjust the path to where you extracted llama.cpp
# Adjust --threads to match your CPU core count (not logical processors)

# Windows
C:\llama-cpp\llama-server.exe ^
  --model models\qwen3.5-35b-a3b.gguf ^
  --host 0.0.0.0 ^
  --port 8080 ^
  --ctx-size 8192 ^
  --threads 8 ^
  --parallel 1

# macOS / Linux
~/llama-cpp/llama-server \
  --model models/qwen3.5-35b-a3b.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  --ctx-size 8192 \
  --threads 8 \
  --parallel 1
```

| Flag | Purpose |
|---|---|
| `--model` | Path to the downloaded GGUF file |
| `--host 0.0.0.0` | Listen on all interfaces (needed for Docker interop if used later) |
| `--port 8080` | Must match `LLM_BASE_URL` in your `.env` |
| `--ctx-size 8192` | Context window in tokens — 8192 is enough for RAG (raise on GPU hosts) |
| `--threads N` | Set to your **physical** core count (e.g., 8 for an 8-core CPU). Using logical/hyperthreaded count may reduce throughput |
| `--parallel 1` | Number of concurrent requests — 1 for single-user CLI use |

You should see output like:

```
main: server is listening on 0.0.0.0:8080
```

**Verify it's working** (optional, from another terminal):

```bash
curl http://localhost:8080/v1/models
```

This should return JSON with the model name.

##### Step 5 — Configure and run Loominary

Ensure your `.env` has these values:

```ini
QDRANT_URL=http://localhost:6333    # will auto-fallback to embedded if unreachable
LLM_BASE_URL=http://localhost:8080
```

Then, in your **original terminal** (not the one running llama-server):

```bash
uv run main.py
```

If you have existing transcripts, select **Reindex all transcripts** first to build the vector index. Then select **Chat with library** to start asking questions.

**What happens with Qdrant:** Loominary tries to connect to `QDRANT_URL`. If no Qdrant server is running, it prints a notice and automatically falls back to embedded file-based storage at `data/qdrant_local/`. No data is lost — the embedded database persists across runs.

```
Qdrant server at http://localhost:6333 is unreachable — falling back to local storage at data\qdrant_local
```

---

#### Option B — Docker Compose (airgapped / production)

**When to use:** Airgapped environments, team deployments, persistent server setup, or when you want everything containerized with no local installs.

This runs three services in Docker: Qdrant (vector DB), llama.cpp (LLM server), and the Loominary app.

**Prerequisites:** Docker and Docker Compose.

**Important:** The initial build downloads ~24 GB of model weights (BGE-M3 + Qwen3.5 GGUF) and bakes them into the images. After building, the images are fully self-contained and need no network access.

```bash
# Build all images (one-time, ~24 GB download)
docker compose build

# Start all services
docker compose up -d

# Run the Loominary CLI
docker compose exec -it loominary uv run python main.py
```

**GPU hosts** — use the GPU override for faster LLM inference and larger context:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

This adds NVIDIA GPU passthrough to the LLM container and enables CUDA for embeddings.

**Services:**

| Service | Image | Port | Purpose |
|---|---|---|---|
| `qdrant` | `qdrant/qdrant:v1.12.6` | 6333, 6334 | Vector database (persistent volume) |
| `llm` | Custom (llama.cpp + GGUF) | 8080 | LLM generation (OpenAI-compatible API) |
| `loominary` | Custom (app + BGE-M3) | — | The CLI app |

**Stopping:**

```bash
docker compose down          # stop services, keep data
docker compose down -v       # stop and delete Qdrant storage volume
```

---

### Chat example

```
? What would you like to do? Chat with library

Library loaded: 847 chunks across your transcripts.
Type your question, or 'quit' to exit.

? You: What did Jensen Huang say about scaling laws?

Jensen discussed how scaling laws continue to hold but are shifting from
purely pre-training compute to inference-time compute [1]. He emphasized
that NVIDIA's architecture is designed to scale across both dimensions [3],
and that the industry is moving toward "test-time compute" where models
think longer rather than just training longer [2].

  [1] (Lex Fridman Podcast — Jensen Huang: NVIDIA, 2026-03-23)
  [2] (Lex Fridman Podcast — Jensen Huang: NVIDIA, 2026-03-23)
  [3] (Lex Fridman Podcast — Jensen Huang: NVIDIA, 2026-03-23)
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

### RAG / Vector Store

| Variable | Default | Description |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | Qdrant server URL. If unreachable, automatically falls back to embedded local storage at `data/qdrant_local/` |
| `QDRANT_COLLECTION` | `loominary_rag` | Qdrant collection name |
| `EMBED_MODEL_PATH` | `BAAI/bge-m3` | HuggingFace model ID or local path to BGE-M3 weights. In Docker this is baked to `/models/bge-m3` |
| `EMBED_DEVICE` | `auto` | `auto` (detect GPU), `cpu`, or `cuda` |
| `SPARSE_MODEL_NAME` | `Qdrant/bm25` | FastEmbed sparse model for BM25 |
| `RAG_CHUNK_TOKENS` | `512` | Tokens per chunk |
| `RAG_CHUNK_OVERLAP` | `64` | Overlap tokens between chunks |
| `RAG_TOP_K` | `8` | Number of hybrid search candidates |
| `RAG_CONTEXT_K` | `5` | Number of chunks injected into the LLM prompt |

### LLM (llama.cpp server)

| Variable | Default | Description |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:8080` | OpenAI-compatible endpoint (llama.cpp server, vLLM, Ollama, etc.) |
| `LLM_MODEL` | `qwen3.5-35b-a3b` | Model name sent in the API request |
| `LLM_CTX_SIZE` | `8192` | Context window (set higher on GPU hosts) |
| `LLM_TEMPERATURE` | `0.2` | Generation temperature |
| `LLM_MAX_TOKENS` | `4096` | Max response tokens (includes reasoning + answer) |

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
├── main.py                        # Entry point — mode selector
├── pyproject.toml                 # Dependencies (uv-managed)
├── .env                           # Your secrets (gitignored)
├── .env.example                   # Template
├── Dockerfile                     # App image (bakes BGE-M3 weights)
├── docker-compose.yml             # Qdrant + llama.cpp + app
├── docker-compose.gpu.yml         # GPU override
├── meetings/                      # YAML configs for automatic meeting mode
│   └── my-meeting.yaml
│
├── docker/
│   └── llm.Dockerfile             # llama.cpp server + Qwen3.5 GGUF
│
├── loominary/
│   ├── config.py                  # Environment loading + validation
│   ├── cli.py                     # Podcast interactive menus + workflow
│   │
│   ├── rag/                       # RAG chatbot pipeline
│   │   ├── chunker.py             # Fixed-window token splitter (BGE-M3 tokenizer)
│   │   ├── embedder.py            # BGE-M3 dense + FastEmbed BM25 sparse
│   │   ├── qdrant.py              # Client, collection setup, server/local fallback
│   │   ├── indexer.py             # Index files, reindex all, auto-index hook
│   │   ├── retriever.py           # Hybrid search (dense + sparse + RRF fusion)
│   │   ├── chat.py                # LLM streaming client + grounded prompt
│   │   └── cli.py                 # Chat REPL + reindex command
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
│   │   ├── schema.py              # CREATE TABLE statements
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
│   ├── qdrant_local/              # Embedded Qdrant storage (when no server)
│   ├── transcripts/               # Output .txt files — podcast_ and meeting_ prefixed
│   └── recordings/                # Meeting screen recordings
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

**`Qdrant server at http://localhost:6333 is unreachable — falling back to local storage`**
This is informational, not an error. Loominary automatically falls back to embedded file-based Qdrant at `data/qdrant_local/`. If you want to use a Qdrant server instead, either start one via `docker run -d -p 6333:6333 qdrant/qdrant:v1.12.6` or use `docker compose up`.

**`httpx.ConnectError` when using "Chat with library"**
The LLM server (llama.cpp) isn't running. Start it with `llama-server --model <path-to-gguf> --host 0.0.0.0 --port 8080 --ctx-size 8192`, or run the full stack with `docker compose up`.

**Chat says "The vector index is empty"**
You need to index your transcripts first. Select **Reindex all transcripts** from the main menu. This reads all transcript files from DuckDB, chunks them, embeds them, and stores them in Qdrant.

---

## Legal Disclaimer

This project is unofficial and is not affiliated with, authorized by, or endorsed by Spotify or Google. It is intended for personal, non-commercial educational use only. Users are responsible for complying with the Terms of Service of all platforms used and for respecting the intellectual property rights of podcast creators and meeting participants.
