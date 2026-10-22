"""DEBT-008: убрать из JSON-конфигов ключи, удалённые из схемы; форматирование не трогать.

Запуск из numerical_solver/ (основной каталог или worktree):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-008\\probes\\strip_removed_keys.py          # проверка
    .venv\\Scripts\\python ..\\vault\\issues\\debt-008\\probes\\strip_removed_keys.py --write  # запись

Файлы: examples/*/config.json, configs/**/*.json, tests/data/*/config.json.
deliverables/ (не в git, переданы разработчику прототипа) и пробы vault не трогаются:
старые ключи в них загрузчик пропускает с предупреждением.

Строка с удаляемым ключом вырезается целиком; если ключ стоял последним в объекте,
у предыдущей строки снимается запятая. Результат сверяется с исходным JSON без
удалённых ключей — иначе отказ, файл не пишется.
"""
import json
import re
import sys
from pathlib import Path

REMOVED = {
    "rock": ("p_ref",),
    "time": ("start_day",),
    "numerics": ("dt_min", "dt_max", "newton_rtol", "newton_atol"),
    "output": ("format",),
}
KEYS = sorted({k for ks in REMOVED.values() for k in ks})
LINE = re.compile(r'^\s*"(%s)"\s*:' % "|".join(KEYS))


def expected(obj):
    """Исходный JSON без удалённых ключей (только в своих секциях)."""
    out = json.loads(json.dumps(obj))
    for section, keys in REMOVED.items():
        if isinstance(out.get(section), dict):
            for k in keys:
                out[section].pop(k, None)
    return out


def strip(text):
    """Вырезать строки удаляемых ключей, поправить запятую у предыдущей строки."""
    out = []
    for line in text.splitlines(keepends=True):
        if LINE.match(line):
            if not line.rstrip().endswith(","):
                # последний ключ объекта: запятая предыдущей непустой строки лишняя
                for i in range(len(out) - 1, -1, -1):
                    if out[i].strip():
                        body = out[i].rstrip("\r\n")
                        if not body.endswith(","):
                            raise ValueError(f"нет запятой перед последним ключом: {out[i]!r}")
                        out[i] = body[:-1] + out[i][len(body):]
                        break
            continue
        out.append(line)
    return "".join(out)


def main(write):
    files = (sorted(Path("examples").glob("*/config.json"))
             + sorted(Path("configs").rglob("*.json"))
             + sorted(Path("tests/data").glob("*/config.json")))
    changed = 0
    for path in files:
        raw = path.read_bytes().decode("utf-8")
        new = strip(raw)
        if new == raw:
            print(f"  без изменений: {path}")
            continue
        if json.loads(new) != expected(json.loads(raw)):
            raise SystemExit(f"{path}: результат не равен исходному без удалённых ключей")
        gone = len(raw.splitlines()) - len(new.splitlines())
        print(f"  {'записан' if write else 'изменится'}: {path} (−{gone} строк)")
        if write:
            path.write_bytes(new.encode("utf-8"))
        changed += 1
    print(f"файлов: {len(files)}, меняется: {changed}")


if __name__ == "__main__":
    main("--write" in sys.argv[1:])
