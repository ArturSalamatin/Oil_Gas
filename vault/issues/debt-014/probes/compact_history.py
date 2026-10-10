"""DEBT-014: перевод time.history 22 конфигов в краткую форму {duration, dt_out}.

Подряд идущие одинаковые объекты {dt, <управление>} сворачиваются в один
{duration = n·dt, dt_out = dt, <управление>}; одиночный объект остаётся как
есть. Файл переписывается целиком json.dumps(indent=2): все 22 конфига уже
в этом формате (у 04a, 19, 21 нет только перевода строки в конце) — это
проверяется до записи, иначе отказ.

Запуск из numerical_solver/ (основной каталог или worktree):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-014\\probes\\compact_history.py           # проверка, без записи
    .venv\\Scripts\\python ..\\vault\\issues\\debt-014\\probes\\compact_history.py --write   # запись
    .venv\\Scripts\\python ..\\vault\\issues\\debt-014\\probes\\compact_history.py --verify  # сверка с HEAD
    .venv\\Scripts\\python ..\\vault\\issues\\debt-014\\probes\\compact_history.py --verify <rev>  # сверка с rev

Запись в основном каталоге проекта отклоняется: только worktree задачи.
"""

import json
import subprocess
import sys
from pathlib import Path

# Каталог numerical_solver, из которого запущен скрипт. Путь кладётся в
# sys.path явно: в worktree иначе импортировался бы пакет основного
# каталога (editable-установка), см. заметку о worktree и PYTHONPATH
SOLVER = Path.cwd()
sys.path.insert(0, str(SOLVER))
from gpn_multiphase_solver.io import config as config_mod  # noqa: E402

# Конфиги с развёрнутой формой (замер на 98ff4a6). Не входят: 16, 17, 20 —
# уже краткие; 18 — генерирует prototype_input.py, файл сверяется с
# конвертацией построчно; tests/data/* — замороженные воспроизведения багов
EXAMPLES = (
    "01_single_phase_no_jt", "02_single_phase_jt", "03_standing_corey",
    "04_table_table", "04a_high_gas_saturation", "05_standing_table_rp",
    "06_table_corey_rp", "07_degassing_adiabatic_only", "08_degassing_jt",
    "09_degassing_latent_heat", "10_deep_degassing", "11_degassing_at_boundary",
    "12_large_drainage_radius", "13a_pwf_ramp_down", "13b_pwf_alternating",
    "14_high_gor_cooling", "15_oil_rate_ramp_up", "19_rs150_cooling",
    "21_rs100_cooling",
)
FILES = (
    *(f"examples/{name}/config.json" for name in EXAMPLES),
    "configs/baseline.json",
    "configs/table_pvt/config.json",
    "configs/val001.json",
)

# Ключи краткой формы: объект с ними уже переведён
COMPACT_KEYS = {"repeat", "duration", "dt_out"}


def refuse_main_tree() -> None:
    """Отказ записи, если текущий каталог — основной рабочий каталог проекта, а не worktree."""
    # Основной каталог: корень git = корень проекта, где лежит этот скрипт,
    # и .git — каталог. У worktree .git — файл, у копии дерева (аудит) —
    # другой корень. Без проверки запуск не из $WT переписал бы конфиги
    # базовой ветки.
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=SOLVER,
                         check=True, capture_output=True, encoding="utf-8").stdout.strip()
    project = Path(__file__).resolve().parents[4]
    if Path(top).resolve() == project and (project / ".git").is_dir():
        sys.exit(f"ОТКАЗ: {SOLVER} — основной каталог проекта; запись только в worktree задачи")


def dumps(raw: dict) -> str:
    """Текст конфига в формате репозитория: json.dumps(indent=2) и перевод строки в конце."""
    return json.dumps(raw, indent=2, ensure_ascii=False) + "\n"


def compact(history: list[dict]) -> list[dict]:
    """Подряд идущие одинаковые объекты {dt, ...} → один {duration, dt_out, ...}."""
    out = []
    i = 0
    while i < len(history):
        entry = history[i]
        if set(entry) & COMPACT_KEYS:
            raise ValueError(f"history[{i}] уже в краткой форме: {entry}")
        n = 1
        while i + n < len(history) and history[i + n] == entry:
            n += 1
        if n == 1:
            out.append(dict(entry))
        else:
            dt = entry["dt"]
            control = {k: v for k, v in entry.items() if k != "dt"}
            # Порядок ключей — как у 16, 17, 20: сначала время, затем управление.
            # n·dt точно: n ≤ 864, dt — целое число секунд в double
            out.append({"duration": n * dt, "dt_out": dt, **control})
        i += n
    return out


def expanded(history: list[dict]):
    """Развёрнутый список интервалов — та же функция, что у load_config."""
    intervals, _blocks = config_mod._expand_history(history)
    return intervals


def without_history(raw: dict) -> dict:
    """Копия конфига без time.history — всё, что перевод не должен трогать."""
    copy = json.loads(json.dumps(raw))
    del copy["time"]["history"]
    return copy


def convert(write: bool) -> None:
    """Проверка и (при write) запись всех FILES; любой отказ — до первой записи."""
    planned = []
    total_old = total_new = 0
    for rel in FILES:
        path = SOLVER / rel
        # Чтение с универсальным переводом строк: CRLF рабочей копии → LF
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        if dumps(raw) not in (text, text + "\n"):
            sys.exit(f"ОТКАЗ {rel}: формат отличается от json.dumps(indent=2) — "
                     f"перезапись изменила бы и другие секции")
        old = raw["time"]["history"]
        new = compact(old)
        new_raw = json.loads(json.dumps(raw))
        new_raw["time"]["history"] = new
        # Эквивалентность: развёрнутые списки равны поинтервально (dt и управление)
        if expanded(old) != expanded(new):
            sys.exit(f"ОТКАЗ {rel}: развёрнутая история изменилась")
        if without_history(raw) != without_history(new_raw):
            sys.exit(f"ОТКАЗ {rel}: изменилось что-то кроме time.history")
        n_lines_old = dumps(raw).count("\n")
        n_lines_new = dumps(new_raw).count("\n")
        print(f"{rel}: объектов {len(old)} → {len(new)}, "
              f"интервалов {len(expanded(new))}, строк {n_lines_old} → {n_lines_new}")
        total_old += len(old)
        total_new += len(new)
        planned.append((path, new_raw))

    print(f"файлов: {len(planned)}, объектов: {total_old} → {total_new}")
    if not write:
        print("проверка без записи; для записи — --write")
        return
    refuse_main_tree()
    for path, new_raw in planned:
        path.write_text(dumps(new_raw), encoding="utf-8")
    print(f"записано файлов: {len(planned)}")


def verify(rev: str) -> None:
    """Сверка записанных файлов с версией rev: всё, кроме формы history, совпадает."""
    for rel in FILES:
        old_text = subprocess.run(
            ["git", "show", f"{rev}:./{rel}"], cwd=SOLVER, check=True,
            capture_output=True, encoding="utf-8").stdout
        old_raw = json.loads(old_text)
        new_raw = json.loads((SOLVER / rel).read_text(encoding="utf-8"))
        # load_config — полный путь загрузки, как у примеров и тестов
        cfg = config_mod.load_config(SOLVER / rel)
        same_rest = without_history(old_raw) == without_history(new_raw)
        same_history = expanded(old_raw["time"]["history"]) == cfg.time.history
        n_old = len(old_raw["time"]["history"])
        n_new = len(new_raw["time"]["history"])
        # Каждый из 22 файлов перевод укорачивает. Если rev уже краткий
        # (например, HEAD после коммита шага 2), сверка нового с новым
        # прошла бы впустую — нужна база задачи
        if n_old <= n_new:
            sys.exit(f"ОТКАЗ {rel}: в {rev} уже {n_old} объектов (сейчас {n_new}) — "
                     f"сверка бессмысленна; укажите базу: "
                     f"--verify (git merge-base HEAD numerical_scheme/implementation)")
        status = "совпадает" if same_rest and same_history else "РАСХОДИТСЯ"
        print(f"{rel}: {status}; объектов {n_old} → {n_new}, "
              f"интервалов {len(cfg.time.history)}")
        if status != "совпадает":
            sys.exit(1)
    print(f"файлов: {len(FILES)}, все совпадают с {rev}")


if __name__ == "__main__":
    print(f"каталог: {SOLVER}")
    print(f"пакет:   {config_mod.__file__}")
    args = sys.argv[1:]
    if args[:1] == ["--verify"]:
        verify(args[1] if len(args) > 1 else "HEAD")
    else:
        convert(write=args[:1] == ["--write"])
