"""DEBT-027, проба аудита: отпечатки историй 23 примеров с кодом плана, подставленным в памяти.

emulate_debt027.install() + fingerprint_bug026 (ожидания — база после BUG-026). Проверка
утверждения плана «проверка только читает состояние — истории побитово прежние».
Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\debt-027\\probes\\fingerprint_emulate.py
"""
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import emulate_debt027  # noqa: E402

emulate_debt027.install()
print("эмуляция кода плана (emulate_debt027.install)", flush=True)
runpy.run_path(str(HERE.parent.parent / "bug-026" / "probes" / "fingerprint_bug026.py"), run_name="__main__")
