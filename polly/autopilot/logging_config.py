"""Logging configuration for autopilot service."""

import logging
from pathlib import Path


def setup_logging() -> logging.Logger:
    """Configure comprehensive logging for autopilot.
    
    Creates separate log files for:
    - autopilot.log: Everything (DEBUG level)
    - trades.log: Trading decisions and executions
    - errors.log: Errors and exceptions only
    - research.log: Research summaries
    
    Returns:
        Configured logger instance
    """
    
    log_dir = Path.home() / ".polly" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Main log file (everything)
    main_handler = logging.FileHandler(log_dir / "autopilot.log")
    main_handler.setFormatter(detailed_formatter)
    main_handler.setLevel(logging.DEBUG)
    
    # Trade log (trades only)
    trade_handler = logging.FileHandler(log_dir / "trades.log")
    trade_handler.setFormatter(simple_formatter)
    trade_handler.setLevel(logging.INFO)
    
    # Error log (errors only)
    error_handler = logging.FileHandler(log_dir / "errors.log")
    error_handler.setFormatter(detailed_formatter)
    error_handler.setLevel(logging.ERROR)
    
    # Research log
    research_handler = logging.FileHandler(log_dir / "research.log")
    research_handler.setFormatter(simple_formatter)
    research_handler.setLevel(logging.INFO)
    
    # Console handler (important messages only)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    console_handler.setLevel(logging.INFO)
    
    # Setup main autopilot logger
    logger = logging.getLogger("autopilot")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(main_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    
    # Setup trade logger
    trade_logger = logging.getLogger("trades")
    trade_logger.setLevel(logging.INFO)
    trade_logger.addHandler(trade_handler)
    
    # Setup research logger
    research_logger = logging.getLogger("research")
    research_logger.setLevel(logging.INFO)
    research_logger.addHandler(research_handler)
    
    return logger

