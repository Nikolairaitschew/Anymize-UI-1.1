import os
import uuid
import time
import requests
import logging
import threading
import sys
from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Import OCR functionality from our new modules
from ocr.config import ensure_directories
from ocr.document_ocr import extract_text_from_file

# Configure Flask application
app = Flask(__name__)
app.secret_key = 'SUPER_SECRET_KEY'  # Please replace with a secure key
app.logger.setLevel(logging.INFO)

# Configuration
NOCODB_BASE = "https://nocodb-s9q9e-u27285.vm.elestio.app"
NOCODB_TOKEN = "wlf8BFp6fkR-NNoL9TZQ91sJ8msFwB_kWhXqPyTZ"
HEADERS = {
    "Content-Type": "application/json",
    "xc-token": NOCODB_TOKEN
}

# Endpoints
JOB_CREATE_ENDPOINT = f"{NOCODB_BASE}/api/v2/tables/mun2eil6g6a3i25/records"
JOB_GET_ENDPOINT = f"{NOCODB_BASE}/api/v2/tables/mun2eil6g6a3i25/records"
JOB_UPDATE_ENDPOINT = f"{NOCODB_BASE}/api/v2/tables/mun2eil6g6a3i25/records"
N8N_WEBHOOK_URL = "https://n8n-96aou-u27285.vm.elestio.app/webhook/bb09cd27-d7fb-4184-bafe-9ababf7cfee9"

def get_job(job_id):
    """Retrieve job information from NoCodeDB"""
    endpoint = f"{NOCODB_BASE}/api/v2/tables/mun2eil6g6a3i25/records/{job_id}"
    logging.debug(f"Anfrage an NoCodeDB GET: {endpoint}")
    response = requests.get(endpoint, headers=HEADERS)
    logging.debug(f"Response Code: {response.status_code}, Text: {response.text}")
    if response.status_code == 200:
        return response.json()
    return None

def poll_for_output_text(job_id, max_retries=30, retry_delay=5):
    """Repeatedly query for output_text until it's filled or max_retries is reached"""
    def poll():
        for attempt in range(max_retries):
            job_data = get_job(job_id)
            if job_data and job_data.get("output_text"):
                logging.info(f"Output text found for job {job_id}: {len(job_data['output_text'])} characters")
                break
            logging.info(f"Waiting for output text for job {job_id} (attempt {attempt+1}/{max_retries})...")
            time.sleep(retry_delay)
    
    # Start polling in a separate thread
    thread = threading.Thread(target=poll)
    thread.daemon = True
    thread.start()

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main route for file upload and processing"""
    if request.method == 'POST':
        if 'file' not in request.files or request.files['file'].filename == '':
            flash('No file selected.')
            return redirect(request.url)
        file = request.files['file']
        
        # Save file temporarily
        upload_folder = 'uploads'
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        temp_path = os.path.join(upload_folder, file.filename)
        file.save(temp_path)
        logging.info(f"File '{file.filename}' saved at '{temp_path}'")
        
        try:
            # Text extraction with auto-detection for handwritten content
            logging.info("Extracting text with automatic handwriting detection")
            
            # Use our modular OCR system with auto-detection
            extracted_text = extract_text_from_file(temp_path)
            
            if not extracted_text or len(extracted_text.strip()) < 10:
                flash("Could not extract any text.")
                return redirect(request.url)
            
            logging.info(f"Text extrahiert, Länge: {len(extracted_text)} Zeichen")
            
            # Create a new job in NoCodeDB
            internal_id = str(uuid.uuid4())
            # Handle file fields correctly according to NoCodeDB requirements
            job_payload = {
                "internal_ID": internal_id,
                "file": None,  # Set file field to null as it's treated as an attachment
                "input_text": extracted_text,  # Store extracted text in input_text field
                "output_text": ""  # output_text initially empty
            }
            
            logging.debug(f"Sende Job-Payload an NoCodeDB: {job_payload}")
            job_response = requests.post(JOB_CREATE_ENDPOINT, json=job_payload, headers=HEADERS)
            logging.debug(f"NoCodeDB Job Create Response: {job_response.status_code} {job_response.text}")
            
            if job_response.status_code != 200:
                flash(f"Error creating job: {job_response.status_code} {job_response.text}")
                return redirect(request.url)
            
            job_data = job_response.json()
            job_id = job_data.get("Id")
            if not job_id:
                flash("Error: No job ID received.")
                return redirect(request.url)
            
            logging.info(f"Job erstellt, ID: {job_id}")
            
            # Store job ID in session
            session['job_id'] = job_id
            
            # Prepare payload for n8n - send extracted text and job_id
            n8n_payload = {
                "text": extracted_text,  # Send extracted text
                "job_id": job_id,
                "callback_url": url_for('result', _external=True),
                "body": {
                    "text": extracted_text,
                    "job_id": job_id
                }
            }
            
            # Custom headers with job_id
            custom_headers = {
                "Content-Type": "application/json",
                "job_id": str(job_id)
            }
            
            logging.debug(f"Sende extrahierten Text an n8n mit job_id {job_id} im Header")
            
            # Send request to n8n
            n8n_response = requests.post(N8N_WEBHOOK_URL, json=n8n_payload, headers=custom_headers)
            
            logging.debug(f"n8n Response: {n8n_response.status_code} {n8n_response.text}")
            if n8n_response.status_code != 200:
                flash(f"Error sending to n8n: {n8n_response.status_code} {n8n_response.text}")
                return redirect(request.url)
            
            # Start polling for output_text in background
            poll_for_output_text(job_id)
            
            flash(f"Job {job_id} erstellt. Bitte warten Sie auf das Ergebnis.")
            return redirect(url_for('result'))
            
        except Exception as e:
            logging.exception("Fehler beim Verarbeiten des Uploads:")
            flash(f"Fehler: {e}")
        # Keep the file for future processing
    
    return render_template('index.html')

@app.route('/result', methods=['GET'])
def result():
    """Result page displaying OCR results"""
    job_id = session.get('job_id')
    if not job_id:
        flash("Kein Job gefunden.")
        return redirect(url_for('index'))
    
    logging.info(f"Abfrage Job-ID: {job_id}")
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
    
    # Use the enhanced result template
    return render_template(
        'enhanced_result.html', 
        input_text=input_text, 
        output_text=output_text,
        processing=not output_text  # Flag for frontend to indicate if job is still being processed
    )

@app.route('/result_ajax', methods=['GET'])
def result_ajax():
    """AJAX endpoint for polling job status and results"""
    job_id = request.args.get('job_id') or session.get('job_id')
    if not job_id:
        return jsonify({'status': 'error', 'message': 'No job_id provided'}), 400
    job_data = get_job(job_id)
    if not job_data:
        return jsonify({'status': 'error', 'message': 'Job not found'}), 404
    input_text = job_data.get('input_text', '')
    output_text = job_data.get('output_text', '')
    if output_text:
        return jsonify({'status': 'done', 'input_text': input_text, 'output_text': output_text})
    else:
        return jsonify({'status': 'processing'})

@app.route('/check_status', methods=['GET'])
def check_status():
    """API endpoint for checking processing status via session"""
    job_id = session.get('job_id')
    if not job_id:
        return jsonify({"status": "error", "message": "No job found in session"}), 404
    
    job_data = get_job(job_id)
    if not job_data:
        return jsonify({"status": "error", "message": "Job not found"}), 404
    
    output_text = job_data.get("output_text", "")
    return jsonify({
        "status": "completed" if output_text else "processing",
        "output_text": output_text
    })

if __name__ == '__main__':
    # Ensure all necessary directories exist before starting the app
    ensure_directories()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
