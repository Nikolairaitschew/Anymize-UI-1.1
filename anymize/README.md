# Enhanced OCR Application

This application provides a web interface for extracting text from various document types, including:
- PDF documents (both searchable and image-based)
- Images containing text (JPG, PNG, TIFF, etc.)
- Documents with handwritten content (automatically detected)
- Word documents (DOCX)
- Plain text files

The system implements a modular, cascading approach to OCR, using multiple techniques to maximize accuracy with intelligent handwriting detection.

## Project Structure

- **ocr/** - Modular OCR system components
  - `config.py` - Common configuration and utilities
  - `document_ocr.py` - Main OCR processing pipeline
  - `image_ocr.py` - Image-specific OCR processing
  - `pdf_ocr.py` - PDF processing and extraction
  - `handwritten_ocr.py` - Specialized handwritten text recognition

- **enhanced_ocr_app.py** - Main Flask web application

- **templates/** - Web interface
  - `index.html` - Upload interface
  - `enhanced_result.html` - Results display with side-by-side comparison

## Technologies Used

- **Flask** - Web framework
- **Tesseract OCR** - Primary OCR engine
- **EasyOCR** - Neural network-based OCR (for handwritten text)
- **PyMuPDF** - PDF text extraction
- **PDF2Image** - PDF to image conversion
- **Apache Tika** - Universal document parsing
- **PIL/Pillow** - Image processing

## Features

1. **Intelligent OCR Pipeline**:
   - Uses the most appropriate extraction method for each file type
   - Applies multiple OCR engines as needed to improve accuracy
   - Falls back to more powerful methods if simpler methods fail

2. **Handwritten Text Recognition**:
   - Special preprocessing for handwritten content
   - EasyOCR as a backup when Tesseract struggles with handwritten text
   - Smart cascading approach with multiple preprocessing techniques

3. **User Interface**:
   - Simple file upload interface
   - Toggle for handwritten text recognition
   - Side-by-side comparison of extracted and processed text
   - Visual diff highlighting to show changes

## Setup and Usage

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the application:
   ```
   python enhanced_ocr_app.py
   ```

3. Open your web browser to http://localhost:5000
