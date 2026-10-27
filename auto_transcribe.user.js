// ==UserScript==
// @name         Auto-Transcribe QA Assistant (DataPlus / WaveSurfer + Gemini)
// @namespace    https://github.com/
// @version      2.1
// @description  Otomasi transkripsi Full Verbatim untuk DataPlus/WaveSurfer di dalam bdIframe (Jepang & Malaysia) dengan Gemini API
// @match        *://*/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      generativelanguage.googleapis.com
// @connect      blob.core.windows.net
// @connect      *
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    // ==========================================
    // 1. HELPER IFRAME & DOM ACCESS
    // ==========================================
    function getIframe() {
        return document.getElementById('bdIframe');
    }

    function getDoc() {
        const ifr = getIframe();
        if (ifr && (ifr.contentDocument || ifr.contentWindow?.document)) {
            return ifr.contentDocument || ifr.contentWindow.document;
        }
        return document;
    }

    function getIframeWindow() {
        const ifr = getIframe();
        return ifr ? ifr.contentWindow : window;
    }

    // ==========================================
    // 2. AUDIO MANAGEMENT & DECODING (BYPASS CORS)
    // ==========================================
    let cachedAudioUrl = null;
    let cachedAudioBuffer = null;
    let isDecodingAudio = false;
    let audioCtx = null;

    function getAudioContext() {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
        return audioCtx;
    }

    function isAudioUrl(url) {
        if (!url || typeof url !== 'string') return false;
        return url.includes('.wav') || url.includes('.mp3') || url.includes('blob.core.windows.net') || url.includes('datapp');
    }

    function detectAudioUrl() {
        // 1. Cek di iframe window performance
        const ifrWin = getIframeWindow();
        if (ifrWin && ifrWin.performance) {
            const res = ifrWin.performance.getEntriesByType('resource').map(r => r.name);
            const found = res.find(isAudioUrl);
            if (found) return found;
        }
        // 2. Cek di main window performance
        const mainRes = performance.getEntriesByType('resource').map(r => r.name);
        const mainFound = mainRes.find(isAudioUrl);
        if (mainFound) return mainFound;

        // 3. Cek tag audio
        const doc = getDoc();
        const audioTags = Array.from(doc.querySelectorAll('audio')).concat(Array.from(document.querySelectorAll('audio')));
        for (let a of audioTags) {
            if (isAudioUrl(a.src)) return a.src;
        }

        return cachedAudioUrl;
    }

    // Download audio menggunakan GM_xmlhttpRequest agar 100% BEBAS CORS
    function downloadAudioArrayBuffer(url) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: "GET",
                url: url,
                responseType: "arraybuffer",
                headers: {
                    "Accept": "*/*"
                },
                onload: (res) => {
                    if (res.status >= 200 && res.status < 300) {
                        resolve(res.response);
                    } else {
                        reject(new Error(`HTTP ${res.status}: Gagal mengunduh audio`));
                    }
                },
                onerror: (err) => reject(err)
            });
        });
    }

    async function ensureAudioLoaded() {
        if (cachedAudioBuffer) return true;

        // Coba ambil langsung dari WaveSurfer buffer di RAM jika ada
        const ifrWin = getIframeWindow();
        if (ifrWin) {
            const ws = ifrWin.wavesurfer || ifrWin.ws;
            if (ws && ws.backend && ws.backend.buffer) {
                cachedAudioBuffer = ws.backend.buffer;
                updateStatus(`Audio siap dari WaveSurfer RAM (${Math.round(cachedAudioBuffer.duration)}s)`, "#10b981");
                return true;
            }
        }

        let url = detectAudioUrl();
        const manualUrlInput = document.getElementById('qa-audio-url');
        if (!url && manualUrlInput && manualUrlInput.value.trim()) {
            url = manualUrlInput.value.trim();
        }

        if (!url) {
            updateStatus("Link audio belum terdeteksi. Silakan paste link audio di kotak bawah!", "#ef4444");
            return false;
        }

        cachedAudioUrl = url;
        if (manualUrlInput && !manualUrlInput.value) {
            manualUrlInput.value = url;
        }

        updateStatus("Mengunduh file audio (Bypass CORS)...", "#3b82f6");

        try {
            isDecodingAudio = true;
            const arrayBuffer = await downloadAudioArrayBuffer(url);
            const ctx = getAudioContext();
            
            cachedAudioBuffer = await new Promise((resolve, reject) => {
                ctx.decodeAudioData(arrayBuffer, resolve, reject);
            });

            isDecodingAudio = false;
            updateStatus(`Audio siap (${Math.round(cachedAudioBuffer.duration)}s)`, "#10b981");
            return true;
        } catch (err) {
            console.error("[Auto-Transcribe] Gagal decode audio:", err);
            isDecodingAudio = false;
            updateStatus("Gagal decode audio. Pastikan link audio benar.", "#ef4444");
            return false;
        }
    }

    // ==========================================
    // 3. AUDIO SLICER & WAV ENCODER
    // ==========================================
    function sliceAudioBuffer(buffer, startSec, endSec) {
        const ctx = getAudioContext();
        const sampleRate = buffer.sampleRate;
        const startOffset = Math.max(0, Math.floor(startSec * sampleRate));
        const endOffset = Math.min(buffer.length, Math.floor(endSec * sampleRate));
        const frameCount = endOffset - startOffset;

        if (frameCount <= 0) return null;

        const channels = buffer.numberOfChannels;
        const slicedBuffer = ctx.createBuffer(channels, frameCount, sampleRate);
        for (let ch = 0; ch < channels; ch++) {
            const srcData = buffer.getChannelData(ch);
            const destData = slicedBuffer.getChannelData(ch);
            for (let i = 0; i < frameCount; i++) {
                destData[i] = srcData[startOffset + i];
            }
        }
        return slicedBuffer;
    }

    function audioBufferToWav(buffer) {
        const numChannels = buffer.numberOfChannels;
        const sampleRate = buffer.sampleRate;
        const format = 1; // PCM
        const bitDepth = 16;

        let samples;
        if (numChannels === 2) {
            const left = buffer.getChannelData(0);
            const right = buffer.getChannelData(1);
            samples = new Float32Array(left.length + right.length);
            let idx = 0, inIdx = 0;
            while (idx < samples.length) {
                samples[idx++] = left[inIdx];
                samples[idx++] = right[inIdx];
                inIdx++;
            }
        } else {
            samples = buffer.getChannelData(0);
        }

        const bytesPerSample = bitDepth / 8;
        const blockAlign = numChannels * bytesPerSample;
        const wavBuffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
        const view = new DataView(wavBuffer);

        function writeString(offset, str) {
            for (let i = 0; i < str.length; i++) {
                view.setUint8(offset + i, str.charCodeAt(i));
            }
        }

        writeString(0, 'RIFF');
        view.setUint32(4, 36 + samples.length * bytesPerSample, true);
        writeString(8, 'WAVE');
        writeString(12, 'fmt ');
        view.setUint32(16, 16, true);
        view.setUint16(20, format, true);
        view.setUint16(22, numChannels, true);
        view.setUint32(24, sampleRate, true);
        view.setUint32(28, sampleRate * blockAlign, true);
        view.setUint16(32, blockAlign, true);
        view.setUint16(34, bitDepth, true);
        writeString(36, 'data');
        view.setUint32(40, samples.length * bytesPerSample, true);

        let offset = 44;
        for (let i = 0; i < samples.length; i++, offset += 2) {
            let s = Math.max(-1, Math.min(1, samples[i]));
            view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        }
        return wavBuffer;
    }

    function arrayBufferToBase64(buffer) {
        let binary = '';
        const bytes = new Uint8Array(buffer);
        const len = bytes.byteLength;
        for (let i = 0; i < len; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return window.btoa(binary);
    }

    // ==========================================
    // 4. ACTIVE REGION & INPUT FIELD RESOLVER
    // ==========================================
    function getActiveRegion() {
        const doc = getDoc();
        const regionEl = doc.querySelector('.wavesurfer-region.region-current') ||
                         doc.querySelector('.wavesurfer-region.wavesurfer-handle-active') ||
                         doc.querySelector('.wavesurfer-region.region-changed.current-icon') ||
                         doc.querySelector('.wavesurfer-region');

        if (!regionEl) return null;
        const title = regionEl.getAttribute('title');
        if (!title || !title.includes('-')) return null;

        const parts = title.split('-');
        const start = parseFloat(parts[0]);
        const end = parseFloat(parts[1]);
        return { start, end, title, el: regionEl };
    }

    function getTargetInput() {
        const doc = getDoc();

        // 1. Jika pengguna sedang mengklik salah satu input/textarea
        if (doc.activeElement && (doc.activeElement.tagName === 'INPUT' || doc.activeElement.tagName === 'TEXTAREA')) {
            if (doc.activeElement.placeholder && doc.activeElement.placeholder.toLowerCase().includes('select')) {
                // Lewati dropdown
            } else {
                return doc.activeElement;
            }
        }

        // 2. Cari kotak dengan placeholder "Please enter the content" (DataPlus standar)
        const contentInput = doc.querySelector('input[placeholder*="content"], textarea[placeholder*="content"], input[placeholder*="Please enter"], textarea[placeholder*="Please enter"]');
        if (contentInput && contentInput.offsetParent !== null) {
            return contentInput;
        }

        // 3. Cari textarea yang visible
        const visibleTextareas = Array.from(doc.querySelectorAll('textarea, input.el-input__inner, input[type="text"]'))
            .filter(el => el.offsetParent !== null && !((el.placeholder || '').toLowerCase().includes('select')));

        if (visibleTextareas.length > 0) {
            const found = visibleTextareas.find(el => (el.placeholder || '').includes('content') || el.tagName === 'TEXTAREA');
            return found || visibleTextareas[visibleTextareas.length - 1];
        }

        return doc.querySelector('textarea');
    }

    function fillInputValue(inputEl, text) {
        if (!inputEl) {
            alert("Tidak dapat menemukan kotak input di halaman!");
            return;
        }

        inputEl.focus();
        inputEl.value = text;

        // Vue / Element UI Native Value Setter
        const proto = inputEl.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
        const nativeSetter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
        if (nativeSetter) {
            nativeSetter.call(inputEl, text);
        }

        inputEl.dispatchEvent(new Event('input', { bubbles: true }));
        inputEl.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // ==========================================
    // 5. TRANSCRIBE WORKFLOW WITH GEMINI API
    // ==========================================
    async function transcribeSegment() {
        const apiKey = document.getElementById('qa-api-key').value.trim();
        if (!apiKey) {
            alert("Harap masukkan Google Gemini API Key Anda terlebih dahulu di panel!");
            return;
        }

        const region = getActiveRegion();
        if (!region) {
            updateStatus("Pilih salah satu segmen region pada waveform!", "#f59e0b");
            return;
        }

        const audioReady = await ensureAudioLoaded();
        if (!audioReady) return;

        const dur = (region.end - region.start).toFixed(2);
        updateStatus(`Memotong: ${region.start.toFixed(2)}s - ${region.end.toFixed(2)}s (${dur}s)...`, "#3b82f6");

        const slicedBuffer = sliceAudioBuffer(cachedAudioBuffer, region.start, region.end);
        if (!slicedBuffer) {
            updateStatus("Gagal memotong segmen audio!", "#ef4444");
            return;
        }

        const wavData = audioBufferToWav(slicedBuffer);
        const base64Audio = arrayBufferToBase64(wavData);

        const lang = document.getElementById('qa-lang-select').value;
        let promptText = "";

        if (lang === "ja") {
            promptText = "You are a professional transcriptionist for Japanese audio. " +
                         "Strictly transcribe the audio verbatim without omission. " +
                         "Rules:\n" +
                         "1. Include all filler words, hesitations, and sounds exactly as heard: 「えーと」「あのー」「えっ」「まー」「うん」「あ」, etc.\n" +
                         "2. Correctly use Japanese punctuation: Japanese commas (、), periods (。), question marks (？), exclamation marks (！).\n" +
                         "3. Maintain proper spacing if there are natural pauses.\n" +
                         "4. Do NOT translate or summarize. Output ONLY the raw transcription.";
        } else {
            promptText = "You are a professional transcriptionist for Malaysian Malay audio. " +
                         "Strictly transcribe the audio verbatim without omission. " +
                         "Rules:\n" +
                         "1. Include all filler words, hesitations, and sounds: 'um', 'uh', 'a', 'e', 'er', 'aa', 'lah', 'kan', 'tu', etc.\n" +
                         "2. Apply standard punctuation (commas, periods, question marks, exclamation marks) accurately based on speech pauses and intonation.\n" +
                         "3. Maintain proper spacing for pauses.\n" +
                         "4. Do NOT translate or summarize. Output ONLY the raw transcription.";
        }

        updateStatus("Memanggil Gemini AI...", "#8b5cf6");

        const payload = {
            contents: [
                {
                    parts: [
                        {
                            inline_data: {
                                mime_type: "audio/wav",
                                data: base64Audio
                            }
                        },
                        {
                            text: promptText
                        }
                    ]
                }
            ],
            generationConfig: {
                temperature: 0.1
            }
        };

        const models = ["gemini-2.5-flash", "gemini-1.5-flash"];
        let resultText = null;

        for (const model of models) {
            try {
                const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
                const resp = await new Promise((resolve, reject) => {
                    GM_xmlhttpRequest({
                        method: "POST",
                        url: endpoint,
                        headers: { "Content-Type": "application/json" },
                        data: JSON.stringify(payload),
                        onload: (r) => {
                            if (r.status === 200) {
                                resolve(JSON.parse(r.responseText));
                            } else {
                                reject(new Error(`HTTP ${r.status}: ${r.responseText}`));
                            }
                        },
                        onerror: (err) => reject(err)
                    });
                });

                if (resp.candidates && resp.candidates[0]?.content?.parts?.[0]?.text) {
                    resultText = resp.candidates[0].content.parts[0].text.trim();
                    break;
                }
            } catch (e) {
                console.warn(`[Auto-Transcribe] Model ${model} gagal:`, e.message);
            }
        }

        if (resultText) {
            const target = getTargetInput();
            fillInputValue(target, resultText);
            updateStatus(`✅ Selesai (${dur}s)! Cek & QA.`, "#10b981");
        } else {
            updateStatus("❌ Gagal transkripsi. Cek API Key Anda.", "#ef4444");
        }
    }

    // ==========================================
    // 6. UI WIDGET (PADA TOP WINDOW)
    // ==========================================
    function createUI() {
        if (window.self !== window.top) return;
        if (document.getElementById('qa-transcribe-panel')) return;

        const panel = document.createElement('div');
        panel.id = 'qa-transcribe-panel';
        panel.innerHTML = `
            <div id="qa-panel-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-weight: bold; font-size: 13px;">🎙️ QA Transcriber v2.1</span>
                <span id="qa-panel-toggle" style="cursor: pointer; opacity: 0.8;">━</span>
            </div>
            <div id="qa-panel-body">
                <div style="margin-bottom: 6px;">
                    <label style="display:block; font-size: 10px; opacity: 0.8; margin-bottom: 2px;">Gemini API Key:</label>
                    <input type="password" id="qa-api-key" placeholder="Paste API Key..." style="width: 100%; box-sizing: border-box; padding: 4px 6px; border-radius: 4px; border: 1px solid #4b5563; background: #1f2937; color: #fff; font-size: 11px;">
                </div>
                <div style="margin-bottom: 6px;">
                    <label style="display:block; font-size: 10px; opacity: 0.8; margin-bottom: 2px;">Audio URL (Auto/Manual):</label>
                    <input type="text" id="qa-audio-url" placeholder="URL .wav terdeteksi otomatis..." style="width: 100%; box-sizing: border-box; padding: 4px 6px; border-radius: 4px; border: 1px solid #4b5563; background: #1f2937; color: #9ca3af; font-size: 10px;">
                </div>
                <div style="display: flex; gap: 6px; margin-bottom: 8px;">
                    <select id="qa-lang-select" style="flex: 1; padding: 4px; border-radius: 4px; border: 1px solid #4b5563; background: #1f2937; color: #fff; font-size: 11px;">
                        <option value="ja">🇯🇵 Bahasa Jepang</option>
                        <option value="ms">🇲🇾 Bahasa Malaysia</option>
                    </select>
                </div>
                <button id="qa-btn-transcribe" style="width: 100%; padding: 8px; background: #2563eb; color: #fff; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 12px; display: flex; align-items: center; justify-content: center; gap: 4px;">
                    ⚡ Transcribe (Alt + Q)
                </button>
                <div id="qa-region-info" style="margin-top: 6px; font-size: 11px; font-weight: 500; color: #60a5fa; text-align: center;">
                    Segmen: mencari...
                </div>
                <div id="qa-status-bar" style="margin-top: 6px; font-size: 11px; padding: 4px; border-radius: 4px; background: rgba(0,0,0,0.2); text-align: center; color: #9ca3af;">
                    Siap (Pilih segmen pada waveform)
                </div>
            </div>
        `;

        Object.assign(panel.style, {
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            width: '260px',
            background: '#111827',
            color: '#f9fafb',
            borderRadius: '8px',
            boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
            zIndex: '999999',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            border: '1px solid #374151',
            padding: '10px'
        });

        document.body.appendChild(panel);

        // Load saved API Key
        const savedKey = localStorage.getItem('qa_gemini_api_key') || '';
        document.getElementById('qa-api-key').value = savedKey;

        document.getElementById('qa-api-key').addEventListener('change', (e) => {
            localStorage.setItem('qa_gemini_api_key', e.target.value.trim());
        });

        // Simpan manual URL jika diubah
        document.getElementById('qa-audio-url').addEventListener('change', (e) => {
            cachedAudioUrl = e.target.value.trim();
            cachedAudioBuffer = null;
        });

        document.getElementById('qa-btn-transcribe').addEventListener('click', transcribeSegment);

        // Toggle Minimize
        const toggleBtn = document.getElementById('qa-panel-toggle');
        const bodyEl = document.getElementById('qa-panel-body');
        toggleBtn.addEventListener('click', () => {
            if (bodyEl.style.display === 'none') {
                bodyEl.style.display = 'block';
                toggleBtn.innerText = '━';
            } else {
                bodyEl.style.display = 'none';
                toggleBtn.innerText = '➕';
            }
        });

        // Loop pendeteksi active region & audio url secara real-time
        setInterval(() => {
            const reg = getActiveRegion();
            const infoEl = document.getElementById('qa-region-info');
            if (infoEl) {
                if (reg) {
                    const dur = (reg.end - reg.start).toFixed(2);
                    infoEl.innerText = `Segmen Aktif: ${reg.start.toFixed(2)}s - ${reg.end.toFixed(2)}s (${dur}s)`;
                } else {
                    infoEl.innerText = `Belum ada segmen terpilih`;
                }
            }

            // Update Audio URL box jika terdeteksi
            const urlInput = document.getElementById('qa-audio-url');
            if (urlInput && !urlInput.value) {
                const detected = detectAudioUrl();
                if (detected) {
                    urlInput.value = detected;
                    cachedAudioUrl = detected;
                }
            }
        }, 500);
    }

    function updateStatus(text, color = '#9ca3af') {
        const bar = document.getElementById('qa-status-bar');
        if (bar) {
            bar.innerText = text;
            bar.style.color = color;
        }
    }

    // Keyboard shortcut (Alt + Q)
    window.addEventListener('keydown', (e) => {
        if (e.altKey && (e.key === 'q' || e.key === 'Q')) {
            e.preventDefault();
            transcribeSegment();
        }
    });

    // Teruskan keydown dari dalam iframe
    setInterval(() => {
        const ifrWin = getIframeWindow();
        if (ifrWin && !ifrWin._hasAutoTranscribeKeyHook) {
            ifrWin._hasAutoTranscribeKeyHook = true;
            ifrWin.addEventListener('keydown', (e) => {
                if (e.altKey && (e.key === 'q' || e.key === 'Q')) {
                    e.preventDefault();
                    transcribeSegment();
                }
            });
        }
    }, 1000);

    setTimeout(createUI, 1500);
})();
