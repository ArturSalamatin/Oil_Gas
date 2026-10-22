"""DEBT-014: README примеров — как править расписание после перевода time.history в краткую форму.

Каждая замена — точный текст; старый текст должен встречаться в файле ровно
один раз, иначе отказ до первой записи. Описательные строки («расписание —
30 интервалов × 43 200 с», «72 интервала») не трогаются: после разворачивания
они верны. Меняются только места, где сказано, какое поле JSON править.

Запуск из numerical_solver/ (основной каталог или worktree):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-014\\probes\\fix_readmes.py           # проверка, без записи
    .venv\\Scripts\\python ..\\vault\\issues\\debt-014\\probes\\fix_readmes.py --write   # запись

Запись в основном каталоге проекта отклоняется: только worktree задачи.
"""

import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()
EXAMPLES = SOLVER / "examples"


def refuse_main_tree() -> None:
    """Отказ записи, если текущий каталог — основной рабочий каталог проекта, а не worktree."""
    # Как в compact_history.py: у основного каталога корень git = корень
    # проекта и .git — каталог; у worktree .git — файл
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=SOLVER,
                         check=True, capture_output=True, encoding="utf-8").stdout.strip()
    project = Path(__file__).resolve().parents[4]
    if Path(top).resolve() == project and (project / ".git").is_dir():
        sys.exit(f"ОТКАЗ: {SOLVER} — основной каталог проекта; запись только в worktree задачи")

# ── 01–10: две строки таблицы «Как модифицировать» ──
DURATION_OLD = "| длительность | `time.history[].dt` |"
DURATION_NEW = "| длительность | `time.history[0].duration` |"
RATE_OLD = "| частота записи | `time.history[]` | число интервалов = число записей; 72 по 3600 с → 73 {what} |"
RATE_NEW = ("| частота записи | `time.history[0].dt_out` | запись раз в `dt_out` на этапе "
            "`duration`: 259 200 / 3600 → 72 интервала, 73 {what}; `duration` должна "
            "делиться на `dt_out` |")

TABLE_EXAMPLES = {
    "01_single_phase_no_jt": "момента",
    "02_single_phase_jt": "шага",
    "03_standing_corey": "шага",
    "04_table_table": "шага",
    "05_standing_table_rp": "шага",
    "06_table_corey_rp": "шага",
    "07_degassing_adiabatic_only": "шага",
    "08_degassing_jt": "шага",
    "09_degassing_latent_heat": "шага",
    "10_deep_degassing": "шага",
}

REPLACEMENTS: dict[str, list[tuple[str, str]]] = {
    name: [(DURATION_OLD, DURATION_NEW),
           (RATE_OLD.format(what=what), RATE_NEW.format(what=what))]
    for name, what in TABLE_EXAMPLES.items()
}

REPLACEMENTS["04a_high_gas_saturation"] = [
    ("Шаг истории равен шагу интегрирования: 864 интервала по 300 с, по одному\n"
     "шагу решателя на запись, 865 записей; `profiles.csv` — около 11 МБ.",
     "Шаг записи равен шагу интегрирования: один объект `time.history`\n"
     "`{\"duration\": 259200.0, \"dt_out\": 300.0, ...}` — 864 интервала по 300 с,\n"
     "по одному шагу решателя на запись, 865 записей; `profiles.csv` — около 11 МБ."),
    ("к шагу записи нет. Перегенерация блока — [rewrite_history.py](rewrite_history.py).",
     "к шагу записи нет. Чтобы после смены `dt_integration` запись по-прежнему\n"
     "шла на каждом шаге, достаточно поменять одно поле `dt_out` (`duration` =\n"
     "259 200 с должна на него делиться)."),
    ("- **`time.history`** — шаг записи можно укрупнить: решение при том же\n"
     "  `dt_integration` и баланс энергии не изменятся, пропадут ранние моменты\n"
     "  для «Переходного процесса» и `plot_profiles_50k.py`. Правка одного\n"
     "  `history[0].dt` меняет длину только первого интервала, а не всего\n"
     "  расчёта; для перегенерации блока — [rewrite_history.py](rewrite_history.py).",
     "- **`time.history`** — шаг записи `dt_out` можно укрупнить: решение при\n"
     "  том же `dt_integration` и баланс энергии не изменятся, пропадут ранние\n"
     "  моменты для «Переходного процесса» и `plot_profiles_50k.py`. `duration`\n"
     "  должна делиться на `dt_out`, иначе конфиг не загрузится."),
    ("| `rewrite_history.py` | перегенерация блока `time.history` (864 × 300 с) |\n", ""),
]

REPLACEMENTS["11_degassing_at_boundary"] = [
    ("- **Длительность:** интервалы в `time.history` (сейчас 72 × 3600 с).",
     "- **Длительность:** `duration` объекта `time.history` (сейчас 259 200 с =\n"
     "  3 сут с записью раз в `dt_out` = 3600 с)."),
]

REPLACEMENTS["12_large_drainage_radius"] = [
    ("- **Длительность и частота записи:** число и длина интервалов в\n"
     "  `time.history`.",
     "- **Длительность и частота записи:** `duration` и `dt_out` объекта\n"
     "  `time.history` (сейчас 15 сут с записью раз в сутки)."),
]

REPLACEMENTS["13a_pwf_ramp_down"] = [
    ("## Расписание\n\n| сутки $k$ | интервалы `time.history` |",
     "## Расписание\n\n"
     "В `config.json` сутки $k$ — один объект `history[k-1]`:\n"
     "`{\"duration\": 86400.0, \"dt_out\": 43200.0, \"control\": \"pressure\", \"p_wf\": …}`.\n"
     "Номера интервалов в таблице — после разворачивания, они же номера записей.\n\n"
     "| сутки $k$ | интервалы `time.history` |"),
    ("последние интервалы `time.history` в",
     "последние объекты `time.history` в"),
    ("- **Ступени:** `p_wf` каждого интервала `time.history`. Конфиг собран\n"
     "  генератором `vault/issues/feat-022/probes/make_13a_config.py` из\n"
     "  конфига-заготовки; другие ступени проще задать, поправив в нём формулу.\n"
     "- **Частота записи:** число интервалов на сутки. Шаг интегрирования —",
     "- **Ступени:** `p_wf` объектов `time.history`, по одному на сутки:\n"
     "  сутки $k$ — `history[k-1]`. Конфиг был собран генератором\n"
     "  `vault/issues/feat-022/probes/make_13a_config.py` в развёрнутой форме\n"
     "  (объект на интервал) и переведён в краткую в DEBT-014 — ступени проще\n"
     "  править прямо в `config.json`.\n"
     "- **Частота записи:** `dt_out` объектов (сейчас 43 200 с — 0.5 сут;\n"
     "  `duration` = 86 400 с должна делиться на `dt_out`). Шаг интегрирования —"),
]

REPLACEMENTS["13b_pwf_alternating"] = [
    ("## Расписание\n\n| сутки $d$ | интервалы `time.history` |",
     "## Расписание\n\n"
     "В `config.json` сутки $d$ — один объект `history[d-1]`:\n"
     "`{\"duration\": 86400.0, \"dt_out\": 43200.0, \"control\": \"pressure\", \"p_wf\": …}`.\n"
     "Номера интервалов в таблице — после разворачивания, они же номера записей.\n\n"
     "| сутки $d$ | интервалы `time.history` |"),
    ("  # Сутки d = 1..30, по два интервала 0.5 сут: нечётные 6 МПа, чётные 10.75 МПа\n"
     "  cfg[\"time\"][\"history\"] = [\n"
     "      {\"dt\": 43200.0, \"control\": \"pressure\",\n"
     "       \"p_wf\": 6.0e6 if d % 2 == 1 else 10.75e6}\n"
     "      for d in range(1, 31) for _ in range(2)]",
     "  # Сутки d = 1..30, запись раз в 0.5 сут: нечётные 6 МПа, чётные 10.75 МПа\n"
     "  cfg[\"time\"][\"history\"] = [\n"
     "      {\"duration\": 86400.0, \"dt_out\": 43200.0, \"control\": \"pressure\",\n"
     "       \"p_wf\": 6.0e6 if d % 2 == 1 else 10.75e6}\n"
     "      for d in range(1, 31)]"),
]

REPLACEMENTS["14_high_gor_cooling"] = [
    ("- **Длительность и частота записи:** число и длина интервалов\n"
     "  `time.history`.",
     "- **Длительность и частота записи:** `duration` и `dt_out` объекта\n"
     "  `time.history` (сейчас 360 сут с записью раз в 30 сут)."),
]

REPLACEMENTS["15_oil_rate_ramp_up"] = [
    ("Каждые сутки в `time.history` разбиты на 24 часовых\n"
     "интервала с одним и тем же дебитом, поэтому результаты записываются раз в\n"
     "час — 361 запись.",
     "Каждые сутки в `time.history` — один объект с записью раз\n"
     "в час (`dt_out` = 3600 с: 24 часовых интервала с одним дебитом), поэтому\n"
     "результаты записываются раз в час — 361 запись."),
    ("Интервал истории с управлением по дебиту в `config.json`:\n\n"
     "```json\n"
     "{\"dt\": 3600.0, \"control\": \"rate\", \"q_oil\": 0.00020833333333333335, \"min_bhp\": 101325.0}\n"
     "```",
     "Сутки с управлением по дебиту в `config.json` — один объект (первые сутки):\n\n"
     "```json\n"
     "{\"duration\": 86400.0, \"dt_out\": 3600.0, \"control\": \"rate\", \"q_oil\": 0.00020833333333333335, \"min_bhp\": 101325.0}\n"
     "```\n\n"
     "Краткая форма `{duration, dt_out}`: этап длительностью `duration` с записью\n"
     "раз в `dt_out` разворачивается в интервалы длиной `dt_out` (FEAT-018)."),
    ("`min_bhp` обязателен.\n\n| сутки $k$ | интервалы (с 1) |",
     "`min_bhp` обязателен.\n\n"
     "Сутки $k$ — объект `history[k-1]`; номера интервалов в таблице — после\n"
     "разворачивания, они же номера записей.\n\n"
     "| сутки $k$ | интервалы (с 1) |"),
    ("последние интервалы `time.history`. При",
     "последние объекты `time.history`. При"),
    ("- **Расписание дебита:** `q_oil` каждого интервала `time.history`, м³ст/с.\n"
     "  Сутки $k$ — интервалы $24(k-1)+1$ … $24k$; дебит суток меняется у всех 24\n"
     "  интервалов сразу.\n"
     "- **Частота записи:** частоту вывода задаёт только структура\n"
     "  `time.history` (DEBT-013). Сутки разбиты на 24 часовых интервала с\n"
     "  одинаковым дебитом; с одним интервалом на сутки записей будет 16, и пила\n"
     "  $T(r_w)$ на графике пропадёт — останутся только вершины зубцов.",
     "- **Расписание дебита:** `q_oil` объектов `time.history`, м³ст/с: сутки $k$ —\n"
     "  объект `history[k-1]` (после разворачивания — интервалы $24(k-1)+1$ … $24k$).\n"
     "- **Частота записи:** частоту вывода задаёт только структура\n"
     "  `time.history` (DEBT-013) — `dt_out` объектов суток. Сейчас `dt_out` =\n"
     "  3600 с, 24 записи в сутки; при `dt_out` = 86 400 с записей будет 16, и пила\n"
     "  $T(r_w)$ на графике пропадёт — останутся только вершины зубцов."),
]

# ── 19, 21: строка таблицы — как у 20 ──
ROW_19_OLD = "| длительность, частота записи | `time.history` | число интервалов = число записей |"
ROW_19_NEW = ("| длительность, частота записи | `time.history` | число интервалов = число записей; "
              "краткая форма `{duration, dt_out}` — этап с записью раз в `dt_out` (FEAT-018) |")
for name in ("19_rs150_cooling", "21_rs100_cooling"):
    REPLACEMENTS[name] = [(ROW_19_OLD, ROW_19_NEW)]


def main(write: bool) -> None:
    """Проверка всех замен; при write — запись. Любой отказ — до первой записи."""
    print(f"каталог: {SOLVER}")
    planned = []
    for name, pairs in REPLACEMENTS.items():
        path = EXAMPLES / name / "README.md"
        # Универсальный перевод строк: CRLF рабочей копии → LF
        text = path.read_text(encoding="utf-8")
        for old, new in pairs:
            n = text.count(old)
            if n != 1:
                sys.exit(f"ОТКАЗ {name}: старый текст встречается {n} раз:\n{old}")
            text = text.replace(old, new)
        planned.append((path, text))
        print(f"{name}: замен {len(pairs)}")
    # После замен в README нет ссылок на удалённый генератор
    for path, text in planned:
        if "rewrite_history" in text:
            sys.exit(f"ОТКАЗ {path}: осталась ссылка на rewrite_history.py")
    print(f"README меняется: {len(planned)}, замен: {sum(len(p) for p in REPLACEMENTS.values())}")
    if not write:
        print("проверка без записи; для записи — --write")
        return
    refuse_main_tree()
    for path, text in planned:
        path.write_text(text, encoding="utf-8")
    print(f"записано README: {len(planned)}")


if __name__ == "__main__":
    main(write=sys.argv[1:2] == ["--write"])
