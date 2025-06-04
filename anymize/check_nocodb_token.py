#!/usr/bin/env python3

import requests
import json
import sys
from config_shared import (
    NOCODB_BASE,
    NOCODB_TOKEN,
    HEADERS,
    TABLE_JOB
)

# Endpunkt für einfachen Test (Abrufen der Tabellenliste)
TEST_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_JOB}/records?limit=1"

# Korrekte Header-Variante laut NocoDB Dokumentation
HEADER_VARIANTS = [
    {
        "name": "xc-token im Header (Offiziell dokumentiert)",
        "headers": {
            "Content-Type": "application/json",
            "xc-token": NOCODB_TOKEN
        }
    },
    {
        "name": "xc-token im Header ohne Content-Type",
        "headers": {
            "xc-token": NOCODB_TOKEN
        }
    },
    {
        "name": "xc-token in Kleinbuchstaben",
        "headers": {
            "Content-Type": "application/json",
            "xc-token": NOCODB_TOKEN.lower()
        }
    }
]

# Funktion zum Ausführen des Tests
def test_token_variants():
    print(f"Testing NoCodeDB Token: {NOCODB_TOKEN}")
    print(f"Testing URL: {TEST_ENDPOINT}")
    print("-" * 80)

    for i, variant in enumerate(HEADER_VARIANTS):
        print(f"\nVariante {i+1}: {variant['name']}")
        print(f"Headers: {json.dumps(variant['headers'], indent=2)}")
        
        try:
            # Parameter ergänzen, falls vorhanden
            params = variant.get('params', {})
            if params:
                print(f"Params: {json.dumps(params, indent=2)}")
                
            # Anfrage senden
            response = requests.get(TEST_ENDPOINT, headers=variant['headers'], params=params, timeout=10)
            
            # Ergebnisse ausgeben
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {json.dumps(dict(response.headers), indent=2)}")
            
            if response.status_code == 200:
                print("✅ ERFOLG! Diese Header-Variante funktioniert!")
                try:
                    # Versuche, die Antwort als JSON zu parsen
                    data = response.json()
                    print(f"Daten erhalten: {len(data.get('list', [])) if isinstance(data, dict) and 'list' in data else 'Kein list-Feld gefunden'} Einträge")
                except Exception as e:
                    print(f"Warnung: Konnte Antwort nicht als JSON parsen: {str(e)}")
            else:
                print(f"❌ FEHLER: Status {response.status_code}")
                try:
                    print(f"Response Body: {response.text[:500]}...")
                except:
                    print(f"Response Body: {response.text}")
                
        except Exception as e:
            print(f"❌ FEHLER bei der Anfrage: {str(e)}")
        
        print("-" * 80)

if __name__ == "__main__":
    test_token_variants()
    
    # Direkter Test auf die Basis-URL, um zu sehen, ob der Server überhaupt erreichbar ist
    print("\nTeste Basis-URL...")
    try:
        response = requests.get(NOCODB_BASE, timeout=10)
        print(f"Status Code für {NOCODB_BASE}: {response.status_code}")
    except Exception as e:
        print(f"Fehler beim Zugriff auf {NOCODB_BASE}: {str(e)}")
