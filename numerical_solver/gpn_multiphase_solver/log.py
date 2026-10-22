"""Настройка логирования для gpn_multiphase_solver.

Два уровня логирования (иерархия Python logging):
  - user_log ("gpn_multiphase_solver") — прогресс расчёта, итоги интервалов.
    Уровень INFO: видим при обычном запуске.
  - dev_log ("gpn_multiphase_solver.dev") — внутреннее состояние модулей,
    PVT min/max, потоки, коэффициенты СЛАУ. Уровень DEBUG.

dev_log наследует от user_log. При level=INFO видны только user-сообщения.
При level=DEBUG — оба. См. модуль-логирования.md.
"""

import logging


def setup_logging(level: str = "INFO") -> None:
    """Настроить логирование. Вызывается в SimulatorFactory."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    logger = logging.getLogger("gpn_multiphase_solver")
    logger.setLevel(log_level)

    # Добавить handler только один раз (повторный вызов не дублирует вывод)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)


# Логгеры для использования в модулях:
#   from gpn_multiphase_solver.log import user_log, dev_log
user_log = logging.getLogger("gpn_multiphase_solver")
dev_log = logging.getLogger("gpn_multiphase_solver.dev")
