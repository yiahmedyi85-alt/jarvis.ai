from __future__ import annotations
import asyncio,base64,os
from google import genai
from google.genai import types
LIVE_MODEL=os.getenv('JARVIS_LIVE_MODEL','gemini-3.1-flash-live-preview')
VOICE_NAME=os.getenv('JARVIS_VOICE','Charon')
def _language_instruction(text:str)->str:return 'Arabic' if any('\u0600'<=ch<='\u06ff' for ch in text) else 'English'
async def run_live_voice(client_ws):
 key=os.getenv('GEMINI_API_KEY')
 if not key:return await client_ws.send_json({'type':'error','message':'GEMINI_API_KEY is not configured.'})
 client=genai.Client(api_key=key)
 try:
  from .orchestrator import JarvisAgent
  agent=JarvisAgent()
 except Exception: agent=None
 config=types.LiveConnectConfig(response_modalities=['AUDIO'],input_audio_transcription={},output_audio_transcription={},speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME))),system_instruction=('You are JARVIS, a polished local desktop AI assistant. Speak naturally and concisely. Support Arabic and English. Always answer in the same language as the user\'s latest message unless asked to switch. For computer actions, do not claim success unless the local agent reports success.'),context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()))
 await client_ws.send_json({'type':'ready','model':LIVE_MODEL,'voice':VOICE_NAME,'input_rate':16000,'output_rate':24000,'languages':['ar','en']})
 try:
  async with client.aio.live.connect(model=LIVE_MODEL,config=config) as session:
   user_parts=[]
   async def browser_to_gemini():
    while True:
     m=await client_ws.receive()
     if m.get('type')=='websocket.disconnect':return
     if m.get('bytes'):await session.send_realtime_input(audio=types.Blob(data=m['bytes'],mime_type='audio/pcm;rate=16000'));continue
     txt=m.get('text')
     if not txt:continue
     try:p=__import__('json').loads(txt)
     except Exception:continue
     if p.get('type')=='text' and str(p.get('text','')).strip():await session.send_realtime_input(text=str(p['text']))
     elif p.get('type')=='stop':return
   async def execute_after_turn(text):
    if not agent or not text.strip():return
    try:r=await asyncio.to_thread(agent.handle,text.strip(),False)
    except Exception as exc:r={'state':'failed','tool':'orchestrator','message':str(exc)}
    if str(r.get('tool',''))=='llm.chat':return
    status=r.get('message') or r.get('data') or 'The local action completed.'
    await session.send_client_content(turns={'role':'user','parts':[{'text':f"Local desktop action result: {status}. Reply briefly in {_language_instruction(text)} and confirm what happened. Do not mention internal tools."}]},turn_complete=True)
   async def gemini_to_browser():
    nonlocal user_parts
    async for response in session.receive():
     sc=getattr(response,'server_content',None)
     if not sc:continue
     ot=getattr(sc,'output_transcription',None)
     if ot and getattr(ot,'text',None):await client_ws.send_json({'type':'transcript','role':'assistant','text':ot.text})
     it=getattr(sc,'input_transcription',None)
     if it and getattr(it,'text',None):user_parts.append(it.text);await client_ws.send_json({'type':'transcript','role':'user','text':it.text})
     mt=getattr(sc,'model_turn',None)
     if mt:
      for part in getattr(mt,'parts',None) or []:
       inline=getattr(part,'inline_data',None);data=getattr(inline,'data',None) if inline else None
       if data:
        enc=data if isinstance(data,str) else base64.b64encode(data).decode('ascii');await client_ws.send_json({'type':'audio','data':enc,'sample_rate':24000});await client_ws.send_json({'type':'state','value':'speaking'})
     if getattr(sc,'turn_complete',False):
      text=' '.join(user_parts).strip();user_parts=[]
      if text:await execute_after_turn(text)
      await client_ws.send_json({'type':'state','value':'listening'});await client_ws.send_json({'type':'turn_complete'})
   a=asyncio.create_task(browser_to_gemini());b=asyncio.create_task(gemini_to_browser());done,pending=await asyncio.wait({a,b},return_when=asyncio.FIRST_COMPLETED)
   for t in pending:t.cancel()
   for t in done:
    exc=t.exception()
    if exc:raise exc
 except Exception as exc:await client_ws.send_json({'type':'error','message':str(exc)})