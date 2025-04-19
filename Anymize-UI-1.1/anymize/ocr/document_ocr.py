import os
import logging
import docx2txt
from tika import parser as tika_parser

from ocr.config import ensure_directories
from ocr.pdf_ocr import extract_text_from_pdf_with_pymupdf, extract_text_from_pdf_with_ocr
from ocr.image_ocr import extract_text_from_image
from ocr.handwritten_ocr import extract_handwritten_text

# Optional import - commented out since calamari-ocr is not installed
# from ocr.calamari_ocr import extract_text_with_calamari, is_likely_handwritten

# Define fallback functions if calamari is not available
def is_likely_handwritten(image_path):
    """Fallback function when calamari is not available"""
    logging.info(f"Calamari OCR not available, assuming text is not handwritten for {image_path}")
    return False

def extract_text_with_calamari(image_path):
    """Fallback function when calamari is not available"""
    logging.info(f"Calamari OCR not available for {image_path}")
    return None

def extract_text_from_docx(docx_path):
    """Extract text from DOCX file
    
    Args:
        docx_path: Path to the DOCX file
        
    Returns:
        string: Extracted text
    """
    try:
        text = docx2txt.process(docx_path)
        return text
    except Exception as e:
        logging.error(f"Error in DOCX extraction: {e}")
        return None

def extract_text_with_tika(file_path):
    """Extract text using Apache Tika (very universal method)
    
    This is a great fallback method as it handles many file formats.
    
    Args:
        file_path: Path to the file
        
    Returns:
        string: Extracted text
    """
    try:
        parsed = tika_parser.from_file(file_path)
        return parsed.get("content", "").strip()
    except Exception as e:
        logging.error(f"Error in Tika extraction: {e}")
        return None

def extract_text_from_text_file(file_path):
    """Extract text from plain text files
    
    Args:
        file_path: Path to the text file
        
    Returns:
        string: File contents
    """
    try:
        # First try UTF-8 encoding
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except UnicodeDecodeError:
        # If UTF-8 fails, try ISO-8859-1 (Latin-1)
        try:
            with open(file_path, 'r', encoding='iso-8859-1') as file:
                return file.read()
        except Exception as e:
            logging.error(f"Error reading text file: {e}")
            return None
    except Exception as e:
        logging.error(f"Error reading text file: {e}")
        return None

def extract_text_from_file(file_path, handwritten=False):
    """Extract text from various file formats using multiple methods
    
    This is the main function to call when processing any file.
    It will automatically select the appropriate extraction method and
    try multiple approaches if needed.
    
    Args:
        file_path: Path to the file
        handwritten: If True, optimize OCR for handwritten text (deprecated, auto-detection is used)
        
    Returns:
        string: Extracted text
    """
    # Ensure necessary directories exist
    ensure_directories()
    
    # Get file extension
    file_extension = os.path.splitext(file_path)[1].lower()
    
    extracted_text = None
    logging.info(f"======= BEGINNING TEXT EXTRACTION FROM: {file_path} =======")
    logging.info(f"File extension: {file_extension}")
    
    # Force always try handwritten detection for image files 
    auto_detect_handwritten = True
    
    if file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif']:
        # For images, always check if it contains handwritten text
        handwritten_score = is_likely_handwritten(file_path)
        logging.info(f"Handwriting detection score: {handwritten_score}")
        
        # Process image with multiple methods and return the best result
        logging.info("TRYING MULTIPLE OCR METHODS FOR IMAGE:")
        
        # Method 1: Try Calamari OCR first - often best for handwritten text
        logging.info("Method 1: Trying Calamari OCR...")
        calamari_text = extract_text_with_calamari(file_path)
        
        if calamari_text and len(calamari_text.strip()) > 10 and not calamari_text.startswith("ERROR:"):
            logging.info(f"✓ Calamari OCR succeeded with {len(calamari_text)} chars")
            extracted_text = calamari_text
        else:
            logging.info("✗ Calamari OCR failed or returned too little text")
        
        # Method 2: Try handwritten OCR if Calamari failed or text is too short
        if not extracted_text or len(extracted_text.strip()) < 20:
            logging.info("Method 2: Trying specialized handwritten OCR...")
            handwritten_text = extract_handwritten_text(file_path)
            if handwritten_text and len(handwritten_text.strip()) > 10:
                logging.info(f"✓ Handwritten OCR succeeded with {len(handwritten_text)} chars")
                extracted_text = handwritten_text
            else:
                logging.info("✗ Handwritten OCR failed or returned too little text")
        
        # Method 3: Try standard image OCR as last resort
        if not extracted_text or len(extracted_text.strip()) < 20:
            logging.info("Method 3: Trying standard Tesseract OCR...")
            image_text = extract_text_from_image(file_path)
            if image_text and len(image_text.strip()) > 10:
                logging.info(f"✓ Standard OCR succeeded with {len(image_text)} chars")
                extracted_text = image_text
            else:
                logging.info("✗ Standard OCR failed or returned too little text")
    
    elif file_extension in ['.pdf']:
        logging.info("PROCESSING PDF FILE:")
        # Method 1: First try PyMuPDF for searchable PDFs
        logging.info("Method 1: Trying PyMuPDF for searchable PDF...")
        pdf_text = extract_text_from_pdf_with_pymupdf(file_path)
        
        if pdf_text and len(pdf_text.strip()) > 100:
            logging.info(f"✓ PyMuPDF succeeded with {len(pdf_text)} chars")
            extracted_text = pdf_text
        else:
            logging.info("✗ PyMuPDF failed or extracted very little text - likely scanned PDF")
            
            # Method 2: Try advanced OCR for scanned PDFs
            logging.info("Method 2: Trying specialized OCR for scanned PDF...")
            # Force handwritten mode to ensure best results with mixed content
            ocr_text = extract_text_from_pdf_with_ocr(file_path, handwritten=True)
            if ocr_text and len(ocr_text.strip()) > 10:
                logging.info(f"✓ PDF OCR succeeded with {len(ocr_text)} chars")
                extracted_text = ocr_text
            else:
                logging.info("✗ PDF OCR failed or returned too little text")
    
    elif file_extension in ['.docx']:
        extracted_text = extract_text_from_docx(file_path)
    
    elif file_extension in ['.txt', '.json', '.py', '.js', '.html', '.css', '.md', '.csv', '.xml']:
        # For text files, just read the content directly
        extracted_text = extract_text_from_text_file(file_path)
    
    # Apache Tika as fallback for other formats
    if not extracted_text:
        logging.info(f"Using Apache Tika for file type: {file_extension}")
        extracted_text = extract_text_with_tika(file_path)
    
    # If we still don't have any text, return a message
    if not extracted_text:
        return "Keine Textextraktion möglich."
    
    return extracted_text
