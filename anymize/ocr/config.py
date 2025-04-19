# Fix for OpenMP runtime initialization issue
import os
import logging

# Set environment variables
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

# Common temp directory configuration
UPLOAD_FOLDER = 'uploads'
TEMP_PDF_PAGES_DIR = os.path.join(UPLOAD_FOLDER, 'temp_pdf_pages')

# Ensure directories exist
def ensure_directories():
    """Create necessary directories if they don't exist"""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if not os.path.exists(TEMP_PDF_PAGES_DIR):
        os.makedirs(TEMP_PDF_PAGES_DIR)

# Language configuration for OCR
DEFAULT_LANGUAGES = ['en', 'de']  # English and German

# Tesseract configuration
TESSERACT_CONFIG_STANDARD = '--psm 3 --oem 3 -l eng+deu'  # Standard config for printed text
TESSERACT_CONFIG_HANDWRITTEN = '--psm 13 --oem 3 -l eng+deu'  # Config optimized for handwritten text

# OCR quality thresholds
MIN_TEXT_LENGTH_STANDARD = 50  # Minimum text length to consider OCR successful for pages
MIN_TEXT_LENGTH_IMAGE = 10     # Minimum text length for images
MIN_TEXT_LENGTH_HANDWRITTEN = 20  # Minimum length for handwritten text detection
