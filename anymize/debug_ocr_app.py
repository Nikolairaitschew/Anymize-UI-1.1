import os
import uuid
import time
import requests
import logging
import threading
import json
from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify
import pytesseract  # OCR für Bilder
from PIL import Image
from pdf2image import convert_from_path  # PDF zu Bild-Konvertierung
import fitz  # PyMuPDF für PDF-Textextraktion
from tika import parser as tika_parser  # Für allgemeine Textextraktion
import docx2txt  # Für DOCX-Dateien
import textract  # Textextraktion aus verschiedenen Formaten

# Import from config_shared
from config_shared import (
    NOCODB_BASE,
    NOCODB_TOKEN,
    HEADERS,
    JOB_CREATE_ENDPOINT,
    JOB_GET_ENDPOINT,  
    JOB_UPDATE_ENDPOINT,
    TABLE_JOB,
    N8N_WEBHOOK_URL
)

# Ausführlicheres Logging konfigurieren
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("debug_ocr.log"),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
app.secret_key = 'SUPER_SECRET_KEY'  # Bitte durch einen sicheren Schlüssel ersetzen

# Verschiedene Header-Varianten testen (laut offizieller Dokumentation)
HEADERS_VARIANTS = [
    # Variante 1: xc-token im Header (Standard, laut Dokumentation)
    {
        "Content-Type": "application/json",
        "xc-token": NOCODB_TOKEN
    },
    # Variante 2: xc-token im Header ohne Content-Type
    {
        "xc-token": NOCODB_TOKEN
    },
    # Variante 3: xc-token in Kleinbuchstaben (für den Fall von Groß-/Kleinschreibungsproblemen)
    {
        "Content-Type": "application/json",
        "xc-token": NOCODB_TOKEN.lower()
    }
]
# Aktuelle Headers
HEADERS = HEADERS_VARIANTS[0]

# Endpunkte
N8N_LOCAL_WEBHOOK_URL = "http://localhost:5678/webhook/bb09cd27-d7fb-4184-bafe-9ababf7cfee9"
N8N_REMOTE_WEBHOOK_URL = "https://n8n-96aou-u27285.vm.elestio.app/webhook-test/f292a87b-b6c9-48c3-9fe6-31d1134adaac"
# Aktuelle URL
N8N_WEBHOOK_URL = N8N_LOCAL_WEBHOOK_URL

def try_get_job_with_all_headers(job_id):
    """Versucht, Job-Informationen mit allen Header-Varianten zu erhalten"""
    endpoint = f"{NOCODB_BASE}/api/v2/tables/mun2eil6g6a3i25/records/{job_id}"
    
    for i, headers in enumerate(HEADERS_VARIANTS):
        logging.debug(f"Versuche Job-Abfrage mit Header-Variante {i+1}: {headers}")
        response = requests.get(endpoint, headers=headers)
        
        logging.debug(f"Variante {i+1} Response Code: {response.status_code}, Text: {response.text}")
        
        if response.status_code == 200:
            logging.info(f"Erfolgreiche Abfrage mit Header-Variante {i+1}")
            return response.json(), i
    
    return None, -1

def try_create_job_with_all_headers(job_payload):
    """Versucht, einen Job mit allen Header-Varianten zu erstellen"""
    for i, headers in enumerate(HEADERS_VARIANTS):
        logging.debug(f"Versuche Job-Erstellung mit Header-Variante {i+1}: {headers}")
        response = requests.post(JOB_CREATE_ENDPOINT, json=job_payload, headers=headers)
        
        logging.debug(f"Variante {i+1} Response Code: {response.status_code}, Text: {response.text}")
        
        if response.status_code == 200:
            logging.info(f"Erfolgreiche Erstellung mit Header-Variante {i+1}")
            return response.json(), i
    
    return None, -1

def get_job(job_id):
    """Job-Informationen aus NoCodeDB abrufen"""
    endpoint = f"{NOCODB_BASE}/api/v2/tables/mun2eil6g6a3i25/records/{job_id}"
    logging.debug(f"Anfrage an NoCodeDB GET: {endpoint}")
    response = requests.get(endpoint, headers=HEADERS)
    logging.debug(f"Response Code: {response.status_code}, Text: {response.text}")
    if response.status_code == 200:
        return response.json()
    return None

def extract_text_from_pdf_with_pymupdf(pdf_path):
    """Text aus PDF mit PyMuPDF extrahieren (gut für durchsuchbare PDFs)"""
    try:
        text = ""
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        logging.error(f"Fehler bei der PyMuPDF-Extraktion: {e}")
        return None

def extract_text_from_pdf_with_ocr(pdf_path):
    """Text aus PDF mittels OCR extrahieren (gut für gescannte PDFs ohne eingebetteten Text)"""
    try:
        text = ""
        # PDF zu Bildern konvertieren
        images = convert_from_path(pdf_path, dpi=300)
        for i, image in enumerate(images):
            # OCR für jedes Bild durchführen
            page_text = pytesseract.image_to_string(image, lang='deu+eng')
            text += f"\n--- Seite {i+1} ---\n{page_text}"
        return text
    except Exception as e:
        logging.error(f"Fehler bei der OCR-Extraktion für PDF: {e}")
        return None

def extract_text_from_image(image_path):
    """Text aus Bildern mittels OCR extrahieren"""
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image, lang='deu+eng')
        return text
    except Exception as e:
        logging.error(f"Fehler bei der Bild-OCR-Extraktion: {e}")
        return None

def extract_text_from_docx(docx_path):
    """Text aus DOCX-Datei extrahieren"""
    try:
        text = docx2txt.process(docx_path)
        return text
    except Exception as e:
        logging.error(f"Fehler bei der DOCX-Extraktion: {e}")
        return None

def extract_text_with_textract(file_path):
    """Text mit textract extrahieren (unterstützt viele Formate)"""
    try:
        text = textract.process(file_path).decode('utf-8')
        return text
    except Exception as e:
        logging.error(f"Fehler bei der textract-Extraktion: {e}")
        return None

def extract_text_with_tika(file_path):
    """Text mit Apache Tika extrahieren (sehr universell)"""
    try:
        parsed = tika_parser.from_file(file_path)
        return parsed.get("content", "").strip()
    except Exception as e:
        logging.error(f"Fehler bei der Tika-Extraktion: {e}")
        return None

def extract_text_from_file(file_path):
    """Text aus verschiedenen Dateiformaten extrahieren mit mehreren Methoden"""
    file_extension = os.path.splitext(file_path)[1].lower()
    
    extracted_text = None
    
    # Basierend auf Dateityp die beste Methode wählen
    if file_extension in ['.pdf']:
        # Versuche erst PyMuPDF für durchsuchbare PDFs
        extracted_text = extract_text_from_pdf_with_pymupdf(file_path)
        
        # Wenn wenig oder kein Text gefunden wurde, versuche OCR
        if not extracted_text or len(extracted_text.strip()) < 100:
            logging.info("PDF enthält möglicherweise wenig Text, versuche OCR...")
            extracted_text = extract_text_from_pdf_with_ocr(file_path)
    
    elif file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
        extracted_text = extract_text_from_image(file_path)
    
    elif file_extension in ['.docx']:
        extracted_text = extract_text_from_docx(file_path)
    
    elif file_extension in ['.txt', '.json', '.py', '.js', '.html', '.css', '.md']:
        # Für Textdateien direkt den Inhalt lesen
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                extracted_text = file.read()
        except UnicodeDecodeError:
            # Bei Encoding-Problemen auf ISO-8859-1 zurückgreifen
            try:
                with open(file_path, 'r', encoding='iso-8859-1') as file:
                    extracted_text = file.read()
            except Exception as e:
                logging.error(f"Fehler beim Lesen der Textdatei: {e}")
    
    # Wenn bisher keine Methode erfolgreich war, verwende textract
    if not extracted_text:
        extracted_text = extract_text_with_textract(file_path)
    
    # Als letztes Mittel Apache Tika verwenden
    if not extracted_text:
        extracted_text = extract_text_with_tika(file_path)
    
    return extracted_text or "Keine Textextraktion möglich."

def poll_for_output_text(job_id, max_retries=30, retry_delay=5):
    """Wiederholt die Abfrage nach output_text, bis es gefüllt ist oder max_retries erreicht ist"""
    def poll():
        for attempt in range(max_retries):
            job_data = get_job(job_id)
            if job_data and job_data.get("output_text"):
                logging.info(f"Output-Text für Job {job_id} gefunden: {len(job_data['output_text'])} Zeichen")
                break
            logging.info(f"Warte auf Output-Text für Job {job_id} (Versuch {attempt+1}/{max_retries})...")
            time.sleep(retry_delay)
    
    # Starte Polling in einem separaten Thread
    thread = threading.Thread(target=poll)
    thread.daemon = True
    thread.start()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files or request.files['file'].filename == '':
            flash('Keine Datei ausgewählt.')
            return redirect(request.url)
        file = request.files['file']
        
        # Datei zwischenspeichern
        upload_folder = 'uploads'
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        temp_path = os.path.join(upload_folder, file.filename)
        file.save(temp_path)
        logging.info(f"Datei '{file.filename}' gespeichert unter '{temp_path}'")
        
        try:
            # Textextraktion mit mehreren Methoden
            extracted_text = extract_text_from_file(temp_path)
            if not extracted_text or len(extracted_text.strip()) < 10:
                flash("Konnte keinen Text extrahieren.")
                return redirect(request.url)
            
            logging.info(f"Text extrahiert, Länge: {len(extracted_text)} Zeichen")
            
            # Neuen Job in NoCodeDB anlegen
            internal_id = str(uuid.uuid4())
            job_payload = {
                "internal_ID": internal_id,
                "file": file.filename,
                "input_text": extracted_text,  # Extrahierten Text im input_text-Feld speichern
                "output_text": ""  # output_text zunächst leer
            }
            
            logging.debug(f"Sende Job-Payload an NoCodeDB: {job_payload}")
            
            # Versuche alle Header-Varianten
            job_data, header_index = try_create_job_with_all_headers(job_payload)
            
            if job_data is None:
                flash(f"Fehler beim Erstellen des Jobs: Alle Authentifizierungsmethoden fehlgeschlagen. Siehe Log für Details.")
                return redirect(request.url)
            
            # Erfolgreiche Header-Variante für zukünftige Anfragen merken
            global HEADERS
            HEADERS = HEADERS_VARIANTS[header_index]
            logging.info(f"Verwende Header-Variante {header_index+1} für alle weiteren Anfragen.")
            
            job_id = job_data.get("Id")
            if not job_id:
                flash("Fehler: Keine Job-ID erhalten.")
                return redirect(request.url)
            
            logging.info(f"Job erstellt, ID: {job_id}")
            
            # Job-ID in der Session speichern
            session['job_id'] = job_id
            
            # Payload für n8n vorbereiten - extrahierten Text und job_id senden
            n8n_payload = {
                "text": extracted_text,  # Sende den extrahierten Text
                "job_id": job_id,
                "callback_url": url_for('result', _external=True),
                "body": {
                    "text": extracted_text,
                    "job_id": job_id
                }
            }
            
            # Custom Headers mit job_id
            custom_headers = {
                "Content-Type": "application/json",
                "job_id": str(job_id)
            }
            
            logging.debug(f"Sende extrahierten Text an n8n mit job_id {job_id} im Header")
            logging.debug(f"Verwende n8n Webhook URL: {N8N_WEBHOOK_URL}")
            
            # Anfrage an n8n senden
            n8n_response = requests.post(N8N_WEBHOOK_URL, json=n8n_payload, headers=custom_headers)
            
            logging.debug(f"n8n Response Code: {n8n_response.status_code}")
            logging.debug(f"n8n Response Text: {n8n_response.text}")
            
            # Wenn lokaler Webhook fehlschlägt, versuche den Remote-Webhook
            if n8n_response.status_code != 200:
                logging.warning(f"Lokaler n8n Webhook fehlgeschlagen. Versuche Remote-Webhook...")
                global N8N_WEBHOOK_URL
                N8N_WEBHOOK_URL = N8N_REMOTE_WEBHOOK_URL
                n8n_response = requests.post(N8N_WEBHOOK_URL, json=n8n_payload, headers=custom_headers)
                logging.debug(f"Remote n8n Response Code: {n8n_response.status_code}")
                logging.debug(f"Remote n8n Response Text: {n8n_response.text}")
            
            if n8n_response.status_code != 200:
                flash(f"Fehler beim Senden an n8n: {n8n_response.status_code} {n8n_response.text}")
                return redirect(request.url)
            
            # Starte Polling nach output_text im Hintergrund
            poll_for_output_text(job_id)
            
            flash(f"Job {job_id} erstellt. Bitte warten Sie auf das Ergebnis.")
            return redirect(url_for('result'))
            
        except Exception as e:
            logging.exception("Fehler beim Verarbeiten des Uploads:")
            flash(f"Fehler: {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logging.info(f"Temporäre Datei '{temp_path}' gelöscht.")
    
    return render_template('index.html')

@app.route('/result', methods=['GET'])
def result():
    job_id = session.get('job_id')
    if not job_id:
        flash("Kein Job gefunden.")
        return redirect(url_for('index'))
    
    logging.info(f"Abfrage Job-ID: {job_id}")
    
    # Versuche alle Header-Varianten
    job_data, header_index = try_get_job_with_all_headers(job_id)
    
    if job_data is not None:
        # Erfolgreiche Header-Variante für zukünftige Anfragen merken
        global HEADERS
        HEADERS = HEADERS_VARIANTS[header_index]
        logging.info(f"Verwende Header-Variante {header_index+1} für alle weiteren Anfragen.")
    
    input_text = ""
    output_text = ""
    
    if job_data:
        input_text = job_data.get("input_text", "")
        output_text = job_data.get("output_text", "")
        if not output_text:
            flash("Die Verarbeitung ist noch nicht abgeschlossen. Bitte warten Sie...")
    else:
        logging.error("Job-Daten konnten nicht von NoCodeDB abgerufen werden.")
    
    # Verwende die verbesserte Ergebnisvorlage
    return render_template(
        'enhanced_result.html', 
        job_id=job_id, 
        input_text=input_text, 
        output_text=output_text,
        processing=not output_text  # Flag für Frontend, ob Job noch in Bearbeitung ist
    )

@app.route('/check_status/<job_id>', methods=['GET'])
def check_status(job_id):
    """API-Endpunkt zum Prüfen des Verarbeitungsstatus"""
    # Versuche alle Header-Varianten
    job_data, _ = try_get_job_with_all_headers(job_id)
    
    if not job_data:
        return jsonify({"status": "error", "message": "Job nicht gefunden"}), 404
    
    output_text = job_data.get("output_text", "")
    return jsonify({
        "status": "completed" if output_text else "processing",
        "output_text": output_text
    })

@app.route('/test-connection', methods=['GET'])
def test_connection():
    """API-Endpunkt zum Testen der Verbindung mit NoCodeDB und n8n"""
    results = {
        "nocodb": {},
        "n8n": {}
    }
    
    # NoCodeDB-Verbindung testen
    for i, headers in enumerate(HEADERS_VARIANTS):
        try:
            response = requests.get(f"{NOCODB_BASE}/api/v2/tables/mun2eil6g6a3i25/records?limit=1", headers=headers)
            results["nocodb"][f"variant_{i+1}"] = {
                "status_code": response.status_code,
                "headers_used": headers,
                "success": response.status_code == 200
            }
        except Exception as e:
            results["nocodb"][f"variant_{i+1}"] = {
                "error": str(e),
                "headers_used": headers,
                "success": False
            }
    
    # n8n-Webhooks testen
    try:
        response = requests.post(
            N8N_LOCAL_WEBHOOK_URL, 
            json={"test": True}, 
            headers={"Content-Type": "application/json"}
        )
        results["n8n"]["local"] = {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "url": N8N_LOCAL_WEBHOOK_URL
        }
    except Exception as e:
        results["n8n"]["local"] = {
            "error": str(e),
            "success": False,
            "url": N8N_LOCAL_WEBHOOK_URL
        }
    
    try:
        response = requests.post(
            N8N_REMOTE_WEBHOOK_URL, 
            json={"test": True}, 
            headers={"Content-Type": "application/json"}
        )
        results["n8n"]["remote"] = {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "url": N8N_REMOTE_WEBHOOK_URL
        }
    except Exception as e:
        results["n8n"]["remote"] = {
            "error": str(e),
            "success": False,
            "url": N8N_REMOTE_WEBHOOK_URL
        }
    
    return jsonify(results)

if __name__ == '__main__':
    # Konfiguration anzeigen
    logging.info(f"Server-Konfiguration:")
    logging.info(f"NoCodeDB URL: {NOCODB_BASE}")
    logging.info(f"n8n Webhook URL (lokal): {N8N_LOCAL_WEBHOOK_URL}")
    logging.info(f"n8n Webhook URL (remote): {N8N_REMOTE_WEBHOOK_URL}")
    
    app.run(debug=True)
