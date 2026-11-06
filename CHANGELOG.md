# MELODYX — Journal de développement back-end

> **Guide pour les agents repreneurs** : Ce document consigne l'intégralité du travail réalisé sur le projet MELODYX. Toutes les fonctionnalités P0 et P1 sont implémentées, testées et validées de bout en bout sur des fichiers réels.

---

## 1. Contexte du projet
- **Projet** : MELODYX — « Your AI-powered music learning studio »
- **Axe stratégique** : « De l’audio à la partition jouable »
- **Hackathon** : IA & Musique · SIMA × EPITECH · 6–7 novembre 2026 · EPITECH Bénin
- **Spécification de référence** : `C:\Users\ADMIN\Downloads\MELODYX — Documentation technique et produit · Développeur back-end.docx`
- **Répertoire du projet** : `C:\Users\ADMIN\Documents\MELODYX`
- **Serveur de développement** : Tourne sur `http://127.0.0.1:5000` via `python run.py`

---

## 2. Test grandeur nature sur la chanson utilisateur (06/11/2026)

Le backend a été testé avec la chanson fournie par l'utilisateur (`uploaded_media_1793958784300.m4a`) :
- **Fichier** : M4A (AAC stéréo 44.1 kHz, 3.14 Mo, 194.16 secondes / ~3 min 14 s).
- **Temps total de traitement** : **50.7 secondes** pour la chaîne complète de bout en bout.
- **Résultats musicaux extraits** :
  - **Tempo estimé** : **129.2 BPM** (confiance : **0.988**)
  - **Tonalité estimée** : **E major** (Mi majeur, confiance : **0.612**)
  - **Signature rythmique** : **4/4**
  - **Accords identifiés** : **266 segments d'accords** (progression : A, C#m, E, G#m, E, A...)
  - **Notes transcrites** : **687 notes de piano** réparties avec attribution main droite / main gauche et horodatage
  - **Mesures calculées** : **104 mesures** synchronisées (`measures[]`)
- **Artefacts générés et exportés avec succès** :
  - `MusicXML Score` : **582 392 octets** (`application/vnd.recordare.musicxml+xml`)
  - `MIDI File` : **4 573 octets** (`audio/midi`)
  - `JSON complet` : **367 087 octets** (`application/json`)
  - `Streaming audio partiel` : Requête HTTP `Range: bytes=0-1023` -> Réponse HTTP **206 Partial Content** (`Content-Range: bytes 0-1023/3140930`).

---

## 3. Rôle de la clé API Gemini (`GEMINI_API_KEY`)

### Principe architectural (Règle R7 de la documentation)
Le document de cadrage impose une séparation stricte :
1. **Ce qui est calculé** (décodage ffmpeg, tempo/battements/tonalité Librosa, transcription polyphonique Basic Pitch, quantification, partition MusicXML, fichier MIDI, streaming audio) :
   - **S'exécute à 100% en local**, sans clé API, sans quotas, sans réseau.
2. **Ce qui est expliqué** (le rôle du « Professeur IA ») :
   - Nécessite la clé API **Google Gemini** (`GEMINI_API_KEY`).
   - Génère le résumé initial pédagogique (`ai.summary`).
   - Répond aux questions posées sur l'endpoint `POST /api/analysis/{id}/teacher`.
   - **Règle R7** : Si aucune clé n'est configurée ou si Gemini est inaccessible, le pipeline n'échoue jamais. L'analyse musicale passe à `status: completed` avec `ai.available: false`, et l'endpoint `/teacher` renvoie HTTP 503 `ai_unavailable`.

### Pour activer Gemini :
Créer le fichier `C:\Users\ADMIN\Documents\MELODYX\.env` :
```env
GEMINI_API_KEY=votre_cle_api_ici
GEMINI_MODEL=gemini-2.0-flash
```
Le serveur charge automatiquement le `.env` au démarrage grâce à `python-dotenv`.

---

## 4. État des tests Pytest
- **22 tests passés avec succès (0 échec)** :
  ```powershell
  cd C:\Users\ADMIN\Documents\MELODYX
  python -m pytest tests/ -v
  ```
- **Conformité JSON Schema** : Validée à 100% sur `contracts/api_v1_schema.json`.
- **Scripts autonomes** :
  - `scripts/smoke_test.py` : Vérification rapide de l'API HTTP.
  - `scripts/test_user_song.py` : Test complet avec la chanson utilisateur.
  - `scripts/live_integration_test.py` : Test d'intégration complet avec polling.
