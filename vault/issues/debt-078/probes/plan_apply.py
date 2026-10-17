"""DEBT-078: правки плана (блоки «До → После») — проверка и применение к дереву.

План: vault/plans/debt-078 co-undersaturated-table-check.md. Блоки здесь — те же,
что в плане, символ в символ (проверяет plan_blocks_check.py).

    python plan_apply.py <корень дерева>            # проверить: каждое «До» встречается ровно один раз
    python plan_apply.py <корень дерева> --write    # применить (в worktree)

README.md пакета вне git: в worktree его нет — правка проверяется и применяется
к файлу основного каталога только с ключом --readme (шаг 3 плана).

Аудит 2 (2026-10-17, база f5239de): DEBT-076 влита (f6e9aa0) — вставки шагов 2–3
перенесены в её группу «PVT» (решение пользователя). Вариант аудита 1 («до мест
DEBT-076», независимый от порядка) — в истории файла и audit1_order_check.py.
"""

import sys
from pathlib import Path

FACTORY = "numerical_solver/gpn_multiphase_solver/factory.py"
CONFIG = "numerical_solver/gpn_multiphase_solver/io/config.py"
T_CONFIG = "numerical_solver/tests/test_config.py"
T_FACTORY = "numerical_solver/tests/test_factory_standing_hydro.py"
P8 = "vault/knowledge/decisions/P8-формат-ввода-json.md"
SCHEMA = "vault/knowledge/decisions/json-config-schema.md"
STANDING_NOTE = "vault/knowledge/decisions/pvt-корреляции-стендинг.md"
README = "numerical_solver/README.md"

EDITS = []


def edit(path, old, new):
    EDITS.append((path, old, new))


# ── Шаг 1. create_pvt: отказ при таблице и c_o ≠ 0 ──
edit(FACTORY, '''\
        if pc.mu_o_undersaturated != "none":
            raise ValueError(
                f"mu_o_undersaturated = {pc.mu_o_undersaturated!r} — только для "
                f"model = 'standing'; у табличного PVT вязкость выше p_b задаёт таблица.")
        # CSV → BlackOilPVT (прототип) → PrototypePVTAdapter → TableFullPVT
''', '''\
        if pc.mu_o_undersaturated != "none":
            raise ValueError(
                f"mu_o_undersaturated = {pc.mu_o_undersaturated!r} — только для "
                f"model = 'standing'; у табличного PVT вязкость выше p_b задаёт таблица.")
        # То же для B_o (DEBT-078): выше p_b его задают недонасыщенные ветви
        # PVTO, c_o читает только StandingFullPVT.Bo. До DEBT-078 значение
        # пропускалось молча: пример 04 с c_o = 3.3e-9 1/Па давал B_o, побитово
        # равный c_o = 0 (vault/issues/debt-078/probes/co_undersaturated.out.txt).
        # Явный 0 проходит: от умолчания PVTConfig он неотличим и ничего не
        # меняет. Знак c_o при загрузке конфига проверяет _validate (io/config.py).
        if pc.co_undersaturated != 0.0:
            raise ValueError(
                f"co_undersaturated = {pc.co_undersaturated} 1/Па — только для "
                f"model = 'standing'; у табличного PVT B_o выше p_b задают "
                f"недонасыщенные ветви таблицы. Уберите поле из секции pvt.")
        # CSV → BlackOilPVT (прототип) → PrototypePVTAdapter → TableFullPVT
''')

# ── Шаг 1. Тест отказа create_pvt ──
edit(T_FACTORY, '''\
        config = load_config(TABLE_PVT)
        config.pvt.mu_o_undersaturated = "beal"
        with pytest.raises(ValueError, match="mu_o_undersaturated"):
            create_pvt(config)


class TestStandingDeepDrawdownDenseGrid:
''', '''\
        config = load_config(TABLE_PVT)
        config.pvt.mu_o_undersaturated = "beal"
        with pytest.raises(ValueError, match="mu_o_undersaturated"):
            create_pvt(config)

    def test_co_with_table_raises(self):
        """co_undersaturated ≠ 0 при табличном PVT — ValueError (DEBT-078).

        Выше p_b у таблицы B_o задают её недонасыщенные ветви, c_o читает только
        StandingFullPVT. До DEBT-078 значение пропускалось молча: пример 04 с
        c_o = 3.3e-9 1/Па давал B_o, побитово равный c_o = 0
        (vault/issues/debt-078/probes/co_undersaturated.out.txt). c_o = 0 у
        табличных конфигов (умолчание) проходит — это проверяют остальные тесты
        на TABLE_PVT.
        """
        config = load_config(TABLE_PVT)
        config.pvt.co_undersaturated = 3.3e-9
        with pytest.raises(ValueError, match="co_undersaturated") as exc:
            create_pvt(config)
        # значение — как в конфиге: по нему пользователь найдёт поле
        assert "= 3.3e-09 1/Па" in str(exc.value)


class TestStandingDeepDrawdownDenseGrid:
''')

# ── Шаг 2. PVTConfig: комментарий у полей Стендинга ──
edit(CONFIG, '''\
    # Для Standing
    co_undersaturated: float = 0.0   # сжимаемость нефти при p > pb, 1/Па
    mu_o_undersaturated: str = "none"  # μ_o при p > pb: "none" | "beal" (FEAT-027)
''', '''\
    # Для Standing. При model = "table" выше p_b B_o и μ_o задаёт таблица:
    # c_o ≠ 0 или μ_o ≠ "none" — отказ create_pvt (factory.py; DEBT-078, FEAT-027)
    co_undersaturated: float = 0.0   # c_o ≥ 0 (_validate, DEBT-078) при p > pb, 1/Па
    mu_o_undersaturated: str = "none"  # μ_o при p > pb: "none" | "beal" (FEAT-027)
''')

# ── Шаг 2. _validate: c_o ≥ 0 в блоке «PVT» DEBT-076 ──
# После цикла плотностей; pc = cfg.pvt там уже задан. Заголовок блока
# расширяется: в нём теперь и плотности, и сжимаемость.
edit(CONFIG, '''\
    # ── PVT: плотности при стандартных условиях (DEBT-076, P8 §5) ──
''', '''\
    # ── PVT: плотности при ст. у. (DEBT-076), сжимаемость нефти (DEBT-078); P8 §5 ──
''')

edit(CONFIG, '''\
                f"{name} = {value} кг/м³: плотность {phase} при стандартных "
                f"условиях (не пластовая) должна быть > 0")

    # ── Скважина: скин-фактор (DEBT-056, P8 §5) ──
''', '''\
                f"{name} = {value} кг/м³: плотность {phase} при стандартных "
                f"условиях (не пластовая) должна быть > 0")

    # Сжимаемость недонасыщенной нефти c_o = −(1/B_o)·∂B_o/∂p при постоянном
    # R_s ≥ 0 (DEBT-078, eq:co_cg problem_statement.tex): при постоянном составе
    # объём жидкости с ростом давления не растёт — условие механической
    # устойчивости (∂p/∂V)_T < 0; c_o < 0 — ошибка знака. В недонасыщенной зоне
    # C_p = φ(c_r + c_o)/B_g (абзац под eq:c_ot; c_r проверен выше, DEBT-068):
    # при c_o < −c_r C_p < 0 — задача некорректна, неявный шаг вырождается на
    # последовательности Δt. Проверка строже: c_o < 0 отвергается и при
    # c_r > |c_o|. Замер до DEBT-078 (vault/issues/debt-078/probes/
    # audit1_dt_dependence.out.txt; пример 03, Стендинг, c_r = 0, 1 сут):
    # c_o = −1e-9 — при dt_integration 3600 и 1800 с расчёт молча (одно
    # предупреждение фабрики, BUG-019), при 900 с — отказ после дробления шага
    # до dt/512 с советом увеличить max_retries; −3.3e-9 (значение примеров
    # 17, 20 с обратным знаком) — отказ при всех трёх шагах. Проверка — при
    # любой модели PVT: при таблице c_o ≠ 0 отвергает и create_pvt, но позже и
    # без слова о знаке; отрицательная c_o табличных данных — свойство таблицы,
    # о ней предупреждает фабрика (_warn_negative_compressibility, BUG-019).
    # Верхней границы нет: ошибку единиц (1e-5 1/Па вместо 1e-9) проверка не
    # ловит (vault/issues/debt-078/probes/co_magnitude.out.txt).
    if pc.co_undersaturated < 0:
        raise ValueError(
            f"pvt.co_undersaturated = {pc.co_undersaturated} 1/Па < 0: сжимаемость "
            f"недонасыщенной нефти c_o = −(1/B_o)·∂B_o/∂p должна быть ≥ 0 — объём "
            f"нефти с ростом давления не растёт (вероятно, ошибка знака)")

    # ── Скважина: скин-фактор (DEBT-056, P8 §5) ──
''')

# ── Шаг 2. Тесты _validate ──
edit(T_CONFIG, '''\
- PVT: плотности при ст. у. pvt.rho_o_std, pvt.rho_g_std > 0 при любой модели PVT (DEBT-076).
''', '''\
- PVT: плотности при ст. у. pvt.rho_o_std, pvt.rho_g_std > 0 при любой модели PVT (DEBT-076).
- PVT: сжимаемость недонасыщенной нефти pvt.co_undersaturated ≥ 0 при любой модели (DEBT-078).
''')

# Класс — сразу после TestValidationPVT (плотности, DEBT-076): тесты секции pvt рядом
edit(T_CONFIG, '''\
        assert (cfg.pvt.rho_o_std, cfg.pvt.rho_g_std) == (rho_o, rho_g)


class TestValidationInitial:
''', '''\
        assert (cfg.pvt.rho_o_std, cfg.pvt.rho_g_std) == (rho_o, rho_g)


class TestValidationOilCompressibility:
    """pvt.co_undersaturated ≥ 0 (DEBT-078).

    Отдельно от TestValidationPVT (плотности, DEBT-076): другая величина и свой
    замер. Имя другое: второй одноимённый класс в модуле молча заменил бы первый.
    """

    @pytest.mark.parametrize("c_o", [
        # при c_r = 0 C_p < 0 в недонасыщенной зоне (абзац под eq:c_ot): расчёт
        # шёл молча с одним предупреждением фабрики (BUG-019) при dt_integration
        # 3600 и 1800 с, при 900 с — отказ шага; B_o выше p_b растёт с давлением
        -1e-9,
        # значение примеров 17, 20 с обратным знаком: отказ после дробления шага
        # до dt/512 с советом увеличить max_retries, при всех трёх шагах
        -3.3e-9,
        # наименьшее по модулю отрицательное число: проверка — по знаку, без допуска
        -5e-324,
    ], ids=["step_dependent", "sign_error_examples_17_20", "tiny"])
    def test_negative_co_rejected(self, tmp_path, c_o):
        """c_o < 0 → ValueError с полным именем поля и значением (DEBT-078).

        c_o = −(1/B_o)·∂B_o/∂p при постоянном R_s (eq:co_cg) ≥ 0: при постоянном
        составе объём жидкости с ростом давления не растёт. Комментарии к случаям —
        замер до DEBT-078 на примере 03 (Стендинг, c_r = 0), 1 сут
        (vault/issues/debt-078/probes/audit1_dt_dependence.out.txt).
        """
        raw = _minimal_raw()
        raw["pvt"]["co_undersaturated"] = c_o
        with pytest.raises(ValueError, match="pvt.co_undersaturated") as exc:
            load_config(_write_json(tmp_path, raw))
        # значение — как в конфиге: по нему пользователь найдёт ошибку
        assert f"= {c_o} 1/Па" in str(exc.value)

    def test_negative_co_rejected_for_table(self, tmp_path):
        """При pvt.model = "table" c_o < 0 отвергает _validate — с сообщением о знаке.

        Без проверки знака отказ дала бы только фабрика (create_pvt: c_o ≠ 0 при
        таблице) — позже и без слова о знаке. CSV-файлы не нужны: load_config
        их не читает.
        """
        raw = _minimal_raw()
        raw["pvt"] = {"model": "table", "rho_o_std": 850.0, "rho_g_std": 0.85,
                      "oil_pvt_file": "oil_pvt.csv", "gas_pvt_file": "gas_pvt.csv",
                      "co_undersaturated": -1e-9}
        with pytest.raises(ValueError, match="должна быть ≥ 0"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("c_o", [0.0, 3.3e-9], ids=["zero_default", "examples_17_20"])
    def test_nonnegative_co_accepted(self, tmp_path, c_o):
        """c_o = 0 и 3.3e-9 1/Па проходят: умолчание и значение примеров 17, 20."""
        raw = _minimal_raw()
        raw["pvt"]["co_undersaturated"] = c_o
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.pvt.co_undersaturated == c_o


class TestValidationInitial:
''')

# ── Шаг 3. Заметки vault ──
edit(P8, '''\
CSV и JSON — в одной папке. Factory ищет CSV относительно расположения JSON.
''', '''\
CSV и JSON — в одной папке. Factory ищет CSV относительно расположения JSON.

Поля корреляций Стендинга при табличном PVT не используются: выше $p_b$ $B_o$ и $\\mu_o$ задают недонасыщенные ветви `oil_pvt.csv`. Ненулевое `co_undersaturated` ([[DEBT-078]]) и `mu_o_undersaturated` ≠ `"none"` ([[FEAT-027]]) — отказ `create_pvt` (`factory.py`). До DEBT-078 `co_undersaturated` при таблице пропускалось молча (проба `vault/issues/debt-078/probes/co_undersaturated.py`: пример 04, $c_o = 3.3\\cdot10^{-9}$ 1/Па — $B_o$ побитово тот же, что при $c_o = 0$).
''')

# Строка _validate таблицы «Этап | Где | Что»: c_o — в группу «PVT (…)» DEBT-076
edit(P8, '''\
PVT (`rho_o_std`, `rho_g_std` > 0 — DEBT-076)''', '''\
PVT (`rho_o_std`, `rho_g_std` > 0 — DEBT-076; `co_undersaturated` ≥ 0 — DEBT-078)''')

edit(P8, '''\
| `from_config` | `factory.py`: `_read_numeric_csv`, `_check_pvto_branches`, `_check_gas_pvt_table`, `_check_relperm_table` |''', '''\
| `from_config` | `factory.py`: `create_pvt` | опции Стендинга при `model = "table"`: `mu_o_undersaturated` ≠ `"none"` (FEAT-027), `co_undersaturated` ≠ 0 (DEBT-078) — отказ |
| | `_read_numeric_csv`, `_check_pvto_branches`, `_check_gas_pvt_table`, `_check_relperm_table` |''')

# Абзац — после абзаца «PVT» DEBT-076, перед «Тепловые параметры»: порядок — как в коде
edit(P8, '''\
Тепловые параметры — наш config (`_validate`, `io/config.py`; DEBT-047, DEBT-049):''', '''\
Сжимаемость недонасыщенной нефти — наш config (`_validate`, `io/config.py`, блок «PVT»): `pvt.co_undersaturated` ≥ 0 ([[DEBT-078]]). $c_o = -(1/B_o)\\,\\partial B_o/\\partial p$ при постоянном $R_s$ (`eq:co_cg`): при постоянном составе объём жидкости с ростом давления не растёт, $c_o < 0$ — ошибка знака. Условие корректности уравнения давления слабее — $c_o \\ge -c_r$ (абзац под `eq:c_ot`): при $c_o < -c_r$ в недонасыщенной зоне $C_p < 0$, и неявный шаг вырождается на последовательности $\\Delta t$. Замер на примере 03 (Стендинг, $c_r = 0$, 1 сут; `vault/issues/debt-078/probes/audit1_dt_dependence.out.txt`): $c_o = -10^{-9}$ при шаге 3600 и 1800 с проходило с одним предупреждением фабрики (BUG-019), при 900 с — отказ шага; $-3.3\\cdot10^{-9}$ — отказ при всех трёх шагах. Проверка — при любой модели PVT. Отрицательная сжимаемость, возникающая из таблиц или корреляций, — по-прежнему предупреждение фабрики (BUG-019). Верхней границы нет: ошибку единиц ($10^{-5}$ 1/Па вместо $10^{-9}$ — $B_o(p_0) \\approx 10^{-46}$, расчёт без отказа) проверка не ловит (`co_magnitude.out.txt`).

Тепловые параметры — наш config (`_validate`, `io/config.py`; DEBT-047, DEBT-049):''')

edit(SCHEMA, '''\
| `co_undersaturated` | float | Сжимаемость недонасыщенной нефти при p > pb, 1/Па; по умолчанию 0 (B_o выше pb не меняется). Только `"standing"` |''', '''\
| `co_undersaturated` | float | Сжимаемость недонасыщенной нефти при p > pb, 1/Па; по умолчанию 0 (B_o выше pb не меняется). Только `"standing"`: при `"table"` значение ≠ 0 → `ValueError` (DEBT-078) |''')

# Строка «Ограничения» секции pvt — её завела DEBT-076
edit(SCHEMA, '''\
Ограничения: `rho_o_std > 0`, `rho_g_std > 0` — при любой `model` (DEBT-076).''', '''\
Ограничения: `rho_o_std > 0`, `rho_g_std > 0` — при любой `model` (DEBT-076); `co_undersaturated ≥ 0` — при любой `model` (DEBT-078).''')

edit(STANDING_NOTE, '''\
co_under — сжимаемость нефти выше pb. Задаётся в JSON как скаляр (порядок 1e-9..1e-10 1/Па).
''', '''\
co_under — сжимаемость нефти выше pb. Задаётся в JSON как скаляр (порядок 1e-9..1e-10 1/Па), `pvt.co_undersaturated` ≥ 0: отрицательное значение отвергает `_validate` (DEBT-078). При табличном PVT поле не используется — ненулевое значение отвергает `create_pvt`.
''')

# ── Шаг 3. README пакета (вне git — основной каталог) ──
README_EDIT = (README, '''\
| | `co_undersaturated` | 1/Па | 0 | для корреляций Стендинга: сжимаемость недонасыщенной нефти $c_o$; при $p \\ge p_b(R_s)$ объёмный коэффициент $B_o = B_o(p_b)\\,e^{-c_o (p - p_b)}$, при $c_o = 0$ $B_o$ зависит только от $R_s$ |''', '''\
| | `co_undersaturated` | 1/Па | 0 | для корреляций Стендинга: сжимаемость недонасыщенной нефти $c_o \\ge 0$; при $p \\ge p_b(R_s)$ объёмный коэффициент $B_o = B_o(p_b)\\,e^{-c_o (p - p_b)}$, при $c_o = 0$ $B_o$ зависит только от $R_s$. При табличном PVT допустимо только 0 |''')


def main():
    root = Path(sys.argv[1]).resolve()
    write = "--write" in sys.argv
    edits = list(EDITS)
    if "--readme" in sys.argv:
        edits = [README_EDIT]
    texts, crlf = {}, {}
    ok = True
    for path, old, new in edits:
        f = root / path
        if path not in texts:
            # Блоки — с \n; окончания строк файла сохраняются при записи
            raw = f.read_bytes().decode("utf-8")
            crlf[path] = "\r\n" in raw
            texts[path] = raw.replace("\r\n", "\n")
        n = texts[path].count(old)
        status = "OK" if n == 1 else f"ОШИБКА: «До» встречается {n} раз"
        print(f"{status:40s} {path}: {old.splitlines()[0][:70]!r}")
        ok &= n == 1
        if n == 1:
            texts[path] = texts[path].replace(old, new)
    if not ok:
        print("Есть ошибки — ничего не записано")
        return 1
    if write:
        for path, text in texts.items():
            if crlf[path]:
                text = text.replace("\n", "\r\n")
            (root / path).write_bytes(text.encode("utf-8"))
        print(f"записано файлов: {len(texts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
