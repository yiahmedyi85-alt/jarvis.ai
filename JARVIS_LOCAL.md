# JARVIS local desktop mode

The new local-first HUD is launched with `python jarvis_desktop.py`.

## Setup

1. Create a virtual environment.
2. Install `requirements.txt`.
3. Copy `.env.example` to `.env` and set `GEMINI_API_KEY` if cloud AI is wanted.
4. Run `python jarvis_desktop.py`.

The local API binds to `127.0.0.1` only. System metrics are read from the current computer. The HUD reports failures instead of showing simulated success.

The existing JARVIS modules remain in the repository; the new `jarvis_local` package is the incremental local-first shell and is designed so more providers and tools can be added without replacing the existing project.

## Security

Never commit `config/api_keys.json`, private keys, or `.env` files. Any credential previously exposed in Git history should be revoked and replaced.

Destructive or sensitive automation should remain behind explicit confirmation and an allowlist before being enabled.
