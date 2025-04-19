# Anymize - Text Anonymisierung und Datenverarbeitung

Anymize ist eine Anwendung zur sicheren Verarbeitung von sensiblen Dokumenten. Das System ermöglicht die Extraktion von Text aus verschiedenen Dokumentformaten, Identifizierung sensibler Daten und Anonymisierung durch ein Hash-Verfahren, das eine spätere Deanonymisierung ermöglicht.

## Komponenten

- **OCR-Anwendung**: Extraktion von Text aus verschiedenen Dokumentformaten
- **NoCodeDB**: Datenbank für die Speicherung von Jobs, Prefixen und anonymisierten Daten
- **n8n Workflow**: Workflow für die Datenverarbeitung und KI-Integration

## Installation

1. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```

2. Stellen Sie sicher, dass Tesseract für OCR installiert ist:
   - Windows: [Tesseract für Windows](https://github.com/UB-Mannheim/tesseract/wiki)
   - macOS: `brew install tesseract`
   - Linux: `apt-get install tesseract-ocr`

3. Uploads-Ordner erstellen (wird automatisch beim ersten Start angelegt):
   ```bash
   mkdir uploads
   ```

## Konfiguration

Die Anwendung nutzt folgende Dienste:

1. **NoCodeDB**: 
   - Server: https://nocodb-s9q9e-u27285.vm.elestio.app
   - API-Token: Im Header als `xc-token`

2. **n8n Webhook**: 
   - Webhook URL: `https://n8n-96aou-u27285.vm.elestio.app/webhook-test/f292a87b-b6c9-48c3-9fe6-31d1134adaac`

## Nutzung

1. OCR-Anwendung starten:
   ```bash
   python enhanced_ocr_app.py
   ```

2. Im Browser öffnen:
   ```
   http://localhost:5000
   ```

3. Datei hochladen und verarbeiten lassen

## Datenbanktabellen

Das System nutzt folgende Tabellen:

1. **user**: Benutzerverwaltung
2. **job**: Verarbeitungsaufträge 
3. **string**: Originaltexte und Hashes
4. **prefix**: Datentypen für sensible Informationen (z.B. "FN" für "First Name")
5. **chat_memory**: Speicherung der Nachrichten

## Textextraktion

Die Anwendung unterstützt verschiedene Dateiformate:

- **PDF**: PyMuPDF für durchsuchbare PDFs, OCR für gescannte Dokumente
- **Bilder**: Tesseract OCR
- **DOCX**: Native Extraktion
- **Textdateien**: Direktes Lesen

## Debugging

Bei Problemen mit der NoCodeDB-Verbindung:

```bash
python check_nocodb_token.py
```

Dies testet verschiedene Authentifizierungsmethoden und zeigt, welche funktioniert.

## Workflow

1. Dokument wird hochgeladen und Text extrahiert
2. Text wird in NoCodeDB im `input_text`-Feld gespeichert
3. n8n erhält den Text zur Verarbeitung (Identifikation sensibler Daten)
4. Sensible Daten werden durch prefix+hash ersetzt
5. Der anonymisierte Text kann an externe LLMs weitergeleitet werden
6. Die Antwort wird deanonymisiert, indem hashes durch die Originaldaten ersetzt werden

## API-Integration

Die Anwendung bietet einen API-Endpunkt zum Prüfen des Verarbeitungsstatus:

```
GET /check_status/<job_id>
