"""Тесты интеграции Factory с табличным PVT (FEAT-012).

Проверяют:
- CSV-ридеры: формат, конвертация единиц SI → бар/сП
- Factory: pvt.model="table" → PrototypeHydroAdapter
- Pipeline: from_config → run → history
- PVT-согласованность: один BlackOilPVT в обёртке и в модели
- Ошибки: отсутствие CSV файла
- Начальное состояние против таблиц: Rs0 в диапазоне, недонасыщенный старт, предупреждения (BUG-017)
- Ветви PVTO-таблицы: не меньше двух строк, давление и p_b(R_s) растут (DEBT-038)
- Строгий разбор CSV: заголовок, число полей, конечные числа (DEBT-042)
- Допустимость значений CSV: пределы столбцов, число строк, рост p и S_g, ветви R_s (DEBT-044)
"""

import logging
import shutil
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.io.config import load_config, SimulationConfig
from gpn_multiphase_solver.factory import (
    SimulatorFactory,
    _read_oil_pvt_csv, _read_gas_pvt_csv, _read_relperm_csv,
    create_pvt, create_relperm, _get_or_create_proto_pvt, _get_or_create_proto_rp,
)
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.pvt.table_full import TableFullPVT
from gpn_multiphase_solver.pvt.prototype_adapter import PrototypePVTAdapter, PrototypeRPAdapter
from gpn_multiphase_solver.units import BAR_TO_PA, CP_TO_PA_S


TABLE_CONFIG = Path(__file__).parent.parent / "configs" / "table_pvt" / "config.json"


# ═══════════════════════════════════════════════════════════
# A. CSV-ридеры
# ═══════════════════════════════════════════════════════════

class TestCSVReaders:
    """Чтение CSV с конвертацией единиц SI → бар/сП."""

    def test_oil_pvt_csv_format(self, tmp_path):
        """4 строки → 4 tuple (Rs, p_bar, Bo, mu_cP)."""
        csv = tmp_path / "oil.csv"
        csv.write_text(
            "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
            "0.0,5000000,1.05,0.003\n"
            "30.0,15000000,1.20,0.0015\n"
        )
        rows = _read_oil_pvt_csv(csv)
        assert len(rows) == 2
        # первая строка: p = 5e6 Па → 50 бар, μ = 0.003 Па·с → 3 сП
        Rs, p, Bo, mu = rows[0]
        assert Rs == 0.0
        assert p == pytest.approx(50.0)
        assert Bo == 1.05
        assert mu == pytest.approx(3.0)

    def test_gas_pvt_csv_format(self, tmp_path):
        """3 строки → 3 tuple (p_bar, Bg, mu_cP)."""
        csv = tmp_path / "gas.csv"
        csv.write_text(
            "pressure_Pa,Bg,mu_g_Pa_s\n"
            "5000000,0.020,0.000012\n"
            "15000000,0.008,0.000014\n"
        )
        rows = _read_gas_pvt_csv(csv)
        assert len(rows) == 2
        # p = 5e6 Па → 50 бар, μ = 1.2e-5 Па·с → 0.012 сП
        p, Bg, mu = rows[0]
        assert p == pytest.approx(50.0)
        assert Bg == 0.020
        assert mu == pytest.approx(0.012)

    def test_relperm_csv_format(self, tmp_path):
        """6 строк → (Sg, kro, krg) без конвертации."""
        csv = tmp_path / "rp.csv"
        csv.write_text(
            "Sg,kro,krg\n"
            "0.0,1.0,0.0\n"
            "0.4,0.3,0.2\n"
            "0.8,0.0,0.8\n"
        )
        Sg, kro, krg = _read_relperm_csv(csv)
        assert len(Sg) == 3
        assert Sg == [0.0, 0.4, 0.8]
        assert kro == [1.0, 0.3, 0.0]
        assert krg == [0.0, 0.2, 0.8]

    def test_oil_csv_skips_blank_lines(self, tmp_path):
        """Пустые строки пропускаются."""
        csv = tmp_path / "oil.csv"
        csv.write_text(
            "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
            "0.0,5000000,1.05,0.003\n"
            "\n"
            "30.0,15000000,1.20,0.0015\n"
        )
        rows = _read_oil_pvt_csv(csv)
        assert len(rows) == 2

    def test_oil_csv_missing_file(self, tmp_path):
        """Несуществующий файл → ValueError."""
        with pytest.raises(ValueError, match="не найден"):
            _read_oil_pvt_csv(tmp_path / "no_such_file.csv")

    def test_gas_csv_missing_file(self, tmp_path):
        """Несуществующий файл → ValueError."""
        with pytest.raises(ValueError, match="не найден"):
            _read_gas_pvt_csv(tmp_path / "no_such_file.csv")

    def test_relperm_csv_missing_file(self, tmp_path):
        """Несуществующий файл → ValueError."""
        with pytest.raises(ValueError, match="не найден"):
            _read_relperm_csv(tmp_path / "no_such_file.csv")


# ═══════════════════════════════════════════════════════════
# B. Factory с табличным PVT
# ═══════════════════════════════════════════════════════════

class TestFactoryTablePVT:
    """Factory: pvt.model="table" → PrototypeHydroAdapter."""

    def test_from_config_creates_prototype_hydro(self):
        """HydroSolver = PrototypeHydroAdapter при pvt.model='table'."""
        config = load_config(TABLE_CONFIG)
        simulator, initial = SimulatorFactory.from_config(config)

        assert isinstance(simulator._hydro, PrototypeHydroAdapter)

    def test_pvt_is_table_full(self):
        """PVT = TableFullPVT при pvt.model='table'."""
        config = load_config(TABLE_CONFIG)
        simulator, initial = SimulatorFactory.from_config(config)

        assert isinstance(simulator._pvt, TableFullPVT)

    def test_factory_passes_max_retries(self):
        """Factory доносит numerics.max_retries до Simulator (DEBT-007, DEBT-015).

        Корень DEBT-007 в том, что Factory создавала адаптер тремя
        позиционными аргументами и лимит всегда оставался равным
        значению по умолчанию. Тест закрывает именно эту дыру. После
        DEBT-015 шаг дробит Simulator — лимит живёт только там.
        """
        config = load_config(TABLE_CONFIG)
        config.numerics.max_retries = 7
        simulator, _ = SimulatorFactory.from_config(config)

        assert simulator._max_retries == 7
        # Лимит в одном месте: у адаптера его нет — он не дробит шаг
        assert not hasattr(simulator._hydro, "_max_retries")

    def test_factory_default_max_retries(self):
        """Без правки конфига Simulator получает штатные 9, а не 5."""
        config = load_config(TABLE_CONFIG)
        simulator, _ = SimulatorFactory.from_config(config)

        assert simulator._max_retries == 9

    def test_factory_passes_newton_fields(self):
        """Поля Ньютона из конфига доходят до прототипа (DEBT-008).

        До DEBT-008 фабрика их не передавала: прототип считал со своими
        умолчаниями при любом значении в конфиге (проба
        vault/issues/debt-008/probes/red_state.out.txt).
        """
        config = load_config(TABLE_CONFIG)
        nc = config.numerics
        nc.newton_max_iter, nc.max_active_set_iter = 7, 5
        nc.rs_switch_tol, nc.sg_switch_tol = 2e-5, 3e-9
        simulator, _ = SimulatorFactory.from_config(config)
        hydro = simulator._hydro
        assert (hydro._max_newton, hydro._max_active_iter) == (7, 5)
        assert (hydro._model.rs_switch_tol, hydro._model.sg_switch_tol) == (2e-5, 3e-9)

    def test_factory_default_newton_fields(self):
        """Без numerics в конфиге — умолчания прототипа: 15, 12, 1e-5, 1e-9."""
        config = load_config(TABLE_CONFIG)
        simulator, _ = SimulatorFactory.from_config(config)
        hydro = simulator._hydro
        assert (hydro._max_newton, hydro._max_active_iter) == (15, 12)
        assert (hydro._model.rs_switch_tol, hydro._model.sg_switch_tol) == (1e-5, 1e-9)

    def test_prototype_relperm_from_csv(self):
        """Прототип получает табличную ОФП с узлами CSV, а не пересчёт на 101 узле (DEBT-006).

        Пересчёт на сетке np.linspace(0, 1, 101) — ветка CoreyRP. Для таблицы
        он дал бы 101 узел и сдвинул порог активации газа sg_activation_cap
        (BUG-018, radial_blackoil/blackoil.py:49-54 — последний узел с
        k_ro > 0) с 0.6 на 0.79: в configs/table_pvt/relperm.csv k_ro = 0
        впервые в узле 0.8, предыдущий узел — 0.6, а на 101 узле — 0.79.
        Замер при планировании DEBT-006: на примерах 04 и 05 такая подмена
        меняет историю лишь в последних битах (отн. ≤ 4e-14) — числовые
        тесты её не видят, видит только этот.
        """
        config = load_config(TABLE_CONFIG)
        assert isinstance(create_relperm(config), PrototypeRPAdapter)
        simulator, _ = SimulatorFactory.from_config(config)
        model = simulator._hydro._model
        Sg, _, _ = _read_relperm_csv(config.config_dir / config.relperm.file)
        np.testing.assert_array_equal(model.relperm.sg, Sg)
        assert model.sg_activation_cap == 0.6

    def test_initial_state_shapes(self):
        """Начальное состояние: размеры массивов = N."""
        config = load_config(TABLE_CONFIG)
        _, initial = SimulatorFactory.from_config(config)

        assert initial.p.shape == (config.grid.N,)
        assert initial.Sg.shape == (config.grid.N,)
        assert initial.Rs.shape == (config.grid.N,)
        assert initial.T.shape == (config.grid.N,)

    def test_config_dir_resolved(self):
        """config_dir заполнен при load_config."""
        config = load_config(TABLE_CONFIG)
        assert config.config_dir == TABLE_CONFIG.parent


# ═══════════════════════════════════════════════════════════
# C. Pipeline: from_config → run → history
# ═══════════════════════════════════════════════════════════

class TestPipeline:
    """Полный pipeline: JSON → Factory → Simulator.run()."""

    def test_run_produces_history(self):
        """run() не падает, history содержит данные."""
        config = load_config(TABLE_CONFIG)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)

        assert history.n_saved > 1

    def test_well_rate_positive(self):
        """Давление снижается (добыча идёт)."""
        config = load_config(TABLE_CONFIG)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)

        # Финальное состояние: давление должно снизиться от начального
        p_final = history.states[-1].p
        assert np.all(p_final <= config.initial_conditions.p0 + 1e-3)


# ═══════════════════════════════════════════════════════════
# D. PVT-согласованность
# ═══════════════════════════════════════════════════════════

class TestPVTConsistency:
    """Один BlackOilPVT в обёртке и в модели."""

    def test_pvt_objects_are_same(self):
        """Один BlackOilPVT у прототипа и обёртки; один FullPVT у адаптера, энергии, Simulator."""
        config = load_config(TABLE_CONFIG)
        simulator, _ = SimulatorFactory.from_config(config)

        hydro = simulator._hydro
        assert isinstance(hydro, PrototypeHydroAdapter)

        # Прототип считает тем же BlackOilPVT, что лежит под TableFullPVT
        assert hydro._model.pvt is simulator._pvt.hydro.proto_pvt
        # Пересчёт потоков в адаптере, энергия и Simulator — один объект
        # FullPVT (DEBT-006; прежде адаптер получал развёрнутый PrototypePVTAdapter)
        assert hydro._pvt is simulator._pvt
        assert simulator._energy._pvt is simulator._pvt

    def test_bo_consistency(self):
        """Bo через обёртку и через прототип совпадают."""
        config = load_config(TABLE_CONFIG)
        simulator, _ = SimulatorFactory.from_config(config)

        our_pvt = simulator._pvt.hydro   # PrototypePVTAdapter
        proto_pvt = our_pvt.proto_pvt    # BlackOilPVT

        p_pa = 15e6
        Rs = 20.0
        p_bar = p_pa / BAR_TO_PA

        bo_our = our_pvt.Bo(np.array([p_pa]), np.array([Rs]))[0]
        bo_proto = proto_pvt.bo(np.array([p_bar]), np.array([Rs]))[0]

        assert bo_our == pytest.approx(bo_proto)

    def test_proto_pvt_shared_for_table(self):
        """Табличная PVT: прототипу — тот же BlackOilPVT, что под обёрткой (DEBT-006)."""
        config = load_config(TABLE_CONFIG)
        pvt = create_pvt(config)
        proto = _get_or_create_proto_pvt(pvt, config.initial_conditions.p0)
        assert proto is pvt.hydro.proto_pvt

    def test_proto_rp_shared_for_table(self):
        """Табличная ОФП: прототипу — тот же TabulatedRelPerm, а не 101 узел (DEBT-006)."""
        relperm = create_relperm(load_config(TABLE_CONFIG))
        assert _get_or_create_proto_rp(relperm) is relperm.proto_rp


class TestWrapperAccess:
    """Публичный доступ к объектам прототипа под обёртками (DEBT-006).

    Фабрика и скрипты графиков берут BlackOilPVT и TabulatedRelPerm через
    свойства, а не через приватные поля _hydro, _pvt, _rp. Свойства только
    для чтения: подмена объекта разорвала бы «один источник» PVT/ОФП для
    прототипа и наших модулей (vault/knowledge/decisions/согласованность-pvt-hydro.md).
    """

    def _wrappers(self):
        """Три обёртки над объектами-метками: конструкторы лишь сохраняют ссылки."""
        proto_pvt, proto_rp = object(), object()
        adapter = PrototypePVTAdapter(proto_pvt, rho_o_std=850.0, rho_g_std=0.85)
        table = TableFullPVT(adapter, c_p_oil=2000.0, c_p_gas=2200.0,
                             mu_JT_oil=-4e-7, mu_JT_gas=3e-6, L_degas=0.0)
        rp = PrototypeRPAdapter(proto_rp)
        return proto_pvt, proto_rp, adapter, table, rp

    def test_prototype_pvt_adapter_proto_pvt(self):
        """PrototypePVTAdapter.proto_pvt — тот самый объект, что передан в конструктор."""
        proto_pvt, _, adapter, _, _ = self._wrappers()
        assert adapter.proto_pvt is proto_pvt

    def test_table_full_pvt_hydro(self):
        """TableFullPVT.hydro — тот самый адаптер, а через него — объект прототипа."""
        proto_pvt, _, adapter, table, _ = self._wrappers()
        assert table.hydro is adapter
        assert table.hydro.proto_pvt is proto_pvt

    def test_prototype_rp_adapter_proto_rp(self):
        """PrototypeRPAdapter.proto_rp — тот самый объект, что передан в конструктор."""
        _, proto_rp, _, _, rp = self._wrappers()
        assert rp.proto_rp is proto_rp

    def test_accessors_read_only(self):
        """Присвоить свойству нельзя — AttributeError: общий объект не подменить."""
        _, _, adapter, table, rp = self._wrappers()
        for obj, name in ((adapter, "proto_pvt"), (table, "hydro"), (rp, "proto_rp")):
            with pytest.raises(AttributeError):
                setattr(obj, name, object())


# ═══════════════════════════════════════════════════════════
# E. Ошибки конфигурации
# ═══════════════════════════════════════════════════════════

class TestConfigErrors:
    """Ошибки при невалидном конфиге с табличным PVT."""

    def test_table_pvt_without_csv_raises(self, tmp_path):
        """pvt.model='table' без CSV файла → ValueError."""
        import json
        bad_config = {
            "geometry": {"r_well": 0.1, "R_ext": 50.0, "h": 10.0},
            "grid": {"N": 10},
            "rock": {"porosity": 0.2, "permeability": 1e-13,
                     "rho_cp_solid": 1e6, "lambda_solid": 1.5,
                     "lambda_oil": 0.14, "lambda_gas": 0.04},
            "pvt": {"model": "table", "rho_o_std": 850.0, "rho_g_std": 0.85,
                    "oil_pvt_file": "missing_oil.csv",
                    "gas_pvt_file": "missing_gas.csv"},
            "relperm": {"model": "corey"},
            "thermal": {"c_p_oil": 2000, "c_p_gas": 1000,
                        "mu_JT_oil": 0, "mu_JT_gas": 0, "L_degas": 0},
            "initial_conditions": {"p0": 20e6, "T0": 350.0, "Rs0": 30.0},
            "time": {"dt_integration": 3600,
                     "history": [{"dt": 86400, "control": "pressure", "p_wf": 15e6}]},
        }
        cfg_path = tmp_path / "bad.json"
        cfg_path.write_text(json.dumps(bad_config))

        config = load_config(cfg_path)
        with pytest.raises(ValueError, match="не найден"):
            SimulatorFactory.from_config(config)


# ═══════════════════════════════════════════════════════════
# F. Начальное состояние против PVT-таблиц (BUG-017)
# ═══════════════════════════════════════════════════════════

def _table_config_with_oil_csv(tmp_path, oil_csv_text):
    """TABLE_CONFIG с подменённой oil_pvt.csv: копия CSV в tmp_path, config_dir → tmp_path."""
    for name in ("gas_pvt.csv", "relperm.csv"):
        shutil.copy(TABLE_CONFIG.parent / name, tmp_path / name)
    (tmp_path / "oil_pvt.csv").write_text(oil_csv_text, encoding="utf-8")
    config = load_config(TABLE_CONFIG)
    config.config_dir = tmp_path
    return config


class TestInitialStateVsTable:
    """Фабрика отвергает начальное состояние, которое таблица не описывает (BUG-017).

    Таблица configs/table_pvt: ветки Rs = 0 (p_b = 5 МПа) и 30 (p_b = 15 МПа),
    газ 5…30 МПа. BlackOilPVT не экстраполирует: Rs вне веток обрезается,
    а запас газа считается с полным Rs0 — решатель видит пересыщение при
    любом давлении (отказ или скачок давления до 111 МПа при Rs0 = 40).
    """

    def test_rs0_above_last_branch_raises(self):
        """Rs0 = 150 > 30: ошибка про диапазон таблицы, а не про пересыщение.

        Проверка диапазона идёт раньше проверки пересыщения: p_b(150) обрезан
        до 15 МПа < p0, и сообщение о пересыщении было бы противоречивым.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 150.0
        with pytest.raises(ValueError, match="вне диапазона таблицы") as exc:
            SimulatorFactory.from_config(config)
        assert "пересыщ" not in str(exc.value)
        assert "Rs0 = 150" in str(exc.value)

    def test_rs0_below_guard_threshold_raises(self):
        """Rs0 = 40: ниже порога 1.5·Rs_max = 45 пробного вектора Ньютона.

        До правки (после BUG-016) первый шаг молча «сходился» с давлением
        111 МПа. Ловит проверку, ограниченную порогом решателя.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 40.0
        with pytest.raises(ValueError, match="вне диапазона таблицы"):
            SimulatorFactory.from_config(config)

    def test_rs0_below_first_branch_raises(self, tmp_path):
        """Таблица с ветками 5 и 30, Rs0 = 0 < 5: ошибка (решение 2 плана).

        Ниже первой ветки нефть молча не разгазируется никогда
        (R_s^sat(p) >= 5 > Rs0), а B_o, μ_o берутся с ветки 5.
        """
        config = _table_config_with_oil_csv(tmp_path, (
            "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
            "5.0,6000000,1.07,0.0028\n"
            "5.0,30000000,1.06,0.0030\n"
            "30.0,15000000,1.20,0.0015\n"
            "30.0,30000000,1.18,0.0016\n"))
        config.initial_conditions.Rs0 = 0.0
        with pytest.raises(ValueError, match="вне диапазона таблицы"):
            SimulatorFactory.from_config(config)

    def test_rs0_on_last_branch_passes(self):
        """Rs0 = 30 ровно на последней ветке, p0 = 20 МПа > p_b = 15 МПа — допустимо.

        Граница включается: R_s^eq(p0) = 30 ровно (обрезка), Rs0 = 30.
        Так стоят 13 из 14 табличных примеров.
        """
        config = load_config(TABLE_CONFIG)
        assert config.initial_conditions.Rs0 == 30.0
        SimulatorFactory.from_config(config)   # не бросает

    def test_supersaturated_start_raises(self):
        """Rs0 = 20 внутри таблицы, p0 = 10 МПа: R_s^eq(10 МПа) = 15 < 20 — ошибка.

        p_b(20) = 11.67 МПа > p0. Решатель стартует только из однофазного
        состояния; без проверки давление на первом шаге скачком росло бы к p_b.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 20.0
        config.initial_conditions.p0 = 10e6
        with pytest.raises(ValueError, match="пересыщено") as exc:
            SimulatorFactory.from_config(config)
        assert "11.6667" in str(exc.value)   # p_b(20) = 5 + 20/30·10 МПа

    def test_p0_at_bubble_point_passes(self):
        """p0 = p_b(30) = 15 МПа ровно: R_s^eq(p0) = Rs0 — допустимо (как пример 11, p0 = 15.05)."""
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.p0 = 15e6
        SimulatorFactory.from_config(config)

    def test_p0_1pa_below_pb_passes(self):
        """p0 на 1 Па ниже p_b(30): избыток Rs 3e-6 < допуска 1e-5 — округление ввода не ошибка."""
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.p0 = 15e6 - 1.0
        SimulatorFactory.from_config(config)

    def test_supersaturation_tolerance_from_config(self):
        """Допуск пересыщения старта — numerics.rs_switch_tol (DEBT-008).

        p0 на 1 Па ниже p_b(30): избыток R_s 3e-6. При умолчании 1e-5 старт
        допустим (тест выше), при допуске 1e-6 — нет: проверка берёт тот же
        допуск, по которому решатель включает газ. До DEBT-008 допуск 1e-5 был
        зашит в фабрике (проба red_state.out.txt, п. 4).
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.p0 = 15e6 - 1.0
        config.numerics.rs_switch_tol = 1e-6
        with pytest.raises(ValueError, match="пересыщено"):
            SimulatorFactory.from_config(config)

    def test_dead_oil_below_table_pb0_passes(self):
        """Rs0 = 0, p0 = 3 МПа ниже табличного p_b(0) = 5 МПа — допустимо.

        R_s^eq(3 МПа) = 0 = Rs0: пересыщения нет, решатель газ не включит.
        Ловит переход на формулировку p0 >= p_b(Rs0) — она дала бы ложную ошибку.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 0.0
        config.initial_conditions.p0 = 3e6
        SimulatorFactory.from_config(config)


class TestInitialRangeWarnings:
    """Предупреждения pvt_range_warnings прототипа для начального состояния (BUG-017)."""

    def test_p0_above_tables_warns(self, caplog):
        """p0 = 32 МПа выше газовой таблицы и веток нефти (до 30 МПа): два предупреждения.

        Расчёт допустим (Rs0 = 30 = R_s^eq), но B_g и B_o молча берутся с краёв
        таблиц — пользователь должен это видеть.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.p0 = 32e6
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            SimulatorFactory.from_config(config)
        text = "\n".join(r.getMessage() for r in caplog.records
                         if r.levelno == logging.WARNING)
        assert "GAS_PVT pressure above table" in text
        assert "OIL_PVT branch pressure above supplied range" in text

    def test_in_range_no_warnings(self, caplog):
        """Штатный табличный конфиг: начальное состояние внутри всех таблиц — предупреждений нет."""
        config = load_config(TABLE_CONFIG)
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            SimulatorFactory.from_config(config)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


# ═══════════════════════════════════════════════════════════
# G. Ветви PVTO-таблицы (DEBT-038)
# ═══════════════════════════════════════════════════════════

# Ветви таблицы configs/table_pvt: R_s = 0 (p_b = 5 МПа) и 30 (p_b = 15 МПа)
OIL_HEADER = "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
OIL_BRANCH_0 = "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
OIL_BRANCH_30 = "30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"


class TestPVTOBranches:
    """Фабрика отвергает CSV-таблицу PVTO с ошибкой в ветвях (DEBT-038).

    Правила формата PVTO (OPM Flow Manual §8.3.245): в ветви R_s не меньше
    двух строк, давление строго растёт по порядку файла (их же проверяет
    XLSX-ридер прототипа, input_reader.py:59-64), p_b растёт с R_s.
    BlackOilPVT их не проверяет: до правки все таблицы ниже, кроме пустой,
    проходили from_config молча (пробы vault/issues/debt-038/probes/).
    Конфиг — TABLE_CONFIG (Rs0 = 30, p0 = 20 МПа).
    """

    def test_one_row_branch_raises(self, tmp_path):
        """Ветвь R_s = 15 из одной строки между полными ветвями 0 и 30.

        До правки B_o = 1.12 и μ_o этой ветви постоянны выше p_b = 10 МПа
        (c_o = 0): нефть у этой ветви несжимаема, сообщения нет.
        """
        config = _table_config_with_oil_csv(
            tmp_path,
            OIL_HEADER + OIL_BRANCH_0 + "15.0,10000000,1.12,0.0022\n" + OIL_BRANCH_30)
        with pytest.raises(ValueError,
                           match=r"R_s = 15 м³ст/м³ст из одной строки \(p = 10 МПа\)") as exc:
            SimulatorFactory.from_config(config)
        assert str(exc.value).startswith("oil_pvt.csv:")

    def test_one_row_last_branch_raises(self, tmp_path):
        """Последняя ветвь R_s = 30 из одной строки — её не допускает и OPM.

        OPM Flow Manual §8.3.245: для последнего R_s нужны не меньше двух
        строк, иначе недонасыщенная область не интерполируется.
        """
        config = _table_config_with_oil_csv(
            tmp_path, OIL_HEADER + OIL_BRANCH_0 + "30.0,15000000,1.20,0.0015\n")
        with pytest.raises(ValueError, match=r"R_s = 30 м³ст/м³ст из одной строки"):
            SimulatorFactory.from_config(config)

    def test_repeated_pressure_raises(self, tmp_path):
        """Давление 20 МПа дважды в ветви 30 (B_o 1.19 и 1.185).

        До правки BlackOilPVT сортировал строки по (p, B_o, μ_o): первой шла
        строка с меньшим B_o, и B_o скачком менялся при 20 МПа. Единственный
        сигнал — RuntimeWarning «divide by zero» из pvt.py без имени файла.
        """
        config = _table_config_with_oil_csv(tmp_path, OIL_HEADER + OIL_BRANCH_0 + (
            "30.0,15000000,1.20,0.0015\n"
            "30.0,20000000,1.19,0.00152\n"
            "30.0,20000000,1.185,0.00153\n"
            "30.0,30000000,1.18,0.0016\n"))
        with pytest.raises(ValueError, match="не растёт строго") as exc:
            SimulatorFactory.from_config(config)
        assert "20 МПа после 20 МПа (строки 2 и 3 ветви)" in str(exc.value)

    def test_pressure_out_of_order_raises(self, tmp_path):
        """Строки ветви 30 переставлены: 15, 30, 20 МПа (решение пользователя 2026-10-07).

        BlackOilPVT исправил бы порядок сортировкой, но XLSX-путь такую
        таблицу отвергает — правила двух путей одинаковы.
        """
        config = _table_config_with_oil_csv(tmp_path, OIL_HEADER + OIL_BRANCH_0 + (
            "30.0,15000000,1.20,0.0015\n"
            "30.0,30000000,1.18,0.0016\n"
            "30.0,20000000,1.19,0.00152\n"))
        with pytest.raises(ValueError, match=r"20 МПа после 30 МПа \(строки 2 и 3 ветви\)"):
            SimulatorFactory.from_config(config)

    def test_rs_typo_extra_branch_raises(self, tmp_path):
        """Опечатка R_s = 30.01 вместо 30 у средней строки ветви 30 — лишняя ветвь из одной строки.

        До правки Rs0 = 30 лежал внутри [0, 30.01], R_s^eq(20 МПа) = 30.007 —
        from_config проходил, B_o около R_s = 30 шёл по искажённым ветвям.
        """
        config = _table_config_with_oil_csv(tmp_path, OIL_HEADER + OIL_BRANCH_0 + (
            "30.0,15000000,1.20,0.0015\n"
            "30.01,22000000,1.19,0.00155\n"
            "30.0,30000000,1.18,0.0016\n"))
        with pytest.raises(ValueError, match=r"R_s = 30\.01 м³ст/м³ст из одной строки"):
            SimulatorFactory.from_config(config)

    def test_bubble_point_not_increasing_raises(self, tmp_path):
        """Опечатка в p_b: ветвь R_s = 15 начинается с 20 МПа вместо 10, у ветви 30 p_b = 15 МПа.

        Внутри каждой ветви давление растёт. До правки from_config проходил
        без предупреждений, а R_s^sat(p) интерполировался np.interp по
        немонотонным узлам p_b: R_s^sat(14 МПа) = 9 вместо 27 (проба
        pb_order.py). Правило OPM — p_b растёт с R_s (решение пользователя
        при аудите 2026-10-07).
        """
        config = _table_config_with_oil_csv(tmp_path, OIL_HEADER + OIL_BRANCH_0 + (
            "15.0,20000000,1.12,0.0022\n"
            "15.0,30000000,1.11,0.0023\n") + OIL_BRANCH_30)
        with pytest.raises(ValueError, match="давление насыщения не растёт с R_s") as exc:
            SimulatorFactory.from_config(config)
        assert "p_b = 15 МПа у ветви R_s = 30" in str(exc.value)
        assert "p_b = 20 МПа у ветви R_s = 15" in str(exc.value)

    def test_empty_table_raises(self, tmp_path):
        """Только заголовок: до правки — IndexError из BlackOilPVT без имени файла.

        Ловит и место вызова: проверка после BlackOilPVT дала бы IndexError.
        """
        config = _table_config_with_oil_csv(tmp_path, OIL_HEADER)
        with pytest.raises(ValueError, match="oil_pvt.csv: нет ни одной числовой строки"):
            SimulatorFactory.from_config(config)

    def test_interleaved_branches_pass(self, tmp_path):
        """Строки ветвей 0 и 30 чередуются в файле — таблица корректна.

        Ветвь — все строки с одним R_s, порядок давлений проверяется внутри
        ветви, как в XLSX-ридере и BlackOilPVT. Ловит слишком строгую проверку
        (требование смежности строк ветви).
        """
        config = _table_config_with_oil_csv(tmp_path, OIL_HEADER + (
            "0.0,5000000,1.05,0.003\n30.0,15000000,1.20,0.0015\n"
            "0.0,30000000,1.04,0.0032\n30.0,30000000,1.18,0.0016\n"))
        SimulatorFactory.from_config(config)   # не бросает


# ═══════════════════════════════════════════════════════════
# H. Строгий разбор CSV-таблиц (DEBT-042)
# ═══════════════════════════════════════════════════════════

# До DEBT-042 ридеры пропускали ошибочную строку молча (continue), лишние
# поля отбрасывали, заголовок не читали. Поведение до правки — замер
# vault/issues/debt-042/probes/red_state.out.txt (2026-10-07).
# Номер строки в сообщении — номер строки файла, заголовок — строка 1.

GAS_HEADER = "pressure_Pa,Bg,mu_g_Pa_s\n"
RP_HEADER = "Sg,kro,krg\n"


def _csv(tmp_path, name, text):
    """Записать text в tmp_path/name (UTF-8) и вернуть путь."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _parse_error(reader, path):
    """Текст ValueError, который ридер бросает на файле path."""
    with pytest.raises(ValueError) as excinfo:
        reader(path)
    return str(excinfo.value)


class TestCSVStrictParsing:
    """Ридеры отвергают строку, которую нельзя разобрать без потерь (DEBT-042)."""

    # ── Нефть: строки данных ──

    def test_oil_number_typo_raises(self, tmp_path):
        """Буква O вместо нуля в давлении.

        До правки строка пропадала, ветвь R_s = 30 оставалась из одной
        строки — DEBT-038 сообщил бы о ветви, а не об опечатке.
        """
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,15OOOOOO,1.20,0.0015\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4, столбец pressure_Pa" in msg
        assert "15OOOOOO" in msg

    def test_oil_decimal_comma_raises(self, tmp_path):
        """Десятичная запятая «1,20» даёт 5 полей вместо 4.

        До правки значения сдвигались на столбец: B_o = 1, μ_o = 20 Па·с
        (20000 сП вместо 1.5) — молча.
        """
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,15000000,1,20,0.0015\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4: число полей 5, а столбцов в заголовке 4" in msg

    def test_oil_short_row_raises(self, tmp_path):
        """Пропущено значение μ_o: 3 поля. До правки строка пропадала."""
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,15000000,1.20\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4: число полей 3, а столбцов в заголовке 4" in msg

    def test_oil_trailing_comma_raises(self, tmp_path):
        """Запятая в конце строки — лишнее пустое поле (решение пользователя 3).

        До правки лишнее поле отбрасывалось. Правило одно для всех строк:
        полей столько же, сколько столбцов в заголовке.
        """
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,15000000,1.20,0.0015,\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4: число полей 5" in msg

    def test_oil_nan_raises(self, tmp_path):
        """float() принимает 'nan'; сравнения с NaN ложны, и DEBT-038 строку не ловит."""
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,nan,1.20,0.0015\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4, столбец pressure_Pa" in msg
        assert "не конечное число" in msg

    def test_oil_inf_raises(self, tmp_path):
        """'inf' в B_o: до правки принимался как бесконечный объёмный коэффициент."""
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,15000000,inf,0.0015\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4, столбец Bo" in msg
        assert "не конечное число" in msg

    # ── Нефть: заголовок и файл ──

    def test_oil_no_header_raises(self, tmp_path):
        """Файл без заголовка: до правки первая строка данных (p_b ветви 0) пропадала."""
        path = _csv(tmp_path, "oil_pvt.csv", OIL_BRANCH_0 + OIL_BRANCH_30)
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: заголовок" in msg
        assert "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s" in msg   # ожидаемый заголовок назван

    def test_oil_swapped_header_raises(self, tmp_path):
        """Столбцы Bo и mu_o_Pa_s переставлены: до правки читались по позиции, молча."""
        path = _csv(tmp_path, "oil_pvt.csv",
                    "Rs_sm3_sm3,pressure_Pa,mu_o_Pa_s,Bo\n" + OIL_BRANCH_0)
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: заголовок" in msg

    def test_oil_semicolon_raises(self, tmp_path):
        """CSV из Excel в русской локали (; и запятая в числах): до правки 0 строк молча."""
        path = _csv(tmp_path, "oil_pvt.csv",
                    "Rs_sm3_sm3;pressure_Pa;Bo;mu_o_Pa_s\n0,0;5000000;1,05;0,003\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: заголовок" in msg
        assert "Разделитель столбцов — запятая" in msg

    def test_oil_empty_file_raises(self, tmp_path):
        """Файл нулевой длины: до правки — StopIteration из next(reader)."""
        path = _csv(tmp_path, "oil_pvt.csv", "")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: файл пуст" in msg

    def test_oil_bom_spaces_and_blank_rows_accepted(self, tmp_path):
        """Допустимо: BOM, пробелы вокруг имён столбцов, строка из пробелов, строка из пустых полей.

        Результат — как у той же таблицы без этих особенностей. Тест зелёный
        и до правки: он защищает от избыточной строгости.
        """
        text = ("﻿Rs_sm3_sm3, pressure_Pa, Bo, mu_o_Pa_s\n"
                "0.0,5000000,1.05,0.003\n"
                "   \n"                        # строка из пробелов
                ",,,\n"                        # пустые ячейки — хвост экспорта из Excel
                "0.0,30000000,1.04,0.0032\n")
        rows = _read_oil_pvt_csv(_csv(tmp_path, "oil_pvt.csv", text))
        clean = _read_oil_pvt_csv(_csv(tmp_path, "clean.csv", OIL_HEADER + OIL_BRANCH_0))
        assert rows == clean
        assert len(rows) == 2

    # ── Газ ──

    def test_gas_number_typo_raises(self, tmp_path):
        """Буква O в B_g: до правки узел 15 МПа пропадал, B_g интерполировался через пропуск."""
        path = _csv(tmp_path, "gas_pvt.csv", GAS_HEADER
                    + "5000000,0.020,0.000012\n15000000,0.0O8,0.000014\n30000000,0.004,0.000018\n")
        msg = _parse_error(_read_gas_pvt_csv, path)
        assert "gas_pvt.csv: строка 3, столбец Bg" in msg

    # ── ОФП ──

    def test_relperm_swapped_header_raises(self, tmp_path):
        """Заголовок Sg,krg,kro: до правки ОФП нефти и газа молча менялись местами."""
        path = _csv(tmp_path, "relperm.csv", "Sg,krg,kro\n0.0,0.0,1.0\n0.8,0.8,0.0\n")
        msg = _parse_error(_read_relperm_csv, path)
        assert "relperm.csv: заголовок" in msg

    def test_relperm_error_in_kro_raises(self, tmp_path):
        """Ошибка во 2-м столбце: до правки Sg дописывался, kro — нет, длины (3, 2, 2)."""
        path = _csv(tmp_path, "relperm.csv",
                    RP_HEADER + "0.0,1.0,0.0\n0.4,0.3x,0.2\n0.8,0.0,0.8\n")
        msg = _parse_error(_read_relperm_csv, path)
        assert "relperm.csv: строка 3, столбец kro" in msg

    def test_relperm_error_in_krg_raises(self, tmp_path):
        """Ошибка в 3-м столбце: до правки длины (3, 3, 2)."""
        path = _csv(tmp_path, "relperm.csv",
                    RP_HEADER + "0.0,1.0,0.0\n0.4,0.3,0.2x\n0.8,0.0,0.8\n")
        msg = _parse_error(_read_relperm_csv, path)
        assert "relperm.csv: строка 3, столбец krg" in msg

    def test_relperm_bad_row_fails_in_from_config(self, tmp_path):
        """Ошибка ОФП ловится в from_config с именем файла, а не при счёте.

        До правки from_config проходил, а run падал на первом вычислении
        ОФП: «ValueError: fp and xp are not of the same length» из np.interp.
        Таблица — configs/table_pvt/relperm.csv с опечаткой в kro строки 6.
        """
        for name in ("oil_pvt.csv", "gas_pvt.csv"):
            shutil.copy(TABLE_CONFIG.parent / name, tmp_path / name)
        _csv(tmp_path, "relperm.csv", RP_HEADER
             + "0.0,1.0,0.0\n0.1,0.8,0.01\n0.2,0.6,0.05\n"
               "0.4,0.3,0.2\n0.6,0.1x,0.5\n0.8,0.0,0.8\n")
        config = load_config(TABLE_CONFIG)
        config.config_dir = tmp_path
        with pytest.raises(ValueError, match="relperm.csv: строка 6, столбец kro"):
            SimulatorFactory.from_config(config)


# ═══════════════════════════════════════════════════════════
# I. Допустимость значений CSV-таблиц (DEBT-044)
# ═══════════════════════════════════════════════════════════

# До DEBT-044 CSV-путь не проверял B > 0, μ > 0, p > 0, R_s ≥ 0, S_g и k_r
# в [0, 1]; число строк и рост p, S_g проверяли только конструкторы прототипа —
# на английском и без имени файла. Поведение до правки — проба
# vault/issues/debt-044/probes/red_state.out.txt (2026-10-07): таблица
# configs/table_pvt с одной испорченной строкой, run 24 ч при p_wf = 15 МПа
# (штатный, = p_b, газа нет) и 10 МПа (газовая зона у забоя). Эталон при
# 10 МПа: S_g max 0.0098, T 349.91…351.02 К.

# Строки данных gas_pvt.csv и relperm.csv конфига configs/table_pvt
TABLE_GAS_ROWS = ["5000000,0.020,0.000012\n", "15000000,0.008,0.000014\n",
                  "30000000,0.004,0.000018\n"]
TABLE_RP_ROWS = ["0.0,1.0,0.0\n", "0.1,0.8,0.01\n", "0.2,0.6,0.05\n",
                 "0.4,0.3,0.2\n", "0.6,0.1,0.5\n", "0.8,0.0,0.8\n"]


def _with_row(header, rows, index, line):
    """Текст таблицы header + rows, где строка данных rows[index] заменена на line."""
    rows = list(rows)
    rows[index] = line
    return header + "".join(rows)


def _table_config_with_csv(tmp_path, name, text):
    """TABLE_CONFIG, где таблица name заменена на text; остальные — копии configs/table_pvt."""
    for fname in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
        shutil.copy(TABLE_CONFIG.parent / fname, tmp_path / fname)
    (tmp_path / name).write_text(text, encoding="utf-8")
    config = load_config(TABLE_CONFIG)
    config.config_dir = tmp_path
    return config


# Значение вне пределов столбца: (файл, текст таблицы, строка файла, столбец, правило).
# Комментарий к случаю — что было до правки (проба red_state).
VALUE_CASES = [
    # ── Газ: p, B_g, μ_g > 0 (строка 3 — узел 15 МПа) ──
    # при 10 МПа счёт проходит с «divide by zero»: S_g max 0.0068 вместо 0.0098
    pytest.param("gas_pvt.csv",
                 _with_row(GAS_HEADER, TABLE_GAS_ROWS, 1, "15000000,0.0,0.000014\n"),
                 3, "Bg", "> 0", id="gas_Bg_zero"),
    # при 10 МПа Ньютон не сходится на первом шаге
    pytest.param("gas_pvt.csv",
                 _with_row(GAS_HEADER, TABLE_GAS_ROWS, 1, "15000000,-0.008,0.000014\n"),
                 3, "Bg", "> 0", id="gas_Bg_negative"),
    # при 10 МПа молча: S_g max 0.0043
    pytest.param("gas_pvt.csv",
                 _with_row(GAS_HEADER, TABLE_GAS_ROWS, 1, "15000000,0.008,0\n"),
                 3, "mu_g_Pa_s", "> 0", id="gas_mu_zero"),
    # при 10 МПа Ньютон не сходится на первом шаге
    pytest.param("gas_pvt.csv",
                 _with_row(GAS_HEADER, TABLE_GAS_ROWS, 1, "15000000,0.008,-0.000014\n"),
                 3, "mu_g_Pa_s", "> 0", id="gas_mu_negative"),
    # узел 5 МПа записан как −5 МПа: при 10 МПа молча S_g max 0.0081
    pytest.param("gas_pvt.csv",
                 _with_row(GAS_HEADER, TABLE_GAS_ROWS, 0, "-5000000,0.020,0.000012\n"),
                 2, "pressure_Pa", "> 0", id="gas_p_negative"),
    # ── Нефть: p, B_o, μ_o > 0, R_s ≥ 0 (строка 4 — насыщенная точка ветви 30) ──
    # Ньютон не сходится на первом шаге, «divide by zero»
    pytest.param("oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                 + "30.0,15000000,0.0,0.0015\n30.0,30000000,1.18,0.0016\n",
                 4, "Bo", "> 0", id="oil_Bo_zero"),
    # при 15 МПа счёт проходит до конца: T min = −245.8 К, сообщений нет
    pytest.param("oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                 + "30.0,15000000,-1.20,0.0015\n30.0,30000000,1.18,0.0016\n",
                 4, "Bo", "> 0", id="oil_Bo_negative"),
    # Ньютон не сходится на первом шаге, «divide by zero»
    pytest.param("oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                 + "30.0,15000000,1.20,0\n30.0,30000000,1.18,0.0016\n",
                 4, "mu_o_Pa_s", "> 0", id="oil_mu_zero"),
    # при 15 МПа молча: T min = 169.8 К
    pytest.param("oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                 + "30.0,15000000,1.20,-0.0015\n30.0,30000000,1.18,0.0016\n",
                 4, "mu_o_Pa_s", "> 0", id="oil_mu_negative"),
    # лишняя ветвь R_s = −5 (p_b = 4 МПа) перед ветвями 0 и 30: в сценарии
    # пробы не задействована, но таблица нефизична
    pytest.param("oil_pvt.csv", OIL_HEADER + "-5.0,4000000,1.02,0.0031\n-5.0,30000000,1.01,0.0033\n"
                 + OIL_BRANCH_0 + OIL_BRANCH_30,
                 2, "Rs_sm3_sm3", "≥ 0", id="oil_Rs_negative"),
    # p_b ветви 0 записано как −5 МПа: при 10 МПа молча T max 351.58 К вместо 351.02
    pytest.param("oil_pvt.csv", OIL_HEADER + "0.0,-5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
                 + OIL_BRANCH_30,
                 2, "pressure_Pa", "> 0", id="oil_p_negative"),
    # ── ОФП: S_g, k_ro, k_rg в [0, 1] ──
    # при 15 МПа Ньютон не сходится (t = 0.33 сут), при 10 МПа молча S_g max 0.035
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 0, "-0.1,1.0,0.0\n"),
                 2, "Sg", "в [0, 1]", id="rp_Sg_negative"),
    # узел за S_g = 1 искажает k_r у S_g → 1; в коротком сценарии не задействован
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "1.2,0.0,0.8\n"),
                 7, "Sg", "в [0, 1]", id="rp_Sg_above_one"),
    # отвергал и TabulatedRelPerm — на английском, без имени файла
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "0.8,-0.1,0.8\n"),
                 7, "kro", "в [0, 1]", id="rp_kro_negative"),
    # при 10 МПа молча: S_g max 0.0116
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 0, "0.0,1.2,0.0\n"),
                 2, "kro", "в [0, 1]", id="rp_kro_above_one"),
    # отвергал и TabulatedRelPerm — на английском, без имени файла
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 1, "0.1,0.8,-0.01\n"),
                 3, "krg", "в [0, 1]", id="rp_krg_negative"),
    # в коротком сценарии не задействован (S_g у забоя < 0.01)
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "0.8,0.0,1.2\n"),
                 7, "krg", "в [0, 1]", id="rp_krg_above_one"),
]

VALUE_READERS = {"oil_pvt.csv": _read_oil_pvt_csv, "gas_pvt.csv": _read_gas_pvt_csv,
                 "relperm.csv": _read_relperm_csv}


class TestCSVValueChecks:
    """CSV-путь отвергает недопустимые значения и неполные таблицы с именем файла (DEBT-044)."""

    # ── Пределы столбцов: проверка при разборе, с номером строки ──

    @pytest.mark.parametrize("name, text, line, column, rule", VALUE_CASES)
    def test_value_out_of_range_raises(self, tmp_path, name, text, line, column, rule):
        """Значение вне пределов столбца → ValueError ридера: файл, строка, столбец, правило.

        Пределы — _OIL_PVT_LIMITS, _GAS_PVT_LIMITS, _RELPERM_LIMITS в factory.py.
        """
        msg = _parse_error(VALUE_READERS[name], _csv(tmp_path, name, text))
        assert f"{name}: строка {line}, столбец {column}:" in msg
        assert f"должно быть {rule}" in msg

    def test_boundary_values_accepted(self, tmp_path):
        """Границы включаются: S_g, k_ro, k_rg = 0 и 1; R_s = 0.

        Ловит строгое неравенство там, где граница допустима: S_g = 0 и
        k_ro = 1 стоят в первой строке всех 15 таблиц ОФП проекта, R_s = 0 —
        ветвь дегазированной нефти.
        """
        Sg, kro, krg = _read_relperm_csv(
            _csv(tmp_path, "relperm.csv", RP_HEADER + "0.0,1.0,0.0\n1.0,0.0,1.0\n"))
        assert (Sg, kro, krg) == ([0.0, 1.0], [1.0, 0.0], [0.0, 1.0])
        rows = _read_oil_pvt_csv(_csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0))
        assert rows[0][0] == 0.0

    def test_value_error_fails_in_from_config(self, tmp_path):
        """B_o < 0 ловится в from_config с именем файла, а не при счёте.

        До правки from_config и run проходили: T min = −245.8 К при
        p_wf = 15 МПа. Ловит вызов ридера в обход проверки пределов.
        """
        config = _table_config_with_csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                                        + "30.0,15000000,-1.20,0.0015\n30.0,30000000,1.18,0.0016\n")
        with pytest.raises(ValueError, match="oil_pvt.csv: строка 4, столбец Bo"):
            SimulatorFactory.from_config(config)

    # ── Таблица целиком: число строк, рост p и S_g, число ветвей ──

    def test_gas_header_only_raises(self, tmp_path):
        """Только заголовок.

        До правки — «GAS_PVT pressure must be strictly increasing with >=2 rows» (pvt.py:32).
        """
        config = _table_config_with_csv(tmp_path, "gas_pvt.csv", GAS_HEADER)
        with pytest.raises(ValueError, match="gas_pvt.csv: строк данных 0, нужно не меньше двух"):
            SimulatorFactory.from_config(config)

    def test_gas_one_row_raises(self, tmp_path):
        """Одна строка: B_g(p) не интерполировать. До правки — то же английское сообщение."""
        config = _table_config_with_csv(tmp_path, "gas_pvt.csv", GAS_HEADER + TABLE_GAS_ROWS[1])
        with pytest.raises(ValueError, match="gas_pvt.csv: строк данных 1, нужно не меньше двух"):
            SimulatorFactory.from_config(config)

    def test_gas_pressure_not_increasing_raises(self, tmp_path):
        """Строки 5 и 15 МПа переставлены.

        До правки — английское сообщение pvt.py:32 без имени файла.
        """
        config = _table_config_with_csv(
            tmp_path, "gas_pvt.csv",
            GAS_HEADER + TABLE_GAS_ROWS[1] + TABLE_GAS_ROWS[0] + TABLE_GAS_ROWS[2])
        with pytest.raises(ValueError,
                           match="gas_pvt.csv: давление не растёт строго: 5 МПа после 15 МПа"):
            SimulatorFactory.from_config(config)

    def test_relperm_header_only_raises(self, tmp_path):
        """Только заголовок: до правки — «RELPERM Sg must be strictly increasing with >=2 rows»."""
        config = _table_config_with_csv(tmp_path, "relperm.csv", RP_HEADER)
        with pytest.raises(ValueError, match="relperm.csv: строк данных 0, нужно не меньше двух"):
            SimulatorFactory.from_config(config)

    def test_relperm_one_row_raises(self, tmp_path):
        """Одна строка ОФП; до правки — то же английское сообщение relperm.py:5."""
        config = _table_config_with_csv(tmp_path, "relperm.csv", RP_HEADER + TABLE_RP_ROWS[0])
        with pytest.raises(ValueError, match="relperm.csv: строк данных 1, нужно не меньше двух"):
            SimulatorFactory.from_config(config)

    def test_relperm_sg_not_increasing_raises(self, tmp_path):
        """Строки S_g = 0.2 и 0.4 переставлены; до правки — английское сообщение relperm.py:5."""
        swapped = TABLE_RP_ROWS[:2] + [TABLE_RP_ROWS[3], TABLE_RP_ROWS[2]] + TABLE_RP_ROWS[4:]
        config = _table_config_with_csv(tmp_path, "relperm.csv", RP_HEADER + "".join(swapped))
        with pytest.raises(ValueError, match="relperm.csv: S_g не растёт строго: 0.2 после 0.4"):
            SimulatorFactory.from_config(config)

    def test_oil_one_branch_raises(self, tmp_path):
        """Одна ветвь R_s = 30: до правки — «OIL_PVT needs >=2 Rs branches, got 1» (pvt.py:46)."""
        config = _table_config_with_csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_30)
        with pytest.raises(ValueError, match="oil_pvt.csv: одна ветвь R_s = 30 м³ст/м³ст"):
            SimulatorFactory.from_config(config)
