import os
import logging
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import fitz  # PyMuPDF for PDF text extraction
from pdf2image import convert_from_path  # PDF to image conversion

from ocr.config import (
    TEMP_PDF_PAGES_DIR, ensure_directories,
    TESSERACT_CONFIG_STANDARD, TESSERACT_CONFIG_HANDWRITTEN,
    MIN_TEXT_LENGTH_STANDARD
)

# Lazy loaded EasyOCR - we'll import from another module
from ocr.handwritten_ocr import get_easyocr_results

def extract_text_from_pdf_with_pymupdf(pdf_path):
    """Extract text from PDF using PyMuPDF (good for searchable PDFs)
    
    This method works well for PDFs with embedded text but not for scanned documents.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text as string or None if extraction failed
    """
    try:
        text = ""
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        logging.error(f"Error in PyMuPDF extraction: {e}")
        return None

def extract_text_from_pdf_with_ocr(pdf_path, handwritten=False):
    """Extract text from PDF using OCR (good for scanned PDFs without embedded text)
    
    This method converts PDF pages to images and performs OCR on each page.
    It tries multiple OCR approaches depending on the content and handwritten flag.
    
    Args:
        pdf_path: Path to the PDF file
        handwritten: If True, optimize for handwritten text recognition
        
    Returns:
        Extracted text as string with page markers
    """
    try:
        text = ""
        # Ensure temp directory exists
        ensure_directories()
        
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=300)
        
        for i, image in enumerate(images):
            # Save the page image for potential use by EasyOCR later
            temp_img_path = os.path.join(TEMP_PDF_PAGES_DIR, f"page_{i+1}.png")
            image.save(temp_img_path)
            
            # Apply grayscale conversion for better OCR
            grayscale_image = image.convert('L')
            
            if not handwritten:
                # First try regular Tesseract OCR
                page_text = pytesseract.image_to_string(grayscale_image, config=TESSERACT_CONFIG_STANDARD)
                
                # If we get reasonable text from standard OCR, use it and continue to next page
                if page_text and len(page_text.strip()) > MIN_TEXT_LENGTH_STANDARD:
                    text += f"\n--- Page {i+1} ---\n{page_text}"
                    continue
            
            # If handwritten flag is true or standard OCR didn't get good results:
            # Apply additional processing for handwritten text
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(grayscale_image)
            enhanced_image = enhancer.enhance(2.0)
            
            # Apply light blur to reduce noise
            processed_image = enhanced_image.filter(ImageFilter.GaussianBlur(radius=0.5))
            
            # Try Tesseract with handwriting-optimized settings
            logging.info(f"Applying Tesseract handwritten text recognition for PDF page {i+1}")
            tesseract_text = pytesseract.image_to_string(processed_image, config=TESSERACT_CONFIG_HANDWRITTEN)
            
            if tesseract_text and len(tesseract_text.strip()) > MIN_TEXT_LENGTH_STANDARD:
                # If Tesseract gets reasonable text with handwritten settings, use it
                text += f"\n--- Page {i+1} ---\n{tesseract_text}"
            else:
                # Otherwise try EasyOCR as a last resort
                logging.info(f"Tesseract OCR insufficient for page {i+1}, trying EasyOCR")
                easyocr_text = get_easyocr_results(temp_img_path)
                
                if easyocr_text and len(easyocr_text.strip()) > 0:
                    logging.info(f"Successfully extracted text with EasyOCR for page {i+1}")
                    text += f"\n--- Page {i+1} ---\n{easyocr_text}"
                else:
                    # If all methods fail, use whatever we got from Tesseract (even if it's not great)
                    text += f"\n--- Page {i+1} ---\n{tesseract_text or 'No text could be extracted from this page.'}"
        
        # Clean up temporary files
        for file in os.listdir(TEMP_PDF_PAGES_DIR):
            os.remove(os.path.join(TEMP_PDF_PAGES_DIR, file))
        
        return text
    except Exception as e:
        logging.error(f"Error in PDF OCR extraction: {e}")
        return None
