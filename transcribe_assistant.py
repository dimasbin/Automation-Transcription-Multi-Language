import os
import sys
import io
import wave
import time
import json
import base64
import threading
import warnings
import winsound
from datetime import datetime

# Pastikan output console Windows mendukung UTF-8 (mencegah crash UnicodeEncodeError emoji)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import numpy as np
import requests
import soundcard as sc
import keyboard
import pyperclip

# Sembunyikan runtime warning agar terminal bersih
warnings.filterwarnings("ignore")

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
SAMPLERATE = 16000

# ==========================================
# DAFTAR BAHASA & PANDUAN PROMPT
# ==========================================
DEFAULT_LANGUAGES = {
    "ja": {
        "name": "🇯🇵 JEPANG (+ LATIN/ROMAJI)",
        "prompt": (
            "You are a professional transcriptionist for Japanese audio. "
            "Strictly transcribe the audio verbatim without omission.\n"
            "Formatting Requirements:\n"
            "Line 1: Native Japanese script (Kanji, Hiragana, Katakana) including all filler words/hesitations exactly as heard (e.g. 「えーと」「あのー」「えっ」「まー」「うん」「あ」) and correct Japanese punctuation (、, 。, ？, ！).\n"
            "Line 2: The exact Latin alphabet (Romaji) transcription of Line 1, also preserving filler words and punctuation.\n"
            "Do NOT include labels like 'Line 1:' or translations. Output strictly the 2 lines."
        )
    },
    "ms": {
        "name": "🇲🇾 MALAYSIA (MELAYU)",
        "prompt": (
            "You are a professional transcriptionist for Malaysian Malay audio. "
            "Strictly transcribe the audio verbatim without omission.\n"
            "Rules:\n"
            "1. Include all filler words, hesitations, and sounds: 'um', 'uh', 'a', 'e', 'er', 'aa', 'lah', 'kan', 'tu', etc.\n"
            "2. Apply standard punctuation (commas, periods, question marks, exclamation marks) accurately based on speech pauses and intonation.\n"
            "3. Maintain proper spacing for pauses.\n"
            "4. Do NOT translate or summarize. Output ONLY the raw transcription."
        )
    },
    "id": {
        "name": "🇮🇩 INDONESIA",
        "prompt": (
            "You are a professional transcriptionist for Indonesian audio. "
            "Strictly transcribe the audio verbatim without omission.\n"
            "Rules:\n"
            "1. Include all filler words, hesitations, and sounds exactly as spoken: 'um', 'uh', 'eh', 'aa', 'anu', 'ya', 'kan', dll.\n"
            "2. Apply standard punctuation (titik, koma, tanda tanya, tanda seru) accurately based on speech pauses and intonation.\n"
            "3. Maintain proper spacing for pauses.\n"
            "4. Do NOT translate or summarize. Output ONLY the raw transcription."
        )
    },
    "en": {
        "name": "🇬🇧 INGGRIS (ENGLISH)",
        "prompt": (
            "You are a professional transcriptionist for English audio. "
            "Strictly transcribe the audio verbatim without omission.\n"
            "Rules:\n"
            "1. Include all filler words, hesitations, and sounds: 'um', 'uh', 'er', 'ah', 'like', 'you know', stuttering, etc.\n"
            "2. Apply standard punctuation (commas, periods, question marks, exclamation marks) accurately based on speech pauses and intonation.\n"
            "3. Do NOT translate or summarize. Output ONLY the raw transcription."
        )
    },
    "zh": {
        "name": "🇨🇳 MANDARIN (+ PINYIN)",
        "prompt": (
            "You are a professional transcriptionist for Mandarin Chinese audio. "
            "Strictly transcribe the audio verbatim without omission.\n"
            "Formatting Requirements:\n"
            "Line 1: Simplified Chinese characters including all modal particles and filler words (e.g. 呃, 那个, 啊, 嗯, 吧, 呢) with correct Chinese punctuation (，。？！).\n"
            "Line 2: The exact Pinyin with tone marks for Line 1.\n"
            "Do NOT include extra labels or translations. Output strictly the 2 lines."
        )
    },
    "ko": {
        "name": "🇰🇷 KOREA (+ LATIN)",
        "prompt": (
            "You are a professional transcriptionist for Korean audio. "
            "Strictly transcribe the audio verbatim without omission.\n"
            "Formatting Requirements:\n"
            "Line 1: Korean Hangul script including all filler words (e.g. 어, 그, 저, 음, 에) and correct Korean punctuation.\n"
            "Line 2: The exact Revised Romanization (Latin) transcription of Line 1.\n"
            "Do NOT include extra labels or translations. Output strictly the 2 lines."
        )
    },
    "th": {
        "name": "🇹🇭 THAILAND (+ LATIN/RTGS)",
        "prompt": (
            "You are a professional transcriptionist for Thai audio. "
            "Strictly transcribe the audio verbatim without omission.\n"
            "Formatting Requirements:\n"
            "Line 1: Native Thai script including all particle and filler words (e.g. เออ, อ่า, เอ่อ, คือ, แบบว่า, นะ, ครับ, ค่ะ) and proper spacing for pauses.\n"
            "Line 2: The exact Latin Romanization (RTGS) transcription of Line 1.\n"
            "Do NOT include extra labels or translations. Output strictly the 2 lines."
        )
    },
    "vi": {
        "name": "🇻🇳 VIETNAM",
        "prompt": (
            "You are a professional transcriptionist for Vietnamese audio. "
            "Strictly transcribe the audio verbatim without omission.\n"
            "Rules:\n"
            "1. Use standard Vietnamese orthography with correct diacritics and tone marks.\n"
            "2. Include all filler words, hesitations, and modal particles: 'à', 'ờ', 'ừ', 'ơ', 'kiểu', 'thì', 'là', 'nhé', 'nha', etc.\n"
            "3. Apply standard punctuation (commas, periods, question marks, exclamation marks) accurately based on speech pauses.\n"
            "4. Do NOT translate or summarize. Output ONLY the raw verbatim transcription."
        )
    }
}

DIARIZATION_INSTRUCTION_SINGLE_LINE = (
    "\n\nSPEAKER DIARIZATION REQUIREMENT:\n"
    "Identify and distinguish different speakers (up to 5 speakers: Speaker 1, Speaker 2, Speaker 3, Speaker 4, Speaker 5).\n"
    "Prefix each turn with the speaker label exactly like 'Speaker 1: [utterance]' or 'Speaker 2: [utterance]'.\n"
    "Maintain strict verbatim speech and punctuation for every speaker."
)

DIARIZATION_INSTRUCTION_TWO_LINE = (
    "\n\nSPEAKER DIARIZATION REQUIREMENT:\n"
    "Identify and distinguish different speakers (up to 5 speakers: Speaker 1, Speaker 2, Speaker 3, Speaker 4, Speaker 5).\n"
    "For each speaker turn, output 2 lines with clear speaker labels:\n"
    "Line 1: 'Speaker X: [native script verbatim]'\n"
    "Line 2: 'Speaker X (Latin): [romanized verbatim]'\n"
    "Separate each speaker turn with a blank line."
)

def load_config():
    cfg = {
        "api_keys": [],
        "api_key": "",
        "language": "ja",
        "hotkey": "f9",
        "switch_hotkey": "f10",
        "diarization_hotkey": "f8",
        "diarization": False,
        "auto_paste": False,
        "save_history": True
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg.update(saved)
        except Exception:
            pass
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)

# ==========================================
# STATE PEREKAM
# ==========================================
class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.recorded_chunks = []
        self.thread = None
        self.config = load_config()
        self.languages = dict(DEFAULT_LANGUAGES)
        if "custom_languages" in self.config and isinstance(self.config["custom_languages"], dict):
            self.languages.update(self.config["custom_languages"])
        self.lang_keys = list(self.languages.keys())
        self.current_lang = self.config.get("language", "ja")
        if self.current_lang not in self.languages:
            self.current_lang = "ja"

        self.diarization = self.config.get("diarization", False)
        self.save_history = self.config.get("save_history", True)

        # Persistent HTTP Session for fast keep-alive pooling
        self.session = requests.Session()

        # Memuat multi API Key (support list 'api_keys' & string 'api_key')
        self.api_keys = []
        if "api_keys" in self.config and isinstance(self.config["api_keys"], list):
            for k in self.config["api_keys"]:
                if isinstance(k, str) and k.strip() and k.strip() not in self.api_keys:
                    self.api_keys.append(k.strip())
        single_key = self.config.get("api_key", "").strip()
        if single_key and single_key not in self.api_keys:
            self.api_keys.insert(0, single_key)

        self.current_key_idx = 0
        self.loopback_mic = None
        self.init_audio_device()

    def get_active_key(self):
        if not self.api_keys:
            return ""
        return self.api_keys[self.current_key_idx % len(self.api_keys)]

    def init_audio_device(self, silent=False):
        try:
            speaker = sc.default_speaker()
            self.loopback_mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            if not silent:
                print(f"[Perangkat Audio] Terhubung ke: {speaker.name} (Loopback Internal)")
        except Exception:
            try:
                mics = sc.all_microphones(include_loopback=True)
                for m in mics:
                    if m.isloopback:
                        self.loopback_mic = m
                        if not silent:
                            print(f"[Perangkat Audio] Menggunakan loopback: {m.name}")
                        break
            except Exception as e2:
                if not silent:
                    print(f"[Error Audio] {e2}")

    def toggle_record(self):
        if not self.is_recording:
            self.start_record()
        else:
            self.stop_and_transcribe()

    def start_record(self):
        if not self.api_keys:
            print("\n❌ API Key Gemini belum dimasukkan!")
            winsound.Beep(400, 200)
            return

        if not self.loopback_mic:
            self.init_audio_device()
            if not self.loopback_mic:
                print("\n❌ Tidak dapat menemukan perangkat audio/speaker untuk merekam.")
                return

        self.is_recording = True
        self.recorded_chunks = []
        winsound.Beep(900, 100)  # Beep mulai
        lang_info = self.languages.get(self.current_lang, {})
        lang_name = lang_info.get("name", self.current_lang.upper())
        active_key = self.get_active_key()
        masked = f"...{active_key[-6:]}" if len(active_key) > 6 else active_key
        key_label = f"Key #{self.current_key_idx + 1} ({masked})" if len(self.api_keys) > 1 else f"({masked})"
        diar_tag = "👥 MULTI-SPEAKER" if self.diarization else "👤 SINGLE"
        print(f"\n🔴 [MEREKAM AUDIO HEADSET] [{diar_tag}] Bahasa: {lang_name} | {key_label} ... (Tekan F9 lagi untuk selesai)")

        def record_worker():
            chunk_size = int(SAMPLERATE * 0.2)
            try:
                with self.loopback_mic.recorder(samplerate=SAMPLERATE) as mic:
                    while self.is_recording:
                        chunk = mic.record(numframes=chunk_size)
                        self.recorded_chunks.append(chunk)
            except Exception:
                # Coba re-init jika device sempat terputus/sleep
                try:
                    self.init_audio_device(silent=True)
                    if self.loopback_mic:
                        with self.loopback_mic.recorder(samplerate=SAMPLERATE) as mic:
                            while self.is_recording:
                                chunk = mic.record(numframes=chunk_size)
                                self.recorded_chunks.append(chunk)
                except Exception:
                    pass

        self.thread = threading.Thread(target=record_worker, daemon=True)
        self.thread.start()

    def process_audio(self, audio_data):
        """
        Auto-gain peak normalization dan smart silence trimming (padding 0.3 detik).
        Mengembalikan: (processed_int16, durasi_final, is_silent)
        """
        # Konversi ke float mono
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            mono = np.mean(audio_data, axis=1)
        else:
            mono = audio_data.flatten()

        peak = np.max(np.abs(mono))
        if peak < 0.002:  # Sangat hening (noise floor murni)
            return None, 0.0, True

        # Silence trimming dengan window 50ms & padding 0.3 detik
        win_size = int(SAMPLERATE * 0.05)
        n_wins = len(mono) // win_size
        if n_wins > 0:
            energies = np.array([
                np.sqrt(np.mean(mono[i * win_size:(i + 1) * win_size] ** 2))
                for i in range(n_wins)
            ])
            thresh = max(0.003, float(np.mean(energies)) * 0.15)
            active_idx = np.where(energies > thresh)[0]
            if len(active_idx) > 0:
                pad_wins = int(0.3 / 0.05)  # 0.3 detik padding
                start_win = max(0, active_idx[0] - pad_wins)
                end_win = min(n_wins, active_idx[-1] + 1 + pad_wins)
                mono = mono[start_win * win_size:end_win * win_size]

        # Auto-Gain (Peak Normalization ke 0.92)
        peak = np.max(np.abs(mono))
        if peak > 0.005:
            mono = mono * (0.92 / peak)

        int16_data = np.int16(np.clip(mono, -1.0, 1.0) * 32767)
        final_dur = len(int16_data) / SAMPLERATE
        return int16_data, final_dur, False

    def stop_and_transcribe(self):
        self.is_recording = False
        winsound.Beep(1200, 100)  # Beep stop
        print("⏹️ [SELESAI REKAM] Memproses audio...")

        if self.thread:
            self.thread.join(timeout=1.0)

        if not self.recorded_chunks:
            print("⚠️ Rekaman kosong.")
            return

        raw_audio = np.concatenate(self.recorded_chunks, axis=0)
        int16_data, dur, is_silent = self.process_audio(raw_audio)

        if is_silent or dur < 0.4:
            print("⚠️ Audio hening atau tidak ada suara yang terdeteksi. Batal mengirim ke API.\n")
            winsound.Beep(400, 200)
            return

        print(f"⏱️ Durasi aktif audio: {dur:.2f} detik")

        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLERATE)
            wf.writeframes(int16_data.tobytes())

        wav_bytes = wav_io.getvalue()
        b64_audio = base64.b64encode(wav_bytes).decode("utf-8")

        # Panggil Gemini API di background thread
        threading.Thread(target=self.call_gemini, args=(b64_audio, dur), daemon=True).start()

    def get_prompt_for_current_state(self):
        lang_info = self.languages.get(self.current_lang, self.languages["ja"])
        base_prompt = lang_info.get("prompt", "")

        if not self.diarization:
            return base_prompt

        # Jika diarization aktif:
        if self.current_lang in ["ja", "zh", "ko", "th"]:
            return base_prompt + DIARIZATION_INSTRUCTION_TWO_LINE
        else:
            return base_prompt + DIARIZATION_INSTRUCTION_SINGLE_LINE

    def save_to_history(self, text, dur):
        if not self.save_history:
            return
        today_str = datetime.now().strftime("%Y-%m-%d")
        history_file = os.path.join(os.path.dirname(__file__), f"history_{today_str}.txt")
        timestamp = datetime.now().strftime("%H:%M:%S")
        lang_name = self.languages.get(self.current_lang, {}).get("name", self.current_lang)
        diar_str = "Multi-Speaker" if self.diarization else "Single-Speaker"

        try:
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{lang_name}] [{diar_str}] ({dur:.2f}s)\n")
                f.write(f"{text}\n")
                f.write("-" * 50 + "\n")
        except Exception:
            pass

    def call_gemini(self, b64_audio, dur):
        if not self.api_keys:
            print("❌ Tidak ada API Key yang tersedia!")
            winsound.Beep(400, 200)
            return

        print("🤖 Mengirim ke Google Gemini AI...")
        prompt = self.get_prompt_for_current_state()

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "audio/wav",
                                "data": b64_audio
                            }
                        },
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1
            }
        }

        models = [
            "gemini-3.5-transcribe",
            "gemini-3.5-flash",
            "gemini-3-flash-preview"
        ]
        result_text = None
        total_keys = len(self.api_keys)

        for key_attempt in range(total_keys):
            key_idx = (self.current_key_idx + key_attempt) % total_keys
            api_key = self.api_keys[key_idx]
            masked = f"...{api_key[-6:]}" if len(api_key) > 6 else api_key
            key_tag = f"[Key #{key_idx + 1} {masked}]"

            for model in models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                try:
                    resp = self.session.post(url, json=payload, timeout=20)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                result_text = parts[0].get("text", "").strip()
                                if result_text:
                                    self.current_key_idx = key_idx
                                    break
                    elif resp.status_code in [429, 403]:
                        err_text = resp.text.lower()
                        if "resource_exhausted" in err_text or "quota" in err_text or resp.status_code == 429:
                            print(f"⚠️ {key_tag} Kuota/Limit habis pada model {model} (HTTP {resp.status_code})")
                            break
                        else:
                            print(f"⚠️ {key_tag} Respon {model}: HTTP {resp.status_code}")
                    else:
                        print(f"⚠️ {key_tag} Respon {model}: HTTP {resp.status_code}")
                except Exception as e:
                    print(f"⚠️ {key_tag} Request ke {model} error: {e}")

            if result_text:
                break

            # Jika key ini limit/gagal dan masih ada key cadangan di daftar
            if not result_text and total_keys > 1 and key_attempt < total_keys - 1:
                next_idx = (key_idx + 1) % total_keys
                next_key = self.api_keys[next_idx]
                next_masked = f"...{next_key[-6:]}" if len(next_key) > 6 else next_key
                print(f"🔄 Kuota habis / error! Otomatis geser ke API Key #{next_idx + 1} ({next_masked})...\n")
                self.current_key_idx = next_idx
                winsound.Beep(1200, 100)
                continue

        if result_text:
            print(f"\n==========================================")
            mode_lbl = "MULTI-SPEAKER" if self.diarization else "SINGLE"
            print(f"📝 HASIL TRANSKRIPSI ({dur:.2f}s | {mode_lbl}):")
            print(result_text)
            print(f"==========================================")

            # Simpan ke riwayat harian
            self.save_to_history(result_text, dur)

            # Salin ke Clipboard agar langsung siap jika ingin Ctrl+V manual
            try:
                pyperclip.copy(result_text)
            except Exception:
                pass

            # Cek fitur auto-paste (default: False/Mati)
            if self.config.get("auto_paste", False):
                time.sleep(0.1)
                keyboard.send("ctrl+v")
                print("✅ Otomatis ditempelkan ke kolom aktif!")
            else:
                today_file = f"history_{datetime.now().strftime('%Y-%m-%d')}.txt"
                print(f"📋 (Tersalin ke Clipboard & tersimpan di {today_file})")

            winsound.Beep(1600, 150)  # Beep sukses
            print("")
        else:
            winsound.Beep(400, 300)
            if total_keys > 1:
                print("❌ Gagal mendapatkan transkripsi (Semua API Key limit atau audio hening).\n")
            else:
                print("⚠️ Audio hening atau tidak terdeteksi suara bicara.\n")

    def toggle_language(self):
        curr_idx = self.lang_keys.index(self.current_lang) if self.current_lang in self.lang_keys else 0
        next_idx = (curr_idx + 1) % len(self.lang_keys)
        self.current_lang = self.lang_keys[next_idx]

        self.config["language"] = self.current_lang
        save_config(self.config)
        winsound.Beep(1400, 100)

        lang_name = self.languages[self.current_lang]["name"]
        print(f"\n🌐 Bahasa aktif dialihkan ke: {lang_name}")

    def toggle_diarization(self):
        self.diarization = not self.diarization
        self.config["diarization"] = self.diarization
        save_config(self.config)

        if self.diarization:
            winsound.Beep(1500, 150)
            print("\n👥 [MODE PEMBICARA] Diarization AKTIF (Membedakan Speaker 1 s/d Speaker 5)")
        else:
            winsound.Beep(1000, 150)
            print("\n👤 [MODE PEMBICARA] Single Speaker AKTIF (Tanpa label Speaker)")


def main():
    os.system("cls" if os.name == "nt" else "clear")
    print("=====================================================")
    print("   🎙️ DATA PLAYBACK TRANSCRIPTION ASSISTANT v4.0    ")
    print("   (Headset Loopback + Speaker Diarization + Gain)   ")
    print("=====================================================")

    recorder = AudioRecorder()

    if not recorder.api_keys:
        print("\nBelum ada Gemini API Key yang tersimpan.")
        key_input = input("Masukkan Gemini API Key: ").strip()
        if key_input:
            recorder.api_keys = [key_input]
            recorder.config["api_keys"] = [key_input]
            recorder.config["api_key"] = key_input
            save_config(recorder.config)
            print("✅ API Key berhasil disimpan!")

    lang_name = recorder.languages[recorder.current_lang]["name"]
    diar_status = "👥 AKTIF (Speaker 1 s/d 5)" if recorder.diarization else "👤 NONAKTIF (Single Voice)"
    today_file = f"history_{datetime.now().strftime('%Y-%m-%d')}.txt"

    print("\n-----------------------------------------------------")
    print(f" Status API Key    : ✅ AKTIF ({len(recorder.api_keys)} Key Terdaftar)")
    for i, k in enumerate(recorder.api_keys):
        m = f"...{k[-6:]}" if len(k) > 6 else k
        prefix = "  👉 " if i == recorder.current_key_idx else "     "
        print(f"{prefix}Key #{i+1}: {m}")
    print(f" Bahasa Saat Ini   : {lang_name}")
    print(f" Mode Multi-Suara  : {diar_status}")
    print(f" File Log Harian   : {today_file}")
    print(f" Tombol Rekam      : [ F9 ]  (Mulai / Selesai)")
    print(f" Tombol Ganti Bhs  : [ F10 ] (Putar ke bahasa berikutnya)")
    print(f" Tombol 2-5 Suara  : [ F8 ]  (Toggle Multi-Speaker on/off)")
    print("\n Daftar Bahasa Tersedia (F10):")
    for code, info in recorder.languages.items():
        prefix = "  👉 " if code == recorder.current_lang else "     "
        print(f"{prefix}[{code}] {info['name']}")
    print("-----------------------------------------------------")
    print("\n👉 Putar audio segmen, tekan [ F9 ] untuk mulai & selesai merekam.")
    print("👉 Tekan [ F8 ] kapan saja untuk mengaktifkan pembedaan Speaker 1 - 5.")
    print("👉 Hasil transkripsi akan muncul di CMD ini & otomatis tersalin ke Clipboard.\n")

    keyboard.add_hotkey("f9", recorder.toggle_record)
    keyboard.add_hotkey("f10", recorder.toggle_language)
    keyboard.add_hotkey("f8", recorder.toggle_diarization)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nProgram dihentikan. Sampai jumpa!")

if __name__ == "__main__":
    main()
