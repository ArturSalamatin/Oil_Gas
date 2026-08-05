"""
Сборка docx-отчёта из markdown-файла.
Поддержка: заголовки, inline/display math, таблицы, картинки, bold/italic, списки.

Использование:
    python build_report.py report.md                 # -> report.docx
    python build_report.py report.md -o output.docx  # указать имя выхода

Зависимости: python-docx, latex2mathml, lxml
"""

import argparse
import os
import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import latex2mathml.converter
import lxml.etree as etree

FONT_NAME = "Times New Roman"
FONT_SIZE = Pt(14)
MARGIN = Cm(2)
MARGIN_TB = Cm(2.5)

XSLT_PATH = r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL"

_xslt_transform = None


def get_xslt_transform():
    global _xslt_transform
    if _xslt_transform is None:
        xslt = etree.parse(XSLT_PATH)
        _xslt_transform = etree.XSLT(xslt)
    return _xslt_transform


# ---------- LaTeX preprocessing ----------

def _extract_brace_group(s, start):
    if start >= len(s) or s[start] != "{":
        return None
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1:i], i + 1
    return None


def _remove_underbrace(latex_str):
    tag = r"\underbrace"
    while tag in latex_str:
        idx = latex_str.index(tag)
        after = idx + len(tag)
        main = _extract_brace_group(latex_str, after)
        if main is None:
            break
        content, pos = main
        if pos < len(latex_str) and latex_str[pos] == "_":
            sub = _extract_brace_group(latex_str, pos + 1)
            if sub is not None:
                _, end = sub
                latex_str = latex_str[:idx] + content + latex_str[end:]
                continue
        latex_str = latex_str[:idx] + content + latex_str[pos:]
    return latex_str


def _replace_substack(latex_str):
    tag = r"\substack"
    while tag in latex_str:
        idx = latex_str.index(tag)
        after = idx + len(tag)
        grp = _extract_brace_group(latex_str, after)
        if grp is None:
            break
        inner, end = grp
        parts = re.split(r"\s*\\\\\s*", inner.strip())
        if len(parts) == 2:
            replacement = r"{" + parts[0] + r" \atop " + parts[1] + r"}"
        else:
            replacement = r"{" + inner + r"}"
        latex_str = latex_str[:idx] + replacement + latex_str[end:]
    return latex_str


def preprocess_latex(latex_str):
    latex_str = _remove_underbrace(latex_str)
    latex_str = _replace_substack(latex_str)
    latex_str = latex_str.replace("{,}", ",")
    latex_str = latex_str.replace(r"\!", "")
    latex_str = latex_str.replace(r"\;", r"\,")
    latex_str = latex_str.replace(r"\_", "_")
    return latex_str


def _fix_nary_empty_body(omml_root):
    NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
    changed = True
    while changed:
        changed = False
        candidates = list(omml_root.iter(f"{{{NS}}}nary"))
        candidates.reverse()
        for nary in candidates:
            e_elem = nary.find(f"{{{NS}}}e")
            if e_elem is None:
                continue
            if len(e_elem) > 0 or (e_elem.text and e_elem.text.strip()):
                continue
            parent = nary.getparent()
            if parent is None:
                continue
            nxt = nary.getnext()
            if nxt is not None:
                parent.remove(nxt)
                e_elem.append(nxt)
                changed = True
                break


def latex_to_omml(latex_str, display="inline"):
    latex_str = preprocess_latex(latex_str)
    mathml = latex2mathml.converter.convert(latex_str, display=display)
    mathml_tree = etree.fromstring(mathml.encode("utf-8"))
    transform = get_xslt_transform()
    omml_tree = transform(mathml_tree)
    root = omml_tree.getroot()
    _fix_nary_empty_body(root)
    return root


# ---------- Document helpers ----------

def set_cell_shading(cell, color):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def set_run_font(run, size=FONT_SIZE, bold=False, italic=False, name=FONT_NAME):
    run.font.name = name
    run.font.size = size
    run.font.bold = bold
    run.font.italic = italic
    rFonts = run._element.rPr.rFonts
    rFonts.set(qn("w:eastAsia"), name)
    rFonts.set(qn("w:cs"), name)


def add_paragraph(doc, text, bold=False, italic=False,
                  alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                  font_size=FONT_SIZE, space_before=0, space_after=0,
                  first_line_indent=None):
    p = doc.add_paragraph()
    p.alignment = alignment
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    if first_line_indent is not None:
        pf.first_line_indent = first_line_indent
    if text:
        run = p.add_run(text)
        set_run_font(run, size=font_size, bold=bold, italic=italic)
    return p


def add_mixed_paragraph(doc, segments, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                        space_before=0, space_after=0, first_line_indent=None,
                        font_size=FONT_SIZE):
    p = doc.add_paragraph()
    p.alignment = alignment
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    if first_line_indent is not None:
        pf.first_line_indent = first_line_indent
    for text, bold, italic in segments:
        run = p.add_run(text)
        set_run_font(run, size=font_size, bold=bold, italic=italic)
    return p


def add_math_paragraph(doc, latex_str, space_before=6, space_after=6):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    try:
        omml = latex_to_omml(latex_str, display="block")
        p._element.append(omml)
    except Exception as e:
        run = p.add_run(f"[MATH ERROR: {latex_str[:60]}]")
        set_run_font(run, italic=True)
        print(f"  WARNING: math conversion failed: {e}")
    return p


# ---------- Markdown parsing ----------

def clean_inline(text):
    text = re.sub(r"\$([^$]+)\$", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = text.replace(r"\,", "\u2009")
    text = text.replace(r"\_", "_")
    text = text.replace(r"\%", "%")
    text = text.replace("—", "–")
    return text


def detect_bold_italic(text):
    segments = []
    pattern = re.compile(r"(\*\*(.+?)\*\*|\*(.+?)\*)")
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            segments.append((clean_inline(text[pos:m.start()]), False, False))
        if m.group(2):
            segments.append((clean_inline(m.group(2)), True, False))
        elif m.group(3):
            segments.append((clean_inline(m.group(3)), False, True))
        pos = m.end()
    if pos < len(text):
        segments.append((clean_inline(text[pos:]), False, False))
    return segments


def is_heading(line):
    m = re.match(r"^(#{1,4})\s+(.*)", line)
    if m:
        return len(m.group(1)), m.group(2).strip()
    return None, None


def strip_heading_number(text):
    text = re.sub(r"^§\d+\.\s*", "", text)
    text = re.sub(r"^\d+(\.\d+)*\.?\s+", "", text)
    return text


def is_table_separator(line):
    return bool(re.match(r"^\|[-|: ]+\|$", line.strip()))


def parse_table_block(lines, start_idx):
    rows = []
    i = start_idx
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("|"):
            break
        if is_table_separator(line):
            i += 1
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
        i += 1
    return rows, i


def _merge_text_with_superscript(parts):
    """Склеивает текст + $^{...}$ в единый math-элемент $\\text{...}^{...}$."""
    merged = []
    i = 0
    while i < len(parts):
        if (i + 1 < len(parts)
                and not (parts[i].startswith("$") and parts[i].endswith("$"))
                and parts[i + 1].startswith("$") and parts[i + 1].endswith("$")):
            math_inner = parts[i + 1][1:-1].strip()
            if re.match(r"^\^", math_inner) or re.match(r"^_", math_inner):
                text_part = parts[i].rstrip()
                trailing = parts[i][len(text_part):]
                last_word_m = re.search(r"(\S+)$", text_part)
                if last_word_m:
                    prefix = text_part[:last_word_m.start()]
                    word = last_word_m.group(1)
                    if prefix:
                        merged.append(prefix)
                    merged.append(f"$\\text{{{word}}}{math_inner}$")
                    if trailing:
                        merged.append(trailing)
                    i += 2
                    continue
        merged.append(parts[i])
        i += 1
    return merged


def add_table(doc, rows):
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=ncols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    for i, row_data in enumerate(rows):
        for j, cell_text in enumerate(row_data):
            if j >= ncols:
                break
            cell = table.rows[i].cells[j]
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf = p.paragraph_format
            pf.space_before = Pt(1)
            pf.space_after = Pt(1)
            pf.line_spacing_rule = WD_LINE_SPACING.SINGLE

            parts = re.split(r"(\$[^$]+\$)", cell_text)
            parts = _merge_text_with_superscript(parts)
            for part in parts:
                if part.startswith("$") and part.endswith("$"):
                    latex_str = part[1:-1]
                    try:
                        omml = latex_to_omml(latex_str)
                        p._element.append(omml)
                    except Exception:
                        run = p.add_run(latex_str)
                        set_run_font(run, size=Pt(12), italic=True)
                else:
                    if part:
                        run = p.add_run(clean_inline(part))
                        set_run_font(run, size=Pt(12), bold=(i == 0))

            if i == 0:
                set_cell_shading(cell, "D9E2F3")
    return table


def add_paragraph_with_inline_math(doc, text, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                                   space_before=0, space_after=0,
                                   first_line_indent=None, base_bold=False):
    parts = re.split(r"(\$[^$]+\$)", text)
    parts = _merge_text_with_superscript(parts)
    has_math = any(p.startswith("$") and p.endswith("$") for p in parts)

    if not has_math:
        segments = detect_bold_italic(text)
        if len(segments) > 1 or (segments and (segments[0][1] or segments[0][2])):
            return add_mixed_paragraph(doc, segments,
                                       alignment=alignment,
                                       space_before=space_before,
                                       space_after=space_after,
                                       first_line_indent=first_line_indent)
        return add_paragraph(doc, clean_inline(text), bold=base_bold,
                             alignment=alignment,
                             space_before=space_before, space_after=space_after,
                             first_line_indent=first_line_indent)

    p = doc.add_paragraph()
    p.alignment = alignment
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    if first_line_indent is not None:
        pf.first_line_indent = first_line_indent

    for part in parts:
        if part.startswith("$") and part.endswith("$"):
            latex_str = part[1:-1]
            try:
                omml = latex_to_omml(latex_str)
                p._element.append(omml)
            except Exception:
                run = p.add_run(latex_str)
                set_run_font(run, italic=True)
        else:
            if part:
                for seg_text, bold, italic in detect_bold_italic(part):
                    run = p.add_run(seg_text)
                    set_run_font(run, bold=bold or base_bold, italic=italic)
    return p


# ---------- Main processing ----------

def process_md(doc, md_text, base_dir):
    lines = md_text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # display math
        if stripped.startswith("$$"):
            math_lines = []
            if stripped == "$$":
                i += 1
                while i < len(lines) and lines[i].strip() != "$$":
                    math_lines.append(lines[i].strip())
                    i += 1
                i += 1
            else:
                content = stripped.strip("$").strip()
                math_lines.append(content)
                i += 1
            latex_str = " ".join(math_lines)
            add_math_paragraph(doc, latex_str)
            continue

        # headings
        level, heading_text = is_heading(stripped)
        if level is not None:
            heading_text = strip_heading_number(heading_text)
            if level == 1:
                add_paragraph_with_inline_math(
                    doc, heading_text, base_bold=True,
                    alignment=WD_ALIGN_PARAGRAPH.CENTER,
                    space_before=12, space_after=6,
                    first_line_indent=Cm(0))
            elif level == 2:
                add_paragraph_with_inline_math(
                    doc, heading_text, base_bold=True,
                    alignment=WD_ALIGN_PARAGRAPH.LEFT,
                    space_before=12, space_after=4,
                    first_line_indent=Cm(0))
            elif level == 3:
                add_paragraph_with_inline_math(
                    doc, heading_text, base_bold=True,
                    alignment=WD_ALIGN_PARAGRAPH.LEFT,
                    space_before=8, space_after=4,
                    first_line_indent=Cm(0))
            else:
                add_paragraph_with_inline_math(
                    doc, heading_text,
                    alignment=WD_ALIGN_PARAGRAPH.LEFT,
                    space_before=6, space_after=2,
                    first_line_indent=Cm(0))
            i += 1
            continue

        # image
        img_m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if img_m:
            caption = img_m.group(1)
            img_rel = img_m.group(2)
            img_path = (base_dir / img_rel).resolve()
            if img_path.suffix == ".svg":
                png = img_path.with_suffix(".png")
                if png.exists():
                    img_path = png
            if img_path.exists() and img_path.suffix in (".png", ".jpg", ".jpeg", ".bmp"):
                doc.add_picture(str(img_path), width=Cm(15))
                last_p = doc.paragraphs[-1]
                last_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                pf = last_p.paragraph_format
                pf.space_before = Pt(6)
                pf.space_after = Pt(2)
                pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
            else:
                add_paragraph(doc, f"[Рисунок: {img_rel}]", italic=True,
                              alignment=WD_ALIGN_PARAGRAPH.CENTER,
                              space_before=6, space_after=2)
            if caption:
                add_paragraph_with_inline_math(
                    doc, caption,
                    alignment=WD_ALIGN_PARAGRAPH.CENTER,
                    space_before=2, space_after=6,
                    first_line_indent=Cm(0),
                    base_bold=False)
            i += 1
            continue

        # table
        if stripped.startswith("|"):
            rows, end_i = parse_table_block(lines, i)
            add_table(doc, rows)
            add_paragraph(doc, "")
            i = end_i
            continue

        # list item
        m_list = re.match(r"^[-*]\s+(.*)", stripped)
        m_num = re.match(r"^\d+\.\s+(.*)", stripped)
        if m_list or m_num:
            item_text = (m_list or m_num).group(1)
            add_paragraph_with_inline_math(
                doc, "– " + item_text,
                first_line_indent=Cm(1.25),
                space_before=2, space_after=2)
            i += 1
            continue

        # regular paragraph
        add_paragraph_with_inline_math(
            doc, stripped,
            first_line_indent=Cm(1.25),
            space_before=0, space_after=0)
        i += 1


def build_report(input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)
    base_dir = input_path.parent

    md_text = input_path.read_text(encoding="utf-8")
    md_text = re.sub(r"^---\n.*?\n---\n", "", md_text, flags=re.DOTALL)
    md_text = md_text.strip()

    doc = Document()

    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = MARGIN
    section.right_margin = MARGIN
    section.top_margin = MARGIN_TB
    section.bottom_margin = MARGIN_TB

    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = FONT_SIZE
    style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    style.paragraph_format.space_after = Pt(0)
    style.paragraph_format.space_before = Pt(0)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONT_NAME)
    style.element.rPr.rFonts.set(qn("w:cs"), FONT_NAME)

    # номера страниц
    footer = section.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run()
    set_run_font(run, size=Pt(12))
    run._element.append(parse_xml(
        f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>'))
    run2 = fp.add_run()
    set_run_font(run2, size=Pt(12))
    run2._element.append(parse_xml(
        f'<w:instrText {nsdecls("w")} xml:space="preserve"> PAGE </w:instrText>'))
    run3 = fp.add_run()
    set_run_font(run3, size=Pt(12))
    run3._element.append(parse_xml(
        f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>'))

    process_md(doc, md_text, base_dir)

    doc.save(str(output_path))
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build docx report from markdown")
    parser.add_argument("input", help="Input markdown file")
    parser.add_argument("-o", "--output", default=None,
                        help="Output docx path (default: same name .docx)")
    parser.add_argument("--open", action="store_true",
                        help="Open the file after building")
    args = parser.parse_args()

    inp = Path(args.input)
    out = Path(args.output) if args.output else inp.with_suffix(".docx")
    build_report(inp, out)
    if args.open:
        os.startfile(str(out.resolve()))
