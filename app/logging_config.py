"""
Centralized logging configuration for AutoAgent.
This ensures consistent logging across all modules.
"""
import logging
import sys
from pathlib import Path

def setup_logging():
    """Setup centralized logging configuration."""
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger('app.services.gemini_parser').setLevel(logging.INFO)
    logging.getLogger('app.routes.workflow').setLevel(logging.INFO)
    logging.getLogger('app.services.telegram_bot').setLevel(logging.INFO)
    logging.getLogger('app.services.enhanced_workflow_executor').setLevel(logging.INFO)
    logging.getLogger('app.tools').setLevel(logging.INFO)
    
    # Suppress overly verbose third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    
    print("🔧 LOGGING: Centralized logging configuration applied")
    return root_logger

# Initialize logging when module is imported
setup_logging()
