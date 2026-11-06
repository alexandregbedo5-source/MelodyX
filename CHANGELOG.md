# MELODYX — Journal de développement back-end & Partition Studio

> **Guide pour les agents repreneurs** : Ce document consigne l'intégralité du travail réalisé sur le projet MELODYX. Toutes les fonctionnalités P0 et P1, le moteur de partition vectorielle PDF et le studio web interactif sont implémentés, testés et validés de bout en bout sur des fichiers réels.

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
  - `Partition PDF Vectorielle (8 pages)` : **50 795 octets** (`application/pdf`)
  - `MusicXML Score` : **582 392 octets** (`application/vnd.recordare.musicxml+xml`)
  - `MIDI File` : **4 573 octets** (`audio/midi`)
  - `JSON complet` : **367 087 octets** (`application/json`)
  - `Streaming audio partiel` : Requête HTTP `Range: bytes=0-1023` -> Réponse HTTP **206 Partial Content**.

---

## 3. Implémentation de la Partition PDF d'Opéra (`app/services/pdf_generator.py`)

Conformément à la demande de l'utilisateur et au modèle visuel de référence (`OIP.webp` - Comptine d'un autre été de Yann Tiersen), un moteur de gravure musicale vectorielle complet a été créé sous ReportLab :
1. **Accolade de piano (Brace)** : Courbe de Bézier vectorielle reliant la portée supérieure et inférieure.
2. **Double portée (Grand Staff)** :
   - Portée clé de sol (𝄞) avec tracé vectoriel précis ancré sur la ligne de Sol (G4).
   - Portée clé de fa (𝄢) avec tracé vectoriel ancré sur la ligne de Fa (F3) et double points.
3. **Armure (Key Signature)** : Prise en charge automatique des 12 tonalités majeures et mineures (dièses et bémols positionnés aux hauteurs conventionnelles de gravure).
4. **Chiffrage de mesure (Time Signature)** : `4/4` (ou métrique personnalisée) gravé en chiffres gras superposés.
5. **Notes et hampes (Stems & Noteheads)** :
   - Têtes de notes elliptiques inclinées à 18° (pleines pour noires/croches/doubles, blanches pour rondes/blanches).
   - Lignes supplémentaires (ledger lines) tracées dynamiquement pour toutes les notes hors portée.
   - Orientation automatique des hampes (vers le haut sur le flanc droit pour les notes sous la 3ème ligne, vers le bas sur le flanc gauche pour les notes au-dessus).
   - Ligatures continues (beams) reliant les groupes de croches de la main gauche et de la main droite.
6. **Grille d'accords et repères d'ensemble** :
   - Accords harmoniques gravés au-dessus de chaque mesure (`[E]`, `[G#m]`, `[A]`, `[B]`, etc.).
   - Numéros de mesures et repères de répétition d'orchestre encadrés (`[A]`, `[B]`, `[C]`, etc.).
7. **Pagination multi-pages** :
   - 4 à 5 systèmes par page avec en-têtes et pieds de page numérotés.
   - **Page Finale — Fiche Conducteur d'Orchestre (Lead Sheet)** :
     - Récapitulatif d'exécution : Tonalité, Tempo, Métrique, Mesures transcrites, Nombre de notes.
     - Grille harmonique complète par mesure (table 4 colonnes).
     - Conseils d'interprétation & coordination musicale (phrasé du clavier, pédale forte, nuances *p* / *f*, repères de groupe).

---

## 4. Activation de l'Endpoint `GET /api/analysis/{id}/pdf` (`app/routes/export.py`)

- Remplacement du stub HTTP 501 par une implémentation complète HTTP 200.
- Génération à la volée si l'artefact n'est pas encore précalculé.
- Enregistrement immédiat dans la table `artifacts`.
- Prise en charge du paramètre `?inline=1` pour affichage direct dans le navigateur ou téléchargement en pièce jointe (`as_attachment`).

---

## 5. Studio Web Interactif (`app/routes/web.py` & `app/templates/index.html`)

Interface web complète dédiée à l'apprentissage et à la visualisation de partitions d'opéra :
- **Visualiseur OpenSheetMusicDisplay (OSMD)** :
  - Rendu SVG vectoriel ultra-net de la partition MusicXML directement dans le navigateur.
  - Commandes de zoom (+, -, 100%), affichage pleine page et défilement fluide.
  - Curseur musical dynamique synchronisé en temps réel sur les notes et mesures lors de la lecture audio.
- **Lecteur Audio Conducteur** :
  - Barre de contrôle avec Play/Pause, timeline interactive, chronomètre et affichage en direct de la mesure et de l'accord en cours (`Mesure 14 • Accord [B]`).
- **Grille Harmonique Cliquable** :
  - Pastilles d'accords interactives : cliquer sur un accord saute instantanément à la mesure correspondante dans la partition et dans l'audio.
- **Boutons d'Exportation en 1 clic** :
  - 📄 Télécharger la Partition PDF (Fiche d'Opéra & Ensemble)
  - 🖨️ Imprimer la Partition (`window.print()` optimisé `@media print` sans éléments d'interface)
  - 🎼 Télécharger MusicXML
  - 🎹 Télécharger MIDI
- **Importation Audio & Enregistrement Micro** :
  - Zone glisser-déposer pour M4A, MP3, WAV, WebM.
  - Enregistreur microphone en direct avec barre de progression de transcription.
  - Bouton de chargement instantané de la chanson démo.

---

## 6. Intégration de la Clé API Gemini (`GEMINI_MODEL=gemini-3.8-flash`)

- La clé fournie par l'utilisateur a été configurée dans `C:\Users\ADMIN\Documents\MELODYX\.env`.
- Le modèle recommandé par Google AI (`gemini-3.8-flash`) est configuré.
- En cas de quota gratuit dépassé (429 Free Tier), la **Règle R7** assure un repli algorithmique immédiat : toute la chaîne de transcription, les partitions vectorielles, le PDF et le studio web continuent de fonctionner à 100% sans interruption.

---

## 7. État des Tests Pytest

- **29 tests passés avec succès sur 29 (0 échec)** :
  ```powershell
  cd C:\Users\ADMIN\Documents\MELODYX
  python -m pytest tests/ -v
  ```
  - `tests/test_health.py` (3 tests) : PASSED
  - `tests/test_upload.py` (5 tests) : PASSED
  - `tests/test_analysis.py` (13 tests) : PASSED (dont CRUD, exports MIDI, XML, JSON, PDF 200, Range 206)
  - `tests/test_schema.py` (1 test) : PASSED
  - `tests/test_pdf.py` (2 tests) : PASSED (conversion diatonique et génération multipages avec conducteur)
  - `tests/test_web.py` (5 tests) : PASSED (index HTML, analyse démo, score XML, PDF démo, audio range)
