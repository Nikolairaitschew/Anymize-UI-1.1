import logging
import easyocr
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

from ocr.config import (
    DEFAULT_LANGUAGES,
    TESSERACT_CONFIG_HANDWRITTEN,
    MIN_TEXT_LENGTH_HANDWRITTEN
)

# Initialize EasyOCR reader (lazy loading - will only initialize when needed)
easyocr_reader = None

def get_easyocr_reader():
    """Initialize and return the EasyOCR reader
    
    Uses lazy loading to avoid initializing unless needed.
    
    Returns:
        easyocr.Reader: Initialized reader object
    """
    global easyocr_reader
    if easyocr_reader is None:
        logging.info("Initializing EasyOCR reader for the first time...")
        easyocr_reader = easyocr.Reader(DEFAULT_LANGUAGES)  # English and German
    return easyocr_reader

def get_easyocr_results(image_path):
    """Extract text from image using EasyOCR
    
    Args:
        image_path: Path to the image file
        
    Returns:
        string: Extracted text joined by newlines
    """
    try:
        reader = get_easyocr_reader()
        result = reader.readtext(image_path)
        
        # Extract all text from the EasyOCR result
        easyocr_text = "\n".join([item[1] for item in result])
        
        if easyocr_text and len(easyocr_text.strip()) > 0:
            logging.info(f"Successfully extracted text with EasyOCR: {len(easyocr_text)} characters")
            return easyocr_text
        else:
            logging.warning("EasyOCR produced minimal results")
            return ""
    except Exception as e:
        logging.error(f"Error in EasyOCR extraction: {e}")
        return ""

def extract_handwritten_text(image_path, try_standard_first=False):
    """Full pipeline for extracting handwritten text
    
    This function implements a multi-stage approach with enhanced preprocessing:
    1. Apply multiple preprocessing techniques optimized for handwritten text
    2. Try EasyOCR first (often better for cursive handwriting)
    3. Also try Tesseract with specialized handwriting configuration
    4. Return the best result from all methods
    
    Args:
        image_path: Path to image file
        try_standard_first: If True, first try standard Tesseract OCR
        
    Returns:
        string: Extracted text from the best method
    """
    try:
        logging.info(f"Beginning advanced handwritten text extraction for {image_path}")
        image = Image.open(image_path)
        
        # Store results from different approaches to compare later
        all_results = {}
        
        # APPROACH 1: Standard OCR (optional)
        if try_standard_first:
            from ocr.image_ocr import extract_text_with_tesseract_standard
            text = extract_text_with_tesseract_standard(image)
            all_results["standard"] = text
            logging.info(f"Standard OCR result: {len(text) if text else 0} characters")

        # APPROACH 2: EasyOCR with original image
        # Often works best for handwritten text without preprocessing
        logging.info("Applying EasyOCR (optimized for handwritten text)")
        easyocr_text = get_easyocr_results(image_path)
        all_results["easyocr_original"] = easyocr_text
        logging.info(f"EasyOCR on original image: {len(easyocr_text) if easyocr_text else 0} characters")
        
        # APPROACH 3: Enhanced preprocessing for difficult handwriting
        # Convert to grayscale
        grayscale_image = image.convert('L')
        
        # Create multiple preprocessed versions for best results
        
        # Version 1: High contrast
        contrast_enhancer = ImageEnhance.Contrast(grayscale_image)
        high_contrast = contrast_enhancer.enhance(2.5)  # Increased contrast
        
        # Version 2: Sharpened + contrast
        sharpener = ImageEnhance.Sharpness(grayscale_image)
        sharpened = sharpener.enhance(2.0)  # Increase sharpness
        contrast_sharp = ImageEnhance.Contrast(sharpened).enhance(1.8)
        
        # Version 3: Brightness + contrast adjustment
        brightness_enhancer = ImageEnhance.Brightness(grayscale_image)
        brightened = brightness_enhancer.enhance(1.2)  # Slight brightness increase
        bright_contrast = ImageEnhance.Contrast(brightened).enhance(1.8)
        
        # Try Tesseract with each preprocessing variant
        logging.info("Trying multiple preprocessing techniques with Tesseract")
        
        # Tesseract with high contrast
        tesseract_contrast = pytesseract.image_to_string(
            high_contrast, 
            config=TESSERACT_CONFIG_HANDWRITTEN
        )
        all_results["tesseract_high_contrast"] = tesseract_contrast
        logging.info(f"Tesseract with high contrast: {len(tesseract_contrast) if tesseract_contrast else 0} chars")
        
        # Tesseract with sharpened + contrast
        tesseract_sharp = pytesseract.image_to_string(
            contrast_sharp, 
            config=TESSERACT_CONFIG_HANDWRITTEN
        )
        all_results["tesseract_sharp"] = tesseract_sharp
        logging.info(f"Tesseract with sharpening: {len(tesseract_sharp) if tesseract_sharp else 0} chars")
        
        # Tesseract with brightness + contrast
        tesseract_bright = pytesseract.image_to_string(
            bright_contrast, 
            config=TESSERACT_CONFIG_HANDWRITTEN
        )
        all_results["tesseract_bright"] = tesseract_bright
        logging.info(f"Tesseract with brightness: {len(tesseract_bright) if tesseract_bright else 0} chars")
        
        # Try EasyOCR on the best preprocessed image
        # First determine which preprocessing gave best Tesseract results
        tesseract_lengths = {
            "high_contrast": len(tesseract_contrast.strip()) if tesseract_contrast else 0,
            "sharp": len(tesseract_sharp.strip()) if tesseract_sharp else 0,
            "bright": len(tesseract_bright.strip()) if tesseract_bright else 0
        }
        
        best_preprocess = max(tesseract_lengths.items(), key=lambda x: x[1])[0]
        logging.info(f"Best preprocessing method from Tesseract tests: {best_preprocess}")
        
        # Apply EasyOCR to the best preprocessed image
        best_image = None
        if best_preprocess == "high_contrast":
            best_image = high_contrast
        elif best_preprocess == "sharp":
            best_image = contrast_sharp
        elif best_preprocess == "bright":
            best_image = bright_contrast
        
        if best_image:
            # Save the best preprocessed image temporarily
            temp_path = f"{os.path.splitext(image_path)[0]}_preprocessed.png"
            best_image.save(temp_path)
            
            # Apply EasyOCR to the preprocessed image
            logging.info(f"Applying EasyOCR to preprocessed image ({best_preprocess})")
            easyocr_preprocessed = get_easyocr_results(temp_path)
            all_results["easyocr_preprocessed"] = easyocr_preprocessed
            logging.info(f"EasyOCR on preprocessed: {len(easyocr_preprocessed) if easyocr_preprocessed else 0} chars")
            
            # Clean up temp file
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        # Select the best result based on text length
        result_lengths = {k: len(v.strip()) if v else 0 for k, v in all_results.items()}
        best_method = max(result_lengths.items(), key=lambda x: x[1])[0]
        best_text = all_results[best_method]
        
        logging.info(f"Best OCR method: {best_method} with {result_lengths[best_method]} characters")
        
        if best_text and len(best_text.strip()) > 0:
            return best_text
        else:
            logging.warning("All OCR methods produced minimal results")
            return "No readable text could be extracted from the handwritten image."
            
    except Exception as e:
        logging.error(f"Error in handwritten text extraction: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return "Error processing handwritten text."
