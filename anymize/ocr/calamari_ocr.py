import os
import logging
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import calamari_ocr.scripts.predict as calamari_predict
from calamari_ocr.ocr import MultiPredictor
# We've removed all problematic imports and added required PIL imports

def setup_calamari_predictor():
    """Initialize and return a Calamari OCR predictor
    
    Calamari OCR is particularly good at handwritten text recognition.
    It uses an ensemble of models for better accuracy.
    
    Returns:
        MultiPredictor: Initialized Calamari predictor
    """
    try:
        # Simplify the predictor setup to avoid version compatibility issues
        from calamari_ocr.ocr.predictor import PredictorParams
        params = PredictorParams()
        
        # Let Calamari use its built-in models
        # This approach is more compatible with different Calamari versions
        return MultiPredictor(params)
    
    except Exception as e:
        logging.error(f"Error setting up Calamari predictor: {e}")
        return None

def extract_text_with_calamari(image_path):
    """Use Calamari OCR to extract text from an image
    
    Calamari OCR is particularly effective for handwritten and historical documents.
    This function applies multiple preprocessing techniques optimized for cursive handwriting.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Extracted text
    """
    logging.info(f"Starting Calamari OCR extraction for: {image_path}")
    
    # Track all results from different preprocessing approaches
    results = {}
    
    try:
        # Open the image and ensure it's in the right format for Calamari
        img = Image.open(image_path)
        logging.info(f"Image loaded, size: {img.size}, mode: {img.mode}")
        
        # Convert to grayscale if needed
        if img.mode != 'L':
            img = img.convert('L')
            logging.info("Converted image to grayscale")
        
        # Create multiple preprocessed versions optimized for different handwriting styles
        
        # 1. Basic preprocessing - high contrast binary
        threshold = 170
        img_binary = img.point(lambda p: 255 if p > threshold else 0)
        temp_binary_path = f"{os.path.splitext(image_path)[0]}_calamari_binary.png"
        img_binary.save(temp_binary_path)
        
        # 2. Contrast enhanced grayscale (better for some cursive styles)
        enhancer = ImageEnhance.Contrast(img)
        img_contrast = enhancer.enhance(2.0)
        temp_contrast_path = f"{os.path.splitext(image_path)[0]}_calamari_contrast.png"
        img_contrast.save(temp_contrast_path)
        
        # 3. Sharpened with medium contrast (better for connected letters)
        sharpener = ImageEnhance.Sharpness(img)
        img_sharp = sharpener.enhance(2.0)
        contrast_sharp = ImageEnhance.Contrast(img_sharp).enhance(1.5)
        temp_sharp_path = f"{os.path.splitext(image_path)[0]}_calamari_sharp.png"
        contrast_sharp.save(temp_sharp_path)
        
        # 4. OpenCV adaptive thresholding (handles uneven lighting well)
        temp_adaptive_path = None
        try:
            import cv2
            img_cv = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            # Resize if the image is very large to improve OCR performance
            h, w = img_cv.shape
            if max(h, w) > 2000:
                scale = 2000 / max(h, w)
                img_cv = cv2.resize(img_cv, (int(w * scale), int(h * scale)))
            
            # Try different adaptive thresholding parameters
            # This often works well with cursive writing
            img_adaptive1 = cv2.adaptiveThreshold(
                img_cv, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, 12
            )
            temp_adaptive_path = f"{os.path.splitext(image_path)[0]}_calamari_adaptive.png"
            cv2.imwrite(temp_adaptive_path, img_adaptive1)
            
            # Also try Gaussian adaptive thresholding
            img_adaptive2 = cv2.adaptiveThreshold(
                img_cv, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 5
            )
            temp_adaptive2_path = f"{os.path.splitext(image_path)[0]}_calamari_adaptive2.png"
            cv2.imwrite(temp_adaptive2_path, img_adaptive2)
            
            # Add dilation to connect broken letters in cursive writing
            kernel = np.ones((2,2), np.uint8)
            img_dilated = cv2.dilate(img_adaptive1, kernel, iterations=1)
            temp_dilated_path = f"{os.path.splitext(image_path)[0]}_calamari_dilated.png"
            cv2.imwrite(temp_dilated_path, img_dilated)
            
        except Exception as cv_error:
            logging.error(f"Error in OpenCV preprocessing: {cv_error}")
            temp_adaptive_path = None
        
        # Initialize the predictor
        predictor = setup_calamari_predictor()
        if not predictor:
            logging.error("Failed to initialize Calamari predictor")
            return None
        
        # Process all preprocessed versions and collect results
        temp_paths = [
            (temp_binary_path, "binary"),
            (temp_contrast_path, "contrast"),
            (temp_sharp_path, "sharp")
        ]
        
        # Add OpenCV paths if available
        if temp_adaptive_path:
            temp_paths.extend([
                (temp_adaptive_path, "adaptive1"),
                (temp_adaptive2_path, "adaptive2"),
                (temp_dilated_path, "dilated")
            ])
        
        # Run prediction on each preprocessed image
        for path, name in temp_paths:
            try:
                logging.info(f"Running Calamari prediction on {name} preprocessed image...")
                prediction_result = list(predictor.predict_dataset(
                    test_image_files=[path], progress_bar=False
                ))[0]
                
                text = prediction_result.sentence
                results[name] = text
                logging.info(f"Result from {name}: {len(text.strip())} chars")
                
                # Clean up
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logging.error(f"Error processing {name} image: {e}")
        
        # Select the best result based on text length
        if results:
            best_method = max(results.items(), key=lambda x: len(x[1].strip()) if x[1] else 0)
            logging.info(f"Best Calamari result: {best_method[0]} with {len(best_method[1].strip())} chars")
            return best_method[1]
        else:
            logging.warning("No successful Calamari OCR results")
            return "ERROR: Calamari OCR extraction failed"
    
    except Exception as e:
        logging.error(f"Error in Calamari OCR extraction: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return "ERROR: Calamari OCR extraction failed"

def is_likely_handwritten(image_path):
    """Analyze image to determine if it likely contains handwritten text
    
    This is a simple heuristic based on the variance of pixel intensities,
    edge detection, and other features typical of handwritten text.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        bool: True if the image likely contains handwritten text
    """
    try:
        import cv2
        
        # Read the image using OpenCV
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return False
        
        # 1. Check variance of pixel intensities
        # Handwritten text often has higher variance due to uneven strokes
        pixel_std = np.std(img)
        
        # 2. Edge detection - handwriting tends to have more varied edges
        edges = cv2.Canny(img, 100, 200)
        edge_density = np.sum(edges > 0) / (img.shape[0] * img.shape[1])
        
        # 3. Check for connected components (blobs)
        # Handwriting tends to have more irregular blobs
        _, thresh = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY_INV)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(thresh)
        
        # Filter out very small components (noise)
        valid_components = [s for s in stats if s[4] > 20]  # Area
        avg_component_size = np.mean([s[4] for s in valid_components]) if valid_components else 0
        component_ratio = len(valid_components) / (img.shape[0] * img.shape[1]) if valid_components else 0
        
        # 4. Calculate histogram of oriented gradients (simplified)
        gx = cv2.Sobel(img, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(img, cv2.CV_32F, 0, 1)
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
        
        logging.info(f"Handwritten likelihood: {handwritten_likelihood:.2f} for {image_path}")
        
        # Return True if the combined score exceeds a threshold
        return handwritten_likelihood > 0.6
    
    except Exception as e:
        logging.error(f"Error in handwritten detection: {e}")
        return False
