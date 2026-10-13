"""FEAT-032: отпечатки историй всех примеров — сверка реализации с эмуляцией планирования.

Отпечаток — sha256 полей p, S_g, R_s, T всех записей истории (ramp_probe.fingerprint).
EXPECTED — замер планирования на 87eb55f:
  - примеры без time.dt_after_control_change — штатные отпечатки (sweep_first1.out.txt,
    строки «orig»): поле выключено по умолчанию, истории побитово прежние;
  - 16 и 17 с time.dt_after_control_change = 2 — отпечатки эмуляции варианта 2
    (example_numbers_h2.out.txt): код FEAT-032 обязан совпасть с эмуляцией побитово.

Запуск из numerical_solver/ (worktree или основной каталог — печатается путь пакета):
    .venv\\Scripts\\python P [имя примера ...]
Без аргументов — все примеры, ~3 мин.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ramp_probe import SOLVER_ROOT, fingerprint  # noqa: E402

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

EXPECTED = {
    "01_single_phase_no_jt": "98a9e2de8144881b",
    "02_single_phase_jt": "283117b789e6cd3d",
    "03_standing_corey": "409ccfb8885b3587",
    "04_table_table": "9cb0ee07436b8644",
    "04a_high_gas_saturation": "15dc354252c96fc0",
    "05_standing_table_rp": "86665873bfb14643",
    "06_table_corey_rp": "b745772a4b4570f5",
    "07_degassing_adiabatic_only": "b3db76c84a0857ae",
    "08_degassing_jt": "1060c407784b5e27",
    "09_degassing_latent_heat": "5dfd90365c77f9bc",
    "10_deep_degassing": "2b16f8c75773df90",
    "11_degassing_at_boundary": "9677ccfca6c2eef6",
    "12_large_drainage_radius": "7c88ff3f4ec7ad03",
    "13a_pwf_ramp_down": "c777e48e26cbd4f5",
    "13b_pwf_alternating": "041bc876f88d8cd1",
    "14_high_gor_cooling": "762bb8afd474ffa8",
    "15_oil_rate_ramp_up": "a6e91358e1482446",
    "16_well_shut_in": "1a063510fc42549b",            # с нарастанием, h0 = 2 с
    "17_shut_in_strong_cooling": "01ac291eb8f87a4e",  # с нарастанием, h0 = 2 с
    "18_prototype_input": "03f9fcb4c112bb8d",
    "19_rs150_cooling": "bc6b6a0079e71ea9",
    "20_rs300_cooling": "a3654c52e358fbf0",
    "21_rs100_cooling": "103e639d7ba06def",
}


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    names = sys.argv[1:] or list(EXPECTED)
    bad = 0
    for name in names:
        cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
        cfg.output.log_level = "ERROR"
        sim, s0 = SimulatorFactory.from_config(cfg)
        fp = fingerprint(sim.run(s0))
        ok = fp == EXPECTED[name]
        bad += not ok
        print(f"{name:30s} {fp} {'ОК' if ok else 'РАСХОЖДЕНИЕ, ожидалось ' + EXPECTED[name]}",
              flush=True)
    print(f"итог: расхождений {bad} из {len(names)}")


if __name__ == "__main__":
    main()
