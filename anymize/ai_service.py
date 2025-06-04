import os
import re
import uuid
import hashlib
import requests
import logging
import json
from config_shared import (
    TEST_WEBHOOK_URL as N8N_WEBHOOK_URL,
    NOCODB_BASE,
    NOCODB_TOKEN,
    HEADERS,
    PREFIX_LIST_ENDPOINT,
    STRING_CREATE_ENDPOINT,
    JOB_UPDATE_ENDPOINT
)

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AnymizeService:
    def __init__(self):
        self.prefixes = self._load_prefixes()
        logger.info(f"Anymize Service initialisiert")
        logger.info(f"Geladene Prefixes: {len(self.prefixes)}")

    def _load_prefixes(self):
        """Lädt alle verfügbaren Prefixes aus der NocoDB-Datenbank"""
        try:
            response = requests.get(PREFIX_LIST_ENDPOINT, headers=HEADERS)
            if response.status_code == 200:
                prefix_data = response.json()
                # Erstelle ein Dictionary mit name als Schlüssel und einem Objekt mit id und prefix als Wert
                prefixes = {
                    item["name"].lower(): {"id": item["Id"], "prefix": item["prefix"]}
                    for item in prefix_data.get("list", [])
                }
                logger.debug(f"Geladene Prefixes: {prefixes}")
                return prefixes
            else:
                logger.error(f"Fehler beim Laden der Prefixes: {response.status_code} {response.text}")
                return {}
        except Exception as e:
            logger.exception("Fehler beim Laden der Prefixes:")
            return {}

    def process_file(self, job_id, text, callback_url=None):
        """
        Sendet den Text an n8n zur Verarbeitung.
        
        Args:
            job_id: Die ID des Jobs in der Datenbank
            text: Der zu verarbeitende Text
            callback_url: Optional, URL für Callback nach Verarbeitung
        
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        try:
            # Payload für n8n vorbereiten - nur den Text senden
            payload = {
                "text": text
            }
            
            # Callback-URL hinzufügen, falls vorhanden
            if callback_url:
                payload["callback_url"] = callback_url
            
            # Custom Headers mit job_id
            custom_headers = {
                "Content-Type": "application/json",
                "job_id": str(job_id)
            }
            
            logger.debug(f"Sende Text an n8n mit job_id {job_id} im Header")
            logger.debug(f"Payload: {payload}")
            
            # Anfrage an n8n senden
            response = requests.post(N8N_WEBHOOK_URL, json=payload, headers=custom_headers)
            
            if response.status_code != 200:
                logger.error(f"Fehler bei der n8n-Anfrage: {response.status_code} {response.text}")
                return False
            
            logger.info(f"Text erfolgreich an n8n gesendet, Job-ID: {job_id}")
            return True
            
        except Exception as e:
            logger.exception(f"Fehler beim Senden des Texts an n8n:")
            return False

    def store_mapping(self, job_id, original, hash_value, prefix_id):
        """
        Speichert ein Mapping in der Datenbank.
        
        Args:
            job_id: Die ID des Jobs
            original: Der Originaltext
            hash_value: Der Hash-Wert
            prefix_id: Die ID des Prefix
            
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        try:
            mapping_payload = {
                "original": original,
                "hash": hash_value,
                "prefixes_id": prefix_id,
                "job_id": job_id
            }
            
            logger.debug(f"Speichere Mapping in NocoDB: {mapping_payload}")
            
            response = requests.post(STRING_CREATE_ENDPOINT, json=mapping_payload, headers=HEADERS)
            
            if response.status_code != 200:
                logger.error(f"Fehler beim Speichern des Mappings: {response.status_code} {response.text}")
                return False
                
            logger.debug(f"Mapping erfolgreich gespeichert: {original} -> {hash_value}")
            return True
            
        except Exception as e:
            logger.exception(f"Fehler beim Speichern des Mappings:")
            return False

    def update_job_output(self, job_id, output_text):
        """
        Aktualisiert den output_text eines Jobs in der Datenbank.
        
        Args:
            job_id: Die ID des Jobs
            output_text: Der neue output_text
            
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        try:
            update_payload = {
                "Id": job_id,
                "output_text": output_text
            }
            
            logger.debug(f"Aktualisiere Job in NocoDB: {update_payload}")
            
            response = requests.patch(JOB_UPDATE_ENDPOINT, json=update_payload, headers=HEADERS)
            
            if response.status_code != 200:
                logger.error(f"Fehler beim Aktualisieren des Jobs: {response.status_code} {response.text}")
                return False
                
            logger.info(f"Job {job_id} erfolgreich aktualisiert")
            return True
            
        except Exception as e:
            logger.exception(f"Fehler beim Aktualisieren des Jobs:")
            return False

# Beispiel für die Verwendung
if __name__ == "__main__":
    # Service initialisieren
    service = AnymizeService()
    
    # Beispiel für die Verarbeitung eines Texts
    job_id = 1  # Beispiel-Job-ID
    sample_text = """
    Sehr geehrter Herr Mustermann,
    
    vielen Dank für Ihre Anfrage vom 15.03.2023. Wie besprochen senden wir Ihnen hiermit die gewünschten Unterlagen zu.
    
    Ihre Kundennummer lautet: K-12345-MM
    
    Bei Rückfragen erreichen Sie uns unter:
    Tel: +49 30 123456789
    E-Mail: info@musterfirma.de
    
    Mit freundlichen Grüßen,
    Max Mustermann
    Musterstraße 123
    12345 Berlin
    """
    
    # Text an n8n senden
    success = service.process_file(job_id, sample_text)
    print(f"Text an n8n gesendet: {'Erfolgreich' if success else 'Fehlgeschlagen'}")
