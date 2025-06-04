"""
OCR Integration for Anymize Application

This module connects the multi-engine OCR system with the Anymize application workflow.
It handles document processing, sensitive data detection, and integration with 
NocoDb and n8n systems.

The workflow:
1. User uploads a document
2. Document is processed by OCR to extract text
3. Local LLM identifies sensitive information based on prefixes
4. Sensitive data is stored in the database with hashed values
5. Document with sensitive data replaced by hashes is sent to external LLM
6. Response from external LLM has hashed values replaced with original data

Usage:
    from ocr_anymize_integration import AnymizeOCRProcessor
    
    processor = AnymizeOCRProcessor()
    result = processor.process_document("document.pdf", "user_prompt")
    print(result.processed_response)  # Secured response with original data
"""

import os
import sys
import uuid
import json
import hashlib
import logging
import requests
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

# Import our multi-engine OCR system
from multi_engine_ocr import (
    MultiEngineOCR, OCRResult, ContentType, 
    PreprocessingPipeline, ContentClassifier
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Import N8N_WEBHOOK_URL from config_shared
from config_shared import (
    TEST_WEBHOOK_URL as N8N_WEBHOOK_URL,
    NOCODB_BASE as NOCODB_BASE_URL,
    NOCODB_TOKEN,
    HEADERS as NOCODB_HEADERS,
    JOB_CREATE_ENDPOINT,
    JOB_UPDATE_ENDPOINT,
    TABLE_JOB
)

# NocoDB API Configuration
NOCODB_API_TOKEN = NOCODB_TOKEN

# NocoDB Table IDs
TABLE_USER = "mj5idkixdjmzgex"
TABLE_STRING = "m1ayzzk79sja5h3"
TABLE_PREFIX = "mhv1s5y9wgzyi9n"
TABLE_CHAT_MEMORY = "m5xltkc7av6zfer"


@dataclass
class SensitiveData:
    """Represents a piece of sensitive data identified in the document"""
    original: str
    prefix_id: int
    prefix_name: str
    prefix_code: str
    hash_value: str = None
    
    def generate_hash(self, job_id: str) -> str:
        """Generate a hash for the sensitive data"""
        if not self.hash_value:
            # Create hash using prefix + job_id as salt
            salt = f"{self.prefix_code}_{job_id}"
            hash_object = hashlib.sha256((self.original + salt).encode())
            # Use the first 8 characters of the hash
            self.hash_value = hash_object.hexdigest()[:8]
        return self.hash_value
    
    def get_replacement(self, job_id: str) -> str:
        """Get the replacement string (prefix_code + hash)"""
        hash_val = self.generate_hash(job_id)
        return f"{self.prefix_code}_{hash_val}"


@dataclass
class ProcessingResult:
    """Container for document processing results"""
    job_id: str
    internal_id: str
    original_text: str
    processed_text: str = ""  # Text with sensitive data replaced by hashes
    llm_response: str = ""    # Response from external LLM
    processed_response: str = ""  # Response with hashes replaced by original data
    sensitive_data: List[SensitiveData] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class NocoDBClient:
    """Client for interacting with NocoDB APIs"""
    
    def __init__(self, base_url: str, api_token: str, headers: Dict[str, str]):
        self.base_url = base_url
        self.headers = headers
        self.headers["xc-token"] = api_token
    
    def create_job(self, user_id: int, internal_id: str, 
                  input_text: str = "", output_text: str = "", 
                  file_path: str = None) -> Dict[str, Any]:
        """Create a new job in NocoDB"""
        url = f"{self.base_url}{JOB_CREATE_ENDPOINT}"
        payload = {
            "user_id": user_id,
            "internal_ID": internal_id,
            "input_text": input_text,
            "output_text": output_text
        }
        
        if file_path:
            # Get just the filename from the path for NocoDB attachment field
            filename = os.path.basename(file_path)
            payload["file"] = [{"url": filename}]  # Correct format for attachment field
        
        response = requests.post(url, json=payload, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to create job: {response.text}")
            raise Exception(f"Failed to create job: {response.status_code}")
        
        return response.json()
    
    def update_job(self, job_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing job in NocoDB"""
        url = f"{self.base_url}{JOB_UPDATE_ENDPOINT}"
        
        payload = {
            "Id": job_id
        }
        payload.update(updates)
        
        response = requests.patch(url, json=payload, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to update job: {response.text}")
            raise Exception(f"Failed to update job: {response.status_code}")
        
        return response.json()
    
    def get_prefixes(self) -> List[Dict[str, Any]]:
        """Get all defined prefixes from NocoDB"""
        url = f"{self.base_url}/api/v2/tables/{TABLE_PREFIX}/records"
        
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to get prefixes: {response.text}")
            raise Exception(f"Failed to get prefixes: {response.status_code}")
        
        return response.json().get("list", [])
    
    def create_prefix(self, name: str, prefix: str) -> Dict[str, Any]:
        """Create a new prefix in NocoDB"""
        url = f"{self.base_url}/api/v2/tables/{TABLE_PREFIX}/records"
        
        payload = {
            "name": name,
            "prefix": prefix
        }
        
        response = requests.post(url, json=payload, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to create prefix: {response.text}")
            raise Exception(f"Failed to create prefix: {response.status_code}")
        
        return response.json()
    
    def store_sensitive_string(self, job_id: int, prefixes_id: int, 
                              original: str, hash_value: str) -> Dict[str, Any]:
        """Store sensitive string data in NocoDB"""
        url = f"{self.base_url}/api/v2/tables/{TABLE_STRING}/records"
        
        payload = {
            "job_id": job_id,
            "prefixes_id": prefixes_id,
            "original": original,
            "hash": hash_value
        }
        
        response = requests.post(url, json=payload, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to store sensitive string: {response.text}")
            raise Exception(f"Failed to store sensitive string: {response.status_code}")
        
        return response.json()
    
    def add_chat_memory(self, job_id: int, internal_id: str, 
                        message: str) -> Dict[str, Any]:
        """Add a chat memory entry in NocoDB"""
        url = f"{self.base_url}/api/v2/tables/{TABLE_CHAT_MEMORY}/records"
        
        payload = {
            "job_id": job_id,
            "internal_ID": internal_id,
            "message": message
        }
        
        response = requests.post(url, json=payload, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to add chat memory: {response.text}")
            raise Exception(f"Failed to add chat memory: {response.status_code}")
        
        return response.json()
    
    def get_sensitive_strings_for_job(self, job_id: int) -> List[Dict[str, Any]]:
        """Get all sensitive strings for a specific job"""
        url = f"{self.base_url}/api/v2/tables/{TABLE_STRING}/records"
        params = {
            "where": f"(job_id,eq,{job_id})",
            "nested[prefixes][fields]": "prefix,name"
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code != 200:
            logger.error(f"Failed to get sensitive strings: {response.text}")
            raise Exception(f"Failed to get sensitive strings: {response.status_code}")
        
        return response.json().get("list", [])


class SensitiveDataDetector:
    """Detects sensitive data in text using local LLM or rule-based approach"""
    
    def __init__(self, nocodb_client: NocoDBClient):
        self.nocodb_client = nocodb_client
        # Load prefixes from database
        self.refresh_prefixes()
    
    def refresh_prefixes(self):
        """Refresh the prefix list from the database"""
        prefixes = self.nocodb_client.get_prefixes()
        self.prefixes = {
            item["name"]: {
                "id": item["Id"],
                "prefix": item["prefix"]
            } for item in prefixes
        }
    
    def detect_with_rules(self, text: str) -> List[SensitiveData]:
        """
        Detect sensitive data using rule-based approach
        
        This is a simplified implementation. In a real system, you'd use
        more sophisticated pattern matching, NER, etc.
        """
        sensitive_data = []
        
        # Simple pattern matching for common sensitive data types
        # In a real implementation, this would be much more comprehensive
        patterns = {
            "First Name": r"\b[A-Z][a-z]{2,25}\b",
            "Last Name": r"\b[A-Z][a-z]{2,25}\b",
            "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "Phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            "Address": r"\b\d+ [A-Za-z]+ (St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road)\b"
        }
        
        import re
        for name, pattern in patterns.items():
            if name not in self.prefixes:
                continue
                
            matches = re.finditer(pattern, text)
            for match in matches:
                # Create a SensitiveData object for each match
                sensitive_data.append(SensitiveData(
                    original=match.group(0),
                    prefix_id=self.prefixes[name]["id"],
                    prefix_name=name,
                    prefix_code=self.prefixes[name]["prefix"]
                ))
        
        return sensitive_data
    
    def detect_with_llm(self, text: str) -> List[SensitiveData]:
        """
        Detect sensitive data using a local LLM
        
        This is a placeholder. In the real implementation, you would:
        1. Call a local LLM (like jan.ai) with the text
        2. Parse the LLM's response to identify sensitive information
        3. Map that to known prefixes or create new ones
        """
        # For now, let's use the rule-based approach as a fallback
        # In a real implementation, you'd implement the LLM-based detection
        return self.detect_with_rules(text)
    
    def detect_sensitive_data(self, text: str, use_llm: bool = True) -> List[SensitiveData]:
        """
        Detect sensitive data in text
        
        Args:
            text: Text to analyze
            use_llm: Whether to use LLM-based detection (vs. rule-based)
            
        Returns:
            List of SensitiveData objects representing sensitive information
        """
        if use_llm:
            return self.detect_with_llm(text)
        else:
            return self.detect_with_rules(text)


class AnymizeOCRProcessor:
    """Main processor that integrates OCR with Anymize workflow"""
    
    def __init__(self, user_id: int = 1):
        self.user_id = user_id
        self.ocr = MultiEngineOCR() if 'MultiEngineOCR' in globals() else None
        self.nocodb_client = NocoDBClient(NOCODB_BASE_URL, NOCODB_API_TOKEN, NOCODB_HEADERS)
        self.sensitive_detector = SensitiveDataDetector(self.nocodb_client)
    
    def extract_text_from_document(self, document_path: str) -> str:
        """Extract text from a document using the OCR system"""
        if self.ocr:
            # Use our multi-engine OCR if available
            result = self.ocr.process_document(document_path)
            return result.text
        else:
            # Fallback using just Tesseract
            import pytesseract
            from PIL import Image
            
            # Check if PDF
            if document_path.lower().endswith('.pdf'):
                # Extract PDF pages as images
                import fitz  # PyMuPDF
                doc = fitz.open(document_path)
                text = ""
                
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap()
                    
                    # Save page as temporary image
                    with tempfile.NamedTemporaryFile(suffix='.png') as tmp:
                        pix.save(tmp.name)
                        # Extract text with Tesseract
                        text += pytesseract.image_to_string(
                            Image.open(tmp.name)
                        ) + "\n\n"
                
                return text
            else:
                # Assume image file
                return pytesseract.image_to_string(Image.open(document_path))
    
    def process_document(self, document_path: str, user_prompt: str = "") -> ProcessingResult:
        """
        Process a document through the Anymize workflow
        
        Args:
            document_path: Path to the document to process
            user_prompt: Optional prompt from the user for the LLM
            
        Returns:
            ProcessingResult with original, processed text and responses
        """
        # Create a unique internal ID for this job
        internal_id = str(uuid.uuid4())
        
        # Step 1: Extract text from document
        logger.info(f"Extracting text from {document_path}")
        original_text = self.extract_text_from_document(document_path)
        
        # Step 2: Create job in NocoDB
        job_data = self.nocodb_client.create_job(
            user_id=self.user_id,
            internal_id=internal_id,
            input_text=original_text
        )
        job_id = job_data["Id"]
        
        # Step 3: Detect sensitive data in the text
        logger.info("Detecting sensitive data")
        sensitive_data = self.sensitive_detector.detect_sensitive_data(original_text)
        
        # Step 4: Replace sensitive data with hashed values and store in database
        processed_text = original_text
        for data in sensitive_data:
            # Generate hash and replacement string
            replacement = data.get_replacement(internal_id)
            
            # Replace in the processed text
            processed_text = processed_text.replace(data.original, replacement)
            
            # Store in database
            self.nocodb_client.store_sensitive_string(
                job_id=job_id,
                prefixes_id=data.prefix_id,
                original=data.original,
                hash_value=data.hash_value
            )
        
        # Step 5: Update job with processed text
        self.nocodb_client.update_job(
            job_id=job_id,
            updates={"output_text": processed_text}
        )
        
        # Step 6: Send to n8n webhook
        logger.info("Sending to n8n webhook")
        n8n_payload = {
            "job_id": job_id,
            "internal_id": internal_id,
            "text": processed_text,
            "user_prompt": user_prompt,
            "callback_url": f"{NOCODB_BASE_URL}/api/callback"  # Example callback URL
        }
        
        try:
            n8n_response = requests.post(N8N_WEBHOOK_URL, json=n8n_payload)
            n8n_response.raise_for_status()
            
            # In a real system, we would wait for the callback from n8n with the LLM response
            # For now, we'll simulate a response
            llm_response = f"This is a simulated response from the LLM based on your document.\n" \
                           f"It would contain any prefix_hash combinations like FN_abc123 that would\n" \
                           f"need to be replaced with the original sensitive data."
            
            # Step 7: Replace hashed values with original data in the response
            processed_response = llm_response
            
            for data in sensitive_data:
                replacement = data.get_replacement(internal_id)
                processed_response = processed_response.replace(replacement, data.original)
            
            # Create result object
            result = ProcessingResult(
                job_id=str(job_id),
                internal_id=internal_id,
                original_text=original_text,
                processed_text=processed_text,
                llm_response=llm_response,
                processed_response=processed_response,
                sensitive_data=sensitive_data
            )
            
            # Add response to chat memory
            self.nocodb_client.add_chat_memory(
                job_id=job_id,
                internal_id=internal_id,
                message=processed_response
            )
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with n8n: {e}")
            raise
    
    def process_subsequent_message(self, job_id: str, user_message: str) -> str:
        """
        Process a subsequent message in an existing conversation
        
        Args:
            job_id: The job ID from the original document processing
            user_message: The new message from the user
            
        Returns:
            The processed response
        """
        # Get sensitive strings for this job
        job_id_int = int(job_id)
        strings_data = self.nocodb_client.get_sensitive_strings_for_job(job_id_int)
        
        # Create SensitiveData objects from database data
        sensitive_data = []
        for item in strings_data:
            prefix_data = item.get("prefixes", {})
            sensitive_data.append(SensitiveData(
                original=item["original"],
                prefix_id=item["prefixes_id"],
                prefix_name=prefix_data.get("name", "Unknown"),
                prefix_code=prefix_data.get("prefix", "XX"),
                hash_value=item["hash"]
            ))
        
        # Get the internal ID from the job
        # In a real implementation, you'd fetch this from the database
        internal_id = "example_internal_id"  # Placeholder
        
        # Process the message (in a real system, this would detect new sensitive data too)
        processed_message = user_message
        for data in sensitive_data:
            replacement = data.get_replacement(internal_id)
            processed_message = processed_message.replace(data.original, replacement)
        
        # Send to n8n webhook
        n8n_payload = {
            "job_id": job_id,
            "internal_id": internal_id,
            "text": processed_message,
            "is_followup": True,
            "callback_url": f"{NOCODB_BASE_URL}/api/callback"  # Example callback URL
        }
        
        try:
            n8n_response = requests.post(N8N_WEBHOOK_URL, json=n8n_payload)
            n8n_response.raise_for_status()
            
            # Simulate a response
            llm_response = f"This is a simulated response to your follow-up message.\n" \
                          f"It would contain any prefix_hash combinations that need to be replaced."
            
            # Replace hashed values with original data
            processed_response = llm_response
            for data in sensitive_data:
                replacement = data.get_replacement(internal_id)
                processed_response = processed_response.replace(replacement, data.original)
            
            # Add response to chat memory
            self.nocodb_client.add_chat_memory(
                job_id=job_id_int,
                internal_id=internal_id,
                message=processed_response
            )
            
            return processed_response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with n8n: {e}")
            raise


# Simple example of how to use the processor
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python ocr_anymize_integration.py <document_path> [prompt]")
        sys.exit(1)
    
    document_path = sys.argv[1]
    user_prompt = sys.argv[2] if len(sys.argv) > 2 else ""
    
    processor = AnymizeOCRProcessor(user_id=1)  # Default user ID
    
    try:
        result = processor.process_document(document_path, user_prompt)
        
        print("\n--- Original Text ---")
        print(result.original_text[:500] + "..." if len(result.original_text) > 500 else result.original_text)
        
        print("\n--- Processed Text (with sensitive data replaced) ---")
        print(result.processed_text[:500] + "..." if len(result.processed_text) > 500 else result.processed_text)
        
        print("\n--- LLM Response ---")
        print(result.llm_response)
        
        print("\n--- Processed Response (with original data restored) ---")
        print(result.processed_response)
        
        print("\n--- Sensitive Data Detected ---")
        for data in result.sensitive_data:
            print(f"{data.prefix_name}: {data.original} -> {data.prefix_code}_{data.hash_value}")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
