// speech.js - Audio recording and text-to-speech module

const Status = {
    INACTIVE: 'inactive',
    LISTENING: 'listening',
    RECORDING: 'recording',
    WAITING: 'waiting',
    PROCESSING: 'processing'
};

class MicrophoneInput {
    constructor(updateCallback, sendCallback) {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.updateCallback = updateCallback;
        this.sendCallback = sendCallback;

        this.audioContext = null;
        this.mediaStreamSource = null;
        this.analyserNode = null;
        this._status = Status.INACTIVE;

        this.lastAudioTime = null;
        this.waitingTimer = null;
        this.silenceStartTime = null;
        this.hasStartedRecording = false;
        this.analysisFrame = null;

        this.options = {
            silenceThreshold: 0.05,
            silenceDuration: 1500, // wait 1.5 seconds of silence before stopping
            waitingTimeout: 2000
        };
    }

    get status() {
        return this._status;
    }

    set status(newStatus) {
        if (this._status === newStatus) return;
        const oldStatus = this._status;
        this._status = newStatus;
        
        const micBtn = document.getElementById("btn-mic");
        if (micBtn) {
            micBtn.dataset.status = newStatus;
            if (newStatus === Status.LISTENING || newStatus === Status.RECORDING) {
                micBtn.classList.add("pulse-animation");
            } else {
                micBtn.classList.remove("pulse-animation");
            }
        }

        this.handleStatusChange(oldStatus, newStatus);
    }

    async initialize() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    channelCount: 1
                }
            });

            this.mediaRecorder = new MediaRecorder(stream);
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 &&
                    (this.status === Status.RECORDING || this.status === Status.WAITING)) {
                    this.audioChunks.push(event.data);
                }
            };

            this.setupAudioAnalysis(stream);
            return true;
        } catch (error) {
            console.error('Microphone initialization error:', error);
            alert('Failed to access microphone. Please check permissions.');
            return false;
        }
    }

    setupAudioAnalysis(stream) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        this.mediaStreamSource = this.audioContext.createMediaStreamSource(stream);
        this.analyserNode = this.audioContext.createAnalyser();
        this.analyserNode.fftSize = 2048;
        this.analyserNode.minDecibels = -90;
        this.analyserNode.maxDecibels = -10;
        this.analyserNode.smoothingTimeConstant = 0.85;
        this.mediaStreamSource.connect(this.analyserNode);
    }

    densify(x) {
        return Math.exp(-5 * (1 - x));
    }

    startAudioAnalysis() {
        const analyzeFrame = () => {
            if (this.status === Status.INACTIVE) return;

            const dataArray = new Uint8Array(this.analyserNode.fftSize);
            this.analyserNode.getByteTimeDomainData(dataArray);

            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                const amplitude = (dataArray[i] - 128) / 128;
                sum += amplitude * amplitude;
            }
            const rms = Math.sqrt(sum / dataArray.length);
            const now = Date.now();

            if (rms > this.densify(this.options.silenceThreshold)) {
                this.lastAudioTime = now;
                this.silenceStartTime = null;

                if ((this.status === Status.LISTENING || this.status === Status.WAITING) && !speechTTS.isSpeaking()) {
                    this.status = Status.RECORDING;
                }
            } else if (this.status === Status.RECORDING) {
                if (!this.silenceStartTime) {
                    this.silenceStartTime = now;
                }

                const silenceDuration = now - this.silenceStartTime;
                if (silenceDuration >= this.options.silenceDuration) {
                    this.status = Status.WAITING;
                }
            }

            this.analysisFrame = requestAnimationFrame(analyzeFrame);
        };

        this.analysisFrame = requestAnimationFrame(analyzeFrame);
    }

    stopAudioAnalysis() {
        if (this.analysisFrame) {
            cancelAnimationFrame(this.analysisFrame);
            this.analysisFrame = null;
        }
    }

    handleStatusChange(oldStatus, newStatus) {
        switch (newStatus) {
            case Status.INACTIVE:
                this.stopRecording();
                this.stopAudioAnalysis();
                this.hideTranscribing();
                if (this.waitingTimer) { clearTimeout(this.waitingTimer); this.waitingTimer = null; }
                break;
            case Status.LISTENING:
                this.stopRecording();
                this.audioChunks = [];
                this.hasStartedRecording = false;
                this.silenceStartTime = null;
                this.lastAudioTime = null;
                this.startAudioAnalysis();
                break;
            case Status.RECORDING:
                if (!this.hasStartedRecording && this.mediaRecorder.state !== 'recording') {
                    this.hasStartedRecording = true;
                    this.mediaRecorder.start(500); // chunk every 500ms
                }
                if (this.waitingTimer) { clearTimeout(this.waitingTimer); this.waitingTimer = null; }
                break;
            case Status.WAITING:
                this.waitingTimer = setTimeout(() => {
                    if (this.status === Status.WAITING) {
                        this.status = Status.PROCESSING;
                    }
                }, this.options.waitingTimeout);
                break;
            case Status.PROCESSING:
                this.stopRecording();
                this.showTranscribing();
                this.process();
                break;
        }
    }

    stopRecording() {
        if (this.mediaRecorder?.state === 'recording') {
            this.mediaRecorder.stop();
            this.hasStartedRecording = false;
        }
    }

    showTranscribing() {
        const input = document.getElementById("chat-input");
        if (input) {
            this._origPlaceholder = input.placeholder;
            input.placeholder = "\uD83C\uDFA4 Transcribing...";
            input.classList.add("transcribing");
        }
    }

    hideTranscribing() {
        const input = document.getElementById("chat-input");
        if (input) {
            input.placeholder = this._origPlaceholder || "Send a message to ShibaClaw...";
            input.classList.remove("transcribing");
        }
    }

    async process() {
        if (this.audioChunks.length === 0) {
            this.status = Status.INACTIVE;
            return;
        }

        const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
        const base64 = await this.convertBlobToBase64(audioBlob);

        try {
            if (typeof realtime !== "undefined" && realtime.connected) {
                const response = await realtime.request("transcribe", { audio: base64 }, 30000);
                if (response.error) {
                    console.error("Transcription error:", response.error);
                    alert("Transcription failed: " + response.error);
                } else if (response.text) {
                    const txt = response.text.trim();
                    if (txt) {
                        if (this.updateCallback) this.updateCallback(txt);
                        if (this.sendCallback) this.sendCallback();
                    }
                }
                this.audioChunks = [];
                this.status = Status.INACTIVE;
            } else {
                console.error("WebSocket not connected");
                this.status = Status.INACTIVE;
            }
        } catch (error) {
             console.error("Transcription process error:", error);
             this.status = Status.INACTIVE;
        }
    }

    convertBlobToBase64(audioBlob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
                const base64Data = reader.result.split(',')[1];
                resolve(base64Data);
            };
            reader.onerror = reject;
            reader.readAsDataURL(audioBlob);
        });
    }

    async toggle() {
        if (this.status === Status.INACTIVE) {
            if (!this.mediaRecorder) {
                const ok = await this.initialize();
                if (!ok) return;
            }
            // Need to resume context if blocked by browser policy
            if (this.audioContext && this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }
            this.status = Status.LISTENING;
        } else {
            this.status = Status.INACTIVE;
        }
    }
}

// Minimal TTS wrapper
const speechTTS = {
    synth: window.speechSynthesis,
    enabled: false,

    cleanTextForSpeech(text) {
        let clean = text.replace(/```[\s\S]*?```/g, "");
        clean = clean.replace(/`[^`]*`/g, "");
        clean = clean.replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1");
        clean = clean.replace(/[*_#]+/g, "");
        clean = clean.replace(/([\u2700-\u27BF]|[\uE000-\uF8FF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|[\u2011-\u26FF]|\uD83E[\uDD10-\uDDFF])/g, "");
        clean = clean.replace(/https?:\/\/[^\s]+/g, "link");
        return clean.trim();
    },

    play(text) {
        if (!this.enabled || !this.synth) return;
        const cleaned = this.cleanTextForSpeech(text);
        if (!cleaned) return;
        
        const utterance = new SpeechSynthesisUtterance(cleaned);
        this.synth.speak(utterance);
    },

    stop() {
        if (this.synth && this.synth.speaking) {
            this.synth.cancel();
        }
    },

    isSpeaking() {
        return this.synth && this.synth.speaking;
    }
};

window.speechInstance = null;
window.speechTTS = speechTTS;

function initSpeechControls() {
    const micBtn = document.getElementById("btn-mic");
    const ttsToggle = document.getElementById("tts-toggle");

    if (micBtn) {
        micBtn.addEventListener("click", () => {
            if (!window.speechInstance) {
                window.speechInstance = new MicrophoneInput(
                    (text) => { chatInput.value = text; updateSendButton(); autoResizeInput(); },
                    () => { sendMessage(); }
                );
            }
            window.speechInstance.toggle();
        });
    }

    // Attempt to load TTS user preference from localStorage
    const storedTTS = localStorage.getItem("shibaclaw_tts_enabled");
    if (storedTTS !== null) {
        speechTTS.enabled = storedTTS === "true";
    }

    if (ttsToggle) {
        ttsToggle.checked = speechTTS.enabled;
        ttsToggle.addEventListener("change", (e) => {
            speechTTS.enabled = e.target.checked;
            localStorage.setItem("shibaclaw_tts_enabled", speechTTS.enabled);
            if (!speechTTS.enabled) speechTTS.stop();
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    setTimeout(initSpeechControls, 500);
});
