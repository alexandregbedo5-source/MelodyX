/* Editing tools for each generated final MusicXML score. */
(() => {
    const byId = id => document.getElementById(id);
    const state = {
        doc: null,
        version: 0,
        dirty: false,
        edited: false,
        open: false,
        analysisId: "",
        instrument: "conductor",
        selected: null,
        keyboardStartOctave: 3,
        playbackActive: false,
        playbackFrame: 0,
        playbackAudio: null,
        playbackTempo: 120,
        playbackEvents: null,
        playbackEventIds: new Set(),
        playbackMidi: new Set(),
        undoStack: [],
        redoStack: [],
    };

    let previewAudioContext = null;
    let renderSequence = 0;
    let queuedRender = null;
    let isRenderingPreview = false;

    const pitchNames = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"];
    const pitchSteps = ["C", "C", "D", "D", "E", "F", "F", "G", "G", "A", "A", "B"];
    const pitchAlters = [0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0];
    const durationTypes = [
        [4, "whole", "Ronde"], [2, "half", "Blanche"], [1, "quarter", "Noire"],
        [0.5, "eighth", "Croche"], [0.25, "16th", "Double croche"], [0.125, "32nd", "Triple croche"],
    ];

    function children(parent, name) {
        if (!parent) return [];
        return Array.from(parent.children).filter(node => node.localName === name);
    }

    function first(parent, name) {
        return children(parent, name)[0] || null;
    }

    function setStatus(message, isError = false) {
        const status = byId("scoreEditorStatus");
        if (!status) return;
        status.textContent = message;
        status.style.color = isError ? "#b42318" : "";
    }

    function allParts() {
        return state.doc ? children(state.doc.documentElement, "part") : [];
    }

    function allMeasures(part) {
        return children(part, "measure");
    }

    function measureNumber(measure, index) {
        return measure?.getAttribute("number") || String(index + 1);
    }

    function getPartName(part) {
        const id = part?.getAttribute("id");
        const list = first(state.doc?.documentElement, "part-list");
        const scorePart = children(list, "score-part").find(item => item.getAttribute("id") === id);
        return first(scorePart, "part-name")?.textContent?.trim() || id || "Partie";
    }

    function getCurrentPartIndex() {
        return Number.parseInt(byId("scoreEditPart")?.value || "0", 10) || 0;
    }

    function getCurrentMeasureIndex() {
        return Number.parseInt(byId("scoreEditMeasure")?.value || "0", 10) || 0;
    }

    function selectedNoteElement() {
        if (!state.doc || !state.selected) return null;
        const part = allParts()[state.selected.partIndex];
        const measure = allMeasures(part)[state.selected.measureIndex];
        return children(measure, "note")[state.selected.noteIndex] || null;
    }

    function notePitch(note) {
        const pitch = first(note, "pitch");
        if (!pitch) return null;
        const step = first(pitch, "step")?.textContent?.trim();
        const octave = Number.parseInt(first(pitch, "octave")?.textContent || "4", 10);
        const alter = Number.parseFloat(first(pitch, "alter")?.textContent || "0");
        const stepSemitones = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
        if (!(step in stepSemitones) || !Number.isFinite(octave)) return null;
        return (octave + 1) * 12 + stepSemitones[step] + alter;
    }

    function pitchLabel(note) {
        if (first(note, "rest")) return "Silence";
        const pitch = notePitch(note);
        if (pitch === null) return "Note non éditable";
        const midi = Math.round(pitch);
        return `${pitchNames[((midi % 12) + 12) % 12]}${Math.floor(midi / 12) - 1}`;
    }

    function durationLabel(note) {
        const type = first(note, "type")?.textContent?.trim();
        const match = durationTypes.find(item => item[1] === type);
        const dots = children(note, "dot").length;
        let label = match ? match[2] : `${first(note, "duration")?.textContent || "?"} unités`;
        if (dots === 1) label += " pointée";
        if (dots > 1) label += " double pointée";
        return label;
    }

    function midiToPitch(midi) {
        const semitone = ((midi % 12) + 12) % 12;
        return `${pitchNames[semitone]}${Math.floor(midi / 12) - 1}`;
    }

    function fillPitchChoices() {
        const select = byId("scoreEditPitch");
        if (!select || select.options.length) return;
        for (let midi = 0; midi <= 127; midi += 1) {
            const option = document.createElement("option");
            option.value = String(midi);
            option.textContent = midiToPitch(midi);
            select.appendChild(option);
        }
        select.value = "60";
    }

    function updateVirtualPiano() {
        const container = byId("scorePianoKeyboard");
        if (!container) return;
        const whiteSemitones = new Set([0, 2, 4, 5, 7, 9, 11]);
        const startMidi = (state.keyboardStartOctave + 1) * 12;
        const selectedMidi = Number.parseInt(byId("scoreEditPitch")?.value || "60", 10);
        container.replaceChildren();
        let whiteIndex = 0;

        for (let offset = 0; offset < 24; offset += 1) {
            const midi = startMidi + offset;
            const semitone = offset % 12;
            const isWhite = whiteSemitones.has(semitone);
            const key = document.createElement("button");
            key.type = "button";
            key.className = `piano-key ${isWhite ? "piano-key-white" : "piano-key-black"}`;
            key.style.left = `${isWhite ? whiteIndex * 40 : whiteIndex * 40 - 13}px`;
            key.dataset.midi = String(midi);
            const isPlaying = state.playbackMidi.has(midi);
            key.setAttribute("aria-label", `Note ${midiToPitch(midi)}${isPlaying ? ", lecture en cours" : ""}`);
            key.setAttribute("aria-pressed", String(midi === selectedMidi));
            key.title = midiToPitch(midi);
            if (midi === selectedMidi) key.classList.add("is-selected");
            if (isPlaying) key.classList.add("is-playing");

            const label = document.createElement("span");
            label.className = "piano-key-label";
            label.textContent = isWhite
                ? `${pitchNames[semitone]}${Math.floor(midi / 12) - 1}`
                : pitchNames[semitone];
            key.appendChild(label);
            key.addEventListener("click", () => chooseVirtualPitch(midi));
            key.addEventListener("keydown", event => {
                if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
                event.preventDefault();
                const nextMidi = midi + (event.key === "ArrowRight" ? 1 : -1);
                const nextKey = container.querySelector(`[data-midi="${nextMidi}"]`);
                if (nextKey) nextKey.focus();
            });
            container.appendChild(key);
            if (isWhite) whiteIndex += 1;
        }

        container.style.width = `${whiteIndex * 40}px`;
        const range = byId("pianoRangeLabel");
        if (range) range.textContent = `${midiToPitch(startMidi)} – ${midiToPitch(startMidi + 23)}`;
    }

    function getAudioContext() {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return null;
        if (!previewAudioContext) previewAudioContext = new AudioContext();
        if (previewAudioContext.state === "suspended") previewAudioContext.resume().catch(() => {});
        return previewAudioContext;
    }

    const playbackVoices = new Set();

    function playVirtualPitch(midi, durationSeconds = 0.55, volumeLevel = 0.11, playbackVoice = false) {
        const context = getAudioContext();
        if (!context) return;
        try {
            const oscillator = context.createOscillator();
            const volume = context.createGain();
            const now = context.currentTime;
            const duration = Math.max(0.07, Math.min(4, Number(durationSeconds) || 0.55));
            const releaseAt = now + duration;
            oscillator.type = "sine";
            oscillator.frequency.value = 440 * Math.pow(2, (midi - 69) / 12);
            volume.gain.setValueAtTime(0.0001, now);
            volume.gain.exponentialRampToValueAtTime(Math.max(0.01, volumeLevel), now + 0.018);
            volume.gain.setValueAtTime(Math.max(0.01, volumeLevel), Math.max(now + 0.02, releaseAt - 0.035));
            volume.gain.exponentialRampToValueAtTime(0.0001, releaseAt);
            oscillator.connect(volume);
            volume.connect(context.destination);
            oscillator.start(now);
            oscillator.stop(releaseAt + 0.015);
            if (playbackVoice) playbackVoices.add({ oscillator, volume });
            oscillator.addEventListener("ended", () => {
                for (const voice of playbackVoices) {
                    if (voice.oscillator === oscillator) playbackVoices.delete(voice);
                }
            }, { once: true });
        } catch (_) {
            // Score editing remains available if browser audio preview is unavailable.
        }
    }

    function partMeasureEvents(part, partIndex, measureIndex, startBeat = 0) {
        const measure = allMeasures(part)[measureIndex];
        if (!measure) return { events: [], endBeat: 0 };
        const divisions = divisionsFor(part, measureIndex);
        let cursor = 0;
        let lastNoteStart = 0;
        let maxCursor = 0;
        let noteIndex = 0;
        const events = [];
        for (const child of Array.from(measure.children)) {
            const amount = Number.parseFloat(first(child, "duration")?.textContent || "0") / divisions;
            if (child.localName === "backup") {
                cursor = Math.max(0, cursor - amount);
            } else if (child.localName === "forward") {
                cursor += amount;
                maxCursor = Math.max(maxCursor, cursor);
            } else if (child.localName === "note") {
                const chordMember = Boolean(first(child, "chord"));
                const start = chordMember ? lastNoteStart : cursor;
                if (!chordMember) {
                    lastNoteStart = start;
                    cursor += amount;
                    maxCursor = Math.max(maxCursor, cursor);
                }
                const midi = first(child, "rest") ? null : notePitch(child);
                if (midi !== null && midi !== undefined && amount > 0) {
                    events.push({
                        id: `${partIndex}:${measureIndex}:${noteIndex}`,
                        midi: Math.round(midi),
                        startBeat: startBeat + start,
                        endBeat: startBeat + start + amount,
                    });
                }
                noteIndex += 1;
            }
        }
        return { events, endBeat: Math.max(0, maxCursor) };
    }

    function measureLengthInBeats(measure, fallback) {
        const time = first(first(measure, "attributes"), "time");
        const beats = Number.parseFloat(first(time, "beats")?.textContent || "0");
        const beatType = Number.parseFloat(first(time, "beat-type")?.textContent || "0");
        if (!Number.isFinite(beats) || !Number.isFinite(beatType) || beats <= 0 || beatType <= 0) return fallback;
        return beats * 4 / beatType;
    }

    function getPlaybackTimeline(tempoBpm) {
        if (!state.doc) return { events: [] };
        const bpm = Number.isFinite(Number(tempoBpm)) && Number(tempoBpm) > 0 ? Number(tempoBpm) : 120;
        if (state.playbackEvents?.doc === state.doc && state.playbackEvents?.bpm === bpm) {
            return state.playbackEvents;
        }

        const parts = allParts();
        if (!parts.length) return { events: [] };
        const measureCount = Math.max(0, ...parts.map(part => allMeasures(part).length));
        const measureStarts = [];
        const measureLengths = [];
        let cursorBeat = 0;
        let nominalLength = 4;
        for (let measureIndex = 0; measureIndex < measureCount; measureIndex += 1) {
            const timingMeasure = allMeasures(parts[0])[measureIndex];
            nominalLength = measureLengthInBeats(timingMeasure, nominalLength);
            measureStarts.push(cursorBeat);
            let maxEnd = 0;
            parts.forEach((part, partIndex) => {
                maxEnd = Math.max(maxEnd, partMeasureEvents(part, partIndex, measureIndex).endBeat);
            });
            const implicitPickup = timingMeasure?.getAttribute("implicit") === "yes";
            const measureLength = Math.max(maxEnd, implicitPickup ? 0 : nominalLength);
            const safeLength = measureLength > 0 ? measureLength : nominalLength || 4;
            measureLengths.push(safeLength);
            cursorBeat += safeLength;
        }

        const events = [];
        parts.forEach((part, partIndex) => {
            const measures = allMeasures(part);
            measures.forEach((_, measureIndex) => {
                const { events: measureEvents } = partMeasureEvents(
                    part,
                    partIndex,
                    measureIndex,
                    measureStarts[measureIndex] || 0,
                );
                events.push(...measureEvents);
            });
        });
        events.sort((left, right) => left.startBeat - right.startBeat || left.midi - right.midi);
        state.playbackEvents = { doc: state.doc, bpm, events, measureStarts, measureLengths };
        return state.playbackEvents;
    }

    function openEditorForPlayback() {
        if (!state.doc || state.open) return;
        state.open = true;
        byId("scoreEditorPanel").hidden = false;
        const toggle = byId("btnToggleScoreEditor");
        const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        icon.classList.add("icon");
        icon.setAttribute("aria-hidden", "true");
        const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
        use.setAttribute("href", "#mx-close");
        icon.appendChild(use);
        const label = document.createElement("span");
        label.textContent = "Fermer l’édition";
        toggle.replaceChildren(icon, label);
        populateParts();
        const firstEvent = currentMeasureEvents()[0];
        if (firstEvent) selectEvent(firstEvent);
        byId("scorePianoKeyboard")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function setPlaybackKeys(activeMidi) {
        const container = byId("scorePianoKeyboard");
        state.playbackMidi = activeMidi;
        if (!container) return;
        const pitches = [...activeMidi];
        if (pitches.length) {
            const startMidi = (state.keyboardStartOctave + 1) * 12;
            const endMidi = startMidi + 23;
            const lowest = Math.min(...pitches);
            const highest = Math.max(...pitches);
            if (highest < startMidi || lowest > endMidi) {
                state.keyboardStartOctave = Math.max(-1, Math.min(7, Math.floor(lowest / 12) - 2));
                updateVirtualPiano();
            }
        }
        const selectedMidi = Number.parseInt(byId("scoreEditPitch")?.value || "60", 10);
        container.querySelectorAll(".piano-key").forEach(key => {
            const midi = Number.parseInt(key.dataset.midi || "-1", 10);
            const isPlaying = activeMidi.has(midi);
            key.classList.toggle("is-playing", isPlaying);
            key.setAttribute("aria-pressed", String(midi === selectedMidi));
            key.setAttribute("aria-label", `Note ${midiToPitch(midi)}${isPlaying ? ", lecture en cours" : ""}`);
        });
    }

    function syncPlaybackTime(timeSeconds, tempoBpm = state.playbackTempo) {
        const seconds = Number(timeSeconds);
        if (!state.doc || !Number.isFinite(seconds) || seconds < 0) return;
        const timeline = getPlaybackTimeline(tempoBpm);
        if (!Number.isFinite(timeline.bpm) || !timeline.events) return;
        const beat = seconds * timeline.bpm / 60;
        const activeEvents = timeline.events.filter(event => event.startBeat <= beat + 0.012 && event.endBeat > beat);
        const nextIds = new Set(activeEvents.map(event => event.id));
        const activeMidi = new Set(activeEvents.map(event => event.midi));
        activeEvents.forEach(event => {
            if (state.playbackEventIds.has(event.id)) return;
            const durationSeconds = (event.endBeat - Math.max(event.startBeat, beat)) * 60 / timeline.bpm;
            playVirtualPitch(event.midi, durationSeconds, 0.065, true);
        });
        state.playbackEventIds = nextIds;
        setPlaybackKeys(activeMidi);
    }

    function playbackFrame() {
        if (!state.playbackActive) return;
        const audio = state.playbackAudio;
        if (!audio || audio.paused || audio.ended) {
            stopPlayback();
            return;
        }
        syncPlaybackTime(audio.currentTime, state.playbackTempo);
        state.playbackFrame = window.requestAnimationFrame(playbackFrame);
    }

    function startPlayback(audioElement, tempoBpm = 120) {
        if (!audioElement) return;
        stopPlayback();
        state.playbackAudio = audioElement;
        state.playbackTempo = Number(tempoBpm) > 0 ? Number(tempoBpm) : 120;
        state.playbackActive = true;
        getAudioContext();
        openEditorForPlayback();
        state.playbackFrame = window.requestAnimationFrame(playbackFrame);
    }

    function stopPlayback() {
        state.playbackActive = false;
        if (state.playbackFrame) window.cancelAnimationFrame(state.playbackFrame);
        state.playbackFrame = 0;
        state.playbackAudio = null;
        state.playbackEventIds.clear();
        setPlaybackKeys(new Set());
        const context = previewAudioContext;
        if (context) {
            const now = context.currentTime;
            playbackVoices.forEach(voice => {
                try {
                    voice.volume.gain.cancelScheduledValues(now);
                    voice.volume.gain.setTargetAtTime(0.0001, now, 0.025);
                    voice.oscillator.stop(now + 0.09);
                } catch (_) { /* Voice may already have stopped. */ }
            });
            playbackVoices.clear();
        }
    }

    function chooseVirtualPitch(midi) {
        const pitchSelect = byId("scoreEditPitch");
        if (!pitchSelect) return;
        pitchSelect.value = String(midi);
        updateVirtualPiano();
        const label = midiToPitch(midi);
        const note = selectedNoteElement();
        const noteStatus = byId("pianoSelectionLabel");
        if (!note) {
            if (noteStatus) noteStatus.textContent = `${label} choisie · sélectionne une note ou un silence.`;
            setStatus(`${label} choisie. Sélectionne un événement pour l’appliquer.`);
        } else if (notePitch(note) !== midi || first(note, "rest")) {
            beginMutation();
            setPitch(note, midi, byId("scoreEditSpelling").value);
            markDirty(`${label} appliquée à la sélection. Enregistre pour conserver le résultat final.`);
            if (noteStatus) noteStatus.textContent = `${label} appliquée à l’événement sélectionné.`;
        } else {
            setStatus(`${label} est déjà la hauteur de cet événement.`);
            if (noteStatus) noteStatus.textContent = `${label} · événement sélectionné.`;
        }
        playVirtualPitch(midi);
    }

    function shiftKeyboardOctave(delta) {
        state.keyboardStartOctave = Math.max(-1, Math.min(7, state.keyboardStartOctave + delta));
        updateVirtualPiano();
    }

    function populateParts() {
        const select = byId("scoreEditPart");
        if (!select) return;
        const oldValue = select.value;
        select.replaceChildren();
        allParts().forEach((part, index) => {
            const option = document.createElement("option");
            option.value = String(index);
            option.textContent = getPartName(part);
            select.appendChild(option);
        });
        if (oldValue && Number(oldValue) < select.options.length) select.value = oldValue;
        populateMeasures();
    }

    function populateMeasures() {
        const select = byId("scoreEditMeasure");
        if (!select) return;
        const oldValue = select.value;
        select.replaceChildren();
        const part = allParts()[getCurrentPartIndex()];
        allMeasures(part).forEach((measure, index) => {
            const option = document.createElement("option");
            option.value = String(index);
            option.textContent = `Mesure ${measureNumber(measure, index)}`;
            select.appendChild(option);
        });
        if (oldValue && Number(oldValue) < select.options.length) select.value = oldValue;
        state.selected = null;
        renderEvents();
        updateVirtualPiano();
        byId("pianoSelectionLabel").textContent = "Sélectionne un événement de la partition.";
    }

    function divisionsFor(part, measureIndex) {
        const measures = allMeasures(part);
        for (let index = Math.min(measureIndex, measures.length - 1); index >= 0; index -= 1) {
            const divisions = first(first(measures[index], "attributes"), "divisions");
            const value = Number.parseFloat(divisions?.textContent || "0");
            if (Number.isFinite(value) && value > 0) return value;
        }
        return 1;
    }

    function currentMeasureEvents() {
        const partIndex = getCurrentPartIndex();
        const measureIndex = getCurrentMeasureIndex();
        const part = allParts()[partIndex];
        const measure = allMeasures(part)[measureIndex];
        if (!measure) return [];

        const divisions = divisionsFor(part, measureIndex);
        let cursor = 0;
        let lastNoteStart = 0;
        let noteIndex = 0;
        const events = [];
        for (const child of Array.from(measure.children)) {
            const amount = Number.parseFloat(first(child, "duration")?.textContent || "0") / divisions;
            if (child.localName === "backup") {
                cursor = Math.max(0, cursor - amount);
            } else if (child.localName === "forward") {
                cursor += amount;
            } else if (child.localName === "note") {
                const chordMember = Boolean(first(child, "chord"));
                const start = chordMember ? lastNoteStart : cursor;
                if (!chordMember) {
                    lastNoteStart = start;
                    cursor += amount;
                }
                const voice = first(child, "voice")?.textContent?.trim() || "1";
                const staff = first(child, "staff")?.textContent?.trim() || "1";
                events.push({
                    partIndex,
                    measureIndex,
                    noteIndex,
                    start,
                    voice,
                    staff,
                    pitch: pitchLabel(child),
                    duration: durationLabel(child),
                    chordMember,
                    rest: Boolean(first(child, "rest")),
                });
                noteIndex += 1;
            }
        }
        return events;
    }

    function renderEvents() {
        const container = byId("scoreEventList");
        if (!container) return;
        container.replaceChildren();
        if (!state.doc) return;

        const events = currentMeasureEvents();
        if (!events.length) {
            const empty = document.createElement("div");
            empty.className = "score-editor-status";
            empty.textContent = "Aucun événement musical dans cette mesure.";
            container.appendChild(empty);
            return;
        }

        events.forEach(event => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "score-event";
            const selected = state.selected && state.selected.partIndex === event.partIndex
                && state.selected.measureIndex === event.measureIndex
                && state.selected.noteIndex === event.noteIndex;
            if (selected) {
                button.classList.add("selected");
                button.setAttribute("aria-pressed", "true");
            } else {
                button.setAttribute("aria-pressed", "false");
            }
            const prefix = event.chordMember ? "Accord · " : "";
            button.textContent = `${prefix}${event.pitch} · ${event.duration} · temps ${event.start.toFixed(2)} · voix ${event.voice}`;
            button.addEventListener("click", () => selectEvent(event));
            container.appendChild(button);
        });
    }

    function selectEvent(event) {
        state.selected = {
            partIndex: event.partIndex,
            measureIndex: event.measureIndex,
            noteIndex: event.noteIndex,
        };
        const note = selectedNoteElement();
        const pitch = notePitch(note);
        if (pitch !== null) byId("scoreEditPitch").value = String(Math.max(0, Math.min(127, Math.round(pitch))));
        const altered = Number.parseFloat(first(first(note, "pitch"), "alter")?.textContent || "0");
        byId("scoreEditSpelling").value = altered < 0 ? "flat" : "sharp";
        const type = first(note, "type")?.textContent?.trim();
        const duration = durationTypes.find(item => item[1] === type);
        if (duration) byId("scoreEditDuration").value = String(duration[0]);
        byId("scoreEditDots").value = String(Math.min(2, children(note, "dot").length));
        updateVirtualPiano();
        byId("pianoSelectionLabel").textContent = `${event.pitch} · événement sélectionné.`;
        setStatus(`${event.pitch} sélectionné dans la mesure ${measureNumber(allMeasures(allParts()[event.partIndex])[event.measureIndex], event.measureIndex)}.`);
        renderEvents();
    }

    function markDirty(message = "Modifications non enregistrées.") {
        state.dirty = true;
        state.playbackEvents = null;
        byId("scoreEditSave").disabled = false;
        setStatus(message);
        renderEvents();
        renderPreview();
    }

    function beginMutation() {
        if (!state.doc) return;
        state.undoStack.push(new XMLSerializer().serializeToString(state.doc));
        if (state.undoStack.length > 50) state.undoStack.shift();
        state.redoStack = [];
        state.playbackEvents = null;
    }

    function restoreSnapshot(targetStack, sourceStack, message) {
        if (!targetStack.length) {
            setStatus(message === "Annulation effectuée." ? "Aucune modification à annuler." : "Aucune modification à rétablir.");
            return;
        }
        sourceStack.push(new XMLSerializer().serializeToString(state.doc));
        const xmlText = targetStack.pop();
        const parsed = new DOMParser().parseFromString(xmlText, "application/xml");
        if (parsed.querySelector("parsererror")) {
            setStatus("Impossible de restaurer cet état de la partition.", true);
            return;
        }
        state.doc = parsed;
        state.selected = null;
        populateParts();
        markDirty(message);
    }

    function setText(parent, name, value) {
        let node = first(parent, name);
        if (!node) {
            node = state.doc.createElementNS(state.doc.documentElement.namespaceURI || null, name);
            parent.appendChild(node);
        }
        node.textContent = String(value);
        return node;
    }

    function removeChildren(parent, name) {
        children(parent, name).forEach(node => node.remove());
    }

    function setPitch(note, midi, spelling = "sharp") {
        removeChildren(note, "rest");
        removeChildren(note, "unpitched");
        removeChildren(note, "accidental");
        let pitch = first(note, "pitch");
        if (!pitch) {
            pitch = state.doc.createElementNS(state.doc.documentElement.namespaceURI || null, "pitch");
            const before = Array.from(note.children).find(node => ["duration", "tie", "instrument", "voice", "type", "dot", "time-modification", "stem", "notehead", "staff"].includes(node.localName));
            note.insertBefore(pitch, before || null);
        }
        const semitone = ((midi % 12) + 12) % 12;
        const flatSpellings = { 1: ["D", -1], 3: ["E", -1], 6: ["G", -1], 8: ["A", -1], 10: ["B", -1] };
        const flat = spelling === "flat" && flatSpellings[semitone];
        setText(pitch, "step", flat ? flat[0] : pitchSteps[semitone]);
        const alter = flat ? flat[1] : pitchAlters[semitone];
        if (alter) setText(pitch, "alter", alter);
        else removeChildren(pitch, "alter");
        setText(pitch, "octave", Math.floor(midi / 12) - 1);
    }

    function setDuration(note, part, measureIndex) {
        const baseLength = Number.parseFloat(byId("scoreEditDuration").value);
        const dots = Number.parseInt(byId("scoreEditDots").value, 10) || 0;
        const dotFactor = dots === 1 ? 1.5 : dots === 2 ? 1.75 : 1;
        const type = durationTypes.find(item => item[0] === baseLength);
        if (!type) return;

        const divisions = divisionsFor(part, measureIndex);
        const durationUnits = Math.max(1, Math.round(baseLength * dotFactor * divisions));
        setText(note, "duration", durationUnits);
        const typeNode = setText(note, "type", type[1]);
        removeChildren(note, "dot");
        for (let index = 0; index < dots; index += 1) {
            const dot = state.doc.createElementNS(state.doc.documentElement.namespaceURI || null, "dot");
            note.insertBefore(dot, typeNode.nextSibling);
        }
        removeChildren(note, "time-modification");
    }

    function applySelection() {
        const note = selectedNoteElement();
        if (!note) {
            setStatus("Sélectionne d’abord une note ou un silence.", true);
            return;
        }
        beginMutation();
        const part = allParts()[state.selected.partIndex];
        setPitch(note, Number.parseInt(byId("scoreEditPitch").value, 10), byId("scoreEditSpelling").value);
        setDuration(note, part, state.selected.measureIndex);
        markDirty("Note modifiée. Enregistre pour conserver le résultat final.");
    }

    function addNoteOrChord() {
        const note = selectedNoteElement();
        if (!note) {
            setStatus("Sélectionne un silence à remplacer ou une note qui servira de base à l’accord.", true);
            return;
        }
        beginMutation();
        if (first(note, "rest")) {
            setPitch(note, Number.parseInt(byId("scoreEditPitch").value, 10), byId("scoreEditSpelling").value);
            setDuration(note, allParts()[state.selected.partIndex], state.selected.measureIndex);
            markDirty("Le silence sélectionné a été remplacé par une note.");
            return;
        }

        const clone = note.cloneNode(true);
        removeChildren(clone, "chord");
        removeChildren(clone, "tie");
        removeChildren(clone, "beam");
        removeChildren(clone, "notations");
        setPitch(clone, Number.parseInt(byId("scoreEditPitch").value, 10), byId("scoreEditSpelling").value);
        setDuration(clone, allParts()[state.selected.partIndex], state.selected.measureIndex);
        const chord = state.doc.createElementNS(state.doc.documentElement.namespaceURI || null, "chord");
        const pitch = first(clone, "pitch");
        clone.insertBefore(chord, pitch || clone.firstChild);
        note.parentNode.insertBefore(clone, note.nextSibling);
        markDirty("Une note a été ajoutée à l’accord sélectionné.");
    }

    function convertToRest() {
        const note = selectedNoteElement();
        if (!note) {
            setStatus("Sélectionne une note à convertir en silence.", true);
            return;
        }
        beginMutation();
        removeChildren(note, "pitch");
        removeChildren(note, "unpitched");
        removeChildren(note, "accidental");
        removeChildren(note, "chord");
        removeChildren(note, "tie");
        removeChildren(note, "rest");
        const rest = state.doc.createElementNS(state.doc.documentElement.namespaceURI || null, "rest");
        const before = Array.from(note.children).find(node => ["duration", "tie", "instrument", "voice", "type", "dot", "time-modification", "stem", "notehead", "staff"].includes(node.localName));
        note.insertBefore(rest, before || null);
        markDirty("La note a été convertie en silence.");
    }

    function deleteSelection() {
        const note = selectedNoteElement();
        if (!note) {
            setStatus("Sélectionne une note ou un silence à supprimer.", true);
            return;
        }
        beginMutation();
        if (!first(note, "chord")) {
            const next = note.nextElementSibling;
            if (next?.localName === "note" && first(next, "chord")) removeChildren(next, "chord");
        }
        note.remove();
        state.selected = null;
        markDirty("Événement supprimé. Enregistre pour conserver le résultat final.");
    }

    function renderPreview() {
        const context = window.MELODYX_SCORE_CONTEXT;
        const osmd = context?.osmd;
        if (!state.doc || !window.opensheetmusicdisplay || !osmd) return;
        try {
            const xmlText = new XMLSerializer().serializeToString(state.doc);
            renderSequence += 1;
            queuedRender = {
                sequence: renderSequence,
                osmd,
                context,
                xmlText: xmlText.replace(/<harmony[\s\S]*?<\/harmony>/gi, ""),
            };
            drainPreviewQueue();
        } catch (error) {
            setStatus("Impossible de rafraîchir l’aperçu de la partition.", true);
        }
    }

    async function drainPreviewQueue() {
        if (isRenderingPreview) return;
        isRenderingPreview = true;
        try {
            while (queuedRender) {
                const job = queuedRender;
                queuedRender = null;
                if (job.sequence !== renderSequence) continue;
                try {
                    await job.osmd.load(job.xmlText);
                    if (job.sequence !== renderSequence) continue;
                    job.osmd.zoom = job.context.zoom || 0.85;
                    job.osmd.render();
                    if (job.osmd.cursor) job.osmd.cursor.show();
                } catch (_) {
                    if (job.sequence === renderSequence) {
                        setStatus("La modification est en mémoire, mais l’aperçu n’a pas pu être rafraîchi.", true);
                    }
                }
            }
        } finally {
            isRenderingPreview = false;
            if (queuedRender) drainPreviewQueue();
        }
    }

    async function save() {
        if (!state.doc || !state.analysisId) {
            setStatus("Aucune partition finale chargée.", true);
            return false;
        }
        if (!state.dirty) return true;

        const saveButton = byId("scoreEditSave");
        saveButton.disabled = true;
        setStatus("Enregistrement en cours…");
        try {
            const xmlText = new XMLSerializer().serializeToString(state.doc);
            const response = await fetch(`/api/analysis/${encodeURIComponent(state.analysisId)}/score?instrument=${encodeURIComponent(state.instrument)}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ musicxml: xmlText, version: state.version }),
            });
            const data = await response.json();
            if (response.status === 409) {
                setStatus(data.error?.message || "Conflit de version : recharge la partition.", true);
                saveButton.disabled = false;
                return false;
            }
            if (!response.ok) throw new Error(data.error?.message || "La partition n’a pas pu être enregistrée.");
            state.version = data.version;
            state.edited = true;
            state.dirty = false;
            saveButton.disabled = true;
            setStatus(`Résultat final enregistré — version ${state.version}.`);
            return true;
        } catch (error) {
            saveButton.disabled = false;
            setStatus(error.message || "Erreur d’enregistrement.", true);
            return false;
        }
    }

    function setScope(analysisId, instrument) {
        renderSequence += 1;
        queuedRender = null;
        state.analysisId = analysisId || "";
        state.instrument = instrument || "conductor";
        state.doc = null;
        state.version = 0;
        state.edited = false;
        state.selected = null;
        state.playbackEvents = null;
        byId("btnToggleScoreEditor").hidden = true;
        byId("scoreEditorPanel").hidden = true;
        const label = window.MELODYX_SCORE_CONTEXT?.labels?.[state.instrument]?.name || state.instrument;
        byId("scoreEditorTitle").textContent = `Édition du résultat final — ${label}`;
        setStatus("Chargement de la partition finale…");
    }

    function setScore(xmlText, headers) {
        try {
            const parsed = new DOMParser().parseFromString(xmlText, "application/xml");
            if (parsed.querySelector("parsererror") || !["score-partwise", "score-timewise"].includes(parsed.documentElement?.localName)) {
                throw new Error("Le document chargé n’est pas une partition MusicXML valide.");
            }
            state.doc = parsed;
            state.playbackEvents = null;
            state.version = Number.parseInt(headers?.get("X-Score-Edit-Version") || "0", 10) || 0;
            state.edited = headers?.get("X-Score-Edited") === "true";
            state.dirty = false;
            state.selected = null;
            state.undoStack = [];
            state.redoStack = [];
            byId("btnToggleScoreEditor").hidden = false;
            byId("scoreEditorPanel").hidden = !state.open;
            byId("scoreEditSave").disabled = true;
            populateParts();
            const label = window.MELODYX_SCORE_CONTEXT?.labels?.[state.instrument]?.name || state.instrument;
            byId("scoreEditorTitle").textContent = `Édition du résultat final — ${label}`;
            setStatus(state.edited ? `Partition modifiée — version ${state.version}.` : "Partition finale prête à être éditée.");
            if (state.playbackActive) openEditorForPlayback();
        } catch (error) {
            state.doc = null;
            byId("btnToggleScoreEditor").hidden = true;
            setStatus(error.message || "Impossible de charger l’éditeur.", true);
        }
    }

    async function toggle() {
        if (!state.doc) {
            setStatus("Charge d’abord une partition finale.", true);
            return;
        }
        if (state.open && state.dirty && !(await save())) return;
        state.open = !state.open;
        byId("scoreEditorPanel").hidden = !state.open;
        const toggle = byId("btnToggleScoreEditor");
        const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        icon.classList.add("icon");
        icon.setAttribute("aria-hidden", "true");
        const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
        use.setAttribute("href", state.open ? "#mx-close" : "#mx-edit");
        icon.appendChild(use);
        const label = document.createElement("span");
        label.textContent = state.open ? "Fermer l’édition" : "Éditer le résultat final";
        toggle.replaceChildren(icon, label);
        if (state.open) {
            populateParts();
            const firstEvent = currentMeasureEvents()[0];
            if (firstEvent) {
                selectEvent(firstEvent);
            }
        }
    }

    async function beforeScopeChange() {
        if (!state.dirty) return true;
        return await save();
    }

    fillPitchChoices();
    byId("scoreEditPart").addEventListener("change", populateMeasures);
    byId("scoreEditMeasure").addEventListener("change", () => { state.selected = null; renderEvents(); });
    byId("scoreEditApply").addEventListener("click", applySelection);
    byId("scoreEditUndo").addEventListener("click", () => restoreSnapshot(state.undoStack, state.redoStack, "Annulation effectuée."));
    byId("scoreEditRedo").addEventListener("click", () => restoreSnapshot(state.redoStack, state.undoStack, "Modification rétablie."));
    byId("scoreEditRest").addEventListener("click", convertToRest);
    byId("scoreEditAdd").addEventListener("click", addNoteOrChord);
    byId("scoreEditDelete").addEventListener("click", deleteSelection);
    byId("scoreEditSave").addEventListener("click", save);
    byId("scoreEditPitch").addEventListener("change", updateVirtualPiano);
    byId("pianoOctaveDown").addEventListener("click", () => shiftKeyboardOctave(-1));
    byId("pianoOctaveUp").addEventListener("click", () => shiftKeyboardOctave(1));
    updateVirtualPiano();

    const computerPitches = { a: 0, w: 1, s: 2, e: 3, d: 4, f: 5, t: 6, g: 7, y: 8, h: 9, u: 10, j: 11 };
    document.addEventListener("keydown", event => {
        if (!state.open || event.altKey || event.ctrlKey || event.metaKey) return;
        if (event.target?.matches("input, select, textarea, [contenteditable='true']")) return;
        const offset = computerPitches[event.key.toLowerCase()];
        if (offset === undefined) return;
        event.preventDefault();
        chooseVirtualPitch((state.keyboardStartOctave + 1) * 12 + offset);
    });
    window.addEventListener("beforeunload", event => {
        if (!state.dirty) return;
        event.preventDefault();
        event.returnValue = "";
    });

    window.scoreEditor = {
        toggle,
        setScope,
        setScore,
        beforeScopeChange,
        save,
        startPlayback,
        stopPlayback,
        syncPlaybackTime,
    };
})();
