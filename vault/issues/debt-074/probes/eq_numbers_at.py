"""Номера уравнений и параграфов problem_statement.tex на заданном коммите (DEBT-074).

Заметки vault ссылаются на постановку номерами ранних редакций. Чтобы заменить
номер меткой по факту, а не по догадке, восстанавливаем нумерацию той редакции,
по которой писалась строка заметки: разбор окружений equation/align и команд
разделов (сквозная нумерация уравнений, приложения — буквами).

Проверка разбора: на текущем дереве номера сверяются с problem_statement.aux.

Запуск из корня проекта:
    numerical_solver/.venv/Scripts/python -I vault/issues/debt-074/probes/eq_numbers_at.py
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
TEX = "numerical_solver/doc/problem_statement.tex"
AUX = ROOT / "numerical_solver/doc/problem_statement.aux"

BS = re.escape(chr(92))
# Токены в порядке появления: разделы, приложение, начало/конец окружений,
# метка, отмена номера, перевод строки внутри align.
TOKEN = re.compile(
    BS + r"(section|subsection|subsubsection)(\*?)\s*\{"
    + "|" + BS + r"appendix\b"
    + "|" + BS + r"(begin|end)\{([A-Za-z*]+)\}"
    + "|" + BS + r"label\{([^}]+)\}"
    + "|" + BS + r"(nonumber|notag)\b"
    + "|" + BS + BS
)
NUMBERED = {"equation", "align", "gather", "multline", "eqnarray", "flalign", "alignat"}
MULTIROW = {"align", "gather", "eqnarray", "flalign", "alignat"}


def strip_comments(text):
    """Убрать комментарии LaTeX: % без предшествующей обратной косой черты."""
    return "\n".join(re.sub(r"(?<!" + BS + r")%.*", "", line) for line in text.splitlines())


def numbering(text):
    """Словарь метка → номер (как в .aux) для текста документа."""
    text = strip_comments(text)
    sec = [0, 0, 0]
    appendix = False
    eq = 0
    labels = {}
    current = ""          # номер для метки вне уравнения — последний раздел
    env = None            # окружение уравнения верхнего уровня
    depth = 0             # вложенные окружения внутри уравнения (cases, aligned, …)
    row_labels, row_nonum = [], False

    def sec_str(level):
        head = chr(ord("A") + sec[0] - 1) if appendix else str(sec[0])
        return ".".join([head] + [str(s) for s in sec[1:level + 1]])

    def close_row(last):
        nonlocal eq, row_labels, row_nonum
        if not row_nonum:
            eq += 1
            for lab in row_labels:
                labels[lab] = str(eq)
        elif row_labels:
            for lab in row_labels:
                labels[lab] = "?"
        row_labels, row_nonum = [], False

    pos_row_start = 0
    for m in TOKEN.finditer(text):
        s = m.group(0)
        if m.group(1) and env is None:
            if m.group(2) == "*":
                continue
            level = ["section", "subsection", "subsubsection"].index(m.group(1))
            sec[level] += 1
            for k in range(level + 1, 3):
                sec[k] = 0
            current = sec_str(level)
        elif s.endswith("appendix") and env is None:
            appendix = True
            sec = [0, 0, 0]
        elif m.group(3) == "begin":
            name = m.group(4)
            if env is None and name in NUMBERED:
                env, depth = name, 0
                row_labels, row_nonum = [], False
                pos_row_start = m.end()
            elif env is not None:
                depth += 1
        elif m.group(3) == "end":
            name = m.group(4)
            if env is not None and depth == 0 and name == env:
                # Последняя строка: пустая после завершающего \\ не нумеруется.
                tail = text[pos_row_start:m.start()]
                if env in MULTIROW and not tail.strip() and not row_labels:
                    pass
                else:
                    close_row(True)
                env = None
            elif env is not None:
                depth -= 1
        elif m.group(5):
            lab = m.group(5)
            if env is None:
                labels[lab] = current
            else:
                row_labels.append(lab)
        elif m.group(6):
            if env is not None:
                row_nonum = True
        elif s == chr(92) * 2:
            if env in MULTIROW and depth == 0:
                close_row(False)
                pos_row_start = m.end()
    return labels


def tex_at(commit):
    """Текст постановки на коммите (None — рабочее дерево)."""
    if commit is None:
        return (ROOT / TEX).read_text(encoding="utf-8")
    return subprocess.run(["git", "show", f"{commit}:{TEX}"], cwd=ROOT,
                          capture_output=True, check=True).stdout.decode("utf-8")


def aux_labels():
    """Метка → номер из .aux текущей сборки."""
    aux = AUX.read_text(encoding="utf-8")
    return {m.group(1): m.group(2) for m in
            re.finditer(BS + r"newlabel\{([^}]+)\}\{\{([^}]*)\}", aux)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    # ── Проверка разбора на текущем дереве ──
    mine, ref = numbering(tex_at(None)), aux_labels()
    keys = [k for k in ref if re.match(r"(eq|sec|ssec|sssec|app):", k)]
    bad = [(k, ref[k], mine.get(k)) for k in keys if mine.get(k) != ref[k]]
    print(f"Проверка по .aux: меток {len(keys)}, расхождений {len(bad)}")
    for b in bad[:20]:
        print("  ", b)
    if bad:
        return

    # ── Номера, на которые ссылаются заметки, в редакциях их написания ──
    cited_eq = ["5", "8", "9", "10", "12", "13", "14", "15", "16", "17", "19", "21",
                "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32",
                "33", "34", "35", "36", "74"]
    cited_sec = ["2", "2.1", "3", "4", "4.1", "4.2", "4.2.4", "5", "5.2"]
    commits = sys.argv[1:] or ["0da3ddf", "6136edb", "f4fb8c4"]
    for c in commits:
        lab = numbering(tex_at(c))
        inv = {}
        for k, v in lab.items():
            if re.match(r"(eq|sec|ssec|sssec|app):", k):
                inv.setdefault(v, []).append(k)
        date = subprocess.run(["git", "log", "-1", "--format=%ci", c], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()[:16]
        print(f"\n== {c} ({date}): меток {len(lab)}")
        print("  уравнения:", "  ".join(f"{n}={','.join(inv.get(n, ['—']))}" for n in cited_eq))
        print("  разделы:  ", "  ".join(f"§{n}={','.join(x for x in inv.get(n, ['—']) if not x.startswith('eq:'))}"
                                          for n in cited_sec))


if __name__ == "__main__":
    main()
