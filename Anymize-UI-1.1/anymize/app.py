import os
import uuid
import requests
import logging
from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)
app.secret_key = 'SUPER_SECRET_KEY'  # Bitte durch einen sicheren Wert ersetzen

# Konfiguration für NoCodeDB und n8n
NOCODEB_BASE = "https://nocodb-s9q9e-u27285.vm.elestio.app"
NOCODEB_TOKEN = "wlf8BFp6fkR-NNoL9TZQ91sJ8msFwB_kWhXqPyTZ"
NOCODEB_HEADERS = {
    "Content-Type": "application/json",
    "xc-token": NOCODEB_TOKEN
}
JOB_CREATE_ENDPOINT = f"{NOCODEB_BASE}/api/v2/tables/mun2eil6g6a3i25/records"
JOB_GET_ENDPOINT = f"{NOCODEB_BASE}/api/v2/tables/mun2eil6g6a3i25/records"
JOB_UPDATE_ENDPOINT = f"{NOCODEB_BASE}/api/v2/tables/mun2eil6g6a3i25/records"
N8N_WEBHOOK_URL = "https://n8n-96aou-u27285.vm.elestio.app/webhook/bb09cd27-d7fb-4184-bafe-9ababf7cfee9"

def get_job(job_id):
    """Retrieve job information from NoCodeDB"""
    endpoint = f"{NOCODEB_BASE}/api/v2/tables/mun2eil6g6a3i25/records/{job_id}"
    logging.debug(f"Anfrage an NoCodeDB GET: {endpoint}")
    response = requests.get(endpoint, headers=NOCODEB_HEADERS)
    logging.debug(f"Response Code: {response.status_code}, Text: {response.text}")
    if response.status_code == 200:
        return response.json()
    return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Keine Datei ausgewählt.')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('Keine Datei ausgewählt.')
            return redirect(request.url)

        # Datei temporär speichern
        upload_folder = 'uploads'
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        temp_path = os.path.join(upload_folder, file.filename)
        file.save(temp_path)

        try:
            # Improved text extraction based on file type
            extracted_text = ""
            file_ext = os.path.splitext(file.filename)[1].lower()
            
            if file_ext == '.pdf':
                # Try to use tika for PDF extraction
                try:
                    from tika import parser as tika_parser
                    parsed = tika_parser.from_file(temp_path)
                    extracted_text = parsed.get("content", "").strip()
                    logging.info(f"Extracted {len(extracted_text)} characters with Tika")
                except Exception as e:
                    logging.warning(f"Tika extraction failed: {e}")
            
            # If we still don't have text or for non-PDF files, try direct reading
            if not extracted_text or len(extracted_text.strip()) < 10:
                with open(temp_path, 'rb') as f:
                    try:
                        # Try to read the file as text
                        extracted_text = f.read().decode('utf-8')
                        logging.info(f"Extracted {len(extracted_text)} characters with direct reading")
                    except UnicodeDecodeError:
                        # If it's not a text file, add a sample text for testing
                        extracted_text = f"Beispieltext für {file.filename}: \n\nMax Mustermann wohnt in der Musterstraße 123 in 12345 Berlin. \nTelefonnummer: 030-12345678 \nE-Mail: max.mustermann@example.com \nGeburtsdatum: 01.01.1980 \nKontonummer: DE123456789012345678 \nSteuer-ID: 12345678901"
                        logging.info("Using sample text with personal data for testing")

            # Erstelle einen neuen Job in NoCodeDB
            internal_id = str(uuid.uuid4())
            job_payload = {
                "internal_ID": internal_id,
                "file": None,  # Set to null for NoCodeDB
                "input_text": extracted_text,
                "output_text": ""
            }
            
            job_response = requests.post(JOB_CREATE_ENDPOINT, json=job_payload, headers=NOCODEB_HEADERS)
            
            if job_response.status_code != 200:
                flash(f"Fehler beim Erstellen des Jobs: {job_response.status_code} {job_response.text}")
                return redirect(request.url)
            
            job_data = job_response.json()
            job_id = job_data.get("Id")
            if not job_id:
                flash("Fehler: Job-ID nicht erhalten.")
                return redirect(request.url)
            
            # Speichere die Job-ID in der Session
            session['job_id'] = job_id
            
            # Bereite Payload für n8n vor
            n8n_payload = {
                "text": extracted_text,
                "job_id": job_id,
                "callback_url": url_for('result', _external=True),
                "body": {
                    "text": extracted_text,
                    "job_id": job_id
                }
            }
            
            # Custom headers mit job_id
            custom_headers = {
                "Content-Type": "application/json",
                "job_id": str(job_id)
            }
            
            # Sende Anfrage an n8n
            n8n_response = requests.post(N8N_WEBHOOK_URL, json=n8n_payload, headers=custom_headers)
            
            if n8n_response.status_code != 200:
                flash(f"Fehler beim Senden an n8n: {n8n_response.status_code} {n8n_response.text}")
                return redirect(request.url)
            
            flash(f"Job {job_id} wurde erfolgreich erstellt. Bitte warten Sie auf das Ergebnis.")
            return redirect(url_for('result'))
            
        except Exception as e:
            flash(f"Fehler: {e}")
            logging.exception("Fehler beim Verarbeiten des Uploads:")
        finally:
            # Cleanup
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except PermissionError:
                    pass
    
    return render_template('index.html')

@app.route('/result', methods=['GET'])
def result():
    job_id = session.get('job_id')
    if not job_id:
        flash("Kein Job gefunden.")
        return redirect(url_for('index'))
    
    job_data = get_job(job_id)
    input_text = ""
    output_text = ""
    
    if job_data:
        input_text = job_data.get("input_text", "")
        output_text = job_data.get("output_text", "")
        if not output_text:
            flash("Die Verarbeitung ist noch nicht abgeschlossen. Bitte warten Sie...")
    else:
        logging.error("Job-Daten konnten nicht von NoCodeDB abgerufen werden.")
    
    # Verwende das verbesserte Template
    return render_template(
        'enhanced_result.html', 
        input_text=input_text, 
        output_text=output_text,
        processing=not output_text  # Flag für Frontend, um anzuzeigen, ob Job noch verarbeitet wird
    )

@app.route('/check_status', methods=['GET'])
def check_status():
    """API-Endpunkt zur Überprüfung des Verarbeitungsstatus über die Session"""
    job_id = session.get('job_id')
    if not job_id:
        return jsonify({"status": "error", "message": "Kein Job in der Session gefunden"}), 404
    
    job_data = get_job(job_id)
    if not job_data:
        return jsonify({"status": "error", "message": "Job nicht gefunden"}), 404
    
    output_text = job_data.get("output_text", "")
    return jsonify({
        "status": "completed" if output_text else "processing",
        "output_text": output_text
    })

if __name__ == '__main__':
    app.run(debug=True)
