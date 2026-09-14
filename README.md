# 🕊️ Saral Yojana (v2)

> **Sarkari schemes, aasaan bhasha mein — now with voice.**
> A voice-first assistant that scrapes any government scheme page, simplifies it in your local language, and reads it out loud in a **male or female voice** across **10 Indian languages**. Includes scholarship quick-picks for **Graduate & PG students** and **in-person appointment booking** at the Bengaluru office.

Built for the **AI Engineer Mixer** hackathon using **Sarvam.ai** + **Anakin.io**.

---

## What's new in v2

| Feature | Description |
|---------|-------------|
| 🎙️ **Voice-first output** | Audio is now the primary output — text is secondary. Every answer is spoken aloud. |
| 👨👩 **Male / Female voice** | Users pick a male or female voice assistant. 39 bulbul:v3 speakers, auto-matched to the chosen language. |
| 🌐 **Multi-language** | 10 Indian languages: Hindi, English, Tamil, Kannada, Telugu, Marathi, Bengali, Gujarati, Malayalam, Punjabi. |
| 🎓 **Scholarship presets** | Quick-pick scholarships for Graduate and PG students — one click loads the scheme, scrapes it, and speaks the answer. |
| 📅 **Appointment booking** | Book an in-person slot at the Bengaluru office for face-to-face scheme/scholarship assistance. |
| 📍 **Bangalore office** | Contact and address updated to Bengaluru (Malleshwaram). |

---

## What it does

1. **Paste a scheme URL** (or pick a scholarship preset)
2. The app **scrapes the page** (Anakin URL Scraper) and **searches for recent references** (Anakin Search API)
3. Sarvam **translates and simplifies** the content into your chosen Indian language
4. Sarvam **generates spoken audio** (bulbul:v3) in your chosen **male or female** voice
5. You see **source cards** with citation links and hear a **playable voice answer**

---

## About this project

Saral Yojana is a voice-first civic-tech assistant that makes Indian government schemes easier to understand and access. It combines live web content retrieval, multilingual simplification, and text-to-speech so users can receive scheme guidance in their preferred Indian language and voice. The app also includes scholarship discovery for graduate and postgraduate students and appointment booking for in-person assistance.

This project was built for the AI Engineer Mixer hackathon using **FastAPI**, **Sarvam.ai**, and **Anakin.io**.

## Resume

[Download Utkarsh Shukla's resume](docs/Utkarsh-Shukla-Resume.pdf)

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up API keys

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```
SARVAM_API_KEY=your_sarvam_key_here
ANAKIN_API_KEY=ak-your-key-here
```

- Get a Sarvam key: https://indus.sarvam.ai/key-management
- Get an Anakin key: https://anakin.io

### 3. Run

```bash
uvicorn app:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

---

## Three tabs in the UI

### 📖 Tab 1: Explain a Scheme
Paste any government scheme URL, ask a question, pick your language and voice gender (male/female), and get a spoken + text answer with source cards.

### 🎓 Tab 2: Scholarships
Quick-pick from preset scholarships for Graduate and PG students. Filter by level (Graduate / Postgraduate / All). Click a scholarship → it auto-fills the explain pipeline with the scheme URL and question.

### 📅 Tab 3: Book Appointment
Book an in-person slot at the Bengaluru office. Pick a date, choose a time slot, and confirm. You get a booking ID and the office address.

---

## Voice & Speaker details

Sarvam's **bulbul:v3** model supports 39 voices. The app auto-selects the best speaker for each language + gender combination:

| Language | Male voice | Female voice |
|----------|-----------|--------------|
| Hindi | shubh | priya |
| English | ratan | ishita |
| Tamil | ratan | ishita |
| Kannada | shubh | ishita |
| Telugu | shubh | neha |
| Marathi | ratan | priya |
| Bengali | rehan | roopa |
| Gujarati | ratan | priya |
| Malayalam | shubh | pooja |
| Punjabi | mani | roopa |

Source: Sarvam docs [cite:be524ab6]

---

## Example input for judges

### Scheme explainer
| Field | Value |
|-------|-------|
| **URL** | `https://www.myscheme.gov.in/schemes/pm-svanidhi` |
| **Question** | `Am I eligible, and how do I apply?` |
| **Language** | Hindi |
| **Voice** | Female (priya) |

### Scholarship
| Field | Value |
|-------|-------|
| **Preset** | PM Research Fellowship (PMRF) |
| **Level** | Postgraduate |
| **Language** | English |
| **Voice** | Male (ratan) |

### Appointment
| Field | Value |
|-------|-------|
| **Name** | Test User |
| **Date** | Tomorrow |
| **Slot** | 10:00 |
| **Location** | Bengaluru office (Malleshwaram) |

---

## Where each sponsor API is used

### Sarvam.ai (language intelligence)

| Feature | Where in code | What it does |
|--------|--------------|--------------|
| **Translation** | `sarvam_simplify_and_translate()` | Translates the English summary + page content into the target Indian language |
| **Text-to-Speech** | `sarvam_tts()` | Generates spoken audio via bulbul:v3 with male/female speaker selection |

### Anakin.io (live web content)

| Feature | Where in code | What it does |
|--------|--------------|--------------|
| **URL Scraper** | `anakin_scrape()` | Scrapes the scheme page into markdown |
| **Search API** | `anakin_search()` | Finds 3 recent references / news about the scheme |

---

## Architecture

```
User (picks scheme URL or scholarship preset + language + voice gender)
        │
        ▼
[1] Anakin URL Scraper  ──→  page markdown (official scheme page)
[2] Anakin Search API   ──→  3 recent references (news, govt circulars)
        │
        ▼
[3] Sarvam Translation   ──→  simplified local-language summary
[4] Sarvam TTS (bulbul:v3) ──→  spoken answer audio (MALE or FEMALE voice)
        │
        ▼
UI: voice player (primary) + text + source cards + citation links
```

### Appointment flow (separate)

```
User picks date + slot → POST /api/appointments/book
        │
        ▼
Booking confirmed (ID generated) → Bengaluru office address shown
```

---

## File structure

```
saral-yojana/
├── app.py              # FastAPI backend (all routes + Sarvam/Anakin logic)
├── requirements.txt    # Python dependencies
├── .env.example        # Template for API keys
├── .gitignore
├── README.md           # This file
└── static/
    └── index.html      # Single-page UI (3 tabs: explain, scholarships, appointment)
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves the HTML UI |
| GET | `/api/health` | Health check + API key status + speaker lists |
| GET | `/api/languages` | List of supported languages |
| GET | `/api/speakers` | Full speaker catalogue (male/female, per-language defaults) |
| GET | `/api/scholarships` | Scholarship presets (optional `?level=Graduate`) |
| POST | `/api/explain` | Main pipeline: scrape → search → translate → TTS |
| GET | `/api/appointments/slots` | Available slots + office address |
| POST | `/api/appointments/book` | Book an in-person appointment |
| GET | `/api/appointments` | List all bookings (admin/demo view) |

### POST /api/explain

```json
{
  "url": "https://www.myscheme.gov.in/schemes/pm-svanidhi",
  "question": "Am I eligible, and how do I apply?",
  "target_language": "hi-IN",
  "voice_gender": "female",
  "speaker": null
}
```

### POST /api/appointments/book

```json
{
  "name": "Ravi Kumar",
  "phone": "9876543210",
  "email": "ravi@email.com",
  "date": "2026-09-01",
  "slot": "10:00",
  "language": "hi-IN",
  "notes": "Need help with PM SVANidhi application"
}
```

---

## Supported languages

Hindi, English, Tamil, Kannada, Telugu, Marathi, Bengali, Gujarati, Malayalam, Punjabi

---

## Scholarship presets

| Level | Scholarships |
|-------|-------------|
| Graduate | National Scholarship Portal (UG), Post-Matric SC Scholarship |
| Postgraduate | MANF Fellowship, PG GATE/GPAT Scholarship, PM Research Fellowship |
| Both | Vidyalakshmi Education Loans |

---

## Limitations

- The 90-minute version supports one scheme URL at a time.
- Live scrape speed depends on the target page; some heavy government pages may time out.
- Sarvam Translation input is truncated to ~3000 characters for speed.
- Appointments are stored in-memory (resets on server restart). Swap for a database for production.
- TTS output is one language + one voice at a time (user picks both).

---

## Tips for a smooth demo

1. **Pre-run the PM SVANidhi URL** before demoing so the first load is cached.
2. Show the **voice gender toggle** — pick female for Hindi, male for English.
3. Switch to the **Scholarships tab** and click PMRF → shows the full pipeline reusing the explain endpoint.
4. Switch to **Appointment tab** → book a slot → show confirmation with Bengaluru address.
5. Emphasize the **audio playback** — that's the visible Sarvam value.

---

## Get API keys

- **Sarvam:** https://indus.sarvam.ai/key-management
- **Anakin:** https://anakin.io

---

## License

MIT — free to use, modify, and demo.
