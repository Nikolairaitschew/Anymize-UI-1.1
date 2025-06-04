#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Anymize OCR App Starter

This script properly configures the Python path and starts the Anymize OCR application
regardless of how it's called. It ensures all modules are imported correctly.
"""

import os
import sys
import logging
from pathlib import Path

# Configure paths
APP_ROOT = Path(__file__).resolve().parent
ANYMIZE_DIR = APP_ROOT / 'anymize'

# Ensure both directories are in the Python path
sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(ANYMIZE_DIR))

# Create logs directory
logs_dir = APP_ROOT / 'logs'
os.makedirs(logs_dir, exist_ok=True)

# Simple startup logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'app_startup.log'),
        logging.StreamHandler()
    ]
)

log = logging.getLogger('startup')

def start_app():
    """Start the Anymize OCR App with all proper path settings"""
    try:
        log.info("Starting Anymize OCR Application")
        log.info(f"Python version: {sys.version}")
        log.info(f"Python executable: {sys.executable}")
        log.info(f"Working directory: {os.getcwd()}")
        log.info(f"App root: {APP_ROOT}")
        log.info(f"Python path: {sys.path}")
        
        # Import the Flask application
        try:
            from anymize.enhanced_ocr_app import app
            log.info("Successfully imported the application")
        except ImportError as e:
            log.error(f"Error importing application: {e}")
            raise
            
        # Start the server
        host = '0.0.0.0'  # Listen on all interfaces
        port = 8000
        
        log.info(f"Starting server on {host}:{port}")
        
        # Check if waitress is available for production serving
        try:
            import waitress
            log.info("Using waitress production server")
            waitress.serve(app, host=host, port=port)
        except ImportError:
            # Fall back to Flask development server
            log.info("Waitress not found, using Flask development server")
            app.run(host=host, port=port, debug=False)
            
    except Exception as e:
        log.error(f"Error during startup: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    start_app()
