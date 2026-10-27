# 🎙️ Playback Audio Transcription Assistant (Windows)

An automated, lossless Windows audio transcription assistant powered by **Google Gemini AI**. Captures digital audio directly from your active headphones/speakers (*WASAPI Loopback*) and transcribes speech from **any website, video, or desktop software** with strict full-verbatim accuracy and multi-language support.

---

## ✨ Key Features

- 🎧 **Universal Digital Audio Capture (Zero Noise)**:
  - Uses Windows WASAPI Loopback to record audio straight from your active output device (Speakers / Headphones).
  - Works with headphones plugged in—completely immune to background room noise.
  - Captures audio from **any source**: Web browsers (DataPlus, YouTube, Coursera, Loom), desktop media players, conferencing apps (Zoom, Teams, Google Meet), etc.
- 🤖 **Gemini 3.5 Speech-to-Text Engine**:
  - Leverages Google's state-of-the-art models (`gemini-3.5-transcribe` with auto-fallback to `gemini-3.5-flash`).
  - Strict **Full Verbatim** enforcement: preserves filler words, natural hesitations (*um, uh, er, ano, eto, lah, kan, etc.*), and precise punctuation.
- 🌐 **Multi-Language Support (8 Languages Built-in)**:
  - 🇯🇵 **Japanese (`ja`)**: 2 Lines (Line 1: Kanji/Kana verbatim; Line 2: Latin Romaji reading).
  - 🇨🇳 **Mandarin Chinese (`zh`)**: 2 Lines (Line 1: Simplified Hanzi; Line 2: Pinyin with tone marks).
  - 🇰🇷 **Korean (`ko`)**: 2 Lines (Line 1: Hangul script; Line 2: Latin Romanization).
  - 🇹🇭 **Thai (`th`)**: 2 Lines (Line 1: Thai script with pauses; Line 2: RTGS Romanization).
  - 🇲🇾 **Malaysian Malay (`ms`)**: Full verbatim with colloquial particles (*lah, kan, tu, dll.*).
  - 🇮🇩 **Indonesian (`id`)**: Full verbatim with natural filler words (*eh, aa, anu, ya, dll.*).
  - 🇬🇧 **English (`en`)**: Full verbatim preserving stutters and pauses (*like, you know, um, uh*).
  - 🇻🇳 **Vietnamese (`vi`)**: Full verbatim in standard Quốc ngữ script with complete tone marks and diacritics.
- 🔄 **Smart Multi-API Key Failover**:
  - Pool multiple Gemini API keys in `config.json`.
  - If Key #1 hits rate limits or quota exhaustion (*HTTP 429 Too Many Requests*), the assistant automatically switches to Key #2 without interrupting or losing the recorded audio.
- ⌨️ **Global Hotkeys**:
  - `[ F9 ]`: Toggle recording (Start record -> plays audio beep -> Stop record -> Transcribe).
  - `[ F10 ]`: Instantly cycle through available languages on the fly.
- 📋 **Flexible Output Modes**:
  - Formatted output printed clearly in the CMD terminal for manual review & copying.
  - Automatically copied to the Windows Clipboard for instant pasting.
  - Optional `"auto_paste"` toggle (disabled by default for QA review control).

---

## 🛠️ Architecture Overview

```mermaid
flowchart LR
    A["Audio Output\n(Headphones/Speakers)"] -->|WASAPI Loopback| B["transcribe_assistant.py\n(Lossless Digital Capture)"]
    B -->|In-Memory 16kHz WAV| C["Google Gemini AI\n(gemini-3.5-transcribe)"]
    C -->|Verbatim & Multi-line| D["Terminal Output (CMD)"]
    D -->|Auto-Copy| E["Windows Clipboard"]
    D -.->|Optional Auto-Paste| F["Target Input Field"]
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Windows 10 or Windows 11
- Python 3.10+ installed ([python.org](https://www.python.org/downloads/))

### 2. Installation
Clone this repository and install the required dependencies:
```bash
git clone https://github.com/your-username/automation-transcription.git
cd automation-transcription
pip install -r requirements.txt
```

### 3. Configuration
Copy `config.example.json` to `config.json` and insert your Gemini API Key(s):
```json
{
    "api_keys": [
        "YOUR_PRIMARY_GEMINI_API_KEY",
        "YOUR_SECONDARY_BACKUP_API_KEY"
    ],
    "language": "ja",
    "hotkey": "f9",
    "switch_hotkey": "f10",
    "auto_paste": false
}
```
> [!TIP]
> You can obtain Gemini API keys for free from [Google AI Studio](https://aistudio.google.com/).

### 4. Running the Assistant
Simply run the batch launcher:
```bash
RUN_ASSISTANT.bat
```
or run directly via terminal:
```bash
python transcribe_assistant.py
```

---

## 🎮 How to Use

1. **Start the Assistant**: Run `RUN_ASSISTANT.bat`. A terminal window will open showing active API keys and current language.
2. **Select Language**: Press **`F10`** anytime to cycle to your target language (Japanese, Malay, Thai, English, etc.).
3. **Play Audio**: Start playing the audio segment in your browser, media player, or app.
4. **Record**:
   - Press **`F9`** to start recording (a beep will sound).
   - Once the audio finishes playing, press **`F9`** again to stop.
5. **Review & Copy**:
   - The verbatim transcription will immediately appear formatted inside the CMD console.
   - It is also pre-copied to your clipboard, ready for manual `Ctrl + V` pasting.

---

## ⚙️ Configuration Reference

| Parameter | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `api_keys` | `array` | `[]` | List of Gemini API keys for automatic failover rotation. |
| `language` | `string` | `"ja"` | Default language code (`ja`, `ms`, `id`, `en`, `zh`, `ko`, `th`, `vi`). |
| `hotkey` | `string` | `"f9"` | Global shortcut key to start/stop recording. |
| `switch_hotkey` | `string` | `"f10"` | Global shortcut key to cycle languages. |
| `auto_paste` | `boolean` | `false` | When `true`, automatically sends `Ctrl+V` to the focused window. |
| `custom_languages` | `object` | `{}` | Optional dictionary to inject custom language prompts without modifying code. |

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
