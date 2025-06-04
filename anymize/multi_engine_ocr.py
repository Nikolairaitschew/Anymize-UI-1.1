"""
Multi-Engine OCR Pipeline

This module implements a comprehensive OCR pipeline that combines multiple
OCR engines to handle various document types and text formats. It dynamically
routes document portions to the appropriate OCR engines based on content type.

Main components:
- Document preprocessing (cleaning, deskewing)
- Content type classification (printed/handwritten/table detection)
- OCR engine routing (Tesseract/Kraken/PaddleOCR/etc.)
- Result merging and post-processing
- Output generation

Usage:
    from multi_engine_ocr import MultiEngineOCR
    
    ocr = MultiEngineOCR()
    result = ocr.process_document("document.pdf")
    print(result.text)  # Get plain text
    # or
    result.save_as_pdf("searchable_document.pdf")  # Save as searchable PDF
"""

import os
import sys
import logging
import tempfile
import json
from typing import List, Dict, Tuple, Union, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import pypdfium2 as pdfium  # For PDF handling
import re
import spacy  # For language detection and NLP
try:
    import enchant  # For spell checking
    ENCHANT_AVAILABLE = True
except ImportError:
    ENCHANT_AVAILABLE = False

# Import optional components (with fallbacks for missing dependencies)
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False

try:
    import kraken
    from kraken import binarization, pageseg, rpred
    KRAKEN_AVAILABLE = True
except ImportError:
    KRAKEN_AVAILABLE = False
    
try:
    import calamari_ocr
    from calamari_ocr.ocr.predict.predictor import Predictor, MultiPredictor
    CALAMARI_AVAILABLE = True
except ImportError:
    CALAMARI_AVAILABLE = False

try:
    import doctr
    from doctr.models import ocr_predictor
    DOCTR_AVAILABLE = True
except ImportError:
    DOCTR_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Define content types for classification
class ContentType(Enum):
    PRINTED_TEXT = "printed_text"
    HANDWRITTEN_TEXT = "handwritten_text"
    TABULAR_DATA = "tabular_data"
    MATHEMATICAL = "mathematical"
    NON_LATIN_SCRIPT = "non_latin_script"
    SCENE_TEXT = "scene_text"
    

@dataclass
class TextBlock:
    """Represents a block of text with position and metadata"""
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int] = None  # (x0, y0, x1, y1)
    page_num: int = 0
    content_type: ContentType = ContentType.PRINTED_TEXT
    engine: str = "unknown"
    language: str = "en"


@dataclass
class OCRResult:
    """Container for OCR results"""
    text: str = ""
    blocks: List[TextBlock] = field(default_factory=list)
    pages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def save_as_pdf(self, output_path: str):
        """Save as searchable PDF with text overlay"""
        try:
            import fitz  # PyMuPDF
            
            if "source_pdf" not in self.metadata:
                logger.warning("No source PDF available to save as searchable PDF")
                return
                
            # Open the source PDF
            source_pdf = self.metadata["source_pdf"]
            doc = fitz.open(source_pdf)
            
            # Add text to each page
            for page_num, page in enumerate(self.pages):
                if page_num >= len(doc):
                    break
                    
                pdf_page = doc[page_num]
                
                # Get blocks for this page
                page_blocks = [block for block in self.blocks if block.page_num == page_num]
                
                # Add text annotations for each block
                for block in page_blocks:
                    if not block.bbox:
                        continue
                        
                    x0, y0, x1, y1 = block.bbox
                    rect = fitz.Rect(x0, y0, x1, y1)
                    pdf_page.insert_text(
                        rect.tl,  # top-left point
                        block.text,
                        fontsize=12,
                        color=(0, 0, 0)
                    )
            
            # Save the modified PDF
            doc.save(output_path)
            logger.info(f"Saved searchable PDF to {output_path}")
            
        except ImportError:
            logger.error("PyMuPDF (fitz) is not installed. Cannot save as searchable PDF.")
        except Exception as e:
            logger.error(f"Error saving searchable PDF: {e}")
        
    def to_json(self, path: str = None):
        """Export results to JSON format"""
        data = {
            "text": self.text,
            "blocks": [
                {
                    "text": block.text,
                    "confidence": block.confidence,
                    "bbox": block.bbox,
                    "page_num": block.page_num,
                    "content_type": block.content_type.value,
                    "engine": block.engine,
                    "language": block.language
                } for block in self.blocks
            ],
            "metadata": {k: v for k, v in self.metadata.items() if isinstance(v, (str, int, float, bool, list, dict))}
        }
        
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
        return json.dumps(data, ensure_ascii=False)


class PreprocessingPipeline:
    """Handles document preprocessing to improve OCR quality"""
    
    def __init__(self):
        pass
    
    def deskew(self, image: np.ndarray) -> np.ndarray:
        """Correct image skew to make text horizontal"""
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
                
            # Apply threshold to get binary image
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Find all contours
            contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            
            # Find text lines using contours
            angles = []
            for contour in contours:
                # Filter small contours
                if cv2.contourArea(contour) < 50:
                    continue
                
                # Get minimal rectangle
                rect = cv2.minAreaRect(contour)
                width, height = rect[1]
                angle = rect[2]
                
                # Ensure angle is between -45 and 45 degrees
                if width < height:
                    angle = angle - 90
                
                # Ignore near-vertical lines
                if abs(angle) < 45:
                    angles.append(angle)
            
            if not angles:
                return image
                
            # Get median angle (more robust than mean)
            skew_angle = np.median(angles)
            
            # Only deskew if angle is significant
            if abs(skew_angle) < 0.5:
                return image
                
            # Rotate image to correct skew
            h, w = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
            rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, 
                                    borderMode=cv2.BORDER_REPLICATE)
            
            logger.info(f"Deskewed image by {skew_angle:.2f} degrees")
            return rotated
            
        except Exception as e:
            logger.warning(f"Deskew failed: {str(e)}")
            return image
    
    def clean_image(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """Apply various preprocessing techniques and return multiple versions"""
        result = {}
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
            
        result["gray"] = gray
        
        # Otsu's binarization
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        result["otsu"] = otsu
        
        # Adaptive thresholding
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY, 11, 2)
        result["adaptive"] = adaptive
        
        # Noise removal
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        _, denoised_bin = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        result["denoised"] = denoised_bin
        
        # High contrast
        pil_img = Image.fromarray(gray)
        enhancer = ImageEnhance.Contrast(pil_img)
        high_contrast_pil = enhancer.enhance(2.0)
        high_contrast = np.array(high_contrast_pil)
        _, high_contrast_bin = cv2.threshold(high_contrast, 0, 255, 
                                           cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        result["high_contrast"] = high_contrast_bin
        
        logger.info(f"Generated {len(result)} preprocessed versions")
        return result
    
    def process(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """Complete preprocessing pipeline"""
        # Deskew first
        deskewed = self.deskew(image)
        
        # Then apply cleaning methods
        processed_versions = self.clean_image(deskewed)
        
        # Add the original deskewed image
        processed_versions["original"] = deskewed
        
        return processed_versions


class ContentClassifier:
    """Detects content types within document images"""
    
    def __init__(self):
        # Load any necessary models or classifiers here
        self.min_handwritten_area = 100  # Min contour area for handwriting
        
    def is_likely_handwritten(self, image: np.ndarray) -> float:
        """Evaluate likelihood that image contains handwritten text"""
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 1. Check variance of pixel intensities
            # Handwritten text often has higher variance due to uneven strokes
            pixel_std = np.std(gray)
            
            # 2. Edge detection - handwriting tends to have more varied edges
            edges = cv2.Canny(gray, 100, 200)
            edge_density = np.sum(edges > 0) / (gray.shape[0] * gray.shape[1])
            
            # 3. Check for connected components (blobs)
            # Handwriting tends to have more irregular blobs
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(thresh)
            
            # Filter out very small components (noise)
            valid_components = [s for s in stats if s[4] > self.min_handwritten_area]  # Area
            avg_component_size = np.mean([s[4] for s in valid_components]) if valid_components else 0
            component_ratio = len(valid_components) / (gray.shape[0] * gray.shape[1]) if valid_components else 0
            
            # 4. Calculate histogram of oriented gradients (simplified)
            gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
            gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
            mag, ang = cv2.cartToPolar(gx, gy)
            gradient_variance = np.std(ang)
            
            # Calculate a combined score
            handwritten_likelihood = (
                (pixel_std > 50) * 0.3 +  # Higher variance suggests handwriting
                (edge_density > 0.1) * 0.2 +  # More edges suggest handwriting
                (avg_component_size < 100) * 0.2 +  # Smaller components suggest handwriting
                (component_ratio > 0.001) * 0.15 +  # More components per area suggest handwriting
                (gradient_variance > 0.5) * 0.15  # More varied strokes suggest handwriting
            )
            
            logger.info(f"Handwritten likelihood: {handwritten_likelihood:.2f}")
            return handwritten_likelihood
            
        except Exception as e:
            logger.warning(f"Handwriting detection failed: {str(e)}")
            return 0.0
    
    def has_table(self, image: np.ndarray) -> Tuple[bool, List[Tuple]]:
        """Detect tables and return their coordinates"""
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
                
            # Adaptive threshold
            binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY_INV, 11, 2)
            
            # Dilate to connect lines
            kernel = np.ones((3, 3), np.uint8)
            dilated = cv2.dilate(binary, kernel, iterations=1)
            
            # Find horizontal lines
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            horizontal_lines = cv2.morphologyEx(dilated, cv2.MORPH_OPEN, horizontal_kernel)
            
            # Find vertical lines
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
            vertical_lines = cv2.morphologyEx(dilated, cv2.MORPH_OPEN, vertical_kernel)
            
            # Combine lines
            table_mask = cv2.bitwise_or(horizontal_lines, vertical_lines)
            
            # Find contours around table cells
            contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter contours and find table regions
            table_regions = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 1000:  # Minimum table area
                    x, y, w, h = cv2.boundingRect(contour)
                    # Check if shape is roughly rectangular
                    rect_area = w * h
                    if area / rect_area > 0.1:  # Fill ratio check
                        table_regions.append((x, y, x+w, y+h))
            
            # If we found table regions, return True and the regions
            if table_regions:
                logger.info(f"Detected {len(table_regions)} table regions")
                return True, table_regions
            else:
                return False, []
                
        except Exception as e:
            logger.warning(f"Table detection failed: {str(e)}")
            return False, []
    
    def detect_script(self, image: np.ndarray) -> str:
        """Detect script type (Latin, Chinese, Arabic, etc.)"""
        try:
            # Simple approach: use Tesseract's script detection
            # Save image temporarily
            with tempfile.NamedTemporaryFile(suffix='.png') as tmp:
                cv2.imwrite(tmp.name, image)
                
                # Run Tesseract with script detection (psm 0)
                output = pytesseract.image_to_osd(tmp.name)
                
                # Extract script info from Tesseract OSD
                script_lines = [line for line in output.split('\n') if 'Script:' in line]
                if script_lines:
                    script = script_lines[0].split('Script:')[1].strip()
                    logger.info(f"Detected script: {script}")
                    
                    # Map Tesseract script names to our categories
                    if script in ['Latin', 'Fraktur']:
                        return 'latin'
                    elif script in ['Han', 'Hangul', 'Japanese']:
                        return 'cjk'  # Chinese, Japanese, Korean
                    elif script == 'Arabic':
                        return 'arabic'
                    elif script == 'Devanagari':
                        return 'devanagari'
                    elif script == 'Cyrillic':
                        return 'cyrillic'
                    else:
                        return script.lower()
                
            return 'latin'  # Default
            
        except Exception as e:
            logger.warning(f"Script detection failed: {str(e)}")
            return 'latin'  # Default to Latin script
    
    def is_math_content(self, image: np.ndarray) -> bool:
        """Detect if image contains mathematical formulas"""
        # This is a simplified implementation
        # In practice, you'd need a more sophisticated model
        try:
            # Extract text with Tesseract
            with tempfile.NamedTemporaryFile(suffix='.png') as tmp:
                cv2.imwrite(tmp.name, image)
                text = pytesseract.image_to_string(tmp.name)
                
            # Check for common math symbols
            math_symbols = ['=', '+', '-', '×', '÷', '∫', '∑', '∏', '√', '∞', 'π', '∆', '∇', 
                           '≈', '≠', '≤', '≥', '∈', '∉', '⊂', '⊃', '∧', '∨']
            
            symbol_count = sum(text.count(symbol) for symbol in math_symbols)
            
            # Check for digit density
            digit_count = sum(c.isdigit() for c in text)
            
            # Calculate math likelihood based on symbol and digit density
            if len(text) > 0:
                math_likelihood = (symbol_count / len(text)) * 3 + (digit_count / len(text))
                
                # Return True if likelihood exceeds threshold
                return math_likelihood > 0.3
            
            return False
            
        except Exception as e:
            logger.warning(f"Math content detection failed: {str(e)}")
            return False
    
    def is_scene_text(self, image: np.ndarray) -> bool:
        """Detect if image contains text in a natural scene vs document"""
        try:
            # Check color variance - scene images typically have higher variance
            if len(image.shape) == 3:  # Color image
                # Calculate variance across all channels
                var_r = np.var(image[:, :, 0])
                var_g = np.var(image[:, :, 1])
                var_b = np.var(image[:, :, 2])
                color_variance = (var_r + var_g + var_b) / 3
                
                # Calculate entropy to measure complexity
                entropy = 0
                for i in range(3):
                    hist = cv2.calcHist([image], [i], None, [256], [0, 256])
                    hist = hist / hist.sum()  # Normalize
                    hist = hist[hist > 0]  # Remove zeros
                    entropy -= np.sum(hist * np.log2(hist))
                
                # Check white pixel ratio (documents have more white)
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                white_ratio = np.sum(gray > 240) / (gray.shape[0] * gray.shape[1])
                
                # Combine metrics
                scene_likelihood = (
                    (color_variance > 2000) * 0.3 +  # High color variance
                    (entropy > 5) * 0.3 +            # High entropy
                    (white_ratio < 0.5) * 0.4        # Less white space
                )
                
                logger.info(f"Scene text likelihood: {scene_likelihood:.2f}")
                return scene_likelihood > 0.5
                
            return False
            
        except Exception as e:
            logger.warning(f"Scene text detection failed: {str(e)}")
            return False
    
    def classify_region(self, image: np.ndarray) -> Dict[ContentType, float]:
        """Classify content types in an image region with confidence scores"""
        # Initialize result with zero confidence for all types
        result = {content_type: 0.0 for content_type in ContentType}
        
        # Check handwritten likelihood
        handwritten_score = self.is_likely_handwritten(image)
        result[ContentType.HANDWRITTEN_TEXT] = handwritten_score
        
        # Set printed text likelihood as inverse of handwritten
        # (with some overlap possible)
        result[ContentType.PRINTED_TEXT] = max(0, 1.0 - handwritten_score * 0.8)
        
        # Check for tables
        has_table, _ = self.has_table(image)
        result[ContentType.TABULAR_DATA] = 0.9 if has_table else 0.0
        
        # Determine script type
        script = self.detect_script(image)
        if script != 'latin':
            result[ContentType.NON_LATIN_SCRIPT] = 0.9
        
        # Check for math content
        if self.is_math_content(image):
            result[ContentType.MATHEMATICAL] = 0.8
        
        # Check for scene text
        if self.is_scene_text(image):
            result[ContentType.SCENE_TEXT] = 0.85
            # If it's scene text, reduce printed text confidence
            result[ContentType.PRINTED_TEXT] *= 0.5
        
        return result
    
    def get_dominant_content_type(self, content_types: Dict[ContentType, float]) -> ContentType:
        """Get the dominant content type based on confidence scores"""
        return max(content_types.items(), key=lambda x: x[1])[0]


class TesseractOCR:
    """Wrapper for Tesseract OCR functionality"""
    
    def __init__(self, langs=None, config=None):
        self.langs = langs if langs else 'eng'
        self.config = config
        
        # Check if Tesseract is installed
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            logger.error(f"Tesseract is not properly installed: {str(e)}")
            raise RuntimeError("Tesseract OCR is not properly installed")
    
    def process_image(self, image: np.ndarray, psm=6) -> Dict[str, any]:
        """
        Process image with Tesseract OCR
        
        Args:
            image: The image as numpy array
            psm: Page segmentation mode (3=auto, 6=single block, etc.)
            
        Returns:
            Dictionary with text and data
        """
        config = f'--psm {psm}'
        if self.config:
            config = f'{config} {self.config}'
            
        # Get text
        text = pytesseract.image_to_string(image, lang=self.langs, config=config)
        
        # Get word data with confidence and bounding boxes
        data = pytesseract.image_to_data(image, lang=self.langs, config=config, 
                                        output_type=pytesseract.Output.DICT)
        
        # Create result with words, confidences, and positions
        result = {
            'text': text,
            'words': [],
            'block_texts': [],
            'confidence': 0.0
        }
        
        # Process word data
        confidences = []
        current_block = []
        current_block_num = -1
        
        for i in range(len(data['text'])):
            word = data['text'][i].strip()
            if not word:
                continue
                
            confidence = float(data['conf'][i])
            if confidence < 0:  # Sometimes Tesseract gives -1 for confidence
                confidence = 0
                
            confidences.append(confidence)
            
            # Get bounding box
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
            
            word_data = {
                'text': word,
                'confidence': confidence,
                'bbox': (x, y, x + w, y + h)
            }
            
            result['words'].append(word_data)
            
            # Group words by block
            block_num = data['block_num'][i]
            if block_num != current_block_num:
                if current_block:
                    result['block_texts'].append(' '.join(current_block))
                current_block = [word]
                current_block_num = block_num
            else:
                current_block.append(word)
        
        # Add the last block
        if current_block:
            result['block_texts'].append(' '.join(current_block))
        
        # Calculate average confidence
        if confidences:
            result['confidence'] = sum(confidences) / len(confidences) / 100.0
        
        return result


class KrakenOCR:
    """Wrapper for Kraken OCR (for handwritten text)"""
    
    def __init__(self, model_path=None):
        if not KRAKEN_AVAILABLE:
            raise ImportError("Kraken is not installed. Install with: pip install kraken")
            
        self.model_path = model_path
        
    def process_image(self, image: np.ndarray) -> Dict[str, any]:
        """Process image with Kraken OCR"""
        # Convert to PIL image as Kraken expects PIL
        pil_image = Image.fromarray(image)
        
        # Binarize the image
        bw_img = binarization.nlbin(pil_image)
        
        # Segment the image into lines
        lines = pageseg.segment(bw_img)
        
        # Load the model - use default if not specified
        if self.model_path and os.path.exists(self.model_path):
            model = rpred.load_any(self.model_path)
        else:
            # Use default model (English)
            model = rpred.load_any()
        
        # Process each line
        result = {
            'text': '',
            'words': [],
            'lines': [],
            'confidence': 0.0
        }
        
        confidences = []
        
        # Process each line
        for line in lines:
            line_img = bw_img.crop(line)
            prediction = rpred.rpred(model, line_img)
            
            line_text = prediction['text']
            result['text'] += line_text + '\n'
            result['lines'].append(line_text)
            
            # Get bounding box
            x0, y0, x1, y1 = line
            
            # Extract confidence
            if 'confidences' in prediction:
                line_confidences = prediction['confidences']
                avg_conf = sum(line_confidences) / len(line_confidences)
                confidences.append(avg_conf)
            else:
                # If confidences not available, use a default
                avg_conf = 0.8
            
            # Add word data (Kraken doesn't split into words, so use the whole line)
            word_data = {
                'text': line_text,
                'confidence': avg_conf,
                'bbox': (x0, y0, x1, y1)
            }
            
            result['words'].append(word_data)
        
        # Calculate average confidence
        if confidences:
            result['confidence'] = sum(confidences) / len(confidences)
        
        return result


class EasyOCR_Engine:
    """Wrapper for EasyOCR"""
    
    def __init__(self, langs=None):
        if not EASYOCR_AVAILABLE:
            raise ImportError("EasyOCR is not installed. Install with: pip install easyocr")
            
        self.langs = langs if langs else ['en']
        
        # Initialize EasyOCR reader
        self.reader = easyocr.Reader(self.langs, gpu=False)
        
    def process_image(self, image: np.ndarray) -> Dict[str, any]:
        """Process image with EasyOCR"""
        # Run EasyOCR
        results = self.reader.readtext(image)
        
        # Extract text and position data
        text_blocks = []
        words = []
        full_text = ""
        confidences = []
        
        for bbox, text, conf in results:
            # Convert bbox from EasyOCR format to (x0, y0, x1, y1)
