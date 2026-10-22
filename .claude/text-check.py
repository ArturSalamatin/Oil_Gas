# -*- coding: utf-8 -*-
"""Механические проверки по разделу «Стиль научного текста» (CLAUDE.md).

Предложения: точка с запятой, два «что» в предложении, длина предложения,
частота связок, связка внутри предложения. Строение текста (.tex): списки
enumerate/itemize, заголовки абзацев (\\paragraph, жирное начало абзаца),
подразделы короче нормы. Слова: настоящее время пассива («Время изложения»),
наращения при числах и десятичная запятая («Числа»), «меняет» («Регистр»),
«например» без запятой, длинное тире и `---` в .tex («Тире»), номер страницы
в ссылке – `\\citet[p.~5]`, «(Connolly, 1990, с. 97)» («Страницы в ссылках»).

Все файлы одного вызова считаются одним текстом: передай документ целиком
(постановку, отчёт) – нормы считаются на него. Маски вида *.tex
раскрываются самим скриптом (PowerShell их не раскрывает).

Находки – кандидаты, а не приговор: точка с запятой в перечне и связка там,
где нужно логическое ударение, законны. Решает автор или рецензент.

    python .claude/text-check.py numerical_solver/doc/problem_statement.tex
    python .claude/text-check.py pseudofunctions/*.tex
    python .claude/text-check.py numerical_solver/README.md
"""
import glob
import io
import re
import sys
from collections import Counter

CONN = ['поэтому', 'при этом', 'тем самым', 'таким образом', 'однако',
        'следовательно', 'напротив', 'в свою очередь']
MAX_WORDS = 35         # свыше – разбивать (ориентир 25)
CONN_RATE = 15         # одна связка – не чаще чем в одном предложении из 15
MAX_INVERSIONS = 3     # связок внутри предложения на главу / рукопись
MIN_SUB_CHARS = 1000   # знаков исходника с формулами: короче – кандидат на слияние с соседним
# Длинное тире – тоже допустимый знак перед связкой: в vault и старых .tex оно ещё есть.
SAFE_BEFORE = ',:;—–-(«'
CONJ = {'и', 'а', 'но', 'или', 'что', 'как', 'если', 'когда'}
# Единицы, после которых «67,5» – десятичная запятая, а не перечень; дополнить единицами проекта.
UNITS = 'бар|атм|мД|мкг|мг|кг|г|мкл|мл|л|мм|см|км|м|сут|ч|мин|с|МПа|кПа|Па|К|моль'
# Ложные срабатывания ожидаемы: «1990-х» – порядковое с законным наращением,
# «определяется габаритами» – свойство модели, а не действие авторов.
WORDS = [
    (re.compile(r'(?<![а-яё])(?:рассматрива|учитыва|использу|оценива|формулиру|обсужда|'
                r'вычисля|применя|сравнива)(?:ется|ются)', re.I), 'наст. время пассива'),
    (re.compile(r'\b\d+-(?:ти|х|и|ми)\b'), 'наращение при числе'),
    (re.compile(r'(?<![а-яё])меня(?:ет|ется|ют|ются)', re.I), '«меняет» → «изменяет»'),
    (re.compile(r'(?<![а-яё])например(?=\s)', re.I), '«например» без запятой'),
    # «Тире»: без исключений. LaTeX-запись --- проверяется отдельно, только в .tex.
    (re.compile('—'), 'длинное тире → среднее (–)'),
    # «Числа»: норма – точка. Если журнал решил ставить запятую, находки этой проверки – норма.
    (re.compile(r'(?<![\d,])\d+,\d+(?=\s*(?:%|°|(?:' + UNITS + r')(?![а-яё])))'),
     'запятая как десятичный разделитель (норма – точка)'),
]

# «Страницы в ссылках»: законна при прямой цитате и по требованию журнала или ГОСТ.
PAGE_RE = [
    re.compile(r'\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])*?\[[^\]]*?(?<![а-яёa-z])(?:pp?|с|стр)\.', re.I),
    re.compile(r'[\[(][^\[\]()]*\d[a-zа-яё]?,\s*(?:pp?|с|стр)\.\s*~?\d', re.I),
]

# Выкладная формула – граница фрагмента (\n): текст до и после неё считается отдельно.
TEX_CLEAN = [
    (r'\\begin\{(equation|align|gather|multline|eqnarray|figure|table)\*?\}.*?\\end\{\1\*?\}', '\n'),
    (r'\$\$.*?\$\$|\\\[.*?\\\]', '\n'),
    (r'\$[^$]*\$', 'X'),
    (r'~?\\(cite|ref|eqref|label|pageref|autoref)\*?(\[[^\]]*\])?\{[^}]*\}', ''),
    (r'\\(emph|textit|textbf|textrm|text|mbox)\{([^}]*)\}', r'\2'),
    (r'\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?', ' '),
    (r'[{}~]', ' '),
]
SECTION_RE = re.compile(r'\\(chapter|section|subsection)(\*?)\s*(?:\[[^\]]*\])?\{')


def strip_comments(text):
    return [re.sub(r'(?<!\\)%.*', '', l) for l in text.split('\n')]


def clean_tex(text):
    for pat, rep in TEX_CLEAN:
        text = re.sub(pat, rep, text, flags=re.S)
    return text


def units_tex(path):
    """Абзацы .tex (разделены пустой строкой) с номером первой строки."""
    lines = strip_comments(io.open(path, encoding='utf-8').read())
    start, buf = None, []
    for i, l in enumerate(lines + [''], 1):
        if l.strip():
            if start is None:
                start = i
            buf.append(l)
        elif buf:
            yield start, clean_tex(' '.join(buf))
            start, buf = None, []


def units_md(path):
    """Строки .md, кроме таблиц, рисунков, заголовков, кода и выкладных формул."""
    code = False
    for i, l in enumerate(io.open(path, encoding='utf-8'), 1):
        s = l.strip()
        if s.startswith('```') or s.startswith('$$'):
            code = not code
            continue
        if code or not s or s.startswith(('|', '!', '#', '<')):
            continue
        yield i, re.sub(r'\$[^$]*\$', 'X', s)


def pages(path, is_tex):
    """Страницы в ссылках – по исходнику: clean_tex удаляет \\cite вместе с аргументами."""
    text = io.open(path, encoding='utf-8').read()
    lines = strip_comments(text) if is_tex else text.split('\n')
    for i, l in enumerate(lines, 1):
        for rx in PAGE_RE:
            for m in rx.finditer(l):
                yield '%s:%d' % (path, i), l[max(0, m.start() - 20):m.end() + 20]


def sentences(text):
    for frag in text.split('\n'):
        for s in re.split(r'(?<=[.!?…])\s+(?=[А-ЯЁA-Z«(])', frag):
            s = ' '.join(s.split())
            if len(s.split()) >= 3:
                yield s


def skip_braced(s, i):
    """Позиция за фигурной скобкой, парной к s[i] == '{'."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == '{':
            depth += 1
        elif s[j] == '}':
            depth -= 1
            if depth == 0:
                return j + 1
    return len(s)


def structure_tex(path):
    """Строение текста: списки, заголовки абзацев, короткие подразделы."""
    lines = strip_comments(io.open(path, encoding='utf-8').read())
    out = []
    prev_blank = True
    for i, l in enumerate(lines, 1):
        s = l.strip()
        where = '%s:%d' % (path, i)
        if re.search(r'\\begin\{(enumerate|itemize)\}', s):
            out.append((where, 'список', s))
        if re.match(r'\\(sub)?paragraph\*?\{', s):
            out.append((where, 'заголовок абзаца', s))
        elif prev_blank and re.match(r'\\textbf\{', s):
            out.append((where, 'жирное начало абзаца', s))
        prev_blank = not s

    text = '\n'.join(lines)
    marks = list(SECTION_RE.finditer(text))
    for k, m in enumerate(marks):
        kind, star = m.group(1), m.group(2)
        title_end = skip_braced(text, m.end() - 1)
        end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
        nxt = marks[k + 1].group(1) if k + 1 < len(marks) else None
        body = text[title_end:end]
        where = '%s:%d' % (path, text.count('\n', 0, m.start()) + 1)
        title = ' '.join(text[m.start():title_end].split())
        if kind == 'chapter' or star:
            continue
        elif kind == 'subsection' or (kind == 'section' and nxt != 'subsection'):
            n = len(' '.join(body.split()))
            if n < MIN_SUB_CHARS:
                out.append((where, 'короткий подраздел: %d зн.' % n, title))
    return out


def main(paths):
    freq, total, inversions, out = Counter(), 0, 0, []
    for path in paths:
        is_tex = path.endswith('.tex')
        if is_tex:
            out.extend(structure_tex(path))
        for where, s in pages(path, is_tex):
            out.append((where, 'страница в ссылке', s))
        units =units_tex(path) if is_tex else units_md(path)
        for line, text in units:
            for s in sentences(text):
                total += 1
                where = '%s:%d' % (path, line)
                if ';' in s:
                    out.append((where, 'точка с запятой', s))
                if len(re.findall(r'\bчто\b', s, re.I)) >= 2:
                    out.append((where, 'два «что»', s))
                n = len(s.split())
                if n > MAX_WORDS:
                    out.append((where, '%d слов' % n, s))
                for rx, what in WORDS:
                    for m in rx.finditer(s):
                        out.append((where, what, s[max(0, m.start() - 40):m.end() + 40]))
                # В .md строка «---» – разделитель, поэтому только .tex.
                if is_tex:
                    for m in re.finditer(r'(?<!-)---(?!-)', s):
                        out.append((where, '--- → -- (среднее тире)', s[max(0, m.start() - 40):m.end() + 40]))
                for c in CONN:
                    for m in re.finditer(r'(?<![а-яё])' + c + r'(?![а-яё])', s, re.I):
                        freq[c] += 1
                        before = s[:m.start()].rstrip()
                        prev = before.split()[-1].lower() if before else ''
                        if before and before[-1] not in SAFE_BEFORE and prev not in CONJ:
                            inversions += 1
                            out.append((where, 'связка внутри: ' + c, s))

    for where, what, s in out:
        print('%-28s %-26s | %s' % (where, what, s[:100]))
    limit = total / CONN_RATE
    print('\nпредложений: %d; связка допустима до %.0f раз' % (total, limit))
    for c, n in freq.most_common():
        print('  %-16s %3d%s' % (c, n, '  <<< чаще 1 на %d' % CONN_RATE if n > limit else ''))
    print('связок внутри предложения: %d%s' % (
        inversions, '  <<< норма до %d' % MAX_INVERSIONS if inversions > MAX_INVERSIONS else ''))


def expand(args):
    paths = []
    for a in args:
        found = sorted(glob.glob(a)) if any(ch in a for ch in '*?[') else [a]
        paths.extend(found or [a])
    return paths


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main(expand(sys.argv[1:]))
