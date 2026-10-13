"""Запись рисунков: PNG, SVG для EMF, экспорт EMF без Inkscape (FEAT-026, в пакете с FEAT-030).

gpn_multiphase_solver.io.figures пишет каждый рисунок PNG и, если EMF
включён (GPN_EXAMPLES_EMF ≠ "0"), ещё SVG в <каталог>/emf/; export_emf
переводит SVG в EMF одним запуском Inkscape. Команда расчёта поставляется
заказчику, у которого Inkscape может не быть: тогда расчёт обязан
завершиться, PNG и SVG — остаться, а пользователь — получить одно
предупреждение. Это поведение до FEAT-030 не проверялось (реестр FEAT-030).

tests/conftest.py ставит GPN_EXAMPLES_EMF = "0" на всю сессию; тесты ниже
задают переменные сами через monkeypatch.
"""

import matplotlib
matplotlib.use("Agg")  # headless backend для CI
import matplotlib.pyplot as plt  # noqa: E402

from gpn_multiphase_solver.io.figures import export_emf, save_figure  # noqa: E402


def _figure():
    """Рисунок из одной линии — содержание для проверок не важно."""
    fig, ax = plt.subplots(figsize=(2, 2))
    ax.plot([0, 1], [0, 1])
    return fig


def test_save_figure_png_only_when_disabled(tmp_path, monkeypatch):
    """GPN_EXAMPLES_EMF = "0": только PNG, каталога emf/ нет.

    Так считают тесты и прогоны без векторных копий; лишний SVG на каждый
    рисунок стоил бы около 0.3 с (замер FEAT-026).
    """
    monkeypatch.setenv("GPN_EXAMPLES_EMF", "0")
    fig = _figure()
    out = save_figure(fig, tmp_path / "x.png", dpi=50)
    plt.close(fig)

    assert out == tmp_path / "x.png"
    assert out.is_file() and out.stat().st_size > 0
    assert not (tmp_path / "emf").exists()


def test_save_figure_writes_svg_when_enabled(tmp_path, monkeypatch):
    """EMF включён (переменная не задана): PNG и emf/x.svg; EMF ещё нет — его делает export_emf."""
    monkeypatch.delenv("GPN_EXAMPLES_EMF", raising=False)
    fig = _figure()
    save_figure(fig, tmp_path / "x.png", dpi=50)
    plt.close(fig)

    assert (tmp_path / "x.png").is_file()
    assert (tmp_path / "emf" / "x.svg").is_file()
    # SVG без EMF рядом — признак «ждёт конвертации» для export_emf
    assert not (tmp_path / "emf" / "x.emf").exists()


def test_export_emf_without_inkscape_keeps_svg(tmp_path, monkeypatch, capsys):
    """Inkscape не найден: export_emf возвращает [], печатает предупреждение, SVG и PNG целы.

    INKSCAPE указывает на несуществующий файл: явный путь — единственный
    кандидат (find_inkscape другие места не проверяет), поэтому тест не
    зависит от того, установлен ли Inkscape на машине. Ловит: падение
    расчёта у пользователя без Inkscape или потерю уже записанных рисунков.
    """
    monkeypatch.delenv("GPN_EXAMPLES_EMF", raising=False)
    monkeypatch.setenv("INKSCAPE", str(tmp_path / "нет" / "inkscape.com"))
    fig = _figure()
    save_figure(fig, tmp_path / "x.png", dpi=50)
    plt.close(fig)

    made = export_emf(tmp_path)

    assert made == []
    assert "Inkscape не найден" in capsys.readouterr().out
    assert (tmp_path / "x.png").is_file()
    assert (tmp_path / "emf" / "x.svg").is_file()
    assert not (tmp_path / "emf" / "x.emf").exists()
