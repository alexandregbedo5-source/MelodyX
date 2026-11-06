"""MELODYX — B7: Analysis pipeline orchestration.

Chains all processing steps (B2→B3→B4→B5→B6) in a background thread
and updates analysis status/progress in the database at each stage.
"""

import json
import logging
import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from flask import Flask

logger = logging.getLogger(__name__)

# Module-level executor — one worker to avoid resource contention
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="melodyx-pipeline")


def _utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_pipeline(app: Flask, analysis_id: str) -> None:
    """Execute the full analysis pipeline inside an application context.

    Stages (in order):
        1. decoding     — B2: ffmpeg conversion, silence check
        2. features     — B3: chroma, energy, tempo, key, chords
        3. transcription— B4: Basic Pitch note detection
        4. quantization — B4: snap to grid, measures, hand assignment
        5. notation     — B5: MIDI and MusicXML generation
        6. ai_interpretation — B6: Gemini summary (failure ≠ analysis failure)

    On critical failure (stages 1–5), the analysis status is set to
    ``failed``.  If only the AI step fails, the analysis is marked
    ``completed`` with ``ai.available = false``.
    """
    with app.app_context():
        from app.models.analysis import (
            update_analysis_status,
            add_warning,
            save_result,
            save_artifact,
            get_analysis,
        )
        from app.extensions import get_db

        # Retrieve the analysis row (we need stored_path)
        db = get_db()
        row = db.execute(
            "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
        if not row:
            logger.error("Pipeline: analysis %s not found.", analysis_id)
            return

        stored_path = row["stored_path"]
        original_filename = row["original_filename"] if "original_filename" in row.keys() and row["original_filename"] else os.path.basename(stored_path)
        analysis_dir = os.path.dirname(stored_path)
        config = app.config

        # Accumulators for the final result
        audio_info: dict[str, Any] = {}
        rhythm_data: dict[str, Any] = {}
        harmony_data: dict[str, Any] = {}
        raw_notes: list[dict] = []
        quantized_notes: list[dict] = []
        measures: list[dict] = []
        ai_result: dict[str, Any] = {"available": False}

        try:
            # ===== STAGE 1: DECODING (B2) ====================================
            update_analysis_status(
                analysis_id, "processing", stage="decoding", progress=0.05
            )
            logger.info("[%s] Stage: decoding", analysis_id)

            from app.services.audio_loader import decode_audio

            decode_result = decode_audio(stored_path, analysis_dir)
            wav_path = decode_result["wav_path"]
            audio_info = {
                "duration_seconds": decode_result["duration_seconds"],
                "sample_rate": decode_result["sample_rate"],
                "channels": decode_result["channels"],
            }
            # Persist audio metadata
            update_analysis_status(
                analysis_id, "processing",
                stage="decoding", progress=0.15,
                duration_seconds=audio_info["duration_seconds"],
                sample_rate=audio_info["sample_rate"],
                channels=audio_info["channels"],
            )
            # Warnings from decoding (e.g. silent_audio)
            for w in decode_result.get("warnings", []):
                if isinstance(w, str):
                    add_warning(analysis_id, {
                        "code": w,
                        "severity": "warning",
                        "message": f"Warning: {w}",
                    })
                else:
                    add_warning(analysis_id, w)

            # ===== STAGE 2: FEATURES (B3) ====================================
            update_analysis_status(
                analysis_id, "processing", stage="features", progress=0.20
            )
            logger.info("[%s] Stage: features", analysis_id)

            from app.services.rhythm_analysis import analyze_rhythm
            from app.services.harmony_analysis import analyze_harmony

            rhythm_data = analyze_rhythm(wav_path)
            update_analysis_status(
                analysis_id, "processing", stage="features", progress=0.35
            )

            harmony_data = analyze_harmony(wav_path)
            update_analysis_status(
                analysis_id, "processing", stage="features", progress=0.45
            )

            # Check confidence on tempo
            tempo_conf = rhythm_data.get("tempo_bpm", {}).get("confidence", 1.0)
            if tempo_conf < 0.5:
                add_warning(analysis_id, {
                    "code": "low_confidence_tempo",
                    "severity": "info",
                    "message": "Tempo estimated with low confidence.",
                })

            # ===== STAGE 3: TRANSCRIPTION (B4) ===============================
            update_analysis_status(
                analysis_id, "processing", stage="transcription", progress=0.50
            )
            logger.info("[%s] Stage: transcription", analysis_id)

            from app.services.transcription import transcribe_audio

            raw_notes = transcribe_audio(wav_path)
            update_analysis_status(
                analysis_id, "processing", stage="transcription", progress=0.60
            )

            if not raw_notes:
                add_warning(analysis_id, {
                    "code": "no_notes_detected",
                    "severity": "warning",
                    "message": "No notes were detected in the audio.",
                })

            # ===== STAGE 4: QUANTIZATION (B4) ================================
            update_analysis_status(
                analysis_id, "processing", stage="quantization", progress=0.65
            )
            logger.info("[%s] Stage: quantization", analysis_id)

            from app.services.quantization import quantize_notes

            beats = rhythm_data.get("beats", [])
            time_sig = rhythm_data.get("time_signature", {}).get("value", "4/4")
            quantized_notes, measures = quantize_notes(raw_notes, beats, time_sig)
            update_analysis_status(
                analysis_id, "processing", stage="quantization", progress=0.70
            )

            # ===== STAGE 5: NOTATION (B5) ====================================
            update_analysis_status(
                analysis_id, "processing", stage="notation", progress=0.72
            )
            logger.info("[%s] Stage: notation", analysis_id)

            # --- MIDI ---
            from app.services.midi_generator import generate_midi

            midi_path = os.path.join(analysis_dir, f"{analysis_id}.mid")
            tempo_bpm = rhythm_data.get("tempo_bpm", {}).get("value") or 120.0
            if tempo_bpm <= 0:
                tempo_bpm = 120.0
            generate_midi(quantized_notes, tempo_bpm, midi_path)

            midi_size = os.path.getsize(midi_path)
            save_artifact(analysis_id, "midi", midi_path, "audio/midi", midi_size)
            update_analysis_status(
                analysis_id, "processing", stage="notation", progress=0.80
            )

            # --- MusicXML ---
            from app.services.score_generator import generate_musicxml

            musicxml_path = os.path.join(analysis_dir, f"{analysis_id}.musicxml")
            key_name = harmony_data.get("key", {}).get("value", "C major")
            chords = harmony_data.get("chords", [])
            generate_musicxml(
                quantized_notes, tempo_bpm, key_name, time_sig, chords, musicxml_path
            )

            xml_size = os.path.getsize(musicxml_path)
            save_artifact(
                analysis_id, "musicxml", musicxml_path,
                "application/vnd.recordare.musicxml+xml", xml_size,
            )

            # --- PDF Sheet Music Score ---
            try:
                from app.services.pdf_generator import generate_sheet_music_pdf
                pdf_path = os.path.join(analysis_dir, f"{analysis_id}.pdf")
                pdf_result_dict = {
                    "audio": {"filename": original_filename},
                    "music": {
                        "tempo_bpm": {"value": tempo_bpm},
                        "key": {"value": key_name},
                        "time_signature": {"value": time_sig},
                        "chords": chords,
                        "measures": measures,
                        "notes": quantized_notes,
                    },
                }
                generate_sheet_music_pdf(pdf_result_dict, pdf_path)
                pdf_size = os.path.getsize(pdf_path)
                save_artifact(analysis_id, "pdf", pdf_path, "application/pdf", pdf_size)
            except Exception as pdf_exc:
                logger.warning("[%s] PDF generation warning (non-fatal): %s", analysis_id, pdf_exc)

            update_analysis_status(
                analysis_id, "processing", stage="notation", progress=0.85
            )

        except Exception as exc:
            # Critical failure in stages 1–5
            logger.exception("[%s] Pipeline failed at a critical stage.", analysis_id)
            error_code = "pipeline_error"
            if "transcri" in str(exc).lower():
                error_code = "transcription_failed"
            elif "decode" in str(exc).lower() or "ffmpeg" in str(exc).lower():
                error_code = "decoding_failed"

            update_analysis_status(
                analysis_id, "failed",
                error_code=error_code,
                error_message=str(exc)[:500],
                completed_at=_utcnow_iso(),
            )
            return

        # ===== STAGE 6: AI INTERPRETATION (B6) — non-critical ===========
        try:
            update_analysis_status(
                analysis_id, "processing", stage="ai_interpretation", progress=0.88
            )
            logger.info("[%s] Stage: ai_interpretation", analysis_id)

            from app.services.gemini_service import get_ai_summary

            # Build a temporary result dict for AI context
            temp_result = {
                "music": {
                    "tempo_bpm": rhythm_data.get("tempo_bpm", {}),
                    "key": harmony_data.get("key", {}),
                    "time_signature": rhythm_data.get("time_signature", {}),
                    "chords": harmony_data.get("chords", []),
                    "beats": rhythm_data.get("beats", []),
                    "measures": measures,
                    "notes": quantized_notes,
                },
            }
            ai_result = get_ai_summary(temp_result, dict(config))

        except Exception as exc:
            logger.warning(
                "[%s] AI interpretation failed (non-critical): %s",
                analysis_id, exc,
            )
            ai_result = {"available": False, "error": str(exc)}

        # ===== ASSEMBLE FINAL RESULT ======================================
        update_analysis_status(
            analysis_id, "processing", stage="ai_interpretation", progress=0.95
        )

        result = {
            "schema_version": config.get("SCHEMA_VERSION", "1.0"),
            "analysis_id": analysis_id,
            "audio": audio_info,
            "music": {
                "tempo_bpm": rhythm_data.get("tempo_bpm", {}),
                "key": harmony_data.get("key", {}),
                "time_signature": rhythm_data.get("time_signature", {}),
                "chords": harmony_data.get("chords", []),
                "beats": rhythm_data.get("beats", []),
                "measures": measures,
                "notes": quantized_notes,
            },
            "ai": ai_result,
            "limits": {
                "max_file_mb": config.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024) // (1024 * 1024),
                "max_duration_s": config.get("MAX_DURATION_SECONDS", 240),
            },
        }

        result_json = json.dumps(result, ensure_ascii=False)
        save_result(analysis_id, result_json, config.get("SCHEMA_VERSION", "1.0"))

        update_analysis_status(
            analysis_id, "completed",
            stage="ai_interpretation",
            progress=1.0,
            completed_at=_utcnow_iso(),
        )
        logger.info("[%s] Pipeline completed successfully.", analysis_id)


def submit_pipeline(app: Flask, analysis_id: str) -> None:
    """Submit the analysis pipeline to the background executor.

    The pipeline runs in a single-threaded executor to avoid resource
    contention from parallel audio processing.

    Args:
        app: The Flask application (needed for app context in the thread).
        analysis_id: The analysis to process.
    """
    if app.config.get("TESTING") and not app.config.get("RUN_PIPELINE_IN_TESTS"):
        logger.info("Test mode: skipping background pipeline execution for %s", analysis_id)
        return

    logger.info("Submitting pipeline for analysis %s", analysis_id)
    _executor.submit(run_pipeline, app, analysis_id)
