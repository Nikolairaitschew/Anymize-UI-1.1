
# n8n Workflow für Anymize

Dieses Dokument beschreibt, wie der n8n-Workflow für die Anymize-Anwendung eingerichtet werden sollte.

## Workflow-Übersicht

Der Workflow besteht aus folgenden Schritten:

1. Empfangen von Daten über einen Webhook
2. Identifizieren sensibler Daten mit einem LLM
3. Verarbeiten der LLM-Antwort und Erstellen von Mappings
4. Speichern der Mappings in der Datenbank
5. Anonymisieren des Textes
6. Aktualisieren des Jobs in der Datenbank
7. (Optional) Senden des anonymisierten Textes an ein externes LLM
8. (Optional) De-anonymisieren der LLM-Antwort

## Detaillierte Einrichtung

### 1. Webhook Node

- **Name**: "Webhook"
- **Authentication**: None
- **HTTP Method**: POST
- **Path**: f292a87b-b6c9-48c3-9fe6-31d1134adaac (oder einen eigenen Pfad)
- **Response Mode**: Last Node

### 2. AI Agent Node

- **Name**: "AI Agent"
- **Connection**: Wähle deine LLM-Verbindung (z.B. OpenAI, Claude)
- **Prompt**:
  ```
  Identifiziere ALLE sensiblen Daten im folgenden Text. Berücksichtige dabei folgende Kategorien:
  
  1. Personenbezogene Daten: Namen, Adressen, Telefonnummern, E-Mail-Adressen, Geburtsdaten, Personalausweis- oder Passnummern, Sozialversicherungsnummern, etc.
  2. Finanzielle Daten: Bankverbindungen, Kreditkartennummern, Kontonummern, Steuer-IDs, etc.
  3. Medizinische Daten: Diagnosen, Behandlungen, Medikamente, Patientennummern, etc.
  4. Berufliche Daten: Arbeitgeber, Position, Gehalt, etc.
  5. Sonstige sensible Daten: Passwörter, Zugangsdaten, vertrauliche Geschäftsinformationen, etc.
  
  Sei gründlich und identifiziere ALLE sensiblen Informationen, unabhängig vom Kontext. Achte besonders auf:
  - Vollständige Namen (Vor- und Nachnamen)
  - Vollständige Adressen oder Adressteile
  - Telefonnummern in beliebigen Formaten
  - E-Mail-Adressen
  - Datumsangaben, die persönliche Ereignisse betreffen könnten
  - Kennnummern jeglicher Art
  - Finanzielle Beträge und Bankdaten
  
  Formatiere die Ausgabe als JSON-Array mit Objekten, die "type" und "value" enthalten:
  [
      {"type": "Vorname", "value": "Max"},
      {"type": "Nachname", "value": "Mustermann"},
      {"type": "Adresse", "value": "Musterstraße 123, 12345 Berlin"},
      {"type": "E-Mail", "value": "max.mustermann@example.com"},
      {"type": "Telefonnummer", "value": "+49 30 123456789"},
      {"type": "Kundennummer", "value": "K-12345-MM"},
      {"type": "IBAN", "value": "DE12 3456 7890 1234 5678 90"}
  ]
  
  Text: {{$json["text"]}}
  ```
- **Model**: Wähle ein geeignetes Modell (z.B. gpt-3.5-turbo, claude-3-sonnet)
- **Temperature**: 0.2 (niedrig für präzise Ergebnisse)

### 3. Function Node: "Process LLM Response"

- **Name**: "Process LLM Response"
- **Code**:
  ```javascript
  // Extrahiere JSON aus der LLM-Antwort
  const response = $input.item.json.response || $input.item.json.output || "";
  const jsonMatch = response.match(/\[\s*\{.*\}\s*\]/s);
  
  if (!jsonMatch) {
    return { 
      success: false, 
      error: "Kein JSON in der LLM-Antwort gefunden",
      job_id: $input.item.json.job_id
    };
  }
  
  try {
    const sensitiveData = JSON.parse(jsonMatch[0]);
    const jobId = $input.item.json.job_id;
    
    // Funktion zum Generieren eines Prefix-Codes
    function generatePrefixCode(name) {
      const words = name.split(/\s+/);
      if (words.length === 1) {
        return name.substring(0, 3).toUpperCase();
      } else {
        return words.map(word => word.charAt(0).toUpperCase()).join('');
      }
    }
    
    // Funktion zum Generieren eines Hash-Werts
    function generateHash(text, prefix) {
      const crypto = require('crypto');
      const hash = crypto.createHash('md5').update(text).digest('hex').substring(0, 8);
      return `${prefix}_${hash}`;
    }
    
    // HTTP-Request an NocoDB senden, um alle verfügbaren Prefixes zu laden
    const options = {
      method: 'GET',
      url: 'https://nocodb-s9q9e-u27285.vm.elestio.app/api/v2/tables/mhv1s5y9wgzyi9n/records',
      headers: {
        'Content-Type': 'application/json',
        'xc-auth': 'wlf8BFp6fkR-NNoL9TZQ91sJ8msFwB_kWhXqPyTZ'
      }
    };
    
    // Prefixes aus der Datenbank laden oder Fallback-Werte verwenden
    let prefixes = {};
    try {
      const prefixResponse = await $http.request(options);
      if (prefixResponse.statusCode === 200 && prefixResponse.body && prefixResponse.body.list) {
        prefixResponse.body.list.forEach(item => {
          prefixes[item.name.toLowerCase()] = { id: item.Id, prefix: item.prefix };
        });
      }
    } catch (error) {
      console.log('Fehler beim Laden der Prefixes:', error.message);
      // Fallback-Prefixes verwenden
      prefixes = {
        "vorname": { id: 1, prefix: "FN" },
        "nachname": { id: 2, prefix: "LN" },
        "adresse": { id: 3, prefix: "ADR" },
        "e-mail": { id: 4, prefix: "EM" },
        "telefonnummer": { id: 5, prefix: "PH" },
        "kundennummer": { id: 6, prefix: "KN" },
        "iban": { id: 7, prefix: "IB" },
        "geburtsdatum": { id: 8, prefix: "GD" },
        "personalausweis": { id: 9, prefix: "PA" },
        "steuernummer": { id: 10, prefix: "ST" }
      };
    }
    
    // Erstelle Mappings
    const mappings = [];
    
    // Funktion zum Erstellen eines neuen Prefix in NocoDB
    async function createNewPrefix(name) {
      const prefixCode = generatePrefixCode(name);
      
      try {
        const createOptions = {
          method: 'POST',
          url: 'https://nocodb-s9q9e-u27285.vm.elestio.app/api/v2/tables/mhv1s5y9wgzyi9n/records',
          headers: {
            'Content-Type': 'application/json',
            'xc-auth': 'wlf8BFp6fkR-NNoL9TZQ91sJ8msFwB_kWhXqPyTZ'
          },
          body: {
            name: name,
            prefix: prefixCode
          }
        };
        
        const response = await $http.request(createOptions);
        
        if (response.statusCode === 200 && response.body) {
          console.log(`Neuer Prefix erstellt: ${name} (${prefixCode}), ID: ${response.body.Id}`);
          return { id: response.body.Id, prefix: prefixCode };
        } else {
          console.log(`Fehler beim Erstellen des Prefix: ${response.statusCode}`);
          return { id: 999, prefix: prefixCode }; // Fallback
        }
      } catch (error) {
        console.log(`Fehler beim Erstellen des Prefix: ${error.message}`);
        return { id: 999, prefix: prefixCode }; // Fallback
      }
    }
    
    // Verarbeite jedes sensible Datum
    for (const item of sensitiveData) {
      const dataType = item.type.trim().toLowerCase();
      const value = item.value.trim();
      
      if (!value) continue; // Leere Werte überspringen
      
      // Prefix finden oder erstellen
      let prefixId, prefixCode;
      
      if (prefixes[dataType]) {
        prefixId = prefixes[dataType].id;
        prefixCode = prefixes[dataType].prefix;
      } else {
        // Neuen Prefix erstellen
        const newPrefix = await createNewPrefix(item.type);
        prefixId = newPrefix.id;
        prefixCode = newPrefix.prefix;
        
        // Prefix zur lokalen Liste hinzufügen
        prefixes[dataType] = { id: prefixId, prefix: prefixCode };
      }
      
      // Hash generieren
      const hash = generateHash(value, prefixCode);
      
      // Mapping hinzufügen
      mappings.push({
        original: value,
        hash: hash,
        prefixes_id: prefixId,
        type: item.type,
        job_id: jobId
      });
    }
    
    return { 
      success: true, 
      job_id: jobId, 
      mappings: mappings,
      text: $input.item.json.text
    };
  } catch (error) {
    return { 
      success: false, 
      error: `Fehler beim Verarbeiten der LLM-Antwort: ${error.message}`,
      job_id: $input.item.json.job_id
    };
  }
  ```

### 4. HTTP Request Node: "Store Mappings"

- **Name**: "Store Mappings"
- **URL**: http://localhost:5001/store-mapping
- **Method**: POST
- **Authentication**: None
- **Send Binary Data**: No
- **Body Content Type**: JSON
- **JSON/RAW Parameters**:
  ```json
  {
    "job_id": "={{$json.job_id}}",
    "original": "={{$json.mappings[0].original}}",
    "hash": "={{$json.mappings[0].hash}}",
    "prefixes_id": "={{$json.mappings[0].prefixes_id}}"
  }
  ```
- **Options**: Execute Once for Each Item

Hinweis: Für jeden Eintrag in `mappings` wird ein separater Request gesendet. In n8n kannst du die Option "Execute Once for Each Item" verwenden und den Index `[0]` durch `[item.index]` ersetzen.

### 5. Function Node: "Anonymize Text"

- **Name**: "Anonymize Text"
- **Code**:
  ```javascript
  const text = $input.item.json.text;
  const mappings = $input.item.json.mappings;
  
  if (!text || !mappings || !Array.isArray(mappings)) {
    return { 
      success: false, 
      error: "Ungültige Eingabedaten",
      job_id: $input.item.json.job_id
    };
  }
  
  try {
    // Sortiere Mappings nach Länge (absteigend), um Teilstrings korrekt zu ersetzen
    const sortedMappings = [...mappings].sort((a, b) => 
      (b.original ? b.original.length : 0) - (a.original ? a.original.length : 0)
    );
    
    let anonymizedText = text;
    for (const mapping of sortedMappings) {
      if (mapping.original && mapping.hash) {
        // Escape special regex characters in the original text
        const escapedOriginal = mapping.original.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(escapedOriginal, 'g');
        anonymizedText = anonymizedText.replace(regex, mapping.hash);
      }
    }
    
    return { 
      success: true, 
      job_id: $input.item.json.job_id, 
      anonymized_text: anonymizedText,
      mappings: mappings  // Weitergeben für spätere De-Anonymisierung
    };
  } catch (error) {
    return { 
      success: false, 
      error: `Fehler beim Anonymisieren: ${error.message}`,
      job_id: $input.item.json.job_id
    };
  }
  ```

### 6. HTTP Request Node: "Update Job"

- **Name**: "Update Job"
- **URL**: http://localhost:5001/update-job
- **Method**: POST
- **Authentication**: None
- **Send Binary Data**: No
- **Body Content Type**: JSON
- **JSON/RAW Parameters**:
  ```json
  {
    "job_id": "={{$json.job_id}}",
    "output_text": "={{$json.anonymized_text}}"
  }
  ```

### 7. OpenRouter Chat Node (Optional)

- **Name**: "OpenRouter Chat"
- **Authentication**: API Key
- **API Key**: Dein OpenRouter API-Key
- **Prompt**: 
  ```
  {{$json.anonymized_text}}
  
  Bitte analysiere diesen Text und beantworte folgende Fragen:
  1. Worum geht es in dem Text?
  2. Welche wichtigen Informationen enthält er?
  3. Gibt es rechtliche Bedenken oder Risiken?
  ```
- **Model**: claude-3-opus-20240229 (oder ein anderes Modell)
- **Temperature**: 0.7

### 8. Function Node: "De-Anonymize Response" (Optional)

- **Name**: "De-Anonymize Response"
- **Code**:
  ```javascript
  const anonymizedResponse = $input.item.json.response || "";
  const mappings = $input.item.json.mappings || [];
  
  if (!anonymizedResponse || !mappings || !Array.isArray(mappings)) {
    return { 
      success: false, 
      error: "Ungültige Eingabedaten für De-Anonymisierung",
      job_id: $input.item.json.job_id
    };
  }
  
  try {
    let deanonymizedResponse = anonymizedResponse;
    
    for (const mapping of mappings) {
      if (mapping.hash && mapping.original) {
        // Escape special regex characters in the hash
        const escapedHash = mapping.hash.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(escapedHash, 'g');
        deanonymizedResponse = deanonymizedResponse.replace(regex, mapping.original);
      }
    }
    
    return { 
      success: true, 
      job_id: $input.item.json.job_id, 
      deanonymized_response: deanonymizedResponse
    };
  } catch (error) {
    return { 
      success: false, 
      error: `Fehler beim De-Anonymisieren: ${error.message}`,
      job_id: $input.item.json.job_id
    };
  }
  ```

## Verbindungen zwischen den Nodes

1. Webhook → AI Agent
2. AI Agent → Process LLM Response
3. Process LLM Response → Store Mappings
4. Store Mappings → Anonymize Text
5. Anonymize Text → Update Job
6. Update Job → OpenRouter Chat (optional)
7. OpenRouter Chat → De-Anonymize Response (optional)

## Hinweise zur Anpassung

- **Lokale Entwicklung**: Wenn du lokal entwickelst, musst du möglicherweise einen Tunnel-Dienst wie ngrok verwenden, damit n8n auf deinen lokalen Process-Service zugreifen kann.
- **Fehlerbehandlung**: Füge Fehlerbehandlungs-Nodes hinzu, um mit Fehlern umzugehen.
- **Sicherheit**: Stelle sicher, dass deine API-Keys und Zugangsdaten sicher gespeichert sind.
- **Skalierung**: Für größere Textmengen oder höhere Last solltest du die Verarbeitung optimieren.

## Testen des Workflows

1. Starte den Process-Service: `python process_app.py`
2. Starte den Upload-Service: `python upload_app.py`
3. Aktiviere den n8n-Workflow
4. Lade eine Datei über die Web-Oberfläche hoch
5. Überprüfe die Logs beider Services und die n8n-Ausführungsprotokolle
