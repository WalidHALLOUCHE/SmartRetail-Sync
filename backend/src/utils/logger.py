"""
Logging configuration for SmartRetail-Sync.
Sets up structured logging with proper formatting.
"""

import logging
import logging.handlers
import os
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/smartretail_sync.log"
) -> None:
    """
    Configure application logging with both console and file handlers.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
    """
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Logging format
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    root_logger.info(f"Logging initialized at level {log_level}")


def get_logger(module_name: str) -> logging.Logger:
    """
    Get logger instance for a module.
    
    Args:
        module_name: Name of the module (__name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(module_name)
