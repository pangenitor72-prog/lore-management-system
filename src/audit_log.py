import asyncio
import logging
from logging import FileHandler
import os
import threading

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audit.log')

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