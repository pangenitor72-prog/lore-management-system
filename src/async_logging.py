
import asyncio
import logging
from logging.handlers import QueueHandler, QueueListener
import queue
import sys

def setup_async_logging():
    """
    Configures logging to be non-blocking using a queue.
    """
    log_queue = queue.Queue(-1)
    queue_handler = QueueHandler(log_queue)

    # Basic configuration for the root logger to use the queue handler
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(queue_handler)

    # The listener will process log records from the queue
    # Let's use a standard stream handler for the output
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    listener = QueueListener(log_queue, handler)
    
    listener.start()

    # Configure other loggers as before, but they will inherit the root handler
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("lms_api").setLevel(logging.INFO)
    logging.getLogger("lms_db").setLevel(logging.INFO)
    logging.getLogger("lms_auditor").setLevel(logging.INFO)
    logging.getLogger("lms_query").setLevel(logging.INFO)
    
    return listener
