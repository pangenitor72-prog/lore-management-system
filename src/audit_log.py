import asyncio
import logging
from logging import FileHandler
import os
import threading

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audit.log')

import re

def redact_credentials(message: str) -> str:
    """Redact potential credentials from log messages."""
    # Redact connection strings
    message = re.sub(
        r'(bolt|neo4j):\/\/([^:]+):([^@]+)@',
        r'\1://\2:***REDACTED***@',
        message
    )
    
    # Redact API keys and tokens
    message = re.sub(
        r'(api[_-]?key|token|password|secret)\s*[=:]\s*[\'"]?([^\s\'"]{8,})[\'"]?',
        r'\1=***REDACTED***',
        message,
        flags=re.IGNORECASE
    )
    
    return message

class AuditLogger:
    _initialized = False
    _handler = None
    _lock = threading.Lock()

    @staticmethod
    def _initialize():
        if not AuditLogger._initialized:
            AuditLogger._handler = FileHandler(LOG_FILE, mode='a', encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            AuditLogger._handler.setFormatter(formatter)
            AuditLogger._initialized = True

    @staticmethod
    def _write_log_sync(message, level):
        with AuditLogger._lock:
            if not AuditLogger._initialized:
                AuditLogger._initialize()
            
            # Apply redaction
            if isinstance(message, str):
                message = redact_credentials(message)
            
            log_record = logging.LogRecord(
                name='audit',
                level=level,
                pathname='',
                lineno=0,
                msg=message,
                args=(),
                exc_info=None
            )
            
            AuditLogger._handler.emit(log_record)

    @staticmethod
    def log_sync(message: str, level: int = logging.INFO):
        AuditLogger._write_log_sync(message, level)

    @staticmethod
    async def log(message: str, level: int = logging.INFO):
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, AuditLogger._write_log_sync, message, level)
        except RuntimeError: # No running loop
            AuditLogger.log_sync(message, level)