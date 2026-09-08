from __future__ import annotations

import base64
import os
from typing import Any

from google import genai
from google.genai import types

LIVE_MODEL = os.getenv("JARVIS_LIVE_MODEL", "gemini-3.1-flash-live-preview")
VOICE_NAME = os.getenv("JARVIS_VOICE", "Charon")


async def run_live_voice(client_ws: Any) -> None:
    """Bridge browser PCM audio <-> Gemini Live native audio."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        await client_ws.send_json({"type": "error", "message": "GEMINI_API_KEY is not configured."})
        return

    client = genai.Client(api_key=key)
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription={},
        output_audio_transcription={},
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=VOICE_NAME,
                )
            )
        ),
        system_instruction=(
            "You are JARVIS, a polished local desktop AI assistant. "
            "Speak naturally and concisely. Address the user as sir when speaking English. "
            "Do not claim a computer action happened unless the local assistant confirms it."
        ),
    )

    await client_ws.send_json({
        "type": "ready",
        "model": LIVE_MODEL,
        "voice": VOICE_NAME,
        "input_rate": 16000,
        "output_rate": 24000,
    })

    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            async def browser_to_gemini() -> None:
                while True:
                    message = await client_ws.receive()
                    if message.get("type") == "websocket.disconnect":
                        return
                    raw = message.get("bytes")
                    if raw:
                        await session.send_realtime_input(
                            audio=types.Blob(data=raw, mime_type="audio/pcm;rate=16000")
                        )
                        continue
                    text = message.get("text")
                    if not text:
                        continue
                    try:
                        import json
                        payload = json.loads(text)
                    except Exception:
                        continue
                    if payload.get("type") == "text" and str(payload.get("text", "")).strip():
                        await session.send_realtime_input(text=str(payload["text"]))
                    elif payload.get("type") == "stop":
                        return

            async def gemini_to_browser() -> None:
                async for response in session.receive():
                    server_content = getattr(response, "server_content", None)
                    if not server_content:
                        continue

                    output_tx = getattr(server_content, "output_transcription", None)
                    if output_tx:
                        text = getattr(output_tx, "text", None)
                        if text:
                            await client_ws.send_json({"type": "transcript", "role": "assistant", "text": text})

                    input_tx = getattr(server_content, "input_transcription", None)
                    if input_tx:
                        text = getattr(input_tx, "text", None)
                        if text:
                            await client_ws.send_json({"type": "transcript", "role": "user", "text": text})

                    model_turn = getattr(server_content, "model_turn", None)
                    if model_turn:
                        for part in (getattr(model_turn, "parts", None) or []):
                            inline = getattr(part, "inline_data", None)
                            audio_data = getattr(inline, "data", None) if inline else None
                            if audio_data:
                                if isinstance(audio_data, str):
                                    encoded = audio_data
                                else:
                                    encoded = base64.b64encode(audio_data).decode("ascii")
                                await client_ws.send_json({"type": "audio", "data": encoded, "sample_rate": 24000})
                                await client_ws.send_json({"type": "state", "value": "speaking"})

                    if getattr(server_content, "turn_complete", False):
                        await client_ws.send_json({"type": "state", "value": "listening"})
                        await client_ws.send_json({"type": "turn_complete"})

            sender = __import__("asyncio").create_task(browser_to_gemini())
            receiver = __import__("asyncio").create_task(gemini_to_browser())
            done, pending = await __import__("asyncio").wait(
                {sender, receiver}, return_when=__import__("asyncio").FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            for task in done:
                exc = task.exception()
                if exc:
                    raise exc
    except Exception as exc:
        await client_ws.send_json({"type": "error", "message": str(exc)})
