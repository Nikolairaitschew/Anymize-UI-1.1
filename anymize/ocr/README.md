# Modular OCR System

This directory contains a modular Optical Character Recognition (OCR) system that supports various document types and includes specialized processing for handwritten text.

## Module Structure

- `__init__.py` - Package initialization file
- `config.py` - Common configuration and utilities
- `document_ocr.py` - Main entry point with logic to handle various file types
- `image_ocr.py` - Specialized OCR for images (photos, scans, etc.)
- `pdf_ocr.py` - PDF processing, including text extraction and OCR for scanned PDFs
- `handwritten_ocr.py` - Specialized handling for handwritten content

## OCR Technologies Used

1. **Tesseract OCR** - Open-source OCR engine for standard text recognition
2. **EasyOCR** - Neural network-based OCR with better handwriting recognition
3. **PyMuPDF (fitz)** - For extracting embedded text from searchable PDFs
4. **Apache Tika** - Universal document parser for multiple formats
5. **DocX2TXT** - For Microsoft Word documents

## OCR Processing Pipeline

The system implements a cascading approach:

1. Try format-specific extractors (e.g., PyMuPDF for PDFs)
2. If needed, try standard Tesseract OCR with optimized settings
3. If quality is low, apply image preprocessing (contrast, blur, etc.)
4. If still poor results, try specialized handwriting settings
5. As last resort, use EasyOCR for better handwriting recognition

## Additional OCR Technologies to Research

Here's a list of additional OCR technologies and approaches that could be added to the system:

1. **Keras-OCR** - Deep learning OCR based on Keras with custom model support
2. **PaddleOCR** - High-performance multilingual OCR toolkit by Baidu
3. **AWS Textract** - AWS's OCR service with layout understanding
4. **Google Cloud Vision OCR** - Google's OCR API with strong language support
5. **Microsoft Azure Computer Vision OCR** - Microsoft's OCR API
6. **Tesseract LSTM** - Newer LSTM-based neural network models in Tesseract
7. **Handwritten Text Recognition (HTR)** - Specialized models for historical documents
8. **Mathpix** - Specialized OCR for mathematical equations
9. **ABBYY FineReader** - Commercial OCR with high accuracy
10. **Kofax OmniPage** - Commercial OCR with zonal recognition
11. **OCRopus** - Open-source document analysis and OCR system
12. **Calamari OCR** - Deep learning OCR focused on historical documents
13. **Kraken OCR** - OCR engine for historical documents
14. **Attention OCR** - Attention-based sequence-to-sequence models for OCR
15. **Table OCR** - Specialized OCR for detecting and parsing tables
16. **Form OCR** - Specialized OCR for form fields
17. **Captcha OCR** - Specialized for captcha recognition
18. **Low-quality document OCR** - Enhanced preprocessing for poor quality scans
19. **Curved/Distorted Text OCR** - For text that isn't straight or flat
20. **Multi-language OCR** - OCR that can detect and handle multiple languages in one document

## Implementation Notes

- All OCR modules use a common logging configuration
- Temporary files are managed consistently
- The system is designed to be extensible - adding new OCR methods is straightforward
- Performance: The system uses lazy loading for resource-intensive components (e.g., EasyOCR)
