# MELODYX — Your AI-powered music learning studio

MELODYX analyses audio recordings and provides detailed musical feedback using AI. Upload a recording, and MELODYX will detect notes, estimate tempo, key, and chords, then let you ask an AI tutor for practice advice.

## Quick Start

```bash
# 1. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# Edit .env and set your GEMINI_API_KEY

# 4. Run the development server
python run.py
```

The API will be available at **http://localhost:5000**.

## API Endpoints

| Method   | Route                                          | Description                     |
| -------- | ---------------------------------------------- | ------------------------------- |
| `GET`    | `/api/health`                                  | Health check                    |
| `POST`   | `/api/upload`                                  | Upload an audio file            |
| `GET`    | `/api/analyses`                                | List session analyses           |
| `GET`    | `/api/analysis/{id}`                           | Get analysis detail / status    |
| `DELETE` | `/api/analysis/{id}`                           | Delete an analysis              |
| `GET`    | `/api/analysis/{id}/audio`                     | Stream original audio           |
| `GET`    | `/api/analysis/{id}/export/{type}`             | Download artifact (midi/musicxml/pdf) |
| `GET`    | `/api/analysis/{id}/artifacts`                 | List available artifacts        |
| `POST`   | `/api/analysis/{id}/ask`                       | Ask AI tutor a question         |

## Tech Stack

- **Backend:** Python 3.11+, Flask 3.x
- **Audio Analysis:** librosa, basic-pitch, pretty_midi, music21
- **AI Tutor:** Google Gemini (`gemini-2.0-flash`)
- **Database:** SQLite (WAL mode)
- **Validation:** Pydantic 2.x

## Project Structure

```
MELODYX/
├── app/
│   ├── __init__.py          # Application factory
│   ├── config.py            # Configuration
│   ├── extensions.py        # Database helpers
│   ├── models/
│   │   └── analysis.py      # DB schema & model functions
│   ├── routes/
│   │   ├── health.py        # GET /api/health
│   │   ├── upload.py        # POST /api/upload
│   │   ├── analysis.py      # GET/DELETE /api/analysis
│   │   ├── export.py        # GET /api/analysis/{id}/export
│   │   └── playback.py      # GET /api/analysis/{id}/audio
│   └── services/            # Business logic (analysis pipeline, AI)
├── contracts/               # Pydantic schemas
├── fixtures/                # Test fixtures
├── tests/                   # Test suite
├── run.py                   # Entry point
├── requirements.txt
└── .env.example
```

## License

Proprietary — All rights reserved.
