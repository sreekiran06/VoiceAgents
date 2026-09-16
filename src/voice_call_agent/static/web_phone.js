// SK Voice Agents - In-Browser Web Phone (Real-Time Audio Stream Simulator)

(function () {
  // Precompute mu-law decode table to Float32 [-1.0, 1.0]
  const MULAW_DECODE_TABLE = new Float32Array(256);
  for (let i = 0; i < 256; i++) {
    const byte = ~i & 0xff;
    const sign = byte & 0x80 ? -1 : 1;
    const exponent = (byte >> 4) & 0x07;
    const mantissa = byte & 0x0f;
    let sample = ((mantissa << 3) + 0x84) << exponent;
    sample -= 0x84;
    MULAW_DECODE_TABLE[i] = (sign * sample) / 32768.0;
  }

  // Linear PCM sample to 8-bit ITU-T G.711 mu-law
  function pcmToMuLawSample(sample) {
    let pcm = Math.max(-32768, Math.min(32767, Math.floor(sample * 32767)));
    const sign = pcm < 0 ? 0x80 : 0x00;
    if (pcm < 0) pcm = -pcm;
    pcm += 0x84;
    if (pcm > 0x7fff) pcm = 0x7fff;

    let exponent = 7;
    const thresholds = [0x100, 0x200, 0x400, 0x800, 0x1000, 0x2000, 0x4000];
    for (let i = 0; i < thresholds.length; i++) {
      if (pcm < thresholds[i]) {
        exponent = i;
        break;
      }
    }
    const mantissa = (pcm >> (exponent + 3)) & 0x0f;
    return ~(sign | (exponent << 4) | mantissa) & 0xff;
  }

  // Base64 helper for Uint8Array
  function uint8ToBase64(bytes) {
    let binary = "";
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  function base64ToUint8(b64) {
    const binary = atob(b64);
    const len = binary.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  }

  class WebPhone {
    constructor() {
      this.socket = null;
      this.audioContext = null;
      this.micStream = null;
      this.processorNode = null;
      this.callSid = null;
      this.streamSid = null;
      this.isCallActive = false;
      this.callStartTime = null;
      this.timerInterval = null;

      this.playbackScheduleTime = 0;
      this.activeSources = [];

      this.outboundBuffer = [];
      this.initUI();
    }

    initUI() {
      // Create Web Phone modal container
      const container = document.createElement("div");
      container.id = "webphone-modal";
      container.className = "webphone-backdrop hidden";
      container.innerHTML = `
        <div class="webphone-card">
          <div class="webphone-header">
            <div class="webphone-titles">
              <span class="webphone-badge">SK Live Line</span>
              <h3>Interactive AI Voice Call</h3>
            </div>
            <button class="webphone-close" id="webphone-close-btn">×</button>
          </div>

          <div class="webphone-body">
            <div class="webphone-avatar-wrap">
              <div class="webphone-avatar" id="webphone-avatar">
                <span>S</span>
                <div class="webphone-ripple" id="webphone-ripple"></div>
              </div>
              <div class="webphone-name">SK Voice Assistant</div>
              <div class="webphone-lang-tag">Telugu · Hindi · English</div>
              <div class="webphone-timer" id="webphone-timer">00:00</div>
              <div class="webphone-status" id="webphone-status">Ready to connect...</div>
            </div>

            <div class="webphone-waves" id="webphone-waves">
              <i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i>
            </div>

            <p class="webphone-hint">
              Speak into your microphone naturally in <b>Telugu, Hindi, or English</b>. Ask about 2BHK flats, book a doctor consultation, or request course details.
            </p>
          </div>

          <div class="webphone-footer">
            <button class="btn-phone btn-phone-start" id="webphone-action-btn">
              <span class="phone-icon">📞</span> Start Call
            </button>
          </div>
        </div>
      `;
      document.body.appendChild(container);

      // Bind events
      document.getElementById("webphone-close-btn").addEventListener("click", () => this.hide());
      document.getElementById("webphone-action-btn").addEventListener("click", () => this.toggleCall());
    }

    show() {
      document.getElementById("webphone-modal").classList.remove("hidden");
    }

    hide() {
      if (this.isCallActive) {
        this.endCall();
      }
      document.getElementById("webphone-modal").classList.add("hidden");
    }

    async toggleCall() {
      if (this.isCallActive) {
        this.endCall();
      } else {
        await this.startCall();
      }
    }

    async startCall() {
      const statusEl = document.getElementById("webphone-status");
      const actionBtn = document.getElementById("webphone-action-btn");
      const avatarEl = document.getElementById("webphone-avatar");

      statusEl.textContent = "Accessing microphone...";

      try {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        if (this.audioContext.state === "suspended") {
          await this.audioContext.resume();
        }

        this.micStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

        statusEl.textContent = "Connecting to voice engine...";

        // Setup WebSocket
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/telephony/media-stream`;
        this.socket = new WebSocket(wsUrl);

        this.callSid = "CA_WEB_" + Math.random().toString(36).substring(2, 9);
        this.streamSid = "MZ_WEB_" + Math.random().toString(36).substring(2, 9);

        this.socket.onopen = () => {
          this.isCallActive = true;
          actionBtn.className = "btn-phone btn-phone-end";
          actionBtn.innerHTML = `<span class="phone-icon">✕</span> End Call`;
          avatarEl.classList.add("in-call");
          statusEl.textContent = "Call Connected. Speak now!";

          // Start call timer
          this.callStartTime = Date.now();
          this.timerInterval = setInterval(() => this.updateTimer(), 1000);

          // 1. Send Twilio connected event
          this.socket.send(
            JSON.stringify({
              event: "connected",
              protocol: "Call",
              version: "1.0.0",
            })
          );

          // 2. Send Twilio start event
          this.socket.send(
            JSON.stringify({
              event: "start",
              streamSid: this.streamSid,
              start: {
                streamSid: this.streamSid,
                callSid: this.callSid,
                tracks: ["inbound"],
                mediaFormat: {
                  encoding: "audio/x-mulaw",
                  sampleRate: 8000,
                  channels: 1,
                },
              },
            })
          );

          // 3. Begin microphone sampling & streaming
          this.setupMicrophoneProcessor();
        };

        this.socket.onmessage = (event) => {
          const data = JSON.parse(event.data);
          this.handleServerEvent(data);
        };

        this.socket.onclose = () => {
          if (this.isCallActive) {
            this.endCall();
          }
        };

        this.socket.onerror = (err) => {
          console.error("WebPhone socket error:", err);
          statusEl.textContent = "Connection error.";
          this.endCall();
        };
      } catch (err) {
        console.error("WebPhone error:", err);
        statusEl.textContent = "Microphone access denied or audio error.";
      }
    }

    setupMicrophoneProcessor() {
      const source = this.audioContext.createMediaStreamSource(this.micStream);
      const inputSampleRate = this.audioContext.sampleRate;
      const targetSampleRate = 8000;
      const resampleRatio = inputSampleRate / targetSampleRate;

      // Use ScriptProcessor (supported in all standard browsers)
      const bufferSize = 2048;
      this.processorNode = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

      this.processorNode.onaudioprocess = (e) => {
        if (!this.isCallActive || !this.socket || this.socket.readyState !== WebSocket.OPEN) {
          return;
        }

        const inputData = e.inputBuffer.getChannelData(0);

        // Simple downsampling to 8000 Hz
        for (let i = 0; i < inputData.length; i += resampleRatio) {
          const sample = inputData[Math.floor(i)];
          const mulawByte = pcmToMuLawSample(sample);
          this.outboundBuffer.push(mulawByte);

          // Once we accumulate 160 bytes (20ms at 8kHz), transmit frame!
          if (this.outboundBuffer.length >= 160) {
            const chunk = new Uint8Array(this.outboundBuffer.slice(0, 160));
            this.outboundBuffer = this.outboundBuffer.slice(160);

            const payloadB64 = uint8ToBase64(chunk);
            this.socket.send(
              JSON.stringify({
                event: "media",
                streamSid: this.streamSid,
                media: {
                  payload: payloadB64,
                },
              })
            );
          }
        }
      };

      const muteNode = this.audioContext.createGain();
      muteNode.gain.value = 0;
      source.connect(this.processorNode);
      this.processorNode.connect(muteNode);
      muteNode.connect(this.audioContext.destination);
    }

    handleServerEvent(data) {
      const statusEl = document.getElementById("webphone-status");
      const wavesEl = document.getElementById("webphone-waves");

      if (data.event === "clear") {
        // Interruption: immediately cancel currently scheduled audio playback!
        statusEl.textContent = "Caller speaking (agent paused)...";
        this.stopAllAudio();
        this.playbackScheduleTime = this.audioContext.currentTime;
      } else if (data.event === "media") {
        statusEl.textContent = "AI Agent is speaking...";
        wavesEl.classList.add("active");

        const payloadB64 = data.media && data.media.payload;
        if (payloadB64) {
          this.playMuLawChunk(payloadB64);
        }
      } else if (data.event === "mark") {
        setTimeout(() => {
          if (this.isCallActive) {
            statusEl.textContent = "Listening to you...";
            wavesEl.classList.remove("active");
          }
        }, 500);
      }
    }

    playMuLawChunk(b64Payload) {
      if (!this.audioContext) return;

      const mulawBytes = base64ToUint8(b64Payload);
      const numSamples = mulawBytes.length;

      // Decode mu-law to Float32 audio buffer at 8000 Hz
      const audioBuffer = this.audioContext.createBuffer(1, numSamples, 8000);
      const channelData = audioBuffer.getChannelData(0);

      for (let i = 0; i < numSamples; i++) {
        channelData[i] = MULAW_DECODE_TABLE[mulawBytes[i]];
      }

      const sourceNode = this.audioContext.createBufferSource();
      sourceNode.buffer = audioBuffer;
      sourceNode.connect(this.audioContext.destination);

      const now = this.audioContext.currentTime;
      const startTime = Math.max(now, this.playbackScheduleTime);
      sourceNode.start(startTime);

      this.playbackScheduleTime = startTime + audioBuffer.duration;
      this.activeSources.push(sourceNode);

      sourceNode.onended = () => {
        const index = this.activeSources.indexOf(sourceNode);
        if (index > -1) this.activeSources.splice(index, 1);
      };
    }

    stopAllAudio() {
      for (const node of this.activeSources) {
        try {
          node.stop();
        } catch (e) {
          // Already stopped
        }
      }
      this.activeSources = [];
    }

    updateTimer() {
      if (!this.callStartTime) return;
      const elapsed = Math.floor((Date.now() - this.callStartTime) / 1000);
      const mins = String(Math.floor(elapsed / 60)).padStart(2, "0");
      const secs = String(elapsed % 60).padStart(2, "0");
      document.getElementById("webphone-timer").textContent = `${mins}:${secs}`;
    }

    endCall() {
      this.isCallActive = false;

      if (this.timerInterval) {
        clearInterval(this.timerInterval);
        this.timerInterval = null;
      }

      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        try {
          this.socket.send(
            JSON.stringify({
              event: "stop",
              streamSid: this.streamSid,
            })
          );
          this.socket.close();
        } catch (e) {
          // ignore
        }
      }

      this.stopAllAudio();

      if (this.processorNode) {
        this.processorNode.disconnect();
        this.processorNode = null;
      }

      if (this.micStream) {
        this.micStream.getTracks().forEach((t) => t.stop());
        this.micStream = null;
      }

      const statusEl = document.getElementById("webphone-status");
      const actionBtn = document.getElementById("webphone-action-btn");
      const avatarEl = document.getElementById("webphone-avatar");
      const wavesEl = document.getElementById("webphone-waves");

      statusEl.textContent = "Call ended.";
      wavesEl.classList.remove("active");
      avatarEl.classList.remove("in-call");
      actionBtn.className = "btn-phone btn-phone-start";
      actionBtn.innerHTML = `<span class="phone-icon">📞</span> Start Call`;
    }
  }

  // Export singleton on window
  window.webPhone = new WebPhone();
})();
