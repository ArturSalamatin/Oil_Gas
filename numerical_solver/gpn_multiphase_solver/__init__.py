"""gpn_multiphase_solver — FVM solver for two-phase Black Oil with energy equation."""

# Номер версии пакета (FEAT-037) — единственный источник: pyproject.toml
# берёт его через [tool.setuptools.dynamic]. Только литерал, без вычислений
# и импортов: setuptools читает его разбором исходника, не импортируя
# пакет. Форма — PEP 440, три числа MAJOR.MINOR.PATCH; между выпусками —
# суффикс .devN. Правило номеров — CHANGELOG.md.
__version__ = "1.0.0.dev0"
