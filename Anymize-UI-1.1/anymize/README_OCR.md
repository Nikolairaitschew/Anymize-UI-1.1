# Anymize OCR App

Eine erweiterte Anwendung zur Extraktion von Text aus verschiedenen Dateiformaten mit mehreren OCR-Methoden und Integration mit NoCodeDB und n8n.

## Funktionen

- **Multi-Methode Textextraktion**: Kombiniert mehrere OCR-Bibliotheken für maximale Kompatibilität
- **Unterstützte Formate**:
  - PDF (durchsuchbar und gescannt)
  - Bilder (JPG, PNG, BMP, TIFF)
  - Office-Dokumente (DOCX)
  - Textdateien (TXT, JSON, PY, JS, HTML, CSS, MD)
  - Und viele mehr durch textract und Apache Tika
- **Robuste PDF-Verarbeitung**:
  - PyMuPDF für durchsuchbare PDFs
  - OCR-Fallback für gescannte PDFs ohne eingebetteten Text
- **NoCodeDB Integration**:
  - Speichert Dateinamen und extrahierten Text in der Datenbank
- **n8n Webhook-Integration**:
  - Sendet extrahierten Text zur weiteren Verarbeitung an n8n
- **Echtzeit-Statusaktualisierung**:
  - Fortschrittsanzeige während der Verarbeitung
  - Automatische Aktualisierung der Ergebnisse
  - Diff-Ansicht zum Vergleich von Original- und verarbeitetem Text

## Installation

### Abhängigkeiten

Installieren Sie die erforderlichen Python-Pakete:

```bash
pip install -r requirements.txt
```

### Zusätzliche Software

Für die OCR-Funktionalität müssen Sie folgende Software installieren:

1. **Tesseract OCR**: 
   - Windows: [Tesseract OCR für Windows](https://github.com/UB-Mannheim/tesseract/wiki)
   - macOS: `brew install tesseract tesseract-lang`
   - Linux: `sudo apt install tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng`

2. **Poppler** (für PDF-Konvertierung):
   - Windows: [Poppler für Windows](https://github.com/oschwartz10612/poppler-windows/releases/)
   - macOS: `brew install poppler`
   - Linux: `sudo apt install poppler-utils`

3. **Java Runtime** (für Tika):
   - Windows: [Java Runtime Environment](https://www.java.com/download/)
   - macOS: `brew install java`
   - Linux: `sudo apt install default-jre`

Stellen Sie sicher, dass die Pfade zu diesen Programmen in Ihrer Systemumgebung korrekt eingerichtet sind.

## Konfiguration

Passen Sie folgende Einstellungen in `enhanced_ocr_app.py` an:

- `NOCODB_BASE`: Basis-URL Ihrer NoCodeDB-Instanz
- `NOCODB_TOKEN`: Ihr NoCodeDB API-Token
- `N8N_WEBHOOK_URL`: URL des n8n-Webhooks

## Verwendung

### Starten der Anwendung

```bash
python enhanced_ocr_app.py
```

Die Anwendung wird standardmäßig auf http://localhost:5000 gestartet.

### Upload und Verarbeitung

1. Öffnen Sie die Anwendung im Browser
2. Wählen Sie eine Datei zum Hochladen aus
3. Die App extrahiert den Text mit der optimalen Methode
4. Der extrahierte Text wird in NoCodeDB gespeichert und an n8n gesendet
5. Die Ergebnisseite zeigt den extrahierten Text und den Verarbeitungsstatus
6. Sobald die Verarbeitung abgeschlossen ist, werden beide Texte und die Unterschiede angezeigt

## Dateistruktur

- `enhanced_ocr_app.py`: Hauptanwendungsdatei
- `templates/`: Enthält die HTML-Templates
  - `index.html`: Upload-Seite
  - `enhanced_result.html`: Ergebnisseite mit Echtzeit-Updates
- `uploads/`: Temporärer Speicherort für hochgeladene Dateien (wird automatisch erstellt)
- `requirements.txt`: Liste der Python-Abhängigkeiten

## Anpassung

### Unterstützung für weitere Sprachen

Die OCR-Funktionalität unterstützt standardmäßig Deutsch und Englisch. Um weitere Sprachen hinzuzufügen, installieren Sie die entsprechenden Sprachpakete für Tesseract und passen Sie die `lang`-Parameter in den OCR-Funktionen an:

```python
page_text = pytesseract.image_to_string(image, lang='deu+eng+fra')  # Fügt Französisch hinzu
```

### Weitere Dateiformate

Die Anwendung nutzt mehrere Methoden zur Textextraktion. Um die Unterstützung für bestimmte Dateiformate zu optimieren, passen Sie die `file_extension`-Bedingungen in der `extract_text_from_file`-Funktion an.
