from __future__ import annotations
import asyncio, base64, json, os
from typing import Any
from google import genai
from google.genai import types
from .desktop_events import set_state

LIVE_MODEL=os.getenv("JARVIS_LIVE_MODEL","gemini-3.1-flash-live-preview")
VOICE_NAME=os.getenv("JARVIS_VOICE","Charon")

async def run_live_voice(client_ws:Any)->None:
    key=os.getenv("GEMINI_API_KEY")
    if not key:
        await client_ws.send_json({"type":"error","message":"GEMINI_API_KEY is not configured."}); return
    client=genai.Client(api_key=key)
    config=types.LiveConnectConfig(
        response_modalities=["AUDIO"], input_audio_transcription={}, output_audio_transcription={},
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME))),
        system_instruction="You are JARVIS, a polished local desktop AI assistant. Speak naturally and concisely. Address the user as sir when speaking English. Do not claim a computer action happened unless the local assistant confirms it."
    )
    try:
        async with client.aio.live.connect(model=LIVE_MODEL,config=config) as session:
            await client_ws.send_json({"type":"ready","model":LIVE_MODEL,"voice":VOICE_NAME,"input_rate":16000,"output_rate":24000}); set_state(voice="listening",message="Voice online")
            async def browser_to_gemini():
                while True:
                    message=await client_ws.receive()
                    if message.get("type")=="websocket.disconnect": return
                    raw=message.get("bytes")
                    if raw:
                        await session.send_realtime_input(audio=types.Blob(data=raw,mime_type="audio/pcm;rate=16000")); continue
                    text=message.get("text")
                    if not text: continue
                    try: payload=json.loads(text)
                    except Exception: continue
                    kind=payload.get("type")
                    if kind=="audio" and payload.get("data"):
                        await session.send_realtime_input(audio=types.Blob(data=base64.b64decode(payload["data"]),mime_type="audio/pcm;rate=16000"))
                    elif kind=="text" and str(payload.get("text"," ")).strip(): await session.send_realtime_input(text=str(payload["text"]))
                    elif kind=="stop": return
            async def gemini_to_browser():
                async for response in session.receive():
                    sc=getattr(response,"server_content",None)
                    if not sc: continue
                    input_tx=getattr(sc,"input_transcription",None)
                    if input_tx and getattr(input_tx,"text",None): await client_ws.send_json({"type":"transcript","role":"user","text":input_tx.text})
                    output_tx=getattr(sc,"output_transcription",None)
                    if output_tx and getattr(output_tx,"text",None): await client_ws.send_json({"type":"transcript","role":"assistant","text":output_tx.text})
                    mt=getattr(sc,"model_turn",None)
                    if mt:
                        for part in (getattr(mt,"parts",None) or []):
                            inline=getattr(part,"inline_data",None); data=getattr(inline,"data",None) if inline else None
                            if data:
                                encoded=data if isinstance(data,str) else base64.b64encode(data).decode("ascii")
                                await client_ws.send_json({"type":"audio","data":encoded,"sample_rate":24000}); await client_ws.send_json({"type":"state","value":"speaking"}); set_state(voice="speaking",message="JARVIS is speaking")
                    if getattr(sc,"turn_complete",False): await client_ws.send_json({"type":"state","value":"listening"}); set_state(voice="listening",message="Listening")
            a=asyncio.create_task(browser_to_gemini()); b=asyncio.create_task(gemini_to_browser()); done,pending=await asyncio.wait({a,b},return_when=asyncio.FIRST_COMPLETED)
            for t in pending:t.cancel()
            for t in done:
                exc=t.exception()
                if exc:raise exc
    except Exception as exc:
        set_state(voice="error",message=str(exc))
        try: await client_ws.send_json({"type":"error","message":str(exc)})
        except Exception: pass