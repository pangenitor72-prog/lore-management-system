import logging
import sys

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Optionally, set a higher level for some noisy loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Custom loggers for specific modules if needed
    logging.getLogger("lms_api").setLevel(logging.INFO)
    logging.getLogger("lms_db").setLevel(logging.INFO)
    logging.getLogger("lms_auditor").setLevel(logging.INFO)
    logging.getLogger("lms_query").setLevel(logging.INFO)
