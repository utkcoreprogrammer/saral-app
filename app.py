"""
Saral Yojana — Sarkari schemes, samjho aasaan bhasha mein.

A FastAPI app that:
  1. Scrapes a government-scheme page (Anakin URL Scraper)
  2. Searches for recent references / news (Anakin Search API)
  3. Simplifies + translates the content (Sarvam Translation)
  4. Generates spoken audio output (Sarvam TTS bulbul:v3) with MALE / FEMALE
     voice selection across 10 Indian languages.

Extra features:
  • Scholarship quick-pick presets for Graduate / PG students.
  • In-person appointment booking for offline assistance (Bangalore office).
  • Voice-first output — audio is always generated; text is secondary.

Run:  uvicorn app:app --reload --port 8000
"""

from __future__ import annotations

import io
import os
import json
import time
import uuid
import base64
import asyncio
import logging
from typing import Any, Optional
from datetime import datetime

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ── Sarvam SDK ──────────────────────────────────────────────────────────────
from sarvamai import SarvamAI

# ── Config ──────────────────────────────────────────────────────────────────
load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
ANAKIN_API_KEY = os.getenv("ANAKIN_API_KEY", "")
PORT = int(os.getenv("PORT", "8000"))

ANAKIN_BASE = "https://api.anakin.io/v1"
MAX_SARVAM_TRANSLATION_CHARS = 1000

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("saral-yojana")

# ── Sarvam client (created once) ─────────────────────────────────────────────
sarvam_client: Optional[SarvamAI] = None
if SARVAM_API_KEY:
    sarvam_client = SarvamAI(api_subscription_key=SARVAM_API_KEY)
    log.info("Sarvam client ready")
else:
    log.warning("SARVAM_API_KEY not set — /explain will not work")

# ── Supported languages ─────────────────────────────────────────────────────
SUPPORTED_LANGUAGES: dict[str, str] = {
    "hi-IN": "Hindi",
    "en-IN": "English",
    "ta-IN": "Tamil",
    "kn-IN": "Kannada",
    "te-IN": "Telugu",
    "mr-IN": "Marathi",
    "bn-IN": "Bengali",
    "gu-IN": "Gujarati",
    "ml-IN": "Malayalam",
    "pa-IN": "Punjabi",
}

# ── Speaker catalogue (bulbul:v3) — gender-tagged ───────────────────────────
# Source: https://docs.sarvam.ai (bulbul:v3 voice list)
# Male / Female pairs, plus a per-language recommended default.
SPEAKERS_MALE: list[str] = [
    "shubh", "aditya", "rahul", "rohan", "amit", "dev", "ratan", "varun",
    "manan", "sumit", "kabir", "aayan", "ashutosh", "advait", "anand",
    "tarun", "sunny", "mani", "gokul", "vijay", "mohit", "rehan", "soham",
]

SPEAKERS_FEMALE: list[str] = [
    "ritu", "priya", "neha", "pooja", "simran", "kavya", "ishita", "shreya",
    "roopa", "tanya", "shruti", "suhani", "kavitha", "rupali",
]

# Best male / female default per language (from Sarvam's recommendation table)
DEFAULT_SPEAKER_BY_LANG: dict[str, dict[str, str]] = {
    "hi-IN": {"male": "shubh", "female": "priya"},
    "en-IN": {"male": "ratan", "female": "ishita"},
    "ta-IN": {"male": "ratan", "female": "ishita"},
    "kn-IN": {"male": "shubh", "female": "ishita"},
    "te-IN": {"male": "shubh", "female": "neha"},
    "mr-IN": {"male": "ratan", "female": "priya"},
    "bn-IN": {"male": "rehan", "female": "roopa"},
    "gu-IN": {"male": "ratan", "female": "priya"},
    "ml-IN": {"male": "shubh", "female": "pooja"},
    "pa-IN": {"male": "mani", "female": "roopa"},
}

# ── Scholarship presets (Graduate & PG students) ─────────────────────────────
SCHOLARSHIP_PRESETS: list[dict[str, str]] = [
    {
        "id": "sch-ug-1",
        "level": "Graduate",
        "title": "National Scholarship Portal — UG",
        "url": "https://www.myscheme.gov.in/schemes/nsp",
        "question": "What scholarships are available for undergraduate students and how do I apply?",
    },
    {
        "id": "sch-ug-2",
        "level": "Graduate",
        "title": "Post-Matric Scholarship for SC Students",
        "url": "https://scholarships.gov.in/",
        "question": "Am I eligible for the Post-Matric SC scholarship as a graduate student?",
    },
    {
        "id": "sch-pg-1",
        "level": "Postgraduate",
        "title": "National Fellowship for Higher Education (MANF)",
        "url": "https://www.myscheme.gov.in/schemes/manf",
        "question": "What is the MANF fellowship for PG students and how do I apply?",
    },
    {
        "id": "sch-pg-2",
        "level": "Postgraduate",
        "title": "PG Scholarship for Professional Courses (GATE/GPAT)",
        "url": "https://www.myscheme.gov.in/schemes/pg-gate-scholarship",
        "question": "How much is the PG GATE scholarship and who is eligible?",
    },
    {
        "id": "sch-ug-pg-1",
        "level": "Both",
        "title": "Vidyalakshmi Portal — Education Loans",
        "url": "https://www.vidyalakshmi.co.in/Students/",
        "question": "What education loans are available for UG and PG students?",
    },
    {
        "id": "sch-pg-3",
        "level": "Postgraduate",
        "title": "Prime Minister's Research Fellowship (PMRF)",
        "url": "https://www.myscheme.gov.in/schemes/pmrf",
        "question": "What is the PM Research Fellowship for PG students and how do I apply?",
    },
]

# ── Appointment storage (in-memory; swap for a DB later) ────────────────────
APPOINTMENTS: list[dict[str, Any]] = []

APPOINTMENT_SLOTS: list[str] = [
    "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00",
]

# Office address (updated to Bangalore)
OFFICE_ADDRESS = {
    "line1": "Saral Yojana Help Desk",
    "line2": "3rd Floor, Brigade Gateway",
    "area": "Dr. Rajkumar Road, Malleshwaram",
    "city": "Bengaluru",
    "state": "Karnataka",
    "pincode": "560055",
    "phone": "+91 80 4567 8900",
    "email": "help@saralyojana.in",
    "maps_url": "https://maps.google.com/?q=Malleshwaram+Bengaluru+560055",
}

# ── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(title="Saral Yojana", version="2.0.0")

_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# ── Pydantic models ─────────────────────────────────────────────────────────
class ExplainRequest(BaseModel):
    url: str
    question: str = "What is this scheme, who is eligible, and how do I apply?"
    target_language: str = "hi-IN"
    voice_gender: str = "female"  # "male" or "female"
    speaker: Optional[str] = None     # override; if None, use language default


class AppointmentRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=10, max_length=15)
    email: str = ""
    date: str  # YYYY-MM-DD
    slot: str  # e.g. "10:00"
    language: str = "en-IN"
    notes: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Anakin helpers
# ─────────────────────────────────────────────────────────────────────────────
async def anakin_scrape(url: str) -> dict[str, Any]:
    """Scrape a single URL → markdown via Anakin URL Scraper."""
    headers = {
        "X-API-Key": ANAKIN_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"url": url, "country": "us", "useBrowser": False, "generateJson": False}
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(
                f"{ANAKIN_BASE}/url-scraper/scrape", headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                md = data.get("markdown", "")
                title = data.get("url", url)
                status = data.get("status", "")
                if status == "failed":
                    error = data.get("error", "Unknown error")
                    log.error(f"Anakin scrape failed with status: {error}")
                    raise RuntimeError(f"Scrape failed: {error}")
            else:
                md, title = "", url
            log.info(f"Scraped {url} → {len(md)} chars")
            return {"title": title, "markdown": md, "url": url}
        except Exception as e:
            log.error(f"Anakin scrape failed: {e}")
            raise RuntimeError(f"Scrape failed: {e}")


async def anakin_search(prompt: str, limit: int = 3) -> list[dict[str, Any]]:
    """Search the web via Anakin Search API → list of results."""
    headers = {
        "X-API-Key": ANAKIN_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"prompt": prompt, "limit": limit}
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{ANAKIN_BASE}/search", headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", []) if isinstance(data, dict) else data
            log.info(f"Anakin search '{prompt}' → {len(results)} results")
            return results[:limit]
        except Exception as e:
            log.error(f"Anakin search failed: {e}")
            return []


# ─────────────────────────────────────────────────────────────────────────────
# Sarvam helpers
# ─────────────────────────────────────────────────────────────────────────────
def _truncate(text: str, limit: int = 900) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[... content truncated for brevity]"


def _resolve_speaker(language_code: str, gender: str, override: Optional[str]) -> str:
    """Pick the best speaker for the language + gender, or use the override."""
    if override:
        return override
    defaults = DEFAULT_SPEAKER_BY_LANG.get(language_code, {})
    if gender == "male":
        return defaults.get("male", "shubh")
    return defaults.get("female", "priya")


def _normalize_sarvam_translation(result: Any) -> str:
    """Return a clean translation string, or an empty string if none is available."""
    translated_text = ""

    if hasattr(result, "translated_text"):
        translated_text = getattr(result, "translated_text") or ""
    elif isinstance(result, dict):
        translated_text = result.get("translated_text", "") or ""

    if not translated_text and hasattr(result, "translations") and result.translations:
        first = result.translations[0]
        if hasattr(first, "translated_text"):
            translated_text = first.translated_text or ""
        elif isinstance(first, dict):
            translated_text = first.get("translated_text", "") or ""

    if not translated_text and isinstance(result, dict):
        translations = result.get("translations", [])
        if translations and isinstance(translations, list):
            first = translations[0]
            if isinstance(first, dict):
                translated_text = first.get("translated_text", "") or ""

    return (translated_text or "").strip()


def sarvam_simplify_and_translate(
    page_markdown: str, question: str, target_language: str
) -> dict[str, str]:
    """Use Sarvam Translation to produce a simplified local-language answer."""
    if not sarvam_client:
        raise RuntimeError("Sarvam API key not configured")

    combined = (
        f"Question: {question}\n\n"
        f"Source page content:\n{page_markdown}\n\n"
        f"Instructions: Using ONLY the information above, write a clear, simple "
        f"summary for a common citizen. Answer the question directly. "
        f"Use short sentences and simple words. Cover: what the scheme is, who "
        f"is eligible, key benefits, and how to apply. "
        f"If the page does not contain the answer, say so honestly."
    )
    # Sarvam mayura:v1 rejects input longer than 1000 characters.
    combined = _truncate(combined, limit=900)
    if len(combined) > MAX_SARVAM_TRANSLATION_CHARS:
        combined = combined[:MAX_SARVAM_TRANSLATION_CHARS]

    result = sarvam_client.text.translate(
        input=combined,
        source_language_code="auto",
        target_language_code=target_language,
    )

    translated_text = _normalize_sarvam_translation(result)

    log.info(f"Sarvam translate → {len(translated_text)} chars")
    if not translated_text:
        translated_text = (
            "This page does not contain a specific scheme detail or usable text for a summary. "
            "Please use a specific government scheme page rather than the main portal homepage."
        )

    return {"simplified_text": translated_text, "language": target_language}


def sarvam_tts(text: str, language_code: str, speaker: str) -> bytes:
    """Generate speech audio via Sarvam TTS (bulbul:v3)."""
    if not sarvam_client:
        raise RuntimeError("Sarvam API key not configured")

    audio = sarvam_client.text_to_speech.convert(
        text=text,
        language_code=language_code,
        model="bulbul:v3",
        speaker=speaker,
    )

    import tempfile
    from sarvamai.play import save

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    save(audio, tmp.name)
    with open(tmp.name, "rb") as f:
        audio_bytes = f.read()
    os.unlink(tmp.name)

    log.info(f"Sarvam TTS (speaker={speaker}) → {len(audio_bytes)} bytes")
    return audio_bytes


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Meta
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "sarvam_configured": bool(SARVAM_API_KEY),
        "anakin_configured": bool(ANAKIN_API_KEY),
        "languages": SUPPORTED_LANGUAGES,
        "speakers_male": SPEAKERS_MALE,
        "speakers_female": SPEAKERS_FEMALE,
    }


@app.get("/api/languages")
async def languages():
    return SUPPORTED_LANGUAGES


@app.get("/api/speakers")
async def speakers():
    """Return the full speaker catalogue with gender tags."""
    return {
        "male": SPEAKERS_MALE,
        "female": SPEAKERS_FEMALE,
        "defaults": DEFAULT_SPEAKER_BY_LANG,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Scholarships
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/scholarships")
async def scholarships(level: Optional[str] = None):
    """Return scholarship presets, optionally filtered by level."""
    if level and level.lower() != "all":
        filtered = [
            s for s in SCHOLARSHIP_PRESETS
            if s["level"].lower() == level.lower() or s["level"] == "Both"
        ]
        return filtered
    return SCHOLARSHIP_PRESETS


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Explain (main pipeline)
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/explain")
async def explain(req: ExplainRequest):
    """
    Full pipeline:
      1. Anakin scrape the scheme URL
      2. Anakin search for recent references
      3. Sarvam simplify + translate
      4. Sarvam TTS → base64 audio (MALE or FEMALE voice, multi-language)

    Voice-first: audio is always generated; text is the secondary view.
    """
    if not SARVAM_API_KEY or not ANAKIN_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API keys not set. Copy .env.example to .env and fill in keys.",
        )

    # Validate gender
    gender = req.voice_gender.lower()
    if gender not in ("male", "female"):
        gender = "female"

    normalized_url = req.url.strip().rstrip("/").lower()
    if normalized_url in {"https://www.myscheme.gov.in", "https://myscheme.gov.in"}:
        raise HTTPException(
            status_code=422,
            detail="Please use a specific scheme page URL, not the portal homepage. Example: a scheme detail page like /schemes/pm-svanidhi.",
        )

    # 1. Scrape the page
    try:
        scraped = await anakin_scrape(req.url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to scrape URL: {e}")

    if not scraped["markdown"].strip():
        raise HTTPException(
            status_code=422, detail="The scraped page had no readable content."
        )

    # 2. Search for recent references
    search_prompt = (
        f"{req.question} — recent updates, eligibility, or news about "
        f"this scheme: {scraped.get('title', req.url)}"
    )
    search_results = await anakin_search(search_prompt, limit=3)

    # 3. Simplify + translate
    try:
        result = sarvam_simplify_and_translate(
            page_markdown=scraped["markdown"],
            question=req.question,
            target_language=req.target_language,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Sarvam translation failed: {e}"
        )

    # 4. TTS — resolve speaker by language + gender
    speaker = _resolve_speaker(req.target_language, gender, req.speaker)
    audio_b64 = None
    try:
        audio_bytes = sarvam_tts(result["simplified_text"], req.target_language, speaker)
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    except Exception as e:
        log.error(f"TTS failed (non-fatal): {e}")

    return JSONResponse(
        {
            "scraped_url": req.url,
            "page_title": scraped["title"],
            "question": req.question,
            "language": req.target_language,
            "voice_gender": gender,
            "speaker_used": speaker,
            "simplified_text": result["simplified_text"],
            "source_cards": [
                {
                    "title": r.get("title", r.get("url", "Source")),
                    "url": r.get("url", r.get("link", "")),
                    "snippet": r.get("snippet", r.get("description", "")),
                }
                for r in search_results
            ],
            "audio_base64": audio_b64,
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Appointments (offline in-person, Bangalore office)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/appointments/slots")
async def get_slots():
    """Return available appointment slots and office address."""
    return {
        "slots": APPOINTMENT_SLOTS,
        "address": OFFICE_ADDRESS,
    }


@app.post("/api/appointments/book")
async def book_appointment(req: AppointmentRequest):
    """Book an in-person appointment at the Bangalore office."""
    # Validate slot
    if req.slot not in APPOINTMENT_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid slot. Available: {', '.join(APPOINTMENT_SLOTS)}",
        )

    # Check for double-booking
    for appt in APPOINTMENTS:
        if appt["date"] == req.date and appt["slot"] == req.slot:
            raise HTTPException(
                status_code=409,
                detail=f"Slot {req.slot} on {req.date} is already booked. Please pick another.",
            )

    booking = {
        "id": str(uuid.uuid4())[:8],
        "name": req.name,
        "phone": req.phone,
        "email": req.email,
        "date": req.date,
        "slot": req.slot,
        "language": req.language,
        "notes": req.notes,
        "created_at": datetime.now().isoformat(),
        "status": "confirmed",
        "office": OFFICE_ADDRESS,
    }
    APPOINTMENTS.append(booking)
    log.info(f"Appointment booked: {booking['id']} for {req.name} on {req.date} {req.slot}")

    return JSONResponse(
        {
            "status": "confirmed",
            "booking_id": booking["id"],
            "name": req.name,
            "date": req.date,
            "slot": req.slot,
            "office": OFFICE_ADDRESS,
            "message": (
                f"Appointment confirmed for {req.name} on {req.date} at {req.slot}. "
                f"Please visit our Bengaluru office. Booking ID: {booking['id']}"
            ),
        },
        status_code=201,
    )


@app.get("/api/appointments")
async def list_appointments():
    """List all booked appointments (for demo / admin view)."""
    return {"appointments": APPOINTMENTS, "total": len(APPOINTMENTS)}


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Index
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = os.path.join(_static_dir, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=True)
