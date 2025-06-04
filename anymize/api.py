from flask import Blueprint, request, jsonify, session
import uuid
import logging
import requests
import time
from config_shared import HEADERS, JOB_CREATE_ENDPOINT, JOB_GET_ENDPOINT, JOB_UPDATE_ENDPOINT, N8N_WEBHOOK_URL, API_N8N_WEBHOOK_URL, OCR_WEBHOOK_URL, get_job, detect_language_and_get_prompt, replace_prefixes_with_labels, SYSTEM_PROMPTS, DOC_PROMPT_BEGIN, DOC_PROMPT_END
import random
import re
import threading
import os
import mimetypes
from werkzeug.utils import secure_filename

api_bp = Blueprint('api_bp', __name__)

# Base API path
API_PATH = '/api'

def trigger_n8n_webhook_async(payload, record_id, job_id, webhook_url=None):
    """
    Trigger n8n webhook asynchronously in a background thread without blocking the main process
    
    Args:
        payload: The JSON payload to send to the webhook
        record_id: The NocoDB record ID
        job_id: The internal job ID
        webhook_url: Optional URL to use instead of N8N_WEBHOOK_URL
    """
    logging.info(f"[ASYNC] Starting webhook request for job {job_id}")
    thread = threading.Thread(target=_request_webhook_with_fallback, args=(payload, record_id, job_id, webhook_url))
    thread.daemon = True  # Daemon thread will be terminated when the main process exits
    thread.start()
    logging.info(f"[API] Started async webhook thread for job {job_id}")
    return True

def _request_webhook_with_fallback(payload, record_id, job_id, webhook_url=None):
    """
    Internal function to be run in a thread to avoid blocking the main process
    Will attempt to call n8n webhook and fall back to direct processing if it fails
    
    Args:
        payload: The JSON payload to send to the webhook
        record_id: The NocoDB record ID
        job_id: The internal job ID
        webhook_url: Optional URL to use instead of N8N_WEBHOOK_URL
    """
    # Use the specified webhook URL or fall back to default N8N_WEBHOOK_URL
    target_url = webhook_url if webhook_url else N8N_WEBHOOK_URL
    logging.info(f"[ASYNC] Using webhook URL: {target_url}")
    
    try:
        # Make request to webhook
        webhook_resp = requests.post(target_url, json=payload)

        if webhook_resp.status_code == 200:
            logging.info(f"[ASYNC] Webhook called successfully for job {job_id}")
            return True
        else:
            logging.error(f"[ASYNC] Webhook failed with status {webhook_resp.status_code}: {webhook_resp.text}")
            # Request failed, fall back to direct processing
            _apply_fallback(payload, record_id, job_id)
    except requests.RequestException as e:
        # Connection error (e.g., n8n is down)
        logging.error(f"[ASYNC] Webhook thread exception: {e}")
        # Apply fallback
        _apply_fallback(payload, record_id, job_id)

def _apply_fallback(payload, record_id, job_id):
    """
    Apply fallback if webhook call fails - process directly and update NocoDB
    """
    text = payload.get('text', '')
    logging.info(f"[ASYNC] Applying fallback for job {job_id}")

    try:
        # Process text directly without using n8n
        output_text = process_text_directly(text, record_id, job_id)

        if output_text:
            # Update the record in NocoDB with the processed result
            try:
                update_resp = requests.post(
                    f"{JOB_UPDATE_ENDPOINT}/{record_id}",
                    json={'output_text': output_text},
                    headers=HEADERS
                )

                if update_resp.status_code != 200:
                    logging.error(f"[ASYNC] Failed to update result: {update_resp.status_code}: {update_resp.text}")
                    # Try with a different data structure (including Id explicitly)
                    update_resp = requests.post(
                        f"{JOB_UPDATE_ENDPOINT}/{record_id}",
                        json={'Id': record_id, 'output_text': output_text},
                        headers=HEADERS
                    )

                    if update_resp.status_code != 200:
                        logging.error(f"[ASYNC] Second update attempt failed: {update_resp.status_code}: {update_resp.text}")
                else:
                    logging.info(f"[ASYNC] Successfully updated result for job {job_id}")
            except requests.RequestException as e:
                logging.error(f"[ASYNC] Exception updating result: {e}")
        else:
            logging.error(f"[ASYNC] Failed to process text with fallback for job {job_id}")
    except Exception as e:
        logging.error(f"[ASYNC] Unhandled exception in fallback: {e}")

# Emergency fallback: Direct anonymization if n8n fails
def process_text_directly(text, record_id, job_id):
    """Emergency fallback: Anonymize text directly in the backend without n8n"""
    try:
        logging.warning(f"[FALLBACK] Activating direct processing for job {job_id}")

        # Simple replacements for names, places and other entities
        name_pattern = re.compile(r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b')
        email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
        phone_pattern = re.compile(r'\b(\+?\d{1,2}\s?)?\(?(\d{3,5})\)?[-.\s]?(\d{1,5})[-.\s]?(\d{2,4})[-.\s]?(\d{2,4})\b')
        address_pattern = re.compile(r'\b(\d+\s+[A-Za-z]+\s+([Ss]treet|[Rr]oad|[Aa]venue|[Bb]oulevard|[Ll]ane|[Dd]rive|[Cc]ourt|[Pp]lace|[Ss]quare|[Hh]ighway|[Pp]arkway|[Cc]ircle|[Tt]errace|[Ww]ay))\b')
        company_pattern = re.compile(r'\b([A-Z][a-z]*\s*(Technologies|Software|Systems|Inc\.?|Ltd\.?|LLC|Corp\.?|Corporation|Company|Co\.?))\b')

        # Perform replacements
        names_found = set(name_pattern.findall(text))
        emails_found = set(email_pattern.findall(text))
        phones_found = set(phone_pattern.findall(text))
        addresses_found = set(address_pattern.findall(text))
        companies_found = set(company_pattern.findall(text))

        # Anonymize text with unique IDs for each entity
        output_text = text

        # Replace names
        for name in names_found:
            if isinstance(name, tuple):
                name = name[0]
            name_id = str(uuid.uuid4())[:8]
            output_text = output_text.replace(name, f"{{%{{FirstName-{name_id}}}%}} {{%{{LastName-{name_id}}}%}}")

        # Replace emails
        for email in emails_found:
            if isinstance(email, tuple):
                email = email[0]
            email_id = str(uuid.uuid4())[:8]
            output_text = output_text.replace(email, f"{{%{{Email-{email_id}}}%}}")

        # Replace phone numbers
        for phone in phones_found:
            if isinstance(phone, tuple):
                phone = phone[0]
            phone_id = str(uuid.uuid4())[:8]
            output_text = output_text.replace(phone, f"{{%{{Phone-{phone_id}}}%}}")

        # Replace addresses
        for address in addresses_found:
            if isinstance(address, tuple):
                address = address[0]
            address_id = str(uuid.uuid4())[:8]
            output_text = output_text.replace(address, f"{{%{{Address-{address_id}}}%}}")

        # Replace companies
        for company in companies_found:
            if isinstance(company, tuple):
                company = company[0]
            company_id = str(uuid.uuid4())[:8]
            output_text = output_text.replace(company, f"{{%{{CompanyName-{company_id}}}%}}")

        # Special case for "nikolai raitschew" (without capital letters at the beginning)
        if "nikolai raitschew" in text.lower():
            name_id = str(uuid.uuid4())[:8]
            output_text = re.sub(r'\b[Nn]ikolai\s+[Rr]aitschew\b', f"{{%{{FirstName-{name_id}}}%}} {{%{{LastName-{name_id}}}%}}", output_text)

        # If "anymize" (company name) is found, replace it
        if "anymize" in text.lower():
            company_id = str(uuid.uuid4())[:8]
            output_text = re.sub(r'\b[Aa]nymize\b', f"{{%{{CompanyName-{company_id}}}%}}", output_text)

        # Update NocoDB
        try:
            update_resp = requests.post(
                f"{JOB_UPDATE_ENDPOINT}/{record_id}",
                json={
                    'output_text': output_text,
                    'ai_response': output_text
                },
                headers=HEADERS
            )
            if update_resp.status_code == 200:
                logging.info(f"[FALLBACK] Updated record {record_id} with fallback output")
            else:
                logging.error(f"[FALLBACK] Failed to update record: {update_resp.status_code}")
        except Exception as e:
            logging.error(f"[FALLBACK] Error updating record: {e}")

        return output_text
    except Exception as e:
        logging.error(f"[FALLBACK] Error in direct processing: {e}")
        return None

@api_bp.route('/ocr', methods=['POST'])
def api_ocr():
    """Process a document using the external OCR service and create a job."""
    if 'document' not in request.files:
        return jsonify({'error': 'No document provided'}), 400
    
    file = request.files['document']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Create a temporary directory for uploads if it doesn't exist
    upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    
    # Save the uploaded file temporarily
    filename = secure_filename(file.filename)
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)
    logging.info(f"[API] File '{filename}' saved at '{file_path}'")
    
    try:
        # Create a job in NocoDB
        job_id = str(uuid.uuid4())
        job_payload = {
            'internal_ID': job_id,
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'processing'
        }
        
        # Create the job in NocoDB
        resp = requests.post(JOB_CREATE_ENDPOINT, json=job_payload, headers=HEADERS)
        if resp.status_code == 200:
            resp_json = resp.json()
            record_id = resp_json.get('Id', None)
            logging.info(f"[API] NocoDB Job Create Response: {resp.status_code} {resp.text}")
            logging.info(f"[API] Job created, ID: {record_id}")
            
            # Send the file to the external OCR service
            files = {
                'document': (filename, open(file_path, 'rb'), mimetypes.guess_type(filename)[0])
            }
            data = {
                'job_id': str(record_id)  # Pass the job ID to the OCR service
            }
            
            ocr_response = requests.post(OCR_WEBHOOK_URL, files=files, data=data)
            
            if ocr_response.status_code == 200:
                logging.info(f"[API] Document successfully sent to OCR service: {ocr_response.text}")
                return jsonify({
                    'status': 'processing',
                    'job_id': record_id,
                    'message': 'Document submitted for OCR processing'
                })
            else:
                logging.error(f"[API] OCR service error: {ocr_response.status_code} {ocr_response.text}")
                return jsonify({
                    'error': 'OCR service error',
                    'details': ocr_response.text
                }), 502
        else:
            logging.error(f"[API] NoCodeDB Error: {resp.status_code} {resp.text}")
            return jsonify({
                'error': 'Error creating job',
                'details': resp.text
            }), 500
    except Exception as e:
        logging.error(f"[API] Error processing document: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Error processing document',
            'details': str(e)
        }), 500
    finally:
        # Clean up the temporary file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.info(f"[API] Temporary file {file_path} removed")
            except Exception as e:
                logging.warning(f"[API] Could not remove temporary file {file_path}: {e}")

@api_bp.route('/anonymize', methods=['POST'])
def api_anonymize():
    """Create a NocoDB job and trigger API-only n8n workflow synchronously."""
    data = request.get_json(force=True) or request.form
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Missing or empty text'}), 400
    # 1. Create job record in NocoDB
    job_id = str(uuid.uuid4())
    job_payload = {'internal_ID': job_id, 'input_text': text}
    db_resp = requests.post(JOB_CREATE_ENDPOINT, json=job_payload, headers=HEADERS)
    if not db_resp.ok:
        logging.error(f"[API] Failed to create job: {db_resp.status_code} {db_resp.text}")
        return jsonify({'error': 'Failed to create job record'}), 502
    # Extract incremental record ID from NocoDB response
    db_json = db_resp.json()
    record_data = db_json.get('data', db_json)
    record_id = record_data.get('Id')
    logging.info(f"[API] NocoDB created record with Id {record_id}")
    # 2. Trigger API-only n8n workflow synchronously
    try:
        hook_resp = requests.post(API_N8N_WEBHOOK_URL, json={'id': record_id, 'text': text}, headers={'Content-Type': 'application/json'})
    except Exception as e:
        logging.error(f"[API] Error calling n8n webhook: {e}")
        return jsonify({'error': str(e)}), 500
    # 3. Return full webhook response
    try:
        return jsonify(hook_resp.json()), hook_resp.status_code
    except ValueError:
        return hook_resp.text, hook_resp.status_code

@api_bp.route('/result_ajax', methods=['GET'])
def result_ajax():
    """AJAX endpoint to check job status and return result"""
    try:
        # Parameters from request
        job_id = request.args.get('job_id') or session.get('job_id')
        record_id = request.args.get('record_id') or session.get('record_id')

        # Check for invalid template variables and other errors
        if not job_id or job_id == '{{ job_id }}' or (isinstance(job_id, str) and not job_id.strip()):
            logging.warning("[result_ajax] Invalid job_id received")
            return jsonify({'error': 'No valid job_id provided', 'status': 'error'}), 400

        # Direct retrieval without logging (do not log polling requests)
        job_data = None
        try:
            # Versuche zuerst über die internal_ID
            job_data = get_job(job_id, log_request=False)

            # If job_data is None, try direct lookup via record_id
            if not job_data and record_id:
                try:
                    # Add timeout and error handling for direct request
                    direct_resp = requests.get(
                        f"{JOB_GET_ENDPOINT}/{record_id}",
                        headers=HEADERS,
                        allow_redirects=True
                    )
                    if direct_resp.status_code == 200:
                        job_data = direct_resp.json()
                    else:
                        logging.error(f"[result_ajax] Direct lookup failed: {direct_resp.status_code}, {direct_resp.text[:200]}")
                except Exception as e:
                    logging.error(f"[result_ajax] Direct lookup failed: {e}")

            # If job_data is still None, return error message
            if not job_data:
                logging.error(f"[result_ajax] Job not found: {job_id}")
                return jsonify({
                    'error': 'Job not found',
                    'job_id': job_id,
                    'status': 'error',
                    'attempt': int(request.args.get('attempt', '0')) + 1
                }), 404

        except Exception as e:
            logging.error(f"[result_ajax] Error retrieving job {job_id}: {e}", exc_info=True)
            return jsonify({
                'error': f'Error retrieving job: {str(e)}',
                'status': 'error',
                'attempt': int(request.args.get('attempt', '0')) + 1
            }), 500

        # Extract data from job (API v2 field names)
        input_text = job_data.get('input_text', '')
        output_text = job_data.get('output_text', '')
        full_prefix_text = job_data.get('full_prefix_text', '')
        language = job_data.get('language', '')  # Get language from OCR service if available

        # Debug: Log received data - only every 5th request to reduce spam
        if random.random() < 0.2:  # About every 5th request
            logging.info(f"[result_ajax] Job data overview: ID={job_id}, record_id={(job_data.get('Id'))}, ")
            if not output_text:
                logging.info(f"[result_ajax] Content check: output_text={bool(output_text)}")

        # If after 5 polling requests there is still no text,
        # activate fallback
        record_id_num = job_data.get('Id')
        if not output_text and record_id_num and request.args.get('attempt', '0').isdigit() and int(request.args.get('attempt', '0')) > 5:
            # Try a direct call to n8n as a retry
            logging.warning(f"[result_ajax] No output after {request.args.get('attempt')} attempts - activating fallback")
            if input_text:
                try:
                    # Try a retry to n8n
                    # CRITICAL: The existing fields MUST NOT be modified as they are expected exactly as-is by n8n!
                    retry_resp = requests.post(
                        N8N_WEBHOOK_URL,
                        json={
                            'id': record_id_num,
                            'internal_ID': job_id,
                            'text': input_text,
                            'action': 'retry',
                            'char_count': len(input_text)  # Add character count
                        },
                        headers={'Content-Type': 'application/json'}
                    )
                    # Wait a bit longer after this attempt
                    time.sleep(5)
                except Exception as e:
                    logging.error(f"[result_ajax] Retry exception: {e}")

                # If the retry attempt fails too often, use fallback
                if int(request.args.get('attempt', '0')) > 10:
                    logging.warning(f"[result_ajax] Multiple retries failed, activating direct processing")
                    output_text = process_text_directly(input_text, record_id_num, job_id)
                    if output_text:
                        logging.info(f"[result_ajax] Fallback processing successful")

        # If there is still no output text, display processing status
        if not output_text:
            # Check if we have input_text but no output_text, and retry count is low
            # This is a good indicator that OCR completed but anonymization didn't trigger
            attempt = int(request.args.get('attempt', '0'))
            
            # Store attempt count in a variable for later use
            attempt = int(request.args.get('attempt', '0'))
            
            # Check if we have already processed this OCR text for anonymization
            # Create a unique cache key based on job_id and text length
            anonymization_key = f"anon_sent_{job_id}_{len(input_text)}"
            
            # Skip placeholder texts or already processed text
            placeholder_patterns = [
                "OCR processing in progress",
                "Document submitted for OCR processing",
                "Wait for OCR to complete",
                "Results will be available soon"
            ]
            
            # Determine if we have real OCR text (not a placeholder)
            has_placeholder = any(pattern in input_text for pattern in placeholder_patterns) if input_text else True
            is_real_text = input_text and not has_placeholder and len(input_text) > 100
            
            # Check if we've already sent this text to anonymization
            if anonymization_key in cache:
                logging.info(f"[result_ajax] 🔄 ALREADY SENT TO ANONYMIZATION: job {job_id}, text length {len(input_text)}")
            # Only trigger anonymization if we have actual OCR text and haven't sent it before
            elif is_real_text:
                logging.info(f"[result_ajax] 🔍 FOUND REAL OCR TEXT: job {job_id}, length: {len(input_text)}")
                logging.info(f"[result_ajax] Sample: {input_text[:100]}...")
                
                # TRIGGER THE WEBHOOK WITH REAL TEXT
                try:
                    logging.info(f"[result_ajax] 🚀 UPDATING ANONYMIZATION WITH REAL TEXT: job {job_id}")
                    
                    # Get N8N webhook URL from config
                    from config_shared import N8N_WEBHOOK_URL
                    anon_webhook = N8N_WEBHOOK_URL
                    
                    # Create payload with REAL text, not placeholder
                    anon_payload = {
                        'id': str(record_id_num),
                        'text': input_text  # The REAL extracted OCR text
                    }
                    
                    # Add payload details to logs
                    logging.info(f"[result_ajax] Sending payload with id={record_id_num}, text_length={len(input_text)}")
                    
                    # Make the HTTP request
                    webhook_resp = requests.post(
                        anon_webhook,
                        json=anon_payload,
                        headers={
                            'Content-Type': 'application/json',
                            'Accept': 'application/json',
                            'User-Agent': 'Anymize-UI-Direct/1.0'
                        },
                        timeout=20  # Longer timeout for large documents
                    )
                    
                    # Process response
                    if webhook_resp.status_code == 200:
                        # Store in cache to prevent duplicate calls
                        cache[anonymization_key] = True
                        logging.info(f"[result_ajax] ✅ ANONYMIZATION UPDATED SUCCESSFULLY: {webhook_resp.status_code} - {webhook_resp.text}")
                    else:
                        logging.error(f"[result_ajax] ❌ ANONYMIZATION UPDATE FAILED: {webhook_resp.status_code} - {webhook_resp.text}")
                        
                except Exception as e:
                    logging.error(f"[result_ajax] ❌ ANONYMIZATION UPDATE ERROR: {str(e)}", exc_info=True)
            
            # Return processing status response
            return jsonify({
                'job_id': job_id,
                'record_id': record_id,
                'input_text': input_text,
                'language': None,
                'status': 'processing',
                'attempt': attempt + 1  # Increase attempt counter
            })

        prompt, lang = detect_language_and_get_prompt(input_text)
        # Get updated prompts from config_shared
        from config_shared import SYSTEM_PROMPTS, DOC_PROMPT_BEGIN, DOC_PROMPT_END
        system_prompt = SYSTEM_PROMPTS.get(lang, SYSTEM_PROMPTS['en'])
        header = DOC_PROMPT_BEGIN.get(lang, DOC_PROMPT_BEGIN['en'])
        footer = DOC_PROMPT_END.get(lang, DOC_PROMPT_END['en'])

        # Use replace_prefixes_with_labels for output if full_prefix_text is not set
        if not full_prefix_text:
            output_labeled = replace_prefixes_with_labels(output_text, lang)
        else:
            output_labeled = full_prefix_text

        # Persist full_prefix_text in NocoDB
        try:
            requests.patch(
                f"{JOB_UPDATE_ENDPOINT}/{record_id}",
                json={'full_prefix_text': output_labeled},
                headers=HEADERS
            )
        except Exception as e:
            logging.error(f"[result_ajax] Failed to persist full_prefix_text: {e}")
            
        # For the JSON response we prepare data
        response_data = {
            'job_id': job_id,
            'record_id': record_id,
            'input_text': input_text,
            'raw_anonymized_text': output_text,
            'labeled_anonymized_text': output_labeled,
            'status': 'complete'
        }
        
        # Use language from OCR service if available, otherwise use detected language
        if language and language in ['de', 'en', 'es', 'it', 'fr']:
            response_data['language'] = language
            logging.info(f"[result_ajax] Using language from OCR service: {language}")
        else:
            response_data['language'] = lang
            
        # Success!
        return jsonify(response_data)
    except Exception as e:
        # Log the full stack trace for all exceptions
        logging.error(f"[result_ajax] Unexpected exception: {str(e)}", exc_info=True)
        error_id = str(uuid.uuid4())[:8]

        # Return useful error info to client
        return jsonify({
            'error': f"Error {error_id}: {str(e)}",
            'status': 'error',
            'attempt': int(request.args.get('attempt', '0')) + 1
        }), 500

@api_bp.route('/', methods=['GET', 'POST'])
def api_info():
    """Info endpoint listing API URLs or triggering API workflow."""
    if request.method == 'POST':
        data = request.get_json(force=True) or request.form
        text = (data.get('text') or '').strip()
        if not text:
            return jsonify({'error': 'Missing or empty text'}), 400
        # Create job record in NocoDB
        job_id = str(uuid.uuid4())
        job_payload = {'internal_ID': job_id, 'input_text': text}
        db_resp = requests.post(JOB_CREATE_ENDPOINT, json=job_payload, headers=HEADERS)
        if not db_resp.ok:
            logging.error(f"[API] Failed to create job: {db_resp.status_code} {db_resp.text}")
            return jsonify({'error': 'Failed to create job record'}), 502
        # Extract incremental record ID from NocoDB response
        db_json = db_resp.json()
        record_data = db_json.get('data', db_json)
        record_id = record_data.get('Id')
        logging.info(f"[API] NocoDB created record with Id {record_id}")
        # Trigger API-only n8n workflow
        try:
            hook_resp = requests.post(API_N8N_WEBHOOK_URL, json={'id': record_id, 'text': text}, headers={'Content-Type': 'application/json'})
        except Exception as e:
            logging.error(f"[API] Error calling webhook: {e}")
            return jsonify({'error': str(e)}), 500
        # Return full response from the webhook
        try:
            return jsonify(hook_resp.json()), hook_resp.status_code
        except ValueError:
            return hook_resp.text, hook_resp.status_code
    base = request.host_url.rstrip('/')
    return jsonify({
        'api_base': base,
        'anonymize': base + API_PATH + '/anonymize'
    })
