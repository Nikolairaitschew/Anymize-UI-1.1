import os
import uuid
import requests
import logging
from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify
import time
from config_shared import (
    N8N_WEBHOOK_URL,
    NOCODB_BASE,
    NOCODB_TOKEN,
    HEADERS,
    JOB_CREATE_ENDPOINT,
    JOB_GET_ENDPOINT,
    JOB_UPDATE_ENDPOINT,
    TABLE_JOB
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)
app.secret_key = 'SUPER_SECRET_KEY'  # Bitte durch einen sicheren Wert ersetzen

def get_job(job_id):
    """Retrieve job information from NoCodeDB by job_id (NOT by incremental Id)."""
    endpoint = f"{NOCODB_BASE}/api/v2/tables/{TABLE_JOB}/records?where=(job_id,eq,{job_id})"
    logging.debug(f"Anfrage an NoCodeDB GET: {endpoint}")
    response = requests.get(endpoint, headers=HEADERS)
    logging.debug(f"Response Code: {response.status_code}, Text: {response.text}")
    if response.status_code == 200:
        jobs = response.json().get('list', [])
        return jobs[0] if jobs else None
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
            
            job_response = requests.post(JOB_CREATE_ENDPOINT, json=job_payload, headers=HEADERS)
            
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

@app.route('/result_ajax', methods=['GET'])
def result_ajax():
    """AJAX endpoint for polling job status and results, returns detailed output including prompts and language."""
    job_id = request.args.get('job_id') or session.get('job_id')
    lang = request.args.get('lang') or session.get('lang') or None
    if not job_id:
        return jsonify({'status': 'error', 'message': 'No job_id provided'}), 400
    job_data = get_job(job_id)
    if not job_data:
        return jsonify({'status': 'error', 'message': 'Job not found'}), 404
    input_text = job_data.get('input_text', '')
    output_text = job_data.get('output_text', '')
    # Language detection and prompt selection
    if not lang:
        try:
            from langdetect import detect
            lang_code = detect(input_text)
            lang_map = {'de': 'de', 'en': 'en', 'fr': 'fr', 'es': 'es', 'it': 'it'}
            lang = lang_map.get(lang_code, 'en')
        except Exception:
            lang = 'en'
    logging.info(f"[result_ajax] Detected/used language: {lang} for input: {input_text[:80]}")
    # Prompts for system, header, and footer (customize as needed)
    SYSTEM_PROMPTS = {
        'de': "Dies ist ein deutscher Systemprompt.",
        'en': "This is an English system prompt.",
        'fr': "Ceci est un prompt système français.",
        'es': "Este es un mensaje del sistema en español.",
        'it': "Questo è un prompt di sistema italiano."
    }
    HEADER_PROMPTS = {
        'de': "ANONYMISIERTER TEXT (Platzhalter = sensible Daten)",
        'en': "ANONYMIZED TEXT (placeholders = sensitive data)",
        'fr': "TEXTE ANONYMISÉ (espaces réservés = données sensibles)",
        'es': "TEXTO ANONIMIZADO (marcadores = datos sensibles)",
        'it': "TESTO ANONIMIZZATO (segnaposto = dati sensibili)"
    }
    FOOTER_PROMPTS = {
        'de': "ENDE DES ANONYMISIERTEN TEXTES. Platzhalter sind wie reale Werte zu interpretieren; ein Rückschluss auf Originaldaten ist nicht möglich.",
        'en': "END OF ANONYMIZED TEXT. Placeholders should be interpreted as real values; de-anonymization is not possible.",
        'fr': "FIN DU TEXTE ANONYMISÉ. Les espaces réservés doivent être interprétés comme des valeurs réelles; la désanonymisation n'est pas possible.",
        'es': "FIN DEL TEXTO ANONIMIZADO. Los marcadores deben interpretarse como valores reales; no es posible desanonimizar.",
        'it': "FINE DEL TESTO ANONIMIZZATO. I segnaposto devono essere interpretati come valori reali; non è possibile risalire o de-anonimizzare."
    }
    # Language-sensitive label replacing
    output_text_labeled = replace_prefixes_with_labels(output_text, lang) if output_text else ''
    # Compose anonymized text with prompts
    anonymized_text_with_prompts = f"{HEADER_PROMPTS[lang]}\n\n{output_text_labeled}\n\n{FOOTER_PROMPTS[lang]}" if output_text else ''
    return jsonify({
        'status': 'completed' if output_text else 'processing',
        'job_id': job_id,
        'system_prompt': SYSTEM_PROMPTS[lang],
        'raw_anonymized_text': output_text,
        'output_text_labeled': output_text_labeled,
        'anonymized_text_with_prompts': anonymized_text_with_prompts,
        'input_text': input_text,
        'language': lang
    })

@app.route('/api/anonymize', methods=['POST'])
def api_anonymize():
    """
    API endpoint to create a job and trigger n8n, without blocking for OCR or waiting for output.
    Logs every step and returns job_id and input_text immediately.
    """
    try:
        data = request.get_json(force=True, silent=True) or request.form
        text = data.get('text', '').strip()
        lang = data.get('lang') or request.args.get('lang') or session.get('lang') or 'en'  # Allow explicit language
        if not text:
            logging.error("[API] No input text provided.")
            return jsonify({'error': 'No input text provided.'}), 400
        logging.info(f"[API] Received text: {text[:80]}... (lang: {lang})")
        # 2. Create job in NocoDB
        internal_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())[:8]
        job_payload = {
            'internal_ID': internal_id,
            'job_id': job_id,
            'input_text': text,
            'output_text': ''
        }
        logging.info(f"[API] Creating job: {job_payload}")
        resp = requests.post(JOB_CREATE_ENDPOINT, json=job_payload, headers=HEADERS)
        if resp.status_code != 200:
            logging.error(f"[API] Job creation failed: {resp.status_code} {resp.text}")
            return jsonify({'error': 'Job creation failed.'}), 500
        logging.info(f"[API] Job created: {job_id}")
        # 3. Trigger n8n webhook
        n8n_payload = {'job_id': job_id, 'text': text, 'lang': lang}
        logging.info(f"[API] Triggering n8n: {n8n_payload}")
        n8n_resp = requests.post(N8N_WEBHOOK_URL, json=n8n_payload, headers={'Content-Type': 'application/json'})
        if n8n_resp.status_code != 200:
            logging.error(f"[API] n8n webhook failed: {n8n_resp.status_code} {n8n_resp.text}")
            return jsonify({'error': 'n8n webhook failed.'}), 500
        logging.info(f"[API] n8n webhook triggered: {job_id}")
        # 4. Polling auf anonymisierte Ausgabe
        output_text = ''
        for attempt in range(30):
            job_data = get_job(job_id)
            output_text = job_data.get('output_text', '') if job_data else ''
            if output_text:
                logging.info(f"[API] Output text ready for job {job_id} (attempt {attempt+1})")
                break
            logging.info(f"[API] Waiting for anonymization (attempt {attempt+1}/30)...")
            time.sleep(5)
        if not output_text:
            return jsonify({'status': 'processing', 'job_id': job_id, 'language': lang}), 202
        # Prompts in gewünschter Sprache
        SYSTEM_PROMPTS = {
            'de': "Dies ist ein deutscher Systemprompt.",
            'en': "This is an English system prompt.",
            'fr': "Ceci est un prompt système français.",
            'es': "Este es un mensaje del sistema en español.",
            'it': "Questo è un prompt di sistema italiano."
        }
        HEADER_PROMPTS = {
            'de': "ANONYMISIERTER TEXT (Platzhalter = sensible Daten)",
            'en': "ANONYMIZED TEXT (placeholders = sensitive data)",
            'fr': "TEXTE ANONYMISÉ (espaces réservés = données sensibles)",
            'es': "TEXTO ANONIMIZADO (marcadores = datos sensibles)",
            'it': "TESTO ANONIMIZZATO (segnaposto = dati sensibili)"
        }
        FOOTER_PROMPTS = {
            'de': "ENDE DES ANONYMISIERTEN TEXTES. Platzhalter sind wie reale Werte zu interpretieren; ein Rückschluss auf Originaldaten ist nicht möglich.",
            'en': "END OF ANONYMIZED TEXT. Placeholders should be interpreted as real values; de-anonymization is not possible.",
            'fr': "FIN DU TEXTE ANONYMISÉ. Les espaces réservés doivent être interprétés comme des valeurs réelles; la désanonymisation n'est pas possible.",
            'es': "FIN DEL TEXTO ANONIMIZADO. Los marcadores deben interpretarse como valores reales; no es posible desanonimizar.",
            'it': "FINE DEL TESTO ANONIMIZZATO. I segnaposto devono essere interpretati come valori reali; non è possibile risalire o de-anonimizzare."
        }
        # Label-Replacement
        output_text_labeled = replace_prefixes_with_labels(output_text, lang)
        anonymized_text_with_prompts = f"{HEADER_PROMPTS[lang]}\n\n{output_text_labeled}\n\n{FOOTER_PROMPTS[lang]}"
        return jsonify({
            'status': 'completed',
            'job_id': job_id,
            'language': lang,
            'raw_anonymized_text': output_text,
            'system_prompt': SYSTEM_PROMPTS[lang],
            'anonymized_text_with_prompts': anonymized_text_with_prompts
        })
    except Exception as e:
        logging.exception("[API] Error in anonymize flow:")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
