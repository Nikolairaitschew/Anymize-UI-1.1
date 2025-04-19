import logging
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

from ocr.config import (
    TESSERACT_CONFIG_STANDARD, 
    MIN_TEXT_LENGTH_IMAGE
)

def extract_text_with_tesseract_standard(image):
    """Extract text using standard Tesseract OCR
    
    Best for printed text in images.
    
    Args:
        image: PIL.Image object (already opened image)
        
    Returns:
        string: Extracted text
    """
    try:
        # For printed text, use standard configuration
        text = pytesseract.image_to_string(image, config=TESSERACT_CONFIG_STANDARD)
        return text
    except Exception as e:
        logging.error(f"Error in standard Tesseract OCR: {e}")
        return ""

def preprocess_image(image_path, enhance_contrast=True, apply_blur=False, 
                    binarize=False, threshold=128, denoise=False):
    """Preprocess image for better OCR results
    
    Args:
        image_path: Path to the image file
        enhance_contrast: If True, enhance image contrast
        apply_blur: If True, apply Gaussian blur to reduce noise
        binarize: If True, convert image to binary (black and white)
        threshold: Threshold value for binarization (0-255)
        denoise: If True, apply denoising filter
        
    Returns:
        PIL.Image: Processed image
    """
    try:
        image = Image.open(image_path)
        
        # Convert to grayscale
        processed_image = image.convert('L')
        
        # Enhance contrast if requested
        if enhance_contrast:
            enhancer = ImageEnhance.Contrast(processed_image)
            processed_image = enhancer.enhance(1.5)  # Adjust contrast level
        
        # Apply blur if requested
        if apply_blur:
            processed_image = processed_image.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        # Convert to binary if requested
        if binarize:
            processed_image = processed_image.point(lambda x: 0 if x < threshold else 255, '1')
        
        # Apply denoise filter if requested
        if denoise:
            processed_image = processed_image.filter(ImageFilter.MedianFilter(size=3))
        
        return processed_image
    
    except Exception as e:
        logging.error(f"Error preprocessing image: {e}")
        return None

def extract_text_from_image(image_path, preprocessing=True):
    """Extract text from image using standard OCR
    
    Args:
        image_path: Path to the image file
        preprocessing: If True, apply preprocessing steps
        
    Returns:
        string: Extracted text
    """
    try:
        if preprocessing:
            # Apply standard preprocessing
            processed_image = preprocess_image(
                image_path,
                enhance_contrast=True,
                apply_blur=False,
                binarize=False
            )
        else:
            # Just open the image
            processed_image = Image.open(image_path).convert('L')
        
        # Extract text using standard Tesseract configuration
        text = extract_text_with_tesseract_standard(processed_image)
        
        # If we don't get a reasonable amount of text, try with different preprocessing
        if not text or len(text.strip()) < MIN_TEXT_LENGTH_IMAGE:
            logging.info("Standard preprocessing produced minimal results, trying alternatives")
            
            # Try with binarization
            binary_image = preprocess_image(
                image_path,
                enhance_contrast=True,
                apply_blur=False,
                binarize=True,
                threshold=150
            )
            binary_text = extract_text_with_tesseract_standard(binary_image)
            
            if binary_text and len(binary_text.strip()) > len(text.strip()):
                text = binary_text
        
        return text
    
    except Exception as e:
        logging.error(f"Error in image OCR: {e}")
        return None
