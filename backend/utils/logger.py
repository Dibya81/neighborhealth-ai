import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from config import get_settings

settings = get_settings()

# Traceability: Stores the short ID for the current request context
request_id_var: ContextVar[str] = ContextVar("request_id", default="system")

class CleanFormatter(logging.Formatter):
    """
    Structured formatter: [TIME] [LEVEL] [TAG] [req:ID] message
    """
    def format(self, record):
        # Time in [HH:MM:SS]
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        
        level = record.levelname
        # Tag is the logger name (last part)
        tag = record.name.split(".")[-1].upper()
        if tag == "__MAIN__": tag = "API"
        
        req_id = request_id_var.get()
        req_part = f" [req:{req_id}]" if req_id != "system" else ""
        
        # Colouring purely via ANSI if not in production (optional, keeping minimal for now)
        msg = record.getMessage()
        
        # Build the final string
        return f"[{timestamp}] [{level}] [{tag}]{req_part} {msg}"

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured structured logger.
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if logger exists
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if not settings.is_production else logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(CleanFormatter())
    
    logger.addHandler(handler)
    logger.propagate = False

    return logger
