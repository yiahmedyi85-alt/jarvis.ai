# JARVIS local desktop mode

The local-first HUD is launched with `python jarvis_desktop.py` or `start_jarvis.bat` on Windows.

## Included

- Futuristic three-column JARVIS HUD matching the supplied visual direction.
- Animated core states: Idle, Listening, Thinking, Executing, Speaking, Error.
- Typed natural-language requests and browser speech recognition.
- Browser speech synthesis for responses when voice is enabled.
- Live CPU, RAM, disk, GPU (when NVIDIA NVML is available), battery, network, internet, OS, uptime, process count, storage and temperature telemetry when the operating system exposes it.
- Local notes with create, edit/save and delete support.
- Local tasks with due dates and completion state API.
- Local calendar events and today's schedule.
- Local non-sensitive memory with clear control.
- Activity logging for tool operations.
- Safe local tools for opening apps/folders, web search, opening URLs, listing/searching files and creating folders/files.
- Destructive file deletion requires explicit confirmation; arbitrary terminal execution is disabled by default.
- Optional Windows startup control from Settings.
- Provider abstraction with Gemini as the first LLM adapter; API keys are read from environment variables, never from frontend code.

## Setup

1. Create a virtual environment.
2. Install `requirements.txt`.
3. Copy `.env.example` to `.env`.
4. Put your own `GEMINI_API_KEY` in `.env` if cloud AI is wanted. Local tools and monitoring do not require an LLM key.
5. Run `python jarvis_desktop.py`.

The local API binds to `127.0.0.1` only. System metrics come from the current computer. Tool results are reported from the actual operation and failures are surfaced instead of simulated.

## Data and privacy

Local notes, tasks, calendar, memory and activity are stored under `~/.jarvis` by default. Set `JARVIS_DATA_DIR` to change that location. Private files are not uploaded by the local tools.

## Security

Never commit `config/api_keys.json`, private keys, or `.env` files. Credentials previously exposed in Git history should be revoked and replaced. Destructive or sensitive automation must remain behind explicit confirmation and an allowlist.

## Integrations

The current shell is intentionally modular. Calendar, mail, Spotify, maps, richer browser extraction, additional LLMs, wake-word engines and other providers can be added behind adapters without replacing the HUD or local tool layer. If a provider is not configured or a capability is unavailable, JARVIS reports that limitation rather than pretending it completed the operation.
