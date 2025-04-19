
import re
import requests
import logging
from flask import Flask, request, jsonify
from ai_service import AnymizeService

# Logging konfigurieren
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

app = Flask(__name__)
app.secret_key = 'ANOTHER_SECRET_KEY'  # Bitte mit einem sicheren Schlüssel ersetzen

# Anymize Service initialisieren
anymize_service = AnymizeService()

@app.route('/process', methods=['POST'])
def process():
    """
    Endpunkt zum Starten der Verarbeitung eines Texts.
    
    Erwarteter JSON-Payload:
    {
       "job_id": "<Job-ID>",
       "text": "<Originaltext>",
       "callback_url": "<Optional: URL für Callback nach Verarbeitung>"
    }
    """
    data = request.get_json()
    logging.debug(f"Eingehende Daten: {data}")
    job_id = data.get("job_id")
    text = data.get("text")
    callback_url = data.get("callback_url")
    
    if not job_id or text is None:
        logging.error("Ungültiger Payload: job_id oder text fehlt")
        return jsonify({"msg": "Invalid payload"}), 400
    
    # Text an n8n zur Verarbeitung senden
    success = anymize_service.process_file(job_id, text, callback_url)
    
    if not success:
        return jsonify({"msg": "Fehler bei der Verarbeitung"}), 500
    
    return jsonify({
        "msg": "Verarbeitung gestartet",
        "job_id": job_id
    }), 200

@app.route('/store-mapping', methods=['POST'])
def store_mapping():
    """
    Endpunkt zum Speichern eines Mappings in der Datenbank.
    Wird von n8n aufgerufen.
    
    Erwarteter JSON-Payload:
    {
       "job_id": "<Job-ID>",
       "original": "<Originaltext>",
       "hash": "<Hash-Wert>",
       "prefixes_id": <Prefix-ID>
    }
    """
    data = request.get_json()
    logging.debug(f"Eingehende Mapping-Daten: {data}")
    job_id = data.get("job_id")
    original = data.get("original")
    hash_value = data.get("hash")
    prefix_id = data.get("prefixes_id")
    
    if not all([job_id, original, hash_value, prefix_id]):
        logging.error("Ungültiger Mapping-Payload: Pflichtfelder fehlen")
        return jsonify({"msg": "Invalid mapping payload"}), 400
    
    # Mapping in der Datenbank speichern
    success = anymize_service.store_mapping(job_id, original, hash_value, prefix_id)
    
    if not success:
        return jsonify({"msg": "Fehler beim Speichern des Mappings"}), 500
    
    return jsonify({
        "msg": "Mapping erfolgreich gespeichert",
        "job_id": job_id
    }), 200

@app.route('/update-job', methods=['POST'])
def update_job():
    """
    Endpunkt zum Aktualisieren des output_text eines Jobs.
    Wird von n8n aufgerufen.
    
    Erwarteter JSON-Payload:
    {
       "job_id": "<Job-ID>",
       "output_text": "<Anonymisierter Text>"
    }
    """
    data = request.get_json()
    logging.debug(f"Eingehende Job-Update-Daten: {data}")
    job_id = data.get("job_id")
    output_text = data.get("output_text")
    
    if not job_id or output_text is None:
        logging.error("Ungültiger Job-Update-Payload: job_id oder output_text fehlt")
        return jsonify({"msg": "Invalid job update payload"}), 400
    
    # Job in der Datenbank aktualisieren
    success = anymize_service.update_job_output(job_id, output_text)
    
    if not success:
        return jsonify({"msg": "Fehler beim Aktualisieren des Jobs"}), 500
    
    return jsonify({
        "msg": "Job erfolgreich aktualisiert",
        "job_id": job_id
    }), 200

if __name__ == '__main__':
    app.run(port=5001, debug=True)
