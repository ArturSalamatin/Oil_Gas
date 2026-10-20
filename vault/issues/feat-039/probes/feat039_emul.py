"""FEAT-039 (планирование): эмуляция нового поведения для прогона тестов – плагин pytest.

TimeSchedule.first_substep_depth подменяется на уровне класса: интервал 0 – тоже смена
управления (первый подшаг <= h0 с удвоением), если поле задано; остальное – как в коде.
Пакет не правится. Падения прогона – список тестов и чисел, которые FEAT-039 меняет.

Запуск из numerical_solver/:
    $env:PYTHONPATH = "..\\vault\\issues\\feat-039\\probes"
    .venv\\Scripts\\python -m pytest tests/ -q -p feat039_emul
"""


def pytest_configure(config):
    from gpn_multiphase_solver.simulator import TimeSchedule

    orig = TimeSchedule.first_substep_depth

    def first_substep_depth(self, interval_idx):
        h0 = self.dt_after_control_change
        if h0 is None or interval_idx > 0:
            return orig(self, interval_idx)
        _, dt = self.substeps(0)
        m = 0
        while dt / 2 ** m > h0:
            m += 1
        return m

    TimeSchedule.first_substep_depth = first_substep_depth
    print("FEAT-039: эмуляция – интервал 0 считается сменой управления")
