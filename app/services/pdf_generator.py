"""MELODYX — Vector Sheet Music & PDF Score Engraving Service.

Produces publication-grade, classical opera/conservatoire-quality piano sheet
music scores (grand staff: treble + bass, key signatures, chord symbols, measure
numbers, rehearsal marks, multi-page layout, and conductor lead sheet guide)
visually identical to classical opera editions.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any, Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page Geometry Constants (A4: 595.27 x 841.89 points)
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = A4
MARGIN_LEFT = 48.0
MARGIN_RIGHT = PAGE_W - 48.0
STAFF_W = MARGIN_RIGHT - MARGIN_LEFT

LINE_SP = 7.0               # Distance between staff lines
STAFF_H = 4 * LINE_SP       # Height of one 5-line staff = 28 points
INTER_STAFF_GAP = 38.0      # Space between treble and bass staves
SYSTEM_H = 2 * STAFF_H + INTER_STAFF_GAP  # Height of one grand staff system = 94 points
SYSTEM_GAP = 36.0           # Vertical space between successive systems

TREBLE_BOTTOM_STEP = 28     # E4 diatonic step (line 0 of treble staff)
BASS_BOTTOM_STEP = 16       # G2 diatonic step (line 0 of bass staff)

KEY_SIGNATURES: dict[str, tuple[int, bool]] = {
    "C major": (0, False), "A minor": (0, False),
    "G major": (1, False), "E minor": (1, False),
    "D major": (2, False), "B minor": (2, False),
    "A major": (3, False), "F# minor": (3, False),
    "E major": (4, False), "C# minor": (4, False),
    "B major": (5, False), "G# minor": (5, False),
    "F# major": (6, False), "D# minor": (6, False),
    "C# major": (7, False), "A# minor": (7, False),
    "F major": (1, True),  "D minor": (1, True),
    "Bb major": (2, True), "G minor": (2, True),
    "Eb major": (3, True), "C minor": (3, True),
    "Ab major": (4, True), "F minor": (4, True),
    "Db major": (5, True), "Bb minor": (5, True),
    "Gb major": (6, True), "Eb minor": (6, True),
    "Cb major": (7, True), "Ab minor": (7, True),
}

_G_CLEF_PATH = """m 488 1499 b 495 1500 490 1500 492 1500 b 541 1465 507 1500 521 1490 b 679 1078 622 1372 679 1210 b 677 1050 679 1068 677 1060 b 477 642 668 893 604 764 l 443 609 l 431 596 l 431 592 l 438 562 l 449 508 l 460 458 b 481 355 475 390 481 355 b 481 355 481 355 481 355 b 490 356 481 355 485 355 b 528 358 495 356 511 358 b 558 356 540 358 552 356 b 839 95 699 338 808 237 b 847 22 845 72 847 47 b 631 -303 847 -113 766 -242 b 620 -309 623 -308 620 -309 l 620 -310 b 631 -359 620 -310 626 -333 l 646 -435 l 660 -496 b 672 -588 668 -535 672 -563 b 664 -653 672 -610 669 -630 b 383 -875 630 -792 509 -875 b 201 -810 321 -875 257 -855 b 129 -680 151 -768 129 -730 b 274 -530 129 -592 200 -530 b 351 -553 300 -530 326 -538 b 412 -669 393 -582 412 -626 b 287 -805 412 -735 366 -800 l 279 -805 l 285 -809 b 383 -830 318 -823 351 -830 b 586 -718 464 -830 540 -789 b 626 -584 612 -678 626 -631 b 619 -528 626 -566 623 -548 b 612 -495 619 -526 616 -510 b 577 -324 590 -387 577 -324 b 577 -324 577 -324 577 -324 b 568 -326 575 -324 571 -324 b 528 -334 558 -328 537 -333 b 465 -338 506 -337 485 -338 b 24 -11 269 -338 87 -206 b -1 145 8 41 -1 93 b 96 442 -1 249 32 351 b 322 714 166 541 236 626 l 352 745 l 345 782 l 332 843 l 315 921 b 303 984 310 950 304 978 b 295 1082 298 1017 295 1049 b 413 1426 295 1208 336 1329 b 488 1499 436 1456 477 1496 m 549 1301 b 541 1301 547 1301 544 1301 b 411 1207 500 1301 447 1263 b 355 1004 374 1152 355 1079 b 359 942 355 984 356 963 b 371 881 362 927 363 917 l 385 818 b 392 782 389 799 392 784 l 392 782 b 434 828 393 782 424 816 b 607 1165 534 941 594 1060 b 608 1193 608 1175 608 1183 b 597 1270 608 1224 604 1254 b 549 1301 589 1286 571 1299 m 398 528 b 393 555 396 542 393 553 b 392 555 393 555 393 555 b 317 470 390 555 347 505 b 190 298 266 408 212 334 b 127 70 148 227 127 148 b 155 -77 127 19 137 -30 b 468 -303 209 -216 333 -303 b 519 -299 484 -303 502 -302 b 568 -284 541 -295 568 -287 l 568 -284 b 563 -263 568 -284 566 -274 l 534 -120 l 511 -13 l 496 61 l 480 133 b 469 187 472 176 469 187 b 468 188 469 187 469 188 b 416 162 462 188 430 172 b 337 13 364 126 337 69 b 413 -124 337 -40 363 -93 b 428 -144 424 -131 428 -137 b 428 -149 428 -145 428 -148 b 409 -166 426 -161 419 -166 b 394 -162 405 -166 400 -165 b 240 77 302 -122 240 -27 l 240 77 b 430 342 240 197 315 301 l 436 344 l 426 394 l 398 528 m 548 194 b 526 195 540 195 532 195 b 519 195 524 195 521 195 l 514 195 l 518 177 l 539 79 l 552 15 l 566 -48 l 594 -187 l 605 -240 b 612 -266 609 -254 611 -266 b 612 -266 612 -266 612 -266 b 641 -248 613 -266 630 -256 b 744 -98 692 -212 730 -156 b 751 -40 749 -79 751 -59 b 548 194 751 76 665 181 """

_F_CLEF_PATH = """m 307 349 b 332 351 315 351 323 351 b 443 340 367 351 408 347 b 741 47 607 306 720 195 b 744 0 743 31 744 16 b 660 -303 744 -90 713 -206 b 28 -755 534 -531 304 -695 b 14 -756 23 -755 19 -756 b -1 -741 4 -756 -1 -750 b 21 -720 -1 -731 1 -728 b 567 -56 337 -601 548 -344 b 568 -11 568 -41 568 -24 b 442 285 568 129 525 233 b 325 319 406 308 367 319 b 93 177 232 319 137 266 b 84 154 91 170 84 155 b 84 154 84 154 84 154 b 88 156 84 154 85 155 b 159 177 110 170 134 177 b 257 134 194 177 231 162 b 294 41 281 108 294 73 b 171 -97 294 -24 246 -90 b 156 -98 166 -97 161 -98 b 6 74 73 -98 6 -22 b 6 80 6 76 6 79 b 307 349 10 223 141 340 m 839 215 b 845 216 841 216 842 216 b 862 213 852 216 860 215 b 899 163 887 206 899 184 b 872 117 899 145 890 127 b 847 111 865 112 856 111 b 808 130 833 111 818 117 b 796 162 800 140 796 151 b 839 215 796 187 812 212 m 839 -112 b 845 -112 841 -112 842 -112 b 862 -115 852 -112 860 -113 b 899 -165 887 -122 899 -144 b 872 -210 899 -183 890 -201 b 847 -217 865 -215 856 -217 b 808 -198 833 -217 818 -210 b 796 -165 800 -188 796 -177 b 839 -112 796 -140 812 -116 """



_G_CLEF_TOKENS = _G_CLEF_PATH.split()
_F_CLEF_TOKENS = _F_CLEF_PATH.split()


def pitch_to_diatonic(pitch: int) -> tuple[int, bool]:
    """Convert a MIDI pitch to (absolute_diatonic_step, is_accidental)."""
    chromatic = pitch % 12
    octave = pitch // 12 - 1
    diatonic_map = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 10: 5, 11: 6}
    accidental_set = {1, 3, 6, 8, 10}
    return octave * 7 + diatonic_map[chromatic], chromatic in accidental_set


def render_vexflow_glyph(
    c: canvas.Canvas,
    tokens: list[str],
    x: float,
    y: float,
    scale_x: float,
    scale_y: float,
):
    """Render a VexFlow vector glyph outline onto ReportLab canvas."""
    p = c.beginPath()
    h = 0
    cur_x, cur_y = x, y

    def next_x() -> float:
        nonlocal h
        val = float(tokens[h])
        h += 1
        return x + val * scale_x

    def next_y() -> float:
        nonlocal h
        val = float(tokens[h])
        h += 1
        return y + val * scale_y

    while h < len(tokens):
        cmd = tokens[h]
        h += 1
        if cmd == "m":
            cur_x = next_x()
            cur_y = next_y()
            p.moveTo(cur_x, cur_y)
        elif cmd == "l":
            cur_x = next_x()
            cur_y = next_y()
            p.lineTo(cur_x, cur_y)
        elif cmd == "q":
            qx, qy = next_x(), next_y()
            ex, ey = next_x(), next_y()
            cp1_x = cur_x + (2.0 / 3.0) * (qx - cur_x)
            cp1_y = cur_y + (2.0 / 3.0) * (qy - cur_y)
            cp2_x = ex + (2.0 / 3.0) * (qx - ex)
            cp2_y = ey + (2.0 / 3.0) * (qy - ey)
            p.curveTo(cp1_x, cp1_y, cp2_x, cp2_y, ex, ey)
            cur_x, cur_y = ex, ey
        elif cmd == "b":
            ex, ey = next_x(), next_y()
            cp1_x, cp1_y = next_x(), next_y()
            cp2_x, cp2_y = next_x(), next_y()
            p.curveTo(cp1_x, cp1_y, cp2_x, cp2_y, ex, ey)
            cur_x, cur_y = ex, ey

    c.setFillColorRGB(0.08, 0.08, 0.08)
    c.drawPath(p, fill=1, stroke=0)


def draw_brace(c: canvas.Canvas, x: float, y_top: float, y_bottom: float):
    """Draw a classical calligraphic piano brace linking treble and bass staves."""
    h = y_top - y_bottom
    mid = (y_top + y_bottom) / 2.0
    p = c.beginPath()
    p.moveTo(x, y_top)
    p.curveTo(x - 6, y_top - h * 0.15, x - 6, mid + h * 0.12, x - 12, mid)
    p.curveTo(x - 6, mid - h * 0.12, x - 6, y_bottom + h * 0.15, x, y_bottom)
    c.setLineWidth(1.8)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    c.drawPath(p, stroke=1, fill=0)


def draw_treble_clef(c: canvas.Canvas, x: float, y_bot: float, sp: float):
    """Draw classical vector G-clef (clé de sol) centered on line 2 (G4)."""
    render_vexflow_glyph(c, _G_CLEF_TOKENS, x, y_bot + sp, 0.024, 0.024)


def draw_bass_clef(c: canvas.Canvas, x: float, y_bot: float, sp: float):
    """Draw classical vector F-clef (clé de fa) centered on line 4 (F3)."""
    render_vexflow_glyph(c, _F_CLEF_TOKENS, x, y_bot + 3 * sp, 0.024, 0.024)


def draw_key_signature(
    c: canvas.Canvas,
    key_name: str,
    x: float,
    treble_y: Optional[float] = None,
    bass_y: Optional[float] = None,
    sp: float = 7.0,
) -> float:
    """Draw key signature accidentals and return the horizontal width consumed."""
    key_clean = key_name.strip()
    num_acc, is_flat = KEY_SIGNATURES.get(key_clean, (0, False))
    if num_acc == 0:
        for k, val in KEY_SIGNATURES.items():
            if k.lower() in key_clean.lower():
                num_acc, is_flat = val
                break

    if num_acc == 0:
        return 0.0

    sharps_treble = [4.0, 2.5, 4.5, 3.0, 1.5, 3.5, 2.0]
    sharps_bass = [3.0, 1.5, 3.5, 2.0, 0.5, 2.5, 1.0]

    flats_treble = [2.0, 3.5, 1.5, 3.0, 1.0, 2.5, 0.5]
    flats_bass = [1.0, 2.5, 0.5, 2.0, 0.0, 1.5, -0.5]

    symbol = "b" if is_flat else "#"
    c.setFont("Times-Bold", 10)

    for i in range(min(num_acc, 7)):
        sx = x + i * 7.5
        t_pos = flats_treble[i] if is_flat else sharps_treble[i]
        b_pos = flats_bass[i] if is_flat else sharps_bass[i]
        if treble_y is not None:
            c.drawString(sx, treble_y + t_pos * sp - 4, symbol)
        if bass_y is not None:
            c.drawString(sx, bass_y + b_pos * sp - 4, symbol)

    return min(num_acc, 7) * 7.5


def group_notes_into_chords(m_notes: list[dict]) -> tuple[list[dict], list[dict]]:
    """Deduplicate note events and group simultaneous pitches into single chords."""
    deduped: list[dict] = []
    seen: set[tuple] = set()
    for n in sorted(m_notes, key=lambda x: -x.get("duration", 0)):
        hand = n.get("hand", "right")
        pitch = n.get("pitch", 60)
        beat_q = round(n.get("beat_position", 0.0) * 8) / 8
        key = (hand, pitch, beat_q)
        if key not in seen:
            seen.add(key)
            deduped.append(n)
    deduped.sort(key=lambda x: x.get("beat_position", 0.0))

    treble_chords: list[dict] = []
    bass_chords: list[dict] = []

    for n in deduped:
        pitch = n.get("pitch", 60)
        hand = n.get("hand", "right")
        beat = n.get("beat_position", 0.0)
        dur = n.get("duration", 0.5)
        target = bass_chords if (hand == "left" or pitch < 57) else treble_chords

        if target and abs(target[-1]["beat"] - beat) < 0.12:
            target[-1]["pitches"].append((pitch, dur))
        else:
            target.append({
                "beat": beat,
                "pitches": [(pitch, dur)],
            })

    return treble_chords, bass_chords


def draw_chord(
    c: canvas.Canvas,
    x: float,
    pitches: list[tuple[int, float]],
    staff_bot: float,
    staff_top: float,
    sp: float,
    base_step: int,
) -> tuple[float, float, bool, float]:
    """Draw a chord with all noteheads and a single shared musical stem."""
    unique_pitches = sorted(list({p: d for p, d in pitches}.items()), key=lambda x: x[0])
    y_coords: list[tuple[float, float]] = []

    for pitch, dur in unique_pitches:
        abs_step, _ = pitch_to_diatonic(pitch)
        delta_steps = abs_step - base_step
        ny = staff_bot + delta_steps * (sp / 2.0)
        y_coords.append((ny, dur))

        # Ledger lines
        c.setLineWidth(0.6)
        c.setStrokeColorRGB(0.1, 0.1, 0.1)
        if ny < staff_bot:
            cur_y = staff_bot - sp
            while cur_y >= ny - 1.0:
                c.line(x - 5.5, cur_y, x + 5.5, cur_y)
                cur_y -= sp
        elif ny > staff_top:
            cur_y = staff_top + sp
            while cur_y <= ny + 1.0:
                c.line(x - 5.5, cur_y, x + 5.5, cur_y)
                cur_y += sp

        # Angled notehead
        c.saveState()
        c.translate(x, ny)
        c.rotate(18)
        if dur >= 2.0:
            c.setLineWidth(1.2)
            c.setFillColorRGB(1.0, 1.0, 1.0)
            c.ellipse(-3.2, -2.1, 3.2, 2.1, stroke=1, fill=0)
        else:
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.ellipse(-3.2, -2.1, 3.2, 2.1, stroke=0, fill=1)
        c.restoreState()

    lowest_y = y_coords[0][0]
    highest_y = y_coords[-1][0]
    avg_y = (lowest_y + highest_y) / 2.0
    mid_staff = (staff_bot + staff_top) / 2.0

    c.setLineWidth(0.7)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    if avg_y < mid_staff:
        stem_x = x + 2.8
        stem_tip_y = highest_y + 20
        c.line(stem_x, lowest_y, stem_x, stem_tip_y)
        return stem_x, stem_tip_y, True, lowest_y
    else:
        stem_x = x - 2.8
        stem_tip_y = lowest_y - 20
        c.line(stem_x, highest_y, stem_x, stem_tip_y)
        return stem_x, stem_tip_y, False, highest_y


def draw_note(
    c: canvas.Canvas,
    x: float,
    y: float,
    staff_bot: float,
    staff_top: float,
    sp: float,
    dur: float = 0.5,
) -> tuple[float, float, bool]:
    """Single note fallback helper."""
    c.setLineWidth(0.6)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    if y < staff_bot:
        cur_y = staff_bot - sp
        while cur_y >= y - 1.0:
            c.line(x - 5.5, cur_y, x + 5.5, cur_y)
            cur_y -= sp
    elif y > staff_top:
        cur_y = staff_top + sp
        while cur_y <= y + 1.0:
            c.line(x - 5.5, cur_y, x + 5.5, cur_y)
            cur_y += sp

    c.saveState()
    c.translate(x, y)
    c.rotate(18)
    if dur >= 2.0:
        c.setLineWidth(1.2)
        c.setFillColorRGB(1.0, 1.0, 1.0)
        c.ellipse(-3.2, -2.1, 3.2, 2.1, stroke=1, fill=0)
    else:
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.ellipse(-3.2, -2.1, 3.2, 2.1, stroke=0, fill=1)
    c.restoreState()

    mid_staff = (staff_bot + staff_top) / 2.0
    c.setLineWidth(0.7)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    if y < mid_staff:
        stem_x = x + 2.8
        stem_end_y = y + 20
        c.line(stem_x, y, stem_x, stem_end_y)
        return stem_x, stem_end_y, True
    else:
        stem_x = x - 2.8
        stem_end_y = y - 20
        c.line(stem_x, y, stem_x, stem_end_y)
        return stem_x, stem_end_y, False


def draw_beams_for_measure(c: canvas.Canvas, stems: list):
    """Connect stems of adjacent eighth/sixteenth notes with a musical clamped beam."""
    if len(stems) < 2:
        return
    stems = sorted(stems, key=lambda s: s[4])
    c.setLineWidth(2.4)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    for i in range(len(stems) - 1):
        s1 = stems[i]
        s2 = stems[i + 1]
        x1, tip1, is_up1, root1, beat1 = s1
        x2, tip2, is_up2, root2, beat2 = s2
        if is_up1 == is_up2 and 0.2 <= (beat2 - beat1) <= 1.1:
            dx = x2 - x1
            dy = tip2 - tip1
            max_dy = 0.35 * dx
            if dy > max_dy:
                target_tip2 = tip1 + max_dy
                c.setLineWidth(0.7)
                c.line(x2, tip2, x2, target_tip2)
                tip2 = target_tip2
            elif dy < -max_dy:
                target_tip2 = tip1 - max_dy
                c.setLineWidth(0.7)
                c.line(x2, tip2, x2, target_tip2)
                tip2 = target_tip2
            c.setLineWidth(2.4)
            c.line(x1, tip1, x2, tip2)


def generate_sheet_music_pdf(
    result_data: dict[str, Any],
    output_path: str,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    max_measures: Optional[int] = None,
    instrument: str = "piano",
) -> str:
    """Generate a publication-grade classical sheet music score PDF from analysis results."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    music = result_data.get("music", {})
    notes = music.get("notes", [])
    measures = music.get("measures", [])
    tempo_info = music.get("tempo_bpm", {})
    tempo_val = round(tempo_info.get("value", 120.0)) if isinstance(tempo_info, dict) else round(float(tempo_info or 120.0))
    key_info = music.get("key", {})
    key_name = key_info.get("value", "C major") if isinstance(key_info, dict) else str(key_info or "C major")
    time_sig_info = music.get("time_signature", {})
    time_sig = time_sig_info.get("value", "4/4") if isinstance(time_sig_info, dict) else str(time_sig_info or "4/4")
    chords = music.get("chords", [])

    is_single_staff = instrument in ("bass", "lead")

    if not title:
        raw_fn = result_data.get("audio", {}).get("filename", "")
        if raw_fn:
            base_t = os.path.splitext(os.path.basename(raw_fn))[0].replace("_", " ").title()
        else:
            base_t = "Partition MELODYX"

        if instrument == "bass":
            title = f"{base_t} — Basse"
        elif instrument == "lead":
            title = f"{base_t} — Chant / Lead"
        elif instrument == "conductor":
            title = f"{base_t} — Conducteur d'Orchestre"
        else:
            title = f"{base_t} — Transcription Piano Solo"

    if not subtitle:
        if instrument == "bass":
            subtitle = "Édition Conforme Opéra & Orchestre • Clé de Fa (Basse Électrique / Contrebasse)"
        elif instrument == "lead":
            subtitle = "Édition Conforme Opéra & Orchestre • Clé de Sol (Ligne Mélodique & Thème)"
        elif instrument == "conductor":
            subtitle = "Partition Complète d'Ensemble & Direction Musicale"
        else:
            subtitle = "Édition Conforme Opéra & Orchestre • Clés de Sol & Fa"

    notes_by_measure: dict[int, list[dict]] = {}
    for n in notes:
        m_idx = n.get("measure", 1)
        notes_by_measure.setdefault(m_idx, []).append(n)

    chord_by_measure: dict[int, str] = {}
    for m in measures:
        m_idx = m.get("index", 1)
        m_start = m.get("start", 0.0)
        for ch in chords:
            if ch.get("start", 0.0) <= m_start < ch.get("end", 0.0):
                chord_by_measure[m_idx] = ch.get("label", "")
                break

    total_measures = len(measures)
    if total_measures == 0:
        total_measures = max(1, math.ceil(len(notes) / 6))
        for m_i in range(1, total_measures + 1):
            measures.append({"index": m_i, "start": (m_i - 1) * 2.0, "end": m_i * 2.0})

    if max_measures and max_measures < total_measures:
        total_measures = max_measures

    measures_per_system = 4
    systems_per_page = 6 if is_single_staff else 4

    c = canvas.Canvas(output_path, pagesize=A4)

    cur_measure = 1
    page_num = 1

    section_letters = {
        1: "A", 9: "B", 17: "C", 25: "D", 33: "E", 41: "F",
        49: "G", 57: "H", 65: "I", 73: "J", 81: "K", 89: "L", 97: "M",
    }

    SINGLE_SYSTEM_GAP = 54.0

    while cur_measure <= total_measures:
        if page_num == 1:
            c.setFont("Times-Bold", 17)
            c.drawCentredString(PAGE_W / 2.0, PAGE_H - 42, title)

            c.setFont("Times-Italic", 9.5)
            c.drawCentredString(PAGE_W / 2.0, PAGE_H - 56, subtitle)

            c.setFont("Times-Bold", 11)
            c.drawString(MARGIN_LEFT, PAGE_H - 72, f"Tempo moderato   (M.M. = {tempo_val})")

            c.setFont("Times-Italic", 9.5)
            c.drawRightString(
                MARGIN_RIGHT, PAGE_H - 72, f"Tonalité: {key_name}  •  Métrique: {time_sig}"
            )

            c.setLineWidth(0.8)
            c.setStrokeColorRGB(0.2, 0.2, 0.2)
            c.line(MARGIN_LEFT, PAGE_H - 82, MARGIN_RIGHT, PAGE_H - 82)
            c.setLineWidth(0.3)
            c.line(MARGIN_LEFT, PAGE_H - 85, MARGIN_RIGHT, PAGE_H - 85)

            first_treble_y = PAGE_H - 148
            first_single_y = PAGE_H - 138
        else:
            c.setFont("Times-Italic", 9)
            c.drawString(MARGIN_LEFT, PAGE_H - 35, title)
            c.drawRightString(MARGIN_RIGHT, PAGE_H - 35, f"MELODYX • Page {page_num}")
            c.setLineWidth(0.4)
            c.setStrokeColorRGB(0.6, 0.6, 0.6)
            c.line(MARGIN_LEFT, PAGE_H - 40, MARGIN_RIGHT, PAGE_H - 40)

            first_treble_y = PAGE_H - 92
            first_single_y = PAGE_H - 86

        for sys_idx in range(systems_per_page):
            if cur_measure > total_measures:
                break

            if is_single_staff:
                # ---------------- SINGLE-STAFF SYSTEM (Bass / Lead) ----------------
                sys_y = first_single_y - sys_idx * (STAFF_H + SINGLE_SYSTEM_GAP)

                c.setStrokeColorRGB(0.12, 0.12, 0.12)
                c.setLineWidth(0.5)
                for i in range(5):
                    c.line(MARGIN_LEFT, sys_y + i * LINE_SP, MARGIN_RIGHT, sys_y + i * LINE_SP)

                c.setLineWidth(0.8)
                c.line(MARGIN_LEFT, sys_y, MARGIN_LEFT, sys_y + 4 * LINE_SP)

                if instrument == "bass":
                    draw_bass_clef(c, MARGIN_LEFT + 8, sys_y, LINE_SP)
                    base_step = BASS_BOTTOM_STEP
                    label = "Basse" if (page_num == 1 and sys_idx == 0) else "Bass"
                    key_w = draw_key_signature(c, key_name, MARGIN_LEFT + 28, treble_y=None, bass_y=sys_y, sp=LINE_SP)
                else:
                    draw_treble_clef(c, MARGIN_LEFT + 8, sys_y, LINE_SP)
                    base_step = TREBLE_BOTTOM_STEP
                    label = "Chant" if (page_num == 1 and sys_idx == 0) else "Lead"
                    key_w = draw_key_signature(c, key_name, MARGIN_LEFT + 28, treble_y=sys_y, bass_y=None, sp=LINE_SP)

                c.setFont("Times-Roman", 8)
                c.drawRightString(MARGIN_LEFT - 10, sys_y + 2 * LINE_SP - 3, label)

                meas_start_x = MARGIN_LEFT + 32 + key_w
                if page_num == 1 and sys_idx == 0:
                    ts_parts = time_sig.split("/")
                    top_digit = ts_parts[0] if ts_parts else "4"
                    bot_digit = ts_parts[1] if len(ts_parts) > 1 else "4"
                    c.setFont("Times-Bold", 12)
                    c.drawCentredString(meas_start_x + 6, sys_y + 2.5 * LINE_SP, top_digit)
                    c.drawCentredString(meas_start_x + 6, sys_y + 0.5 * LINE_SP, bot_digit)
                    meas_start_x += 16

                sec_letter = section_letters.get(cur_measure, "")
                if sec_letter:
                    c.setFont("Times-Bold", 9)
                    c.rect(meas_start_x + 2, sys_y + 4 * LINE_SP + 14, 12, 11, stroke=1, fill=0)
                    c.drawCentredString(meas_start_x + 8, sys_y + 4 * LINE_SP + 16, sec_letter)

                avail_w = MARGIN_RIGHT - meas_start_x
                bar_w = avail_w / measures_per_system

                for b in range(measures_per_system):
                    if cur_measure > total_measures:
                        break

                    m_num = cur_measure
                    bx = meas_start_x + b * bar_w
                    bx_end = bx + bar_w

                    c.setLineWidth(0.6)
                    if m_num == total_measures:
                        c.line(bx_end - 3, sys_y, bx_end - 3, sys_y + 4 * LINE_SP)
                        c.setLineWidth(1.6)
                        c.line(bx_end, sys_y, bx_end, sys_y + 4 * LINE_SP)
                    else:
                        c.line(bx_end, sys_y, bx_end, sys_y + 4 * LINE_SP)

                    c.setFont("Times-Italic", 7.5)
                    c.drawString(bx + 3, sys_y + 4 * LINE_SP + 3, str(m_num))

                    ch_label = chord_by_measure.get(m_num, "")
                    if ch_label:
                        c.setFont("Times-Bold", 9)
                        c.drawCentredString(bx + bar_w / 2.0, sys_y + 4 * LINE_SP + 4, ch_label)

                    m_notes = notes_by_measure.get(m_num, [])
                    if instrument == "bass":
                        filt_notes = [n for n in m_notes if n.get("pitch", 60) < 57 or n.get("hand") == "left"]
                    else:
                        filt_notes = [n for n in m_notes if n.get("pitch", 60) >= 55 or n.get("hand") == "right"]

                    t_ch, b_ch = group_notes_into_chords(filt_notes)
                    active_chords = b_ch if instrument == "bass" else t_ch

                    stems: list = []
                    for ch in active_chords:
                        beat_pos = ch["beat"]
                        nx = bx + 10 + (beat_pos / 4.0) * (bar_w - 20)
                        sx, tip, is_up, root = draw_chord(
                            c, nx, ch["pitches"], sys_y, sys_y + 4 * LINE_SP, LINE_SP, base_step
                        )
                        stems.append((sx, tip, is_up, root, beat_pos))

                    draw_beams_for_measure(c, stems)
                    cur_measure += 1

            else:
                # ---------------- GRAND STAFF SYSTEM (Piano / Conductor) ----------------
                treble_y = first_treble_y - sys_idx * (SYSTEM_H + SYSTEM_GAP)
                bass_y = treble_y - INTER_STAFF_GAP - STAFF_H
                sys_y = bass_y

                c.setStrokeColorRGB(0.12, 0.12, 0.12)
                c.setLineWidth(0.5)
                for i in range(5):
                    c.line(MARGIN_LEFT, treble_y + i * LINE_SP, MARGIN_RIGHT, treble_y + i * LINE_SP)
                    c.line(MARGIN_LEFT, bass_y + i * LINE_SP, MARGIN_RIGHT, bass_y + i * LINE_SP)

                draw_brace(c, MARGIN_LEFT, treble_y + 4 * LINE_SP, bass_y)
                c.setLineWidth(0.8)
                c.line(MARGIN_LEFT, bass_y, MARGIN_LEFT, treble_y + 4 * LINE_SP)

                c.setFont("Times-Roman", 8)
                label = "Piano" if (page_num == 1 and sys_idx == 0) else "Pno."
                if instrument == "conductor":
                    label = "Orch." if (page_num == 1 and sys_idx == 0) else "Ens."
                c.drawRightString(MARGIN_LEFT - 14, sys_y + (SYSTEM_H / 2.0) - 3, label)

                draw_treble_clef(c, MARGIN_LEFT + 8, treble_y, LINE_SP)
                draw_bass_clef(c, MARGIN_LEFT + 8, bass_y, LINE_SP)

                key_w = draw_key_signature(c, key_name, MARGIN_LEFT + 28, treble_y, bass_y, LINE_SP)

                meas_start_x = MARGIN_LEFT + 32 + key_w
                if page_num == 1 and sys_idx == 0:
                    ts_parts = time_sig.split("/")
                    top_digit = ts_parts[0] if ts_parts else "4"
                    bot_digit = ts_parts[1] if len(ts_parts) > 1 else "4"
                    c.setFont("Times-Bold", 12)
                    c.drawCentredString(meas_start_x + 6, treble_y + 2.5 * LINE_SP, top_digit)
                    c.drawCentredString(meas_start_x + 6, treble_y + 0.5 * LINE_SP, bot_digit)
                    c.drawCentredString(meas_start_x + 6, bass_y + 2.5 * LINE_SP, top_digit)
                    c.drawCentredString(meas_start_x + 6, bass_y + 0.5 * LINE_SP, bot_digit)
                    meas_start_x += 16

                sec_letter = section_letters.get(cur_measure, "")
                if sec_letter:
                    c.setFont("Times-Bold", 9)
                    c.rect(meas_start_x + 2, treble_y + 4 * LINE_SP + 14, 12, 11, stroke=1, fill=0)
                    c.drawCentredString(meas_start_x + 8, treble_y + 4 * LINE_SP + 16, sec_letter)

                avail_w = MARGIN_RIGHT - meas_start_x
                bar_w = avail_w / measures_per_system

                for b in range(measures_per_system):
                    if cur_measure > total_measures:
                        break

                    m_num = cur_measure
                    bx = meas_start_x + b * bar_w
                    bx_end = bx + bar_w

                    c.setLineWidth(0.6)
                    if m_num == total_measures:
                        c.line(bx_end - 3, bass_y, bx_end - 3, treble_y + 4 * LINE_SP)
                        c.setLineWidth(1.6)
                        c.line(bx_end, bass_y, bx_end, treble_y + 4 * LINE_SP)
                    else:
                        c.line(bx_end, bass_y, bx_end, treble_y + 4 * LINE_SP)

                    c.setFont("Times-Italic", 7.5)
                    c.drawString(bx + 3, treble_y + 4 * LINE_SP + 3, str(m_num))

                    ch_label = chord_by_measure.get(m_num, "")
                    if ch_label:
                        c.setFont("Times-Bold", 9)
                        c.drawCentredString(bx + bar_w / 2.0, treble_y + 4 * LINE_SP + 4, ch_label)

                    m_notes = notes_by_measure.get(m_num, [])
                    t_chords, b_chords = group_notes_into_chords(m_notes)

                    treble_stems: list = []
                    bass_stems: list = []

                    for ch in t_chords:
                        beat_pos = ch["beat"]
                        nx = bx + 10 + (beat_pos / 4.0) * (bar_w - 20)
                        sx, tip, is_up, root = draw_chord(
                            c, nx, ch["pitches"], treble_y, treble_y + 4 * LINE_SP, LINE_SP, TREBLE_BOTTOM_STEP
                        )
                        treble_stems.append((sx, tip, is_up, root, beat_pos))

                    for ch in b_chords:
                        beat_pos = ch["beat"]
                        nx = bx + 10 + (beat_pos / 4.0) * (bar_w - 20)
                        sx, tip, is_up, root = draw_chord(
                            c, nx, ch["pitches"], bass_y, bass_y + 4 * LINE_SP, LINE_SP, BASS_BOTTOM_STEP
                        )
                        bass_stems.append((sx, tip, is_up, root, beat_pos))

                    draw_beams_for_measure(c, treble_stems)
                    draw_beams_for_measure(c, bass_stems)

                    cur_measure += 1

        c.setFont("Times-Roman", 8)
        c.drawCentredString(
            PAGE_W / 2.0, 22, f"Page {page_num}  •  MELODYX Partition Studio  •  Édition de Concert"
        )
        c.showPage()
        page_num += 1

    # Final Page for conductor and piano: Fiche Conducteur d'Orchestre & Grille Harmonique (Lead Sheet)
    if instrument in ("conductor", "piano"):
        _draw_conductor_guide_page(
            c, title, key_name, tempo_val, time_sig, total_measures, len(notes), chord_by_measure, result_data
        )
        c.showPage()

    c.save()
    logger.info("Generated PDF sheet music [%s] at: %s (%d pages)", instrument, output_path, page_num)
    return output_path


def generate_multi_instrument_pdfs(
    result_data: dict[str, Any],
    output_dir: str,
    analysis_id: str,
    title: Optional[str] = None,
) -> dict[str, str]:
    """Generate separate PDF sheet music scores for all instruments plus conductor.

    Returns:
        Dict mapping instrument IDs (``conductor``, ``piano``, ``lead``, ``bass``)
        to their respective generated PDF file paths.
    """
    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)

    base_title = title or result_data.get("audio", {}).get("filename", "")
    if base_title:
        base_title = os.path.splitext(os.path.basename(base_title))[0].replace("_", " ").title()
    else:
        base_title = "Partition MELODYX"

    results: dict[str, str] = {}

    # 1. Conductor
    cond_path = str(out_p / f"{analysis_id}.pdf")
    generate_sheet_music_pdf(
        result_data,
        cond_path,
        title=f"{base_title} — Conducteur d'Orchestre",
        instrument="conductor",
    )
    results["conductor"] = cond_path

    # 2. Piano
    piano_path = str(out_p / f"{analysis_id}_piano.pdf")
    generate_sheet_music_pdf(
        result_data,
        piano_path,
        title=f"{base_title} — Piano Solo",
        instrument="piano",
    )
    results["piano"] = piano_path

    # 3. Lead / Chant
    lead_path = str(out_p / f"{analysis_id}_lead.pdf")
    generate_sheet_music_pdf(
        result_data,
        lead_path,
        title=f"{base_title} — Chant / Lead",
        instrument="lead",
    )
    results["lead"] = lead_path

    # 4. Basse
    bass_path = str(out_p / f"{analysis_id}_bass.pdf")
    generate_sheet_music_pdf(
        result_data,
        bass_path,
        title=f"{base_title} — Basse",
        instrument="bass",
    )
    results["bass"] = bass_path

    return results

    c.save()
    logger.info("Generated PDF sheet music at: %s (%d pages)", output_path, page_num)
    return output_path


def _draw_conductor_guide_page(
    c: canvas.Canvas,
    title: str,
    key_name: str,
    tempo: int,
    time_sig: str,
    total_measures: int,
    total_notes: int,
    chord_by_measure: dict[int, str],
    result_data: dict[str, Any],
):
    """Render a Lead Sheet and Orchestra Conductor Guide on the final page."""
    guide_title = f"GUIDE DU CONDUCTEUR — {title.upper()}"
    if len(guide_title) > 55:
        c.setFont("Times-Bold", 12)
    elif len(guide_title) > 40:
        c.setFont("Times-Bold", 14)
    else:
        c.setFont("Times-Bold", 16)
    c.drawCentredString(PAGE_W / 2.0, PAGE_H - 45, guide_title)

    c.setFont("Times-Italic", 10)
    c.drawCentredString(
        PAGE_W / 2.0,
        PAGE_H - 62,
        "Fiche Technique d'Orchestre, Grille Harmonique & Analyse Pédagogique",
    )

    c.setLineWidth(0.8)
    c.line(MARGIN_LEFT, PAGE_H - 72, MARGIN_RIGHT, PAGE_H - 72)

    # Box 1: Orchestra & Synthesis Parameters
    c.setStrokeColor(HexColor("#2C3E50"))
    c.setFillColor(HexColor("#F8F9FA"))
    c.rect(MARGIN_LEFT, PAGE_H - 165, STAFF_W, 85, fill=1, stroke=1)

    c.setFillColor(HexColor("#1A252F"))
    c.setFont("Times-Bold", 11)
    c.drawString(MARGIN_LEFT + 14, PAGE_H - 96, "PARAMÈTRES D'EXÉCUTION & NOMENCLATURE")

    c.setFont("Times-Roman", 9.5)
    col1_x = MARGIN_LEFT + 14
    col2_x = MARGIN_LEFT + 180
    col3_x = MARGIN_LEFT + 340

    c.drawString(col1_x, PAGE_H - 114, f"• Tonalité principale : {key_name}")
    c.drawString(col1_x, PAGE_H - 130, f"• Métrique : {time_sig}")
    c.drawString(col1_x, PAGE_H - 146, f"• Tempo de référence : ♩ = {tempo} BPM")

    c.drawString(col2_x, PAGE_H - 114, f"• Mesures totales : {total_measures} mesures")
    c.drawString(col2_x, PAGE_H - 130, f"• Notes transcrites : {total_notes} événements")
    duration_s = result_data.get("audio", {}).get("duration_seconds", 0)
    dur_str = f"{int(duration_s // 60)}m {int(duration_s % 60)}s" if duration_s else "Non renseigné"
    c.drawString(col2_x, PAGE_H - 146, f"• Durée d'exécution : {dur_str}")

    c.drawString(col3_x, PAGE_H - 114, "• Instrumentation : Piano Solo / Conducteur")
    c.drawString(col3_x, PAGE_H - 130, "• Système : Portée double (Sol + Fa)")
    c.drawString(col3_x, PAGE_H - 146, "• Standards : Conforme SACEM / Édition")

    # Box 2: Harmonic Grid
    c.setFont("Times-Bold", 11)
    c.setFillColor(HexColor("#1A252F"))
    c.drawString(MARGIN_LEFT, PAGE_H - 185, "GRILLE HARMONIQUE COMPLÈTE (LEAD SHEET)")

    grid_top_y = PAGE_H - 200
    grid_cols = 8
    grid_col_w = STAFF_W / grid_cols
    cell_h = 24.0

    disp_measures = min(total_measures, 64)
    rows = math.ceil(disp_measures / grid_cols)

    for r in range(rows):
        cy = grid_top_y - r * cell_h
        for col in range(grid_cols):
            m_num = r * grid_cols + col + 1
            if m_num > total_measures:
                break
            cx = MARGIN_LEFT + col * grid_col_w

            c.setLineWidth(0.4)
            c.setStrokeColor(HexColor("#CCCCCC"))
            c.setFillColor(HexColor("#FFFFFF") if (r % 2 == 0) else HexColor("#FBFBFC"))
            c.rect(cx, cy - cell_h, grid_col_w, cell_h, fill=1, stroke=1)

            c.setFillColor(HexColor("#888888"))
            c.setFont("Times-Italic", 7)
            c.drawString(cx + 3, cy - 8, str(m_num))

            ch = chord_by_measure.get(m_num, "")
            if ch:
                c.setFillColor(HexColor("#9C7A28"))
                c.setFont("Times-Bold", 10)
                c.drawCentredString(cx + grid_col_w / 2.0, cy - cell_h + 6, ch)

    # Box 3: Pedagogical Guide & Instructions
    pedag_y = grid_top_y - rows * cell_h - 22
    if pedag_y > 100:
        c.setStrokeColor(HexColor("#D4AF37"))
        c.setFillColor(HexColor("#FCFAF4"))
        c.rect(MARGIN_LEFT, pedag_y - 120, STAFF_W, 115, fill=1, stroke=1)

        c.setFillColor(HexColor("#7A5F18"))
        c.setFont("Times-Bold", 11)
        c.drawString(MARGIN_LEFT + 14, pedag_y - 16, "RECOMMANDATIONS D'INTERPRÉTATION & PÉDAGOGIE")

        c.setFillColor(HexColor("#2C3E50"))
        c.setFont("Times-Roman", 9)
        c.drawString(
            MARGIN_LEFT + 14,
            pedag_y - 34,
            "1. Phrasé & Nuances : Privilégier un jeu legato à la main droite pour faire ressortir la ligne mélodique.",
        )
        c.drawString(
            MARGIN_LEFT + 14,
            pedag_y - 48,
            "2. Pédale de sustain : Renouveler la pédale forte à chaque changement d'accord selon la grille harmonique.",
        )
        c.drawString(
            MARGIN_LEFT + 14,
            pedag_y - 62,
            "3. Équilibre des mains : Veiller à ce que l'accompagnement en clé de Fa ne couvre pas le thème en clé de Sol.",
        )
        c.drawString(
            MARGIN_LEFT + 14,
            pedag_y - 76,
            f"4. Cadence & Tempérament : En tonalité de {key_name}, soigner la justesse expressive des altérations.",
        )
        c.drawString(
            MARGIN_LEFT + 14,
            pedag_y - 90,
            "5. Répétition & Ensembles : Utiliser les repères alphabétiques [A], [B], [C] pour caler les pupitres.",
        )

    # Footer
    c.setFont("Times-Roman", 8)
    c.setFillColor(HexColor("#666666"))
    c.drawCentredString(
        PAGE_W / 2.0,
        22,
        "MELODYX Platform • SIMA x EPITECH AI & Music Hackathon • Édition Haute Résolution",
    )
