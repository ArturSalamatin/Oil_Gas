"""BUG-026: отпечатки историй 23 примеров после смены h0 в 16 и 17 на 0.11 с.

Обёртка над feat-032/probes/fingerprint_examples.py: ожидания 21 примера — прежние
(поле time.dt_after_control_change у них не задано), у 16 и 17 — замер планирования
BUG-026 при h0 = 0.11 с (h0_series.py, example_16/17*.out.txt; та же функция отпечатка);
у 18 — после влития DEBT-057 новый (см. ниже).

Запуск из numerical_solver/ (P — путь к скрипту): .venv\\Scripts\\python P [имя примера ...]
Без аргументов — все 23 примера, ~4 мин.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd().parent / "vault" / "issues" / "feat-032" / "probes"))
import fingerprint_examples as fe  # noqa: E402

fe.EXPECTED["16_well_shut_in"] = "87cd3498258184cf"            # h0 = 0.11 с
fe.EXPECTED["17_shut_in_strong_cooling"] = "1b97396204eff005"  # h0 = 0.11 с
# DEBT-057 (пористость φ(p) в энергии) меняет T примера 18. Признак её влития —
# tests/test_energy_porosity.py. Отпечаток (p, S_g, R_s, T) снят аудитом 1 BUG-026
# на коде ветки DEBT-057 (audit1/debt057_fp18.out.txt); отпечаток DEBT-057
# fd040715fc926897 — другой: только по T.
if (Path.cwd() / "tests" / "test_energy_porosity.py").exists():
    fe.EXPECTED["18_prototype_input"] = "9b429849070f30eb"

if __name__ == "__main__":
    fe.main()
