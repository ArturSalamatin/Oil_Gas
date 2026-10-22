"""Сценарий 18: вход прототипа (INPUT_TEMPLATE.xlsx) — расчёт с температурой, сверка с прототипом и CMG IMEX."""

from pathlib import Path

from gpn_multiphase_solver.cli import configure_batch_run
# Консоль UTF-8 и matplotlib без окна — как у команды (FEAT-030)
configure_batch_run()

from gpn_multiphase_solver.io.figures import export_emf  # noqa: E402
from gpn_multiphase_solver.report.pipeline import run_case  # noqa: E402
# Папка скрипта уже в sys.path (её кладёт Python) — оттуда prototype_input
import prototype_input  # noqa: E402

if __name__ == "__main__":
    here = Path(__file__).parent
    # Заголовок, 6 моментов профилей (по моменту на каждый режим p_wf
    # 150 / 120 / 100 бар и конец), без стационарной аналитики — секция
    # output конфига; её пишет перевод книги (prototype_input.convert, FEAT-030)
    r = run_case(here / "config.json", here / "output")
    # Каталог, куда run_case записал результаты: при занятом here/output —
    # соседний с датой и временем в имени (DEBT-082)
    output = r.output_dir
    # Прототип на той же книге и эталон CMG IMEX T07: сводка и два рисунка.
    prototype_input.report_and_plot(r.history, r.grid, output, r.title)
    # Рисунки сравнения созданы после export_emf внутри run_case —
    # второй вызов переводит в EMF только их.
    export_emf(output)
