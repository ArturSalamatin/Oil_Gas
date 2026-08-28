"""Настройка логирования для gpn_multiphase_solver."""

import logging


def setup_logging(level: str = "INFO") -> None:
    """Настроить логирование. Вызывается в SimulatorFactory."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    logger = logging.getLogger("gpn_multiphase_solver")
    logger.setLevel(log_level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)


user_log = logging.getLogger("gpn_multiphase_solver")
dev_log = logging.getLogger("gpn_multiphase_solver.dev")
