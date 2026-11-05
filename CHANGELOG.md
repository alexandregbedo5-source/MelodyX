# MELODYX — Journal de développement back-end

> **Guide pour les agents repreneurs** : Ce document consigne l'intégralité du travail réalisé sur le projet MELODYX. Toutes les fonctionnalités P0 et P1 sont implémentées, testées et validées de bout en bout. Un nouvel agent peut reprendre directement en lisant ce journal.

---

## 1. Contexte du projet
- **Projet** : MELODYX — « Your AI-powered music learning studio »
- **Axe stratégique** : « De l’audio à la partition jouable »
- **Hackathon** : IA & Musique · SIMA × EPITECH · 6–7 novembre 2026 · EPITECH Bénin
- **Spécification de référence** : `C:\Users\ADMIN\Downloads\MELODYX — Documentation technique et produit · Développeur back-end.docx`
- **Répertoire du projet** : `C:\Users\ADMIN\Documents\MELODYX`
- **Serveur de développement** : Tourne sur `http://127.0.0.1:5000` via `python run.py`

---

## 2. Stack technique et environnement validé
- **Système d'exploitation** : Windows 11
- **Interpréteur Python** : Python 3.14 (`C:\Python314\python.exe`)
- **Framework Web** : Flask 3.1.3 (modulaire avec Blueprints, sans CORS car monolithe partagé)
- **Base de données** : SQLite 3 en mode WAL avec clés étrangères activées
- **Audio Decoding / Probing** :
  - `ffmpeg` version 7.1 installé dans `C:\Users\ADMIN\.local\bin\ffmpeg.EXE` (dans le PATH)
  - `av` (PyAV 17.1.0) comme fallback de probing natif direct
  - `soundfile` 0.14.0
- **Analyse Audio & Harmonique** :
  - `librosa` 1.0.0 (chroma STFT, RMS, Krumhansl-Kessler key profiling, template matching pour accords majeurs/mineurs avec lissage)
- **Transcription IA** :
  - `basic-pitch` 0.4.0 (modèle Spotify ONNX `nmp.onnx`)
  - `onnxruntime` 1.27.0
  - `numba` 0.68.1 + `llvmlite` 0.50.0 + `mir_eval` 0.8.2 + `resampy` 0.4.3
- **Notation & MIDI** :
  - `pretty_midi` 0.2.11 (génération de fichier `.mid` avec pistes main droite / main gauche)
  - `music21` 10.5.2 (génération de partition MusicXML `.musicxml` en grande portée avec quantification musicale stricte)
- **Professeur IA** :
  - `google-genai` 2.34.0 (SDK officiel Google Gen AI) pour Gemini 2.0 Flash avec prompts contraints, grounding structuré, fallback hors-ligne et cache SHA-256
- **Validation & Schéma** :
  - `jsonschema` 4.26.0 (validation de contrat contre `contracts/api_v1_schema.json`)
  - `pytest` 9.1.1

---

## 3. État des priorités

### Priorités P0 (100% Terminées et validées)
| # | Module / Fonctionnalité | Rôle / Fichier | Statut |
|---|-------------------------|----------------|--------|
| 1 | Squelette Flask, config, `/api/health` | `app/__init__.py`, `config.py`, `routes/health.py` | ✅ Terminé & Testé |
| 2 | Upload, validation, stockage, DB | `routes/upload.py`, `models/analysis.py` | ✅ Terminé & Testé |
| 3 | Décodage et tâche de fond avec statuts | `services/audio_loader.py`, `services/pipeline.py` | ✅ Terminé & Testé |
| 4 | Basic Pitch → notes → MIDI | `services/transcription.py`, `services/midi_generator.py` | ✅ Terminé & Testé |
| 5 | Librosa : tempo, battements, tonalité | `services/rhythm_analysis.py`, `services/harmony_analysis.py` | ✅ Terminé & Testé |
| 6 | Quantification, `measures[]`, MusicXML | `services/quantization.py`, `services/score_generator.py` | ✅ Terminé & Testé |
| 7 | Gemini : résumé et repli | `services/gemini_service.py` (R7: échec IA n'échoue pas l'analyse) | ✅ Terminé & Testé |
| 8 | Lecture audio original (Range) & exports | `routes/playback.py`, `routes/export.py` | ✅ Terminé & Testé |

### Priorités P1 (100% Terminées et validées)
| # | Module / Fonctionnalité | Rôle / Fichier | Statut |
|---|-------------------------|----------------|--------|
| 1 | Endpoint teacher (questions IA) | `routes/analysis.py` (`POST /api/analysis/{id}/teacher`) | ✅ Terminé & Testé |
| 2 | Accords horodatés fiabilisés | `services/harmony_analysis.py` (templates maj/min + lissage) | ✅ Terminé & Testé |
| 3 | Export JSON versionné | `routes/export.py` (`GET /api/analysis/{id}/json`) | ✅ Terminé & Testé |
| 4 | Historique des analyses de session | `routes/analysis.py` (`GET /api/analyses`) | ✅ Terminé & Testé |
| 5 | Suppression d'analyse et fichiers | `routes/analysis.py` (`DELETE /api/analysis/{id}`) | ✅ Terminé & Testé |
| 6 | Enregistrement micro navigateur | `routes/upload.py` (`POST /api/audio/record`) | ✅ Terminé & Testé |
| 7 | Relancer avec options | `routes/analysis.py` (`POST /api/analysis/start`) | ✅ Terminé & Testé |
| 8 | Export PDF (stub 501 au MVP) | `routes/export.py` (`GET /api/analysis/{id}/pdf`) | ✅ Terminé & Testé |

---

## 4. Architecture des fichiers du projet

```
C:\Users\ADMIN\Documents\MELODYX\
├── app\
│   ├── __init__.py              # Factory Flask, headers X-Request-Id & CSP, errorhandlers JSON canoniques
│   ├── config.py                # Configuration par variables d'environnement (.env)
│   ├── extensions.py            # SQLite thread-safe avec WAL mode et row_factory
│   ├── models\
│   │   ├── __init__.py
│   │   └── analysis.py          # Tables: sessions, analyses, analysis_results, artifacts, ai_interactions
│   ├── routes\
│   │   ├── __init__.py
│   │   ├── health.py            # GET /api/health
│   │   ├── upload.py            # POST /api/audio/upload, POST /api/audio/record
│   │   ├── analysis.py          # GET /api/analysis/<id>, GET /api/analyses, DELETE /api/analysis/<id>, POST /api/analysis/start, POST /api/analysis/<id>/teacher
│   │   ├── export.py            # GET /api/analysis/<id>/score, /midi, /json, /pdf
│   │   └── playback.py          # GET /api/analysis/<id>/audio (requêtes HTTP Range 200/206)
│   └── services\
│       ├── __init__.py
│       ├── audio_loader.py      # B2: Conversion ffmpeg 22050Hz mono, détection silence RMS
│       ├── audio_features.py    # B3: Chromagram STFT, énergie RMS
│       ├── rhythm_analysis.py   # B3: Librosa beat tracking, tempo, heuristique signature rythmique
│       ├── harmony_analysis.py  # B3: Profils Krumhansl-Kessler 24 tonalités, gabarits d'accords maj/min
│       ├── transcription.py     # B4: Spotify Basic Pitch (ONNX), filtrage confiance, mapping MIDI
│       ├── quantization.py      # B4: Grille 16th, découpage measures[], séparation main droite/gauche
│       ├── midi_generator.py    # B5: PrettyMIDI 2 pistes (Acoustic Grand Piano), tempo map
│       ├── score_generator.py   # B5: Music21 grande portée, clés Sol/Fa, symboles accords, .quantize([4])
│       ├── gemini_service.py    # B6: Google Gen AI, prompts contraints, validation grounding, cache SHA-256
│       └── pipeline.py         # B7: ThreadPoolExecutor, progression continue, résilience IA (R7)
├── contracts\
│   └── api_v1_schema.json       # JSON Schema Draft-07 officiel pour validation du contrat v1
├── fixtures\
│   ├── demo_piano_analysis.json # Fixture complète d'analyse piano solo pour le front-end
│   ├── demo_piano.mid           # Fichier MIDI réel de démonstration
│   ├── demo_piano.musicxml      # Partition MusicXML réelle de démonstration
│   ├── demo_piano.wav          # Audio WAV réel de démonstration
│   ├── error_invalid_file.json  # Fixture d'erreur fichier non supporté (415)
│   ├── error_analysis_failed.json # Fixture d'erreur analyse échouée (200 avec status: failed)
│   └── error_ai_unavailable.json # Fixture d'analyse réussie avec IA indisponible
├── tests\
│   ├── conftest.py              # Configuration pytest et fixtures client/app isolées
│   ├── test_health.py           # 3 tests du endpoint /api/health
│   ├── test_upload.py           # 5 tests upload, record, extensions, MIME, Request-Id
│   ├── test_analysis.py         # 12 tests CRUD analyse, restarts, exports MIDI/MusicXML/JSON, Range audio, teacher cache
│   ├── test_schema.py           # Test de conformité JSON Schema de demo_piano_analysis.json
│   ├── smoke_test.py            # Test rapide HTTP autonome
│   └── live_integration_test.py# Test de bout en bout complet sur le serveur en direct
├── uploads\                     # Dossier de stockage hors web public (ségrégation par analysis_id)
├── .env.example                 # Modèle de configuration sans secrets
├── .gitignore                   # Ignore .env, *.db, uploads/, __pycache__, etc.
├── requirements.txt             # Dépendances épinglées
├── run.py                       # Point d'entrée de démarrage Flask
└── README.md                    # Documentation complète d'utilisation
```

---

## 5. Problèmes rencontrés et solutions apportées

### Bug 1 : Discordance de noms de colonnes SQL
- **Symptôme** : Certaines routes utilisaient `analysis_id` ou `file_hash` au lieu de `id` et `file_sha256`.
- **Correction** : Réécriture complète de `upload.py`, `analysis.py`, `export.py` et `playback.py` pour s'appuyer exclusivement sur les fonctions du modèle `app/models/analysis.py`.

### Bug 2 : Format des codes d'erreur HTTP dans l'enveloppe
- **Symptôme** : L'errorhandler renvoyait le code numérique HTTP dans `error.code`.
- **Correction** : Mise en conformité avec la spécification § 9.4 : utilisation de codes textuels explicites (`invalid_request`, `not_found`, `file_too_large`, `unsupported_format`, `unprocessable_entity`, `rate_limited`, `internal_error`).

### Bug 3 : Absence initiale de ffmpeg / ffprobe sur le système hôte
- **Symptôme** : `subprocess.run(["ffprobe", ...])` levait `FileNotFoundError`.
- **Correction** : 
  1. Extraction du binaire FFmpeg officiel embarqué dans `imageio_ffmpeg` vers `C:\Users\ADMIN\.local\bin\ffmpeg.EXE` (dans le PATH).
  2. Implémentation d'un fallback direct via `av` (PyAV) dans `_ffprobe_info`, permettant d'inspecter les flux audio (durée, canaux, fréquence d'échantillonnage) même en l'absence de ffprobe externe.

### Bug 4 : Structure du tuple `note_events` de Basic Pitch
- **Symptôme** : `event[4]` dans Basic Pitch est une liste de pitch-bends et non un float de confiance. `float(event[4])` causait un `TypeError`.
- **Correction** : Utilisation de `event[3]` (amplitude normalisée servant d'indicateur de confiance/vélocité) et extraction sécurisée des éléments optionnels.

### Bug 5 : Quantization sur audio avec peu de battements
- **Symptôme** : Si un enregistrement court ou sans percussion a moins de 2 battements détectés par librosa, `_build_grid` renvoyait un tableau vide et `np.argmin` levait `ValueError: attempt to get argmin of an empty sequence`.
- **Correction** : Synthèse d'une grille régulière 16th et de mesures régulières basées sur le tempo estimé (ou 120 BPM par défaut) couvrant toute la durée du morceau.

### Bug 6 : Tempo nul causant une division par zéro
- **Symptôme** : Sur certains signaux continus, le tempo estimé pouvait être 0.0, ce qui provoquait `ZeroDivisionError` dans `pretty_midi` (`60.0 / (initial_tempo * resolution)`) et `score_generator`.
- **Correction** : Garde-fou systématique `if tempo_bpm <= 0: tempo_bpm = 120.0` dans `rhythm_analysis.py`, `midi_generator.py`, `score_generator.py` et `pipeline.py`.

### Bug 7 : Exception `Cannot convert inexpressible durations to MusicXML` dans music21
- **Symptôme** : Les durées flottantes brutes issues de la détection produisaient des silences non conventionnels lors du rendu MusicXML.
- **Correction** : 
  1. Alignement des durées sur les valeurs musicales standard (`[0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0]`).
  2. Alignement des offsets sur la grille de double-croches (`round(offset * 4) / 4`).
  3. Remplissage des portées vides par un silence entier (`Rest(type='whole')`).
  4. Application systématique de `.quantize([4], processOffsets=True, processDurations=True)` sur les portées avant export.

---

## 6. Validation et résultats des tests

### Tests automatisés Pytest
Exécuter :
```powershell
cd C:\Users\ADMIN\Documents\MELODYX
python -m pytest tests/ -v
```
**Résultat** : **22 tests passés avec succès (0 échec)** en ~3 secondes.

### Validation du contrat JSON Schema
Exécuter :
```powershell
python -m pytest tests/test_schema.py -v
```
**Résultat** : `demo_piano_analysis.json` est conforme à 100% au schéma JSON Draft-07 (`contracts/api_v1_schema.json`).

### Test d'intégration de bout en bout en direct
Le serveur étant démarré, exécuter :
```powershell
python tests/live_integration_test.py
```
**Résultat validé** :
- `POST /api/audio/upload` -> Réception du fichier WAV, attribution de session `melodyx_sid`, status 202 queued.
- Polling `GET /api/analysis/{id}` -> Progression 5% (decoding), 20% (features), 50% (transcription), 80% (notation), 100% (completed).
- 18 notes détectées, Tonalité C major (confiance 1.0), Tempo 117.45 BPM.
- Export MusicXML (`18 953 bytes`, MIME `application/vnd.recordare.musicxml+xml`).
- Export MIDI (`227 bytes`, MIME `audio/midi`).
- Export JSON complet (`11 946 bytes`, MIME `application/json`).
- Streaming audio partiel avec requêtes `Range: bytes=0-100` -> Réponse HTTP 206 `Content-Range: bytes 0-100/392534`.

---

## 7. Instructions pour le prochain agent

Si tu reprends ce projet :
1. **Dossier de travail** : `C:\Users\ADMIN\Documents\MELODYX`.
2. **Pour lancer le serveur** : `python run.py` (ou vérifier si la tâche de fond est déjà active).
3. **Pour lancer les tests** : `python -m pytest tests/ -v`.
4. **Si la clé Gemini API est fournie par l'utilisateur** :
   - Renseigner `GEMINI_API_KEY=AIzaSy...` dans `C:\Users\ADMIN\Documents\MELODYX\.env`.
   - Le service `gemini_service.py` s'activera automatiquement et générera l'explication pédagogique dans le champ `ai.summary` de l'analyse, et répondra aux questions sur `/api/analysis/{id}/teacher`.
   - Sans clé API, le système fonctionne déjà parfaitement grâce à la règle R7 (l'analyse passe à `completed` avec `ai.available: false`).
5. **Fixtures front-end** :
   - Tous les fichiers requis par l'équipe front-end sont prêts dans `fixtures/` (`demo_piano_analysis.json`, `demo_piano.mid`, `demo_piano.musicxml`, `demo_piano.wav`, et les 3 cas d'erreurs).
