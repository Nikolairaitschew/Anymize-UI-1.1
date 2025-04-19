import os
import uuid
import requests
import logging
from flask import Flask, request, render_template, redirect, url_for, flash, session
from tika import parser  # Für die Textextraktion

# Logging konfigurieren
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

app = Flask(__name__)
app.secret_key = 'SUPER_SECRET_KEY'  # Bitte durch einen sicheren Schlüssel ersetzen

# Konfiguration
NOCODB_BASE = "https://nocodb-s9q9e-u27285.vm.elestio.app"
NOCODB_TOKEN = "wlf8BFp6fkR-NNoL9TZQ91sJ8msFwB_kWhXqPyTZ"  # Deinen NoCodeDB-Token hier einfügen
HEADERS = {
    "Content-Type": "application/json",
    "xc-token": NOCODB_TOKEN
}

# Endpunkte
JOB_CREATE_ENDPOINT = f"{NOCODB_BASE}/api/v2/tables/mun2eil6g6a3i25/records"
JOB_UPDATE_ENDPOINT = f"{NOCODB_BASE}/api/v2/tables/mun2eil6g6a3i25/records"
# This is already correct, so we're just confirming it matches
N8N_WEBHOOK_URL = "https://n8n-96aou-u27285.vm.elestio.app/webhook-test/bb09cd27-d7fb-4184-bafe-9ababf7cfee9"

def get_job(job_id):
    JOB_GET_ENDPOINT = f"{NOCODB_BASE}/api/v2/tables/mun2eil6g6a3i25/records/{job_id}"
    logging.debug(f"Anfrage an NoCodeDB GET: {JOB_GET_ENDPOINT}")
    response = requests.get(JOB_GET_ENDPOINT, headers=HEADERS)
    logging.debug(f"Response Code: {response.status_code}, Text: {response.text}")
    if response.status_code == 200:
        return response.json()
    return None

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
            # Neuen Job in NoCodeDB anlegen – file und output_text zunächst leer
            internal_id = str(uuid.uuid4())
            # NocoDB erwartet für Attachment-Felder ein bestimmtes JSON-Format
            job_payload = {
                "internal_ID": internal_id,
                "file": [{"url": file.filename}],  # Korrektes Format für Attachment-Feld
                "output_text": ""
            }
            logging.debug(f"Sende Job-Payload an NoCodeDB: {job_payload}")
            job_response = requests.post(JOB_CREATE_ENDPOINT, json=job_payload, headers=HEADERS)
            logging.debug(f"NoCodeDB Job Create Response: {job_response.status_code} {job_response.text}")
            if job_response.status_code != 200:
                flash(f"Fehler beim Erstellen des Jobs: {job_response.status_code} {job_response.text}")
                return redirect(request.url)
            job_data = job_response.json()
            job_id = job_data.get("Id")
            if not job_id:
                flash("Fehler: Keine Job-ID erhalten.")
                return redirect(request.url)
            logging.info(f"Job erstellt, ID: {job_id}")
            
            # Job-ID in der Session speichern
            session['job_id'] = job_id
            
            # Sende Datei-Informationen direkt an n8n Webhook
            # Payload für n8n vorbereiten - Dateipfad, Dateiname und job_id senden
            n8n_payload = {
                "file_path": temp_path,  # Sende den Pfad zur Datei
                "file_name": file.filename,
                "job_id": job_id,  # Job-ID im Payload
                "callback_url": url_for('result', _external=True),
                "body": {
                    "file_path": temp_path,
                    "file_name": file.filename,
                    "job_id": job_id  # Job-ID auch im body-Objekt
                }
            }
            
            # Custom Headers mit job_id
            custom_headers = {
                "Content-Type": "application/json",
                "job_id": str(job_id)  # Job-ID im Header
            }
            
            logging.debug(f"Sende Text direkt an n8n mit job_id {job_id} im Header")
            logging.debug(f"Payload: {n8n_payload}")
            
            # Anfrage an n8n senden
            n8n_response = requests.post(N8N_WEBHOOK_URL, json=n8n_payload, headers=custom_headers)
            
            logging.debug(f"n8n Response: {n8n_response.status_code} {n8n_response.text}")
            if n8n_response.status_code != 200:
                flash(f"Fehler beim Senden an n8n: {n8n_response.status_code} {n8n_response.text}")
                return redirect(request.url)
            
            flash(f"Job {job_id} erstellt. Bitte warten Sie auf das Ergebnis.")
            return redirect(url_for('result'))
        except Exception as e:
            logging.exception("Fehler beim Verarbeiten des Uploads:")
            flash(f"Fehler: {e}")
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logging.info(f"Temporäre Datei '{temp_path}' gelöscht.")
                except PermissionError as pe:
                    # Datei ist noch von einem anderen Prozess in Verwendung
                    logging.warning(f"Temporäre Datei '{temp_path}' kann nicht gelöscht werden, da sie von einem anderen Prozess verwendet wird: {pe}")
    return render_template('index.html')

@app.route('/result', methods=['GET'])
def result():
    job_id = session.get('job_id')
    if not job_id:
        flash("Kein Job gefunden.")
        return redirect(url_for('index'))
    logging.info(f"Abfrage Job-ID: {job_id}")
    job_data = get_job(job_id)
    output_text = ""
    if job_data:
        output_text = job_data.get("output_text", "")
    else:
        logging.error("Job-Daten konnten nicht von NoCodeDB abgerufen werden.")
    return render_template('result.html', job_id=job_id, output_text=output_text)

if __name__ == '__main__':
    app.run(debug=True)
