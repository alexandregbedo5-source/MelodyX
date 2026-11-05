"""MELODYX — B6: Gemini AI service for the music teacher.

Handles all communication with the Google Gemini API, including
the initial analysis summary and follow-up questions. Validates
responses, caches results, and handles failures gracefully.
"""

import hashlib
import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# System instruction for Gemini — never changes
_SYSTEM_INSTRUCTION = (
    "You are a friendly, knowledgeable music teacher helping students understand "
    "their piano performance analysis. Rules:\n"
    "1. NEVER invent notes, chords, or fingerings that are not in the provided data.\n"
    "2. Clearly distinguish between: MEASURED values (from audio analysis), "
    "ESTIMATED values (with confidence scores), and UNAVAILABLE data.\n"
    "3. Adapt your language to the student's level (beginner or intermediate).\n"
    "4. Respond in the requested language.\n"
    "5. Always respond with valid JSON matching the required schema.\n"
    "6. If asked about something not in the data, say it is unavailable."
)

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "grounding": {
            "type": "object",
            "properties": {
                "measured": {"type": "array", "items": {"type": "string"}},
                "estimated": {"type": "array", "items": {"type": "string"}},
                "unavailable": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["measured", "estimated", "unavailable"],
        },
    },
    "required": ["answer", "grounding"],
}


def _build_cache_key(analysis_id: str, selection: Optional[dict], question: str, level: str) -> str:
    """Build a deterministic cache key for an AI interaction."""
    raw = json.dumps({
        "analysis_id": analysis_id,
        "selection": selection,
        "question": question.strip().lower(),
        "level": level,
    }, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _build_context(analysis_data: dict, selection: Optional[dict] = None) -> str:
    """Build structured context string from analysis data.
    
    If selection is provided, only include notes and chords from
    the selected measure range.
    """
    music = analysis_data.get("music", {})
    
    context_parts = []
    
    # General info
    tempo = music.get("tempo_bpm", {})
    key = music.get("key", {})
    ts = music.get("time_signature", {})
    
    context_parts.append(f"Tempo: {tempo.get('value', 'unknown')} BPM (confidence: {tempo.get('confidence', 'N/A')})")
    context_parts.append(f"Key: {key.get('value', 'unknown')} (confidence: {key.get('confidence', 'N/A')})")
    context_parts.append(f"Time signature: {ts.get('value', 'unknown')} (confidence: {ts.get('confidence', 'N/A')})")
    
    notes = music.get("notes", [])
    chords = music.get("chords", [])
    measures = music.get("measures", [])
    
    # Filter by selection if provided
    if selection and measures:
        m_start = selection.get("measure_start", 1)
        m_end = selection.get("measure_end", m_start)
        notes = [n for n in notes if m_start <= n.get("measure", 0) <= m_end]
        
        # Filter chords by time range of selected measures
        sel_measures = [m for m in measures if m_start <= m.get("index", 0) <= m_end]
        if sel_measures:
            t_start = sel_measures[0].get("start", 0)
            t_end = sel_measures[-1].get("end", float("inf"))
            chords = [c for c in chords if c.get("start", 0) >= t_start and c.get("start", 0) < t_end]
        
        context_parts.append(f"\nSelected measures: {m_start} to {m_end}")
    
    # Notes
    if notes:
        context_parts.append(f"\nNotes ({len(notes)} total):")
        for n in notes[:50]:  # Cap context size
            context_parts.append(
                f"  - {n.get('name', '?')} (MIDI {n.get('pitch', '?')}), "
                f"start={n.get('start', '?')}s, dur={n.get('duration', '?')}s, "
                f"hand={n.get('hand', '?')}, confidence={n.get('confidence', '?')}"
            )
    
    # Chords
    if chords:
        context_parts.append(f"\nChords ({len(chords)} total):")
        for c in chords:
            context_parts.append(
                f"  - {c.get('label', '?')} at {c.get('start', '?')}s–{c.get('end', '?')}s "
                f"(confidence: {c.get('confidence', '?')})"
            )
    
    # Known limits
    context_parts.append("\nKnown limitations:")
    context_parts.append("  - Transcription is estimated (Basic Pitch model), not perfect")
    context_parts.append("  - Hand assignment (left/right) is heuristic based on pitch")
    context_parts.append("  - Fingerings are NOT available")
    context_parts.append("  - Chord detection is estimated via template matching")
    
    return "\n".join(context_parts)


def _call_gemini(prompt: str, system_instruction: str, config: dict) -> str:
    """Call the Gemini API with retry and timeout.
    
    Args:
        prompt: The user prompt.
        system_instruction: System instruction for the model.
        config: App config dict with GEMINI_API_KEY, GEMINI_MODEL, etc.
    
    Returns:
        The raw text response from Gemini.
    
    Raises:
        RuntimeError: If all retries are exhausted.
        ValueError: If the API key is not configured.
    """
    api_key = config.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")
    
    model_name = config.get("GEMINI_MODEL", "gemini-2.0-flash")
    timeout = config.get("GEMINI_TIMEOUT", 25)
    max_retries = config.get("GEMINI_MAX_RETRIES", 2)
    
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
    except ImportError:
        raise ImportError("google-genai package is required. Install with: pip install google-genai")
    
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
            )
            return response.text
        except Exception as e:
            last_error = e
            logger.warning("Gemini API call attempt %d failed: %s", attempt + 1, e)
            if attempt < max_retries:
                wait = 2 ** attempt  # Exponential backoff: 1s, 2s
                time.sleep(wait)
    
    raise RuntimeError(f"Gemini API call failed after {max_retries + 1} attempts: {last_error}")


def _validate_response(response: dict) -> bool:
    """Validate that the AI response matches the expected schema."""
    if not isinstance(response, dict):
        return False
    if "answer" not in response or "grounding" not in response:
        return False
    grounding = response["grounding"]
    if not isinstance(grounding, dict):
        return False
    for key in ("measured", "estimated", "unavailable"):
        if key not in grounding or not isinstance(grounding[key], list):
            return False
    return True


def get_ai_summary(analysis_data: dict, config: dict) -> dict:
    """Generate an AI summary of the analysis results.
    
    Args:
        analysis_data: The complete analysis result dict.
        config: App configuration dict.
    
    Returns:
        A dict with keys: answer, grounding, model, cached.
        On failure: {"available": False, "error": str}
    """
    try:
        context = _build_context(analysis_data)
        prompt = (
            f"Analyze this piano performance and provide a helpful, educational summary.\n\n"
            f"Musical data:\n{context}\n\n"
            f"Provide a clear summary suitable for a beginner student. "
            f"Respond in JSON with 'answer' (string) and 'grounding' "
            f"(object with 'measured', 'estimated', 'unavailable' arrays of strings)."
        )
        
        raw = _call_gemini(prompt, _SYSTEM_INSTRUCTION, config)
        response = json.loads(raw)
        
        if not _validate_response(response):
            logger.error("AI response failed schema validation: %s", raw[:500])
            return {"available": False, "error": "AI response did not match expected format."}
        
        model_name = config.get("GEMINI_MODEL", "gemini-2.0-flash")
        return {
            "available": True,
            "summary": response["answer"],
            "grounding": response["grounding"],
            "model": model_name,
            "cached": False,
        }
    except Exception as e:
        logger.exception("AI summary generation failed.")
        return {"available": False, "error": str(e)}


def ask_teacher(
    analysis_data: dict,
    question: str,
    selection: Optional[dict],
    level: str,
    language: str,
    config: dict,
) -> dict:
    """Answer a student's question about a specific part of the analysis.
    
    Args:
        analysis_data: The complete analysis result dict.
        question: The student's question.
        selection: Optional dict with measure_start and measure_end.
        level: "beginner" or "intermediate".
        language: Language code ("fr" or "en").
        config: App configuration dict.
    
    Returns:
        A dict with keys: answer, grounding, model, cached.
        On failure: {"available": False, "error": str}
    """
    try:
        context = _build_context(analysis_data, selection)
        
        lang_instruction = "Respond in French." if language == "fr" else "Respond in English."
        level_instruction = (
            "The student is a beginner — use simple, encouraging language."
            if level == "beginner"
            else "The student is intermediate — you can use some technical terms."
        )
        
        prompt = (
            f"A {level} piano student asks: \"{question}\"\n\n"
            f"Musical context:\n{context}\n\n"
            f"{level_instruction}\n{lang_instruction}\n"
            f"Respond in JSON with 'answer' (string) and 'grounding' "
            f"(object with 'measured', 'estimated', 'unavailable' arrays of strings)."
        )
        
        raw = _call_gemini(prompt, _SYSTEM_INSTRUCTION, config)
        response = json.loads(raw)
        
        if not _validate_response(response):
            logger.error("Teacher response failed validation: %s", raw[:500])
            return {"available": False, "error": "AI response did not match expected format."}
        
        model_name = config.get("GEMINI_MODEL", "gemini-2.0-flash")
        return {
            "answer": response["answer"],
            "grounding": response["grounding"],
            "model": model_name,
            "cached": False,
        }
    except Exception as e:
        logger.exception("Teacher question failed.")
        return {"available": False, "error": str(e)}
