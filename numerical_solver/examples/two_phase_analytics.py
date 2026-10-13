"""Печать аналитики двухфазного стационара для примеров (пункты A–E).

Проверки — gpn_multiphase_solver.diagnostics.two_phase и .closed_form
(DEBT-011), там же их вывод. Здесь — сводный отчёт report и CLI.

Запуск для конкретного примера:
    cd numerical_solver
    .venv\\Scripts\\python examples\\two_phase_analytics.py 03
"""

import sys
from pathlib import Path

import numpy as np

_EXAMPLES = Path(__file__).resolve().parent
_ROOT = _EXAMPLES.parent
# Прототип radial_blackoil — установленный дистрибутив (DEBT-059), путь к нему не добавляется
for _p in (str(_ROOT), str(_EXAMPLES)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gpn_multiphase_solver.diagnostics.closed_form import solve_closed  # noqa: E402
from gpn_multiphase_solver.diagnostics.two_phase import (  # noqa: E402
    compute_free_gas_prediction, compute_gor, degassing_front, dupuit_check,
    predict_saturation)


# ── Сводный отчёт ────────────────────────────────────────────────

def report(history, grid, config, pvt) -> dict:
    """Все проверки с печатью в консоль. Возвращает сводку."""
    Rs0 = config.initial_conditions.Rs0

    print(f"── Аналитика двухфазного стационара "
          f"(ОФП: {config.relperm.model}) ──")

    # Однофазный сценарий: газа нет, обращать (B) не на чем, GOR не
    # определён (G_g = 0). Сообщаем, а не падаем — так же поступает
    # rs_analytics при Rs0 = 0.
    if Rs0 <= 0.0:
        print(f"  не проверяется: Rs0 = {Rs0} — растворённого газа нет, "
              f"сценарий однофазный")
        return dict(applicable=False)

    # ОФП по конфигу — тем же конструктором, что фабрика собирает решатель
    # (у report решателя нет: сигнатура общая для main.py 03–05 и CLI)
    from gpn_multiphase_solver.factory import create_relperm
    relperm = create_relperm(config)

    # A. Газовый фактор
    gor_w, gor_e = compute_gor(history)
    print(f"  A. GOR(забой)  = {gor_w:.8f}   |GOR - Rs0| = {abs(gor_w - Rs0):.2e}")
    print(f"     GOR(контур) = {gor_e:.8f}   Rs0 = {Rs0:.1f} м³ст/м³ст")

    pred, act = compute_free_gas_prediction(history, config)
    # Сравниваем только там, где газ есть: в однофазной зоне обе величины
    # нулевые и относительная ошибка не определена.
    nz = act > 1e-12
    rel_gas = float(np.max(np.abs(pred[nz] - act[nz]) / act[nz])) if nz.any() else 0.0
    print(f"     своб. газ = |G^o|·(Rs0-Rs): max отн. откл. = {rel_gas:.2e}")

    # B. Насыщенность при численном давлении — проверка самого замыкания
    idx, Sg_num, Sg_pred = predict_saturation(history, config, pvt, relperm)
    ok = ~np.isnan(Sg_pred)
    dSg = float(np.max(np.abs(Sg_pred[ok] - Sg_num[ok]))) if ok.any() else np.nan
    rel = (np.abs(Sg_pred[ok] - Sg_num[ok]) / Sg_num[ok]).max() * 100 if ok.any() else np.nan
    print(f"  B. S_g из GOR=Rs0 при численном p: {ok.sum()} ячеек, "
          f"max|ΔS_g| = {dSg:.2e} ({rel:.3f} %)")

    # C. Фронт
    fr = degassing_front(history, grid, config, pvt)
    same = np.array_equal(fr["cells_below_pb"], fr["cells_with_gas"])
    d_rb = abs(fr["r_b_formula"] - fr["r_b_interp"]) / fr["r_b_interp"]
    print(f"  C. фронт: r_b = {fr['r_b_interp']:.5f} м (интерп. профиля), "
          f"{fr['r_b_formula']:.5f} м (формула), расхожд. {d_rb*100:.2f} %")
    print(f"     pb = {fr['pb']/1e6:.4f} МПа; "
          f"ячейки p<pb и ячейки Sg>0 совпадают: {same}")

    # D. Дюпюи
    dup = dupuit_check(history, grid, config, pvt)
    rel_slope = abs(dup["slope_fit"] - dup["slope_theory"]) / dup["slope_theory"]
    print(f"  D. Дюпюи: {dup['n_cells']} однофазных ячеек, "
          f"max|p - Дюпюи| = {dup['max_dev']:.2e} Па")
    print(f"     наклон: {dup['slope_fit']:.5e} Па (профиль) vs "
          f"{dup['slope_theory']:.5e} Па (из G^o), отн. разн. {rel_slope:.2e}")

    # E. Замкнутое решение — ничего из расчёта не используется
    r = grid.r_centers
    cl = solve_closed(config, pvt, relperm, r)
    p_num = history.states[-1].p
    q_num = abs(history.hydro_results[-1].G_o[0])
    dp_max = float(np.abs(cl["p"] - p_num).max())
    # Та же депрессия, по которой solve_closed строит решение (FEAT-022);
    # p_wf берётся из решения — при управлении по дебиту оно вычислено (FEAT-020)
    dep = config.initial_conditions.p0 - cl["p_wf"]
    print("  E. Замкнутое решение (дебит квадратурой, профиль ОДУ):")
    print(f"     q_o = {cl['q_o']:.6e} м³ст/с (аналитика) vs "
          f"{q_num:.6e} (расчёт), расхожд. {abs(cl['q_o']-q_num)/q_num*100:.3f} %")
    print(f"     max|p_ана - p_чис| = {dp_max/1e3:.2f} кПа "
          f"({dp_max/dep*100:.3f} % депрессии)")
    print(f"     S_g макс = {cl['Sg'].max():.5f} (аналитика) vs "
          f"{history.states[-1].Sg.max():.5f} (расчёт)")

    return dict(applicable=True,
                gor_well=gor_w, gor_ext=gor_e, rel_free_gas=rel_gas,
                dSg_max=dSg, front=fr, dupuit=dup, closed=cl,
                sat_idx=idx, sat_num=Sg_num, sat_pred=Sg_pred)


def _resolve_example(name_or_prefix: str) -> Path:
    """examples/<имя>/ по полному имени или числовому префиксу ('03').

    Пользователю не нужно печатать '03_standing_corey' целиком.
    Ошибка при отсутствии или неоднозначности префикса.
    """
    exact = _EXAMPLES / name_or_prefix
    if exact.is_dir():
        return exact
    matches = sorted(d for d in _EXAMPLES.iterdir()
                     if d.is_dir() and d.name.startswith(name_or_prefix))
    if not matches:
        raise SystemExit(f"нет примера '{name_or_prefix}'")
    if len(matches) > 1:
        raise SystemExit(f"неоднозначно: {[m.name for m in matches]}")
    return matches[0]


# ── Автономный запуск ──
if __name__ == "__main__":
    from gpn_multiphase_solver.io.config import load_config
    from gpn_multiphase_solver.factory import SimulatorFactory

    if len(sys.argv) < 2:
        raise SystemExit(
            "укажите пример: python examples\\two_phase_analytics.py 03")

    folder = _resolve_example(sys.argv[1])
    config = load_config(folder / "config.json")
    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)

    report(history, sim.grid, config, sim.pvt)
