"""
Systematic Logger Configuration for Multi-Tenant Document Intelligence

This module provides a centralized logging configuration that can be used
across the entire application. It supports different log levels, file output,
console output, and structured logging.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        # Add color to the level name
        if hasattr(record, 'levelname'):
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'getMessage']:
                log_entry[key] = value
        
        return json.dumps(log_entry, ensure_ascii=False)


class LoggerConfig:
    """Centralized logger configuration."""
    
    def __init__(self):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Default configuration
        self.config = {
            'level': logging.INFO,
            'console': True,
            'file': True,
            'json_format': False,
            'max_file_size': 10 * 1024 * 1024,  # 10MB
            'backup_count': 5,
            'log_file': 'app.log',
            'error_file': 'error.log'
        }
    
    def configure(self, 
                 level: str = 'INFO',
                 console: bool = True,
                 file: bool = True,
                 json_format: bool = False,
                 log_file: Optional[str] = None,
                 error_file: Optional[str] = None,
                 max_file_size: int = 10 * 1024 * 1024,
                 backup_count: int = 5) -> None:
        """
        Configure the logging system.
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console: Enable console logging
            file: Enable file logging
            json_format: Use JSON format for structured logging
            log_file: Custom log file name
            error_file: Custom error log file name
            max_file_size: Maximum file size before rotation
            backup_count: Number of backup files to keep
        """
        # Update configuration
        self.config.update({
            'level': getattr(logging, level.upper()),
            'console': console,
            'file': file,
            'json_format': json_format,
            'log_file': log_file or self.config['log_file'],
            'error_file': error_file or self.config['error_file'],
            'max_file_size': max_file_size,
            'backup_count': backup_count
        })
        
        # Clear existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        # Set level
        root_logger.setLevel(self.config['level'])
        
        # Console handler
        if self.config['console']:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.config['level'])
            
            if self.config['json_format']:
                console_handler.setFormatter(JSONFormatter())
            else:
                console_formatter = ColoredFormatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                console_handler.setFormatter(console_formatter)
            
            root_logger.addHandler(console_handler)
        
        # File handlers
        if self.config['file']:
            # General log file
            file_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / self.config['log_file'],
                maxBytes=self.config['max_file_size'],
                backupCount=self.config['backup_count']
            )
            file_handler.setLevel(self.config['level'])
            
            if self.config['json_format']:
                file_handler.setFormatter(JSONFormatter())
            else:
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler.setFormatter(file_formatter)
            
            root_logger.addHandler(file_handler)
            
            # Error log file (only ERROR and CRITICAL)
            error_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / self.config['error_file'],
                maxBytes=self.config['max_file_size'],
                backupCount=self.config['backup_count']
            )
            error_handler.setLevel(logging.ERROR)
            
            if self.config['json_format']:
                error_handler.setFormatter(JSONFormatter())
            else:
                error_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                error_handler.setFormatter(error_formatter)
            
            root_logger.addHandler(error_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance with the given name."""
        return logging.getLogger(name)
    
    def set_level(self, level: str) -> None:
        """Set the logging level."""
        level_value = getattr(logging, level.upper())
        logging.getLogger().setLevel(level_value)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level_value)


# Global logger configuration instance
logger_config = LoggerConfig()


def setup_logging(level: str = 'INFO', 
                 console: bool = True, 
                 file: bool = True,
                 json_format: bool = False,
                 **kwargs) -> None:
    """
    Setup logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console: Enable console logging
        file: Enable file logging
        json_format: Use JSON format for structured logging
        **kwargs: Additional configuration options
    """
    logger_config.configure(
        level=level,
        console=console,
        file=file,
        json_format=json_format,
        **kwargs
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logger_config.get_logger(name)


def log_function_call(func):
    """Decorator to log function calls."""
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} failed with error: {e}")
            raise
    return wrapper


def log_async_function_call(func):
    """Decorator to log async function calls."""
    async def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(f"Calling async {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"Async {func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Async {func.__name__} failed with error: {e}")
            raise
    return wrapper


# Convenience functions for common logging patterns
def log_request(logger: logging.Logger, method: str, url: str, status_code: int, 
                response_time: float, **extra):
    """Log HTTP request details."""
    logger.info(f"{method} {url} - {status_code} - {response_time:.3f}s", extra=extra)


def log_database_operation(logger: logging.Logger, operation: str, table: str, 
                           record_id: str = None, **extra):
    """Log database operations."""
    message = f"DB {operation} on {table}"
    if record_id:
        message += f" (ID: {record_id})"
    logger.debug(message, extra=extra)


def log_kafka_message(logger: logging.Logger, action: str, topic: str, 
                     message_id: str = None, **extra):
    """Log Kafka message operations."""
    message = f"Kafka {action} on topic {topic}"
    if message_id:
        message += f" (ID: {message_id})"
    logger.info(message, extra=extra)


def log_embedding_operation(logger: logging.Logger, operation: str, 
                           document_id: str, tenant_id: str, **extra):
    """Log embedding operations."""
    logger.info(f"Embedding {operation} for document {document_id} (tenant: {tenant_id})", 
                extra=extra)


# Initialize with default configuration
setup_logging()
