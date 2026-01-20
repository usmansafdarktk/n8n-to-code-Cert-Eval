"""Logging configuration using loguru."""
import sys
from pathlib import Path
from loguru import logger

from app.config.settings import settings


def setup_logging() -> None:
    """Configure application logging."""
    # Remove default handler
    logger.remove()

    # Console handler
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
    )

    # File handler with rotation
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        settings.log_file,
        rotation="500 MB",
        retention="10 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.log_level,
    )

    logger.info("Logging configured successfully")
