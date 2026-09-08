(() => {
  const mic = document.getElementById('mic');
  const core = document.getElementById('core');
  const stateEl = document.getElementById('state');
  const subEl = document.getElementById('sub');
  if (!mic) return;

  // Remove the old click handler from the static UI and replace the button.
  const cleanMic = mic.cloneNode(true);
  mic.replaceWith(cleanMic);

  let ws = null;
  let stream = null;
  let audioContext = null;
  let inputContext = null;
  let processor = null;
  let source = null;
  let gain = null;
  let listening = false;
  let nextPlayTime = 0;

  function setState(value, subtitle) {
    const v = String(value || 'idle').toLowerCase();
    if (core) core.dataset.state = v;
    if (stateEl) stateEl.textContent = value ? String(value).toUpperCase() : 'Idle';
    if (subEl && subtitle) subEl.textContent = subtitle;
  }

  function bytesToBase64(bytes) {
    let binary = '';
    const step = 0x8000;
    for (let i = 0; i < bytes.length; i += step) {
      binary += String.fromCharCode(...bytes.subarray(i, i + step));
    }
    return btoa(binary);
  }

  function base64ToBytes(text) {
    const binary = atob(text);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  function downsampleTo16k(float32, inputRate) {
    if (inputRate === 16000) return float32;
    const ratio = inputRate / 16000;
    const outLength = Math.max(1, Math.round(float32.length / ratio));
    const out = new Int16Array(outLength);
    let offset = 0;
    for (let i = 0; i < outLength; i++) {
      const next = Math.min(float32.length, Math.round((i + 1) * ratio));
      let sum = 0, count = 0;
      while (offset < next && offset < float32.length) {
        sum += float32[offset++];
        count++;
      }
      const sample = Math.max(-1, Math.min(1, count ? sum / count : 0));
      out[i] = sample < 0 ? sample * 32768 : sample * 32767;
    }
    return out;
  }

  function floatToPCM16(float32, inputRate) {
    const maybe = downsampleTo16k(float32, inputRate);
    if (maybe instanceof Int16Array) return maybe;
    const out = new Int16Array(maybe.length);
    for (let i = 0; i < maybe.length; i++) {
      const s = Math.max(-1, Math.min(1, maybe[i]));
      out[i] = s < 0 ? s * 32768 : s * 32767;
    }
    return out;
  }

  function playPCM16(base64, sampleRate = 24000) {
    const bytes = base64ToBytes(base64);
    const samples = new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2));
    if (!audioContext) audioContext = new AudioContext({ sampleRate: sampleRate });
    if (audioContext.state === 'suspended') audioContext.resume().catch(() => {});
    const buffer = audioContext.createBuffer(1, samples.length, sampleRate);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 32768;
    const node = audioContext.createBufferSource();
    node.buffer = buffer;
    node.connect(audioContext.destination);
    const start = Math.max(audioContext.currentTime + 0.02, nextPlayTime);
    node.start(start);
    nextPlayTime = start + buffer.duration;
    node.onended = () => {
      if (listening && audioContext && audioContext.currentTime >= nextPlayTime - 0.03) {
        setState('Listening', 'Speak naturally — I\'m listening.');
      }
    };
  }

  async function stopVoice(sendStop = true) {
    listening = false;
    if (sendStop && ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send(JSON.stringify({ type: 'stop' })); } catch (_) {}
    }
    if (processor) { try { processor.disconnect(); } catch (_) {} processor = null; }
    if (source) { try { source.disconnect(); } catch (_) {} source = null; }
    if (gain) { try { gain.disconnect(); } catch (_) {} gain = null; }
    if (inputContext) { try { await inputContext.close(); } catch (_) {} inputContext = null; }
    if (stream) {
      for (const track of stream.getTracks()) track.stop();
      stream = null;
    }
    if (ws) {
      try { ws.close(); } catch (_) {}
      ws = null;
    }
    cleanMic.textContent = '♩';
    cleanMic.title = 'Voice input';
    setState('Idle', 'Speak or type your request');
  }

  async function startVoice() {
    if (listening) return;
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Microphone access is not supported by this desktop web view.');
      }
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });

      const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
      ws = new WebSocket(`${protocol}://${location.host}/api/live`);
      ws.binaryType = 'arraybuffer';

      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('Voice connection timed out.')), 10000);
        ws.addEventListener('open', () => { clearTimeout(timer); resolve(); }, { once: true });
        ws.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Could not connect to Gemini Live.')); }, { once: true });
      });

      listening = true;
      cleanMic.textContent = '■';
      cleanMic.title = 'Stop voice conversation';
      setState('Listening', 'Speak naturally — I\'m listening.');

      ws.onmessage = (event) => {
        let msg;
        try { msg = JSON.parse(event.data); } catch (_) { return; }
        if (msg.type === 'ready') {
          setState('Listening', `Voice online — ${msg.voice || 'Charon'}`);
        } else if (msg.type === 'audio') {
          setState('Speaking', 'JARVIS is speaking…');
          playPCM16(msg.data, Number(msg.sample_rate) || 24000);
        } else if (msg.type === 'transcript') {
          // Keep the current UI responsive without replacing its existing chat rendering.
          if (msg.role === 'user' && stateEl) stateEl.textContent = 'Listening';
          if (msg.role === 'assistant' && subEl) subEl.textContent = msg.text;
        } else if (msg.type === 'state') {
          setState(msg.value, msg.value === 'speaking' ? 'JARVIS is speaking…' : 'Speak naturally — I\'m listening.');
        } else if (msg.type === 'error') {
          setState('Error', msg.message || 'Voice connection failed.');
          stopVoice(false).catch(() => {});
        }
      };
      ws.onclose = () => {
        if (listening) stopVoice(false).catch(() => {});
      };

      inputContext = new AudioContext();
      if (inputContext.state === 'suspended') await inputContext.resume();
      source = inputContext.createMediaStreamSource(stream);
      processor = inputContext.createScriptProcessor(4096, 1, 1);
      gain = inputContext.createGain();
      gain.gain.value = 0;
      source.connect(processor);
      processor.connect(gain);
      gain.connect(inputContext.destination);

      processor.onaudioprocess = (event) => {
        if (!listening || !ws || ws.readyState !== WebSocket.OPEN) return;
        const input = event.inputBuffer.getChannelData(0);
        const pcm = floatToPCM16(input, inputContext.sampleRate);
        const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
        // Send as JSON so the FastAPI websocket can receive it consistently across Chromium builds.
        try {
          ws.send(JSON.stringify({ type: 'audio', data: bytesToBase64(bytes) }));
        } catch (_) {}
      };
    } catch (err) {
      await stopVoice(false);
      setState('Error', err?.message || 'Microphone unavailable.');
    }
  }

  cleanMic.addEventListener('click', () => {
    if (listening) stopVoice();
    else startVoice();
  });
})();
