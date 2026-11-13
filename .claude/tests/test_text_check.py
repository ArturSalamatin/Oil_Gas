"""Проверки подписей и формулировок в механической проверке текста."""
import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch


SPEC = importlib.util.spec_from_file_location('text_check', Path(__file__).parents[1] / 'text-check.py')
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class TextCheckTest(unittest.TestCase):
    def test_caption_with_nested_braces_and_blank_lines(self):
        # Подпись внутри рисунка проверяется один раз с её номером строки.
        source = ('Введение содержит текст.\n\n\\begin{figure}\n\n'
                  '\\caption[Кратко]{Результат играет важную роль при \\textbf{расчёте}.}\n'
                  '\\end{figure}\n\nЗаключение содержит текст.\n')
        with patch.object(CHECK.io, 'open', mock_open(read_data=source)):
            units = list(CHECK.units_tex('example.tex'))
        self.assertEqual(sum('важную роль' in text for _, text in units), 1)
        self.assertIn((5, 'Результат играет важную роль при расчёте.'), units)
        self.assertTrue(any('Заключение' in text for _, text in units))

    def test_evaluative_phrases_and_legitimate_role(self):
        # Оценка отмечается, а использование роли как параметра допустимо.
        source = 'Результат играет важную роль. Время играет роль параметра. Эта величина скромная.\n'
        output = io.StringIO()
        with patch.object(CHECK.io, 'open', mock_open(read_data=source)), contextlib.redirect_stdout(output):
            CHECK.main(['example.md'])
        self.assertEqual(output.getvalue().count('пустой оборот'), 1)
        self.assertIn('оценочное или разговорное слово', output.getvalue())

    def test_decimal_comma_and_comments(self):
        # Запятая в формуле обнаруживается, а координаты и комментарий не отмечаются.
        source = '$p=0{,}44$; $(0, 1)$; $[0,1]$. % $0{,}33$\n'
        with patch.object(CHECK.io, 'open', mock_open(read_data=source)):
            found = list(CHECK.tex_decimal_commas('example.tex'))
        self.assertEqual(len(found), 1)
        self.assertIn('0{,}44', found[0][1])


if __name__ == '__main__':
    unittest.main()
