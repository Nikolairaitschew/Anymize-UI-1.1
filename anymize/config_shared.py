import requests
import logging
import uuid
import re
import time
import os

# API-only n8n webhook URL for text and id
API_N8N_WEBHOOK_URL = 'https://n8n-96aou-u27285.vm.elestio.app/webhook/631b6585-1382-4906-a272-21481d311388'

# OCR webhook URL for document processing
OCR_WEBHOOK_URL = 'https://n8n-96aou-u27285.vm.elestio.app/webhook/9b2b5bf2-37d2-4c1a-ae54-81e34b122463'

# Further anonymization webhook URL (for enhanced_result.html)
FURTHER_ANONYMIZATION_WEBHOOK_URL = 'https://n8n-96aou-u27285.vm.elestio.app/webhook/8a820add-6f5b-495f-870e-cfc95e469a82'

# Raw text processing webhook URL (for text input feature)
RAW_TEXT_WEBHOOK_URL = 'https://n8n-96aou-u27285.vm.elestio.app/webhook/28e7e980-467b-49d3-aed6-c90c1ddb6273'

# Authentication webhook URL (for email verification)
AUTH_EMAIL_WEBHOOK_URL = 'https://n8n-96aou-u27285.vm.elestio.app/webhook/191e0984-2c5d-46e8-b999-810100f4ee77'

# Test webhook URL (for testing purposes)
TEST_WEBHOOK_URL = 'https://n8n-96aou-u27285.vm.elestio.app/webhook-test/bb09cd27-d7fb-4184-bafe-9ababf7cfee9'

# --- Konfiguration ---
# NocoDB connection settings with proper redirect handling
NOCODB_BASE = os.environ.get('NOCODB_BASE', 'https://nocodb-s9q9e-u27285.vm.elestio.app/api/v2')

# API Token - SECURITY WARNING: For production, always use environment variable!
DEFAULT_TOKEN = 'wlf8BFp6fkR-NNoL9TZQ91sJ8msFwB_kWhXqPyTZ'
NOCODB_TOKEN = os.environ.get('NOCODB_TOKEN', DEFAULT_TOKEN)

# Security warning for development token usage
if NOCODB_TOKEN == DEFAULT_TOKEN:
    logging.warning("  SECURITY WARNING: Using default NOCODB_TOKEN! Set NOCODB_TOKEN environment variable for production!")
    logging.warning("  To set: export NOCODB_TOKEN='your-secure-token-here'")

HEADERS = {
    'accept': 'application/json',
    'xc-token': NOCODB_TOKEN,  # API v2 uses xc-token, not xc-auth
    'Content-Type': 'application/json'
}

# NocoDB Table IDs
TABLE_JOB = 'mun2eil6g6a3i25'
TABLE_USER = 'mj5idkixdjmzgex'
TABLE_STRING = 'm1ayzzk79sja5h3'
TABLE_PREFIX = 'mhv1s5y9wgzyi9n'
TABLE_CHAT_MEMORY = 'm5xltkc7av6zfer'

# Legacy support - points to TABLE_JOB
TABLE_ID = TABLE_JOB

# Link Field IDs from NocoDB relations
LINK_FIELD_JOB_TO_USER = 'cp2ruywux9sa86i'  # Link field in job table pointing to user
LINK_FIELD_USER_TO_JOBS = 'crdl8yf2o9h4evm'  # Link field in user table pointing to jobs

# Job-related API Endpoints
JOB_CREATE_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_JOB}/records"
JOB_GET_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_JOB}/records"
JOB_UPDATE_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_JOB}/records"

# Link endpoints for job-user relations
JOB_LINK_USER_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_JOB}/links/{LINK_FIELD_JOB_TO_USER}/records"
USER_LINK_JOB_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_USER}/links/{LINK_FIELD_USER_TO_JOBS}/records"

# Other table endpoints
USER_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_USER}/records"
USER_LIST_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_USER}/records"
USER_UPDATE_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_USER}/records"
STRING_CREATE_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_STRING}/records"
PREFIX_LIST_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_PREFIX}/records"
CHAT_MEMORY_ENDPOINT = f"{NOCODB_BASE}/tables/{TABLE_CHAT_MEMORY}/records"

# API Endpoints
N8N_WEBHOOK_URL = os.environ.get('N8N_WEBHOOK', 'https://n8n-96aou-u27285.vm.elestio.app/webhook/bb09cd27-d7fb-4184-bafe-9ababf7cfee9')

# Memory cache for job lookups (to reduce API calls to NocoDB)
_job_cache = {}
_job_cache_timestamps = {}
CACHE_TTL = 5  # seconds

def get_job(job_id, log_request=True):
    """
    Get job data from NocoDB - with fallbacks and caching.
    First tries direct lookup by job_id in 'Id' field,
    then API filter by job_id in 'internal_ID' field.

    Args:
        job_id: The job ID (can be string 'job_id' or numeric Id)
        log_request: Whether to log the request (default: True)

    Returns:
        dict: Job data or None if not found
    """
    # Check for invalid inputs to prevent errors
    job_id_str = str(job_id).strip() if job_id else ''
    if job_id_str == '{{ job_id }}' or (isinstance(job_id, str) and not job_id.strip()):
        return None

    # Check cache for recent results
    if job_id_str in _job_cache:
        cache_time = _job_cache_timestamps.get(job_id_str, 0)
        if time.time() - cache_time < CACHE_TTL:
            if log_request:
                logging.info(f"[get_job] Cache hit for {job_id_str}")
            return _job_cache[job_id_str]

    # Is this a numeric ID (primary key)?
    is_numeric = isinstance(job_id, int) or (isinstance(job_id, str) and job_id.isdigit())

    # 1. Try with direct ID lookup if numeric
    if is_numeric:
        try:
            if log_request:
                logging.info(f"[get_job] Trying direct lookup for ID {job_id}")
            endpoint = f"{JOB_GET_ENDPOINT}/{job_id}"
            resp = requests.get(endpoint, headers=HEADERS, allow_redirects=True)
            if resp.status_code == 200:
                resp_json = resp.json()
                # Handle NocoDB v2 nested 'data'
                record = resp_json.get('data', resp_json)
                _job_cache[job_id_str] = record
                _job_cache_timestamps[job_id_str] = time.time()
                return record
            else:
                if log_request:
                    logging.error(f"[get_job] Direct lookup failed: {resp.status_code}, response: {resp.text[:200]}")
        except Exception as e:
            if log_request:
                logging.error(f"[get_job] Direct lookup exception: {e}")

    # 2. Try with filter by internal_ID field
    try:
        if log_request:
            logging.info(f"[get_job] Trying filter by internal_ID={job_id_str}")

        # In API v2, the where filter uses a different format
        where_param = f"(internal_ID,eq,{job_id_str})"
        params = {
            "where": where_param,
            "limit": 1
        }

        resp = requests.get(
            JOB_GET_ENDPOINT,
            headers=HEADERS,
            params=params,
            allow_redirects=True
        )

        if resp.status_code == 200:
            resp_json = resp.json()
            # Handle NocoDB v2 wrapper: parse 'data' then 'list'
            payload = resp_json.get('data', resp_json)
            if isinstance(payload, dict) and 'list' in payload:
                records = payload.get('list', [])
            elif isinstance(payload, list):
                records = payload
            else:
                records = resp_json.get('list', [])
            if records:
                record = records[0]
                _job_cache[job_id_str] = record
                _job_cache_timestamps[job_id_str] = time.time()
                return record
        else:
            if log_request:
                logging.error(f"[get_job] Filter lookup failed: {resp.status_code}, response: {resp.text[:200]}")
    except Exception as e:
        if log_request:
            logging.error(f"[get_job] Filter lookup exception: {e}")

    # No fallback to full table scan as it's inefficient with a large database
    # If both direct lookup and filter failed, return None
    return None

def link_job_to_user(job_id, user_id):
    """
    Link a job to a user in NocoDB.
    
    Args:
        job_id: The job ID (numeric ID in NocoDB)
        user_id: The user ID (numeric ID in NocoDB)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not job_id or not user_id:
        logging.warning(f"[link_job_to_user] Missing job_id ({job_id}) or user_id ({user_id})")
        return False
        
    try:
        # Build the endpoint URL
        endpoint = f"{JOB_LINK_USER_ENDPOINT}/{job_id}"
        
        # Payload is an array of user IDs to link
        payload = [{"Id": user_id}]
        
        logging.info(f"[link_job_to_user] Linking job {job_id} to user {user_id}")
        
        # Make the request
        resp = requests.post(endpoint, json=payload, headers=HEADERS, allow_redirects=True)
        resp.raise_for_status()
        
        logging.info(f"[link_job_to_user] Successfully linked job {job_id} to user {user_id}")
        return True
        
    except Exception as e:
        logging.error(f"[link_job_to_user] Failed to link job {job_id} to user {user_id}: {e}")
        return False

def check_job_user_link(job_id, user_id):
    """
    Check if a job is linked to a specific user.
    
    Args:
        job_id: The job ID (numeric ID in NocoDB)
        user_id: The user ID (numeric ID in NocoDB)
        
    Returns:
        bool: True if job is linked to user, False otherwise
    """
    if not job_id or not user_id:
        logging.warning(f"[check_job_user_link] Missing job_id ({job_id}) or user_id ({user_id})")
        return False
        
    try:
        # Build the endpoint URL to check links for this job
        endpoint = f"{JOB_LINK_USER_ENDPOINT}/{job_id}"
        
        logging.info(f"[check_job_user_link] Checking if job {job_id} is linked to user {user_id}")
        
        # Get all linked users for this job
        resp = requests.get(endpoint, headers=HEADERS, allow_redirects=True)
        resp.raise_for_status()
        
        data = resp.json()
        logging.info(f"[check_job_user_link] API Response: {data}")
        
        # The API might return different formats - handle both cases
        # Case 1: Direct user object (single linked user)
        if isinstance(data, dict) and data.get('Id'):
            linked_user_id = str(data.get('Id'))
            if linked_user_id == str(user_id):
                logging.info(f"[check_job_user_link] Job {job_id} is linked to user {user_id}")
                return True
                
        # Case 2: List of linked records
        elif isinstance(data, dict) and 'list' in data:
            linked_records = data.get('list', [])
            for record in linked_records:
                record_id = record.get('Id')
                logging.info(f"[check_job_user_link] Comparing record ID {record_id} (type: {type(record_id)}) with user_id {user_id} (type: {type(user_id)})")
                # Convert both to string for comparison to handle type mismatches
                if str(record_id) == str(user_id):
                    logging.info(f"[check_job_user_link] Job {job_id} is linked to user {user_id}")
                    return True
                    
        # Case 3: Direct list of records
        elif isinstance(data, list):
            for record in data:
                record_id = record.get('Id')
                if str(record_id) == str(user_id):
                    logging.info(f"[check_job_user_link] Job {job_id} is linked to user {user_id}")
                    return True
        
        logging.info(f"[check_job_user_link] Job {job_id} is NOT linked to user {user_id}")
        return False
        
    except Exception as e:
        logging.error(f"[check_job_user_link] Failed to check link for job {job_id} and user {user_id}: {e}")
        return False

def replace_prefixes_with_labels(text, lang):
    """
    Simply returns the text without any replacements.
    This function is kept for compatibility with existing code.
    """
    return text

def detect_language_and_get_prompt(text):
    """
    Detect language of text and return a system prompt and language code.
    """
    try:
        lang = detect(text)
        if lang not in SYSTEM_PROMPTS:
            lang = 'en'
    except Exception:
        lang = 'en'
    prompt = SYSTEM_PROMPTS.get(lang, SYSTEM_PROMPTS['en'])
    return prompt, lang

SYSTEM_PROMPTS = {
    'de': 'SYSTEMINSTRUKTION: Du bist ein spezialisierter Assistent zur Verarbeitung anonymisierter Dokumente. WICHTIGSTE REGEL: Alle Platzhalter im Format {%{PREFIX-Hash}%} MÜSSEN UNVERÄNDERT bleiben und EXAKT als der jeweilige Wert behandelt werden. Beispiel: Wenn es {%{Vorname-a1b2}%} im Text gibt, dann benutze bei jeder Erwähnung genau diesen Platzhalter, ohne ihn zu verändern oder zu erklären. Ersetze den Platzhalter NIEMALS mit Ausdrücken wie "ein anonymisierter Name" oder Ähnlichem. Gib direkte, präzise Antworten und keine Metadaten über den Anonymisierungsprozess oder deine Funktionsweise. Behandle die Platzhalter als normale Entitäten entsprechend ihrem Präfix (z.B. Vorname = Person, Ort = Ortschaft usw.).',
    'en': 'SYSTEM INSTRUCTION: You are a specialized assistant for processing anonymized documents. MOST IMPORTANT RULE: All placeholders in the format {%{PREFIX-Hash}%} MUST remain UNCHANGED and be treated EXACTLY as the respective value. Example: If there is {%{FirstName-a1b2}%} in the text, use exactly this placeholder in every reference, without modifying or explaining it. NEVER replace the placeholder with expressions like "an anonymized name" or similar. Give direct, precise answers without metadata about the anonymization process or your operation. Treat the placeholders as normal entities according to their prefix (e.g., FirstName = person, Location = place, etc.).',
    'fr': 'INSTRUCTION SYSTÈME: Vous êtes un assistant spécialisé dans le traitement de documents anonymisés. RÈGLE LA PLUS IMPORTANTE: Tous les espaces réservés au format {%{PRÉFIXE-Hash}%} DOIVENT rester INCHANGÉS et être traités EXACTEMENT comme la valeur respective. Exemple: S\'il y a {%{Prénom-a1b2}%} dans le texte, utilisez exactement cet espace réservé dans chaque référence, sans le modifier ni l\'expliquer. NE REMPLACEZ JAMAIS l\'espace réservé par des expressions comme "un nom anonymisé" ou similaire. Donnez des réponses directes et précises sans métadonnées sur le processus d\'anonymisation ou votre fonctionnement. Traitez les espaces réservés comme des entités normales selon leur préfixe (ex. Prénom = personne, Lieu = endroit, etc.).',
    'es': 'INSTRUCCIÓN DEL SISTEMA: Eres un asistente especializado en el procesamiento de documentos anonimizados. REGLA MÁS IMPORTANTE: Todos los marcadores en el formato {%{PREFIJO-Hash}%} DEBEN permanecer SIN CAMBIOS y ser tratados EXACTAMENTE como el valor respectivo. Ejemplo: Si hay {%{Nombre-a1b2}%} en el texto, use exactamente este marcador en cada referencia, sin modificarlo ni explicarlo. NUNCA reemplace el marcador con expresiones como "un nombre anonimizado" o similar. Dé respuestas directas y precisas sin metadatos sobre el proceso de anonimización o su funcionamiento. Trate los marcadores como entidades normales según su prefijo (ej. Nombre = persona, Ubicación = lugar, etc.).',
    'it': 'ISTRUZIONE DI SISTEMA: Sei un assistente specializzato nell\'elaborazione di documenti anonimizzati. REGOLA PIÙ IMPORTANTE: Tutti i segnaposto nel formato {%{PREFISSO-Hash}%} DEVONO rimanere INVARIATI ed essere trattati ESATTAMENTE come il rispettivo valore. Esempio: Se c\'è {%{Nome-a1b2}%} nel testo, usa esattamente questo segnaposto in ogni riferimento, senza modificarlo o spiegarlo. NON sostituire MAI il segnaposto con espressioni come "un nome anonimizzato" o simili. Fornisci risposte dirette e precise senza metadati sul processo di anonimizzazione o sul tuo funzionamento. Tratta i segnaposto come entità normali secondo il loro prefisso (es. Nome = persona, Luogo = posto, ecc.).'
}

DOC_PROMPT_BEGIN = {
    'de': """KRITISCHE VERARBEITUNGSANWEISUNG: Dieses Dokument enthält rechtlich-anonymisierte Informationen, die einer besonderen Behandlung bedürfen.

PRÄZISE PLATZHALTERVERWENDUNG - ABSOLUTE PRIORITÄT:
Alle sensiblen Daten wurden durch spezielle Platzhalter im Format {%{Kategorie-Hash}%} ersetzt (z.B. {%{Vorname-xxxx}%}, {%{Nachname-xxxx}%}, {%{Adresse-xxxx}%}, {%{Unternehmensname-xxxx}%}). Diese Platzhalter MÜSSEN in deinen Antworten EXAKT wie im Originaldokument verwendet werden.

VERBINDLICHE REGELN:
1. PLATZHALTER-INTEGRITÄT:
   - Alle Platzhalter im Format {%{Typ-xxxx}%} sind als die tatsächlichen Werte zu behandeln, die sie ersetzen.
   - Diese Platzhalter MÜSSEN in ihrer EXAKTEN und VOLLSTÄNDIGEN Form wiedergegeben werden.
   - Die spezielle Formatierung {%{Typ-xxxx}%} muss bei jeder Verwendung präzise beibehalten werden.

2. VERBOT VON UMSCHREIBUNGEN:
   - Es ist STRENG UNTERSAGT, Platzhalter mit Ausdrücken wie "ein anonymisierter Name", "anonymisierte Firma", "Person X" oder ähnlichen Umschreibungen zu ersetzen.
   - Verwende NIEMALS Formulierungen, die darauf hinweisen, dass es sich um anonymisierte Daten handelt.

3. DIREKTES ANTWORTVERHALTEN:
   - Bei Fragen nach Namen, Adressen oder anderen anonymisierten Inhalten MUSST du stets den entsprechenden Platzhalter in seiner unveränderten Form verwenden.
   - Beispiel: Auf die Frage "Wer ist der Absender?" ist die korrekte Antwort "{%{person-abc123}%}" (falls so im Dokument angegeben).

4. RECHTLICHER KONTEXT:
Die Platzhalter SIND die eigentlichen Werte im Kontext dieses Dokuments. Ihre exakte Verwendung ist rechtlich relevant und ermöglicht die konsistente Verarbeitung der Inhalte unter Einhaltung der Datenschutzbestimmungen.""",

    'en': """CRITICAL PROCESSING INSTRUCTION: This document contains legally anonymized information that requires special handling.

PRECISE PLACEHOLDER USAGE - ABSOLUTE PRIORITY:
All sensitive data has been replaced with special placeholders in the format {%{Category-Hash}%} (e.g., {%{FirstName-xxxx}%}, {%{LastName-xxxx}%}, {%{Address-xxxx}%}, {%{CompanyName-xxxx}%}). These placeholders MUST be used in your answers EXACTLY as they appear in the original document.

BINDING RULES:
1. PLACEHOLDER INTEGRITY:
   - All placeholders in the format {%{Type-xxxx}%} are to be treated as the actual values they replace.
   - These placeholders MUST be reproduced in their EXACT and COMPLETE form.
   - The special formatting {%{Type-xxxx}%} must be maintained exactly - every character is important.

2. PROHIBITION OF CIRCUMLOCUTIONS:
   - It is STRICTLY FORBIDDEN to replace placeholders with expressions like "an anonymized name", "anonymized company", "Person X", or similar circumlocutions.
   - NEVER use formulations that indicate these are anonymized data.

3. DIRECT RESPONSE BEHAVIOR:
   - When asked about names, addresses, or other anonymized content, you MUST always use the corresponding placeholder in its unchanged form.
   - Example: To the question "Who is the sender?", the correct answer is "{%{FirstName-abc123}%}" (if stated as such in the document).

4. LEGAL CONTEXT:
The placeholders ARE the actual values in the context of this document. Their exact usage is legally relevant and enables consistent processing of the content while complying with data protection regulations.""",

    'fr': """INSTRUCTION DE TRAITEMENT CRITIQUE: Ce document contient des informations légalement anonymisées qui nécessitent une manipulation spéciale.

UTILISATION PRÉCISE DES ESPACES RÉSERVÉS - PRIORITÉ ABSOLUE:
Toutes les données sensibles ont été remplacées par des espaces réservés spéciaux au format {%{Catégorie-Hash}%} (par exemple, {%{Prénom-xxxx}%}, {%{Nom-xxxx}%}, {%{Adresse-xxxx}%}, {%{NomEntreprise-xxxx}%}). Ces espaces réservés DOIVENT être utilisés dans vos réponses EXACTEMENT comme ils apparaissent dans le document original.

RÈGLES CONTRAIGNANTES:
1. INTÉGRITÉ DES ESPACES RÉSERVÉS:
   - Tous les espaces réservés au format {%{Type-xxxx}%} doivent être traités comme les valeurs réelles qu'ils remplacent.
   - Ces espaces réservés DOIVENT être reproduits sous leur forme EXACTE et COMPLÈTE.
   - Le formatage spécial {%{Type-xxxx}%} doit être maintenu exactement - chaque caractère est important.

2. INTERDICTION DE CIRCONLOCUTIONS:
   - Il est STRICTEMENT INTERDIT de remplacer les espaces réservés par des expressions comme "un nom anonymisé", "entreprise anonymisée", "Personne X" ou des circonlocutions similaires.
   - N'utilisez JAMAIS de formulations indiquant qu'il s'agit de données anonymisées.

3. COMPORTEMENT DE RÉPONSE DIRECT:
   - Lorsqu'on vous interroge sur des noms, des adresses ou d'autres contenus anonymisés, vous DEVEZ toujours utiliser l'espace réservé correspondant sous sa forme inchangée.
   - Exemple: À la question "Qui est l'expéditeur?", la réponse correcte est "{%{Prénom-abc123}%}" (si indiqué comme tel dans le document).

4. CONTEXTE JURIDIQUE:
Les espaces réservés SONT les valeurs réelles dans le contexte de ce document. Leur utilisation exacte est juridiquement pertinente et permet un traitement cohérent du contenu tout en respectant les réglementations de protection des données.""",

    'es': """INSTRUCCIÓN CRÍTICA DE PROCESAMIENTO: Este documento contiene información legalmente anonimizada que requiere un manejo especial.

USO PRECISO DE MARCADORES - PRIORIDAD ABSOLUTA:
Todos los datos sensibles han sido reemplazados con marcadores especiales en el formato {%{Categoría-Hash}%} (por ejemplo, {%{Nombre-xxxx}%}, {%{Apellido-xxxx}%}, {%{Dirección-xxxx}%}, {%{NombreEmpresa-xxxx}%}). Estos marcadores DEBEN ser utilizados en sus respuestas EXACTAMENTE como aparecen en el documento original.

REGLAS VINCULANTES:
1. INTEGRIDAD DE LOS MARCADORES:
   - Todos los marcadores en el formato {%{Tipo-xxxx}%} deben ser tratados como los valores reales que reemplazan.
   - Estos marcadores DEBEN reproducirse en su forma EXACTA y COMPLETA.
   - El formato especial {%{Tipo-xxxx}%} debe mantenerse exactamente - cada carácter es importante.

2. PROHIBICIÓN DE CIRCUNLOQUIOS:
   - Está ESTRICTAMENTE PROHIBIDO reemplazar marcadores con expresiones como "un nombre anonimizado", "empresa anonimizada", "Persona X" o circunloquios similares.
   - NUNCA utilice formulaciones que indiquen que estos son datos anonimizados.

3. COMPORTAMIENTO DE RESPUESTA DIRECTA:
   - Cuando se le pregunte sobre nombres, direcciones u otro contenido anonimizado, DEBE utilizar siempre el marcador correspondiente en su forma sin cambios.
   - Ejemplo: A la pregunta "¿Quién es el remitente?", la respuesta correcta es "{%{Nombre-abc123}%}" (si así se indica en el documento).

4. CONTEXTO LEGAL:
Los marcadores SON los valores reales en el contexto de este documento. Su uso exacto es legalmente relevante y permite un procesamiento consistente del contenido mientras se cumple con las regulaciones de protección de datos.""",

    'it': """ISTRUZIONE CRITICA DI ELABORAZIONE: Questo documento contiene informazioni legalmente anonimizzate che richiedono una gestione speciale.

USO PRECISO DEI SEGNAPOSTO - PRIORITÀ ASSOLUTA:
Tutti i dati sensibili sono stati sostituiti con segnaposto speciali nel formato {%{Categoria-Hash}%} (ad esempio, {%{Nome-xxxx}%}, {%{Cognome-xxxx}%}, {%{Indirizzo-xxxx}%}, {%{NomeAzienda-xxxx}%}). Questi segnaposto DEVONO essere utilizzati nelle tue risposte ESATTAMENTE come appaiono nel documento originale.

REGOLE VINCOLANTI:
1. INTEGRITÀ DEI SEGNAPOSTO:
   - Tutti i segnaposto nel formato {%{Tipo-xxxx}%} devono essere trattati come i valori effettivi che sostituiscono.
   - Questi segnaposto DEVONO essere riprodotti nella loro forma ESATTA e COMPLETA.
   - La formattazione speciale {%{Tipo-xxxx}%} deve essere mantenuta esattamente - ogni carattere è importante.

2. DIVIETO DI CIRCONLOCUZIONI:
   - È SEVERAMENTE VIETATO sostituire i segnaposto con espressioni come "un nome anonimizzato", "azienda anonimizzata", "Persona X" o circonlocuzioni simili.
   - NON utilizzare MAI formulazioni che indichino che si tratta di dati anonimizzati.

3. COMPORTAMENTO DI RISPOSTA DIRETTO:
   - Quando ti vengono chiesti nomi, indirizzi o altro contenuto anonimizzato, DEVI sempre utilizzare il segnaposto corrispondente nella sua forma invariata.
   - Esempio: Alla domanda "Chi è il mittente?", la risposta corretta è "{%{Nome-abc123}%}" (se così indicato nel documento).

4. CONTESTO LEGALE:
I segnaposto SONO i valori effettivi nel contesto di questo documento. Il loro uso esatto è legalmente rilevante e consente un'elaborazione coerente del contenuto nel rispetto delle normative sulla protezione dei dati."""
}

DOC_PROMPT_END = {
    'de': """VERBINDLICHE SCHLUSSANWEISUNG - HÖCHSTE PRIORITÄT:

Bei der Verarbeitung oder Beantwortung von Fragen zu diesem Dokument MÜSSEN folgende Regeln strikt eingehalten werden:

1. PLATZHALTER-INTEGRITÄT:
   - Alle Platzhalter im Format {%{Typ-xxxx}%} sind als die tatsächlichen Werte zu behandeln, die sie ersetzen.
   - Diese Platzhalter MÜSSEN in ihrer EXAKTEN und VOLLSTÄNDIGEN Form wiedergegeben werden.
   - Die spezielle Formatierung {%{Typ-xxxx}%} muss bei jeder Verwendung präzise beibehalten werden.

2. VERBOT VON UMSCHREIBUNGEN:
   - Es ist STRENG UNTERSAGT, Platzhalter mit Ausdrücken wie "ein anonymisierter Name", "anonymisierte Firma", "Person X" oder ähnlichen Umschreibungen zu ersetzen.
   - Verwende NIEMALS Formulierungen, die darauf hinweisen, dass es sich um anonymisierte Daten handelt.

3. DIREKTES ANTWORTVERHALTEN:
   - Bei Fragen nach Namen, Adressen oder anderen anonymisierten Inhalten MUSST du stets den entsprechenden Platzhalter in seiner unveränderten Form verwenden.
   - Beispiel: Auf die Frage "Wer ist der Absender?" ist die korrekte Antwort "{%{person-abc123}%}" (falls so im Dokument angegeben).

4. RECHTLICHE BEDEUTUNG:
   - Die korrekte Verwendung der Platzhalter ist rechtlich bindend und entscheidend für die Einhaltung von Datenschutzvorschriften.
   - Jede Abweichung von diesen Regeln kann zu falscher Informationsverarbeitung führen und ist nicht zulässig.

HINWEIS: Der Platzhalter selbst IST die Antwort und muss in allen Fällen exakt reproduziert werden.""",

    'en': """BINDING FINAL INSTRUCTION - HIGHEST PRIORITY:

When processing or answering questions about this document, the following rules MUST be strictly adhered to:

1. PLACEHOLDER INTEGRITY:
   - All placeholders in the format {%{Type-xxxx}%} are to be treated as the actual values they replace.
   - These placeholders MUST be reproduced in their EXACT and COMPLETE form.
   - The special formatting {%{Type-xxxx}%} must be maintained exactly - every character is important.

2. PROHIBITION OF CIRCUMLOCUTIONS:
   - It is STRICTLY FORBIDDEN to replace placeholders with expressions like "an anonymized name", "anonymized company", "Person X", or similar circumlocutions.
   - NEVER use formulations that indicate these are anonymized data.

3. DIRECT RESPONSE BEHAVIOR:
   - When asked about names, addresses, or other anonymized content, you MUST always use the corresponding placeholder in its unchanged form.
   - Example: To the question "Who is the sender?", the correct answer is "{%{FirstName-abc123}%}" (if stated as such in the document).

4. LEGAL SIGNIFICANCE:
   - The correct use of placeholders is legally binding and crucial for compliance with data protection regulations.
   - Any deviation from these rules can lead to incorrect information processing and is not permissible.

NOTE: The placeholder itself IS the answer and must be reproduced exactly in all cases.""",

    'fr': """INSTRUCTION FINALE CONTRAIGNANTE - PRIORITÉ MAXIMALE:

Lors du traitement ou de la réponse à des questions sur ce document, les règles suivantes DOIVENT être strictement respectées:

1. INTÉGRITÉ DES ESPACES RÉSERVÉS:
   - Tous les espaces réservés au format {%{Type-xxxx}%} doivent être traités comme les valeurs réelles qu'ils remplacent.
   - Ces espaces réservés DOIVENT être reproduits sous leur forme EXACTE et COMPLÈTE.
   - Le formatage spécial {%{Type-xxxx}%} doit être maintenu exactement - chaque caractère est important.

2. INTERDICTION DE CIRCONLOCUTIONS:
   - Il est STRICTEMENT INTERDIT de remplacer les espaces réservés par des expressions comme "un nom anonymisé", "entreprise anonymisée", "Personne X" ou des circonlocutions similaires.
   - N'utilisez JAMAIS de formulations indiquant qu'il s'agit de données anonymisées.

3. COMPORTEMENT DE RÉPONSE DIRECT:
   - Lorsqu'on vous interroge sur des noms, des adresses ou d'autres contenus anonymisés, vous DEVEZ toujours utiliser l'espace réservé correspondant sous sa forme inchangée.
   - Exemple: À la question "Qui est l'expéditeur?", la réponse correcte est "{%{Prénom-abc123}%}" (si indiqué comme tel dans le document).

4. IMPORTANCE JURIDIQUE:
   - L'utilisation correcte des espaces réservés est juridiquement contraignante et cruciale pour le respect des réglementations de protection des données.
   - Tout écart par rapport à ces règles peut conduire à un traitement incorrect des informations et n'est pas admissible.

REMARQUE: L'espace réservé lui-même EST la réponse et doit être reproduit exactement dans tous les cas.""",

    'es': """INSTRUCCIÓN FINAL VINCULANTE - MÁXIMA PRIORIDAD:

Al procesar o responder preguntas sobre este documento, se DEBEN cumplir estrictamente las siguientes reglas:

1. INTEGRIDAD DE LOS MARCADORES:
   - Todos los marcadores en el formato {%{Tipo-xxxx}%} deben ser tratados como los valores reales que reemplazan.
   - Estos marcadores DEBEN reproducirse en su forma EXACTA y COMPLETA.
   - El formato especial {%{Tipo-xxxx}%} debe mantenerse exactamente - cada carácter es importante.

2. PROHIBICIÓN DE CIRCUNLOQUIOS:
   - Está ESTRICTAMENTE PROHIBIDO reemplazar marcadores con expresiones como "un nombre anonimizado", "empresa anonimizada", "Persona X" o circunloquios similares.
   - NUNCA utilice formulaciones que indiquen que estos son datos anonimizados.

3. COMPORTAMIENTO DE RESPUESTA DIRECTA:
   - Cuando se le pregunte sobre nombres, direcciones u otro contenido anonimizado, DEBE utilizar siempre el marcador correspondiente en su forma sin cambios.
   - Ejemplo: A la pregunta "¿Quién es el remitente?", la respuesta correcta es "{%{Nombre-abc123}%}" (si así se indica en el documento).

4. SIGNIFICADO LEGAL:
   - El uso correcto de los marcadores es legalmente vinculante y crucial para el cumplimiento de las regulaciones de protección de datos.
   - Cualquier desviación de estas reglas puede llevar a un procesamiento incorrecto de la información y no es permisible.

NOTA: El marcador en sí mismo ES la respuesta y debe reproducirse exactamente en todos los casos.""",

    'it': """ISTRUZIONE FINALE VINCOLANTE - MASSIMA PRIORITÀ:

Durante l'elaborazione o la risposta a domande su questo documento, le seguenti regole DEVONO essere rigorosamente rispettate:

1. INTEGRITÀ DEI SEGNAPOSTO:
   - Tutti i segnaposto nel formato {%{Tipo-xxxx}%} devono essere trattati come i valori effettivi che sostituiscono.
   - Questi segnaposto DEVONO essere riprodotti nella loro forma ESATTA e COMPLETA.
   - La formattazione speciale {%{Tipo-xxxx}%} deve essere mantenuta esattamente - ogni carattere è importante.

2. DIVIETO DI CIRCONLOCUZIONI:
   - È SEVERAMENTE VIETATO sostituire i segnaposto con espressioni come "un nome anonimizzato", "azienda anonimizzata", "Persona X" o circonlocuzioni simili.
   - NON utilizzare MAI formulazioni che indichino che si tratta di dati anonimizzati.

3. COMPORTAMENTO DI RISPOSTA DIRETTO:
   - Quando ti vengono chiesti nomi, indirizzi o altro contenuto anonimizzato, DEVI sempre utilizzare il segnaposto corrispondente nella sua forma invariata.
   - Esempio: Alla domanda "Chi è il mittente?", la risposta corretta è "{%{Nome-abc123}%}" (se così indicato nel documento).

4. SIGNIFICATO LEGALE:
   - L'uso corretto dei segnaposto è legalmente vincolante e cruciale per la conformità alle normative sulla protezione dei dati.
   - Qualsiasi deviazione da queste regole può portare a un'elaborazione errata delle informazioni e non è ammissibile.

NOTA: Il segnaposto stesso È la risposta e deve essere riprodotto esattamente in tutti i casi."""
}
