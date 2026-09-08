from __future__ import annotations

import asyncio
import base64
import os
from typing import Any

from google import genai
from google.genai import types

LIVE_MODEL = os.getenv("JARVIS_LIVE_MODEL", "gemini-3.1-flash-live-preview")
VOICE_NAME = os.getenv("JARVIS_VOICE", "Charon")


def _language_instruction(text: str) -> str:
    has_arabic = any("\u0600" <= ch <= "\u06ff" for ch in text)
    return "Arabic" if has_arabic else "English"


async def run_live_voice(client_ws: Any) -> None:
    """Bridge browser PCM audio <-> Gemini Live and execute local desktop commands."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        await client_ws.send_json({"type": "error", "message": "GEMINI_API_KEY is not configured."})
        return

    client = genai.Client(api_key=key)
    agent = None
    try:
        from .orchestrator import JarvisAgent
        agent = JarvisAgent()
    except Exception:
        pass

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription={},
        output_audio_transcription={},
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
            )
        ),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=False)
        ),
        system_instruction=(
            "You are JARVIS, a polished local desktop AI assistant. "
            "Speak naturally and concisely. Support Arabic and English. "
            "Always answer in the same language as the user's latest message unless the user asks to switch. "
            "The local JARVIS agent may execute desktop commands after a user turn. "
            "Do not claim that a computer action succeeded unless the local agent reports success. "
            "For ordinary conversation, respond normally."
        ),
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow()
        ),
    )

    await client_ws.send_json({
        "type": "ready",
        "model": LIVE_MODEL,
        "voice": VOICE_NAME,
        "input_rate": 16000,
        "output_rate": 24000,
        "languages": ["ar", "en"],
    })

    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            current_user_text = []

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
                        payload = __import__("json").loads(text)
                    except Exception:
                        continue
                    if payload.get("type") == "text" and str(payload.get("text", "")).strip():
                        await session.send_realtime_input(text=str(payload["text"]))
                    elif payload.get("type") == "stop":
                        return

            async def execute_after_turn(text: str) -> None:
                if not agent or not text.strip():
                    return
                try:
                    result = await asyncio.to_thread(agent.handle, text.strip(), False)
                except Exception as exc:
                    result = {"state": "failed", "tool": "orchestrator", "message": str(exc)}

                tool = str(result.get("tool", ""))
                if tool == "llm.chat":
                    return

                # Feed the trusted local execution result back into the Live session so JARVIS
                # can answer the user with the result in the correct language.
                language = _language_instruction(text)
                status = result.get("message") or result.get("data") or "The local action completed."
                prompt = (
                    f"Local desktop action result: {status}. "
                    f"Reply to the user in {language}, briefly confirm what happened, "
                    "and do not mention internal tools."
                )
                await session.send_client_content(
                    turns={"role": "user", "parts": [{"text": prompt}]},
                    turn_complete=True,
                )

            async def gemini_to_browser() -> None:
                nonlocal current_user_text
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
                            current_user_text.append(text)
                            await client_ws.send_json({"type": "transcript", "role": "user", "text": text})

                    model_turn = getattr(server_content, "model_turn", None)
                    if model_turn:
                        for part in (getattr(model_turn, "parts", None) or []):
                            inline = getattr(part, "inline_data", None)
                            audio_data = getattr(inline, "data", None) if inline else None
                            if audio_data:
                                encoded = audio_data if isinstance(audio_data, str) else base64.b64encode(audio_data).decode("ascii")
                                await client_ws.send_json({"type": "audio", "data": encoded, "sample_rate": 24000})
                                await client_ws.send_json({"type": "state", "value": "speaking"})

                    if getattr(server_content, "turn_complete", False):
                        user_text = " ".join(current_user_text).strip()
                        current_user_text = []
                        if user_text:
                            await execute_after_turn(user_text)
                        await client_ws.send_json({"type": "state", "value": "listening"})
                        await client_ws.send_json({"type": "turn_complete"})

            sender = asyncio.create_task(browser_to_gemini())
            receiver = asyncio.create_task(gemini_to_browser())
            done, pending = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                exc = task.exception()
                if exc:
                    raise exc
    except Exception as exc:
        await client_ws.send_json({"type": "error", "message": str(exc)})