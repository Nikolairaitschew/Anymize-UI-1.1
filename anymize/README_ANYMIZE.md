# Anymize

Anonymisierung sensibler Daten per OCR und KI.

## Features
- Upload von PDF, DOCX, TXT und Bilddateien (JPG, PNG, TIFF)
- Automatische Handschriftenerkennung via Tesseract und/oder EasyOCR
- Anonymisierung empfindlicher Informationen mit Platzhaltern
- Speicherung ausgeschriebener Präfixtexte zur späteren Deanonymisierung
- UI- und API-Zugriff

## Installation
1. Repository klonen:
   ```bash
   git clone <repo-url>
   cd Animize/Anymize-UI-1.1/anymize
   ```
2. Virtuelle Umgebung erstellen und aktivieren:
   ```bash
   python -m venv venv
   .\\venv\\Scripts\\activate
   ```
3. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```

## Konfiguration
Umgebungsvariablen in `.env` oder System:
- `NOCODB_BASE`: Basis-URL Ihrer NocoDB-Instanz (z.B. `https://no...`)
- `NOCODB_API_KEY`: Ihr API-Key für NocoDB
- `N8N_WEBHOOK_URL`: URL des n8n-Webhooks für Anonymisierung
- `FLASK_SECRET_KEY`: Geheimschlüssel für Sessions
- `PORT` (optional): Port für die Anwendung (Default: 8000)

## Verwendung
### UI
1. Server starten:
   ```bash
   python enhanced_ocr_app.py
   ```
2. Im Browser öffnen: `http://localhost:8000`
3. Datei hochladen, Anonymisierung abwarten, Ergebnis ansehen oder als PDF herunterladen.

### API
- **POST** `/api/anonymize`:
  ```json
  {
    "text": "Ihr Text hier"
  }
  ```
- Antwort:
  ```json
  {
    "job_id": "12345",
    "input_text": "...",
    "output_text": "..."
  }
  ```

## Projektstruktur
```
anymize/
├── api.py               # Blueprint für REST-API
├── enhanced_ocr_app.py  # Flask-App mit UI-Endpunkten
├── config_shared.py     # Konfiguration und Utility-Funktionen
├── templates/           # HTML-Templates
├── uploads/             # Temporärer Ordner für Uploads
├── requirements.txt
└── README_ANYMIZE.md    # Diese Anleitung
```

