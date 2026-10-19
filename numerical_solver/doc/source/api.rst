Публичный интерфейс
===================

..
   Перечень публичного интерфейса пакета — единственный: README §4,
   tests/test_public_api.py, функции, которые вызывают скрипты примеров,
   абстрактные классы для расширения. Докстринги этих объектов — в стиле
   NumPy с русскими заголовками разделов; правило проверяет tests/test_docs.py.

Расчёт
------

.. autofunction:: gpn_multiphase_solver.report.pipeline.run_case

.. autoclass:: gpn_multiphase_solver.report.pipeline.CaseResult

.. autoexception:: gpn_multiphase_solver.report.pipeline.CaseConfigError

.. autoexception:: gpn_multiphase_solver.report.pipeline.CaseRunError

.. autofunction:: gpn_multiphase_solver.cli.configure_batch_run

.. autofunction:: gpn_multiphase_solver.cli.main

Конфигурация и книга ввода
--------------------------

.. autofunction:: gpn_multiphase_solver.io.config.load_config

.. autoclass:: gpn_multiphase_solver.io.config.SimulationConfig

.. autoclass:: gpn_multiphase_solver.io.config.GeometryConfig

.. autoclass:: gpn_multiphase_solver.io.config.GridConfig

.. autoclass:: gpn_multiphase_solver.io.config.RockConfig

.. autoclass:: gpn_multiphase_solver.io.config.PVTConfig

.. autoclass:: gpn_multiphase_solver.io.config.RelPermConfig

.. autoclass:: gpn_multiphase_solver.io.config.ThermalConfig

.. autoclass:: gpn_multiphase_solver.io.config.InitialConfig

.. autoclass:: gpn_multiphase_solver.io.config.HistoryInterval

.. autoclass:: gpn_multiphase_solver.io.config.TimeConfig

.. autoclass:: gpn_multiphase_solver.io.config.NumericsConfig

.. autoclass:: gpn_multiphase_solver.io.config.OutputConfig

.. autofunction:: gpn_multiphase_solver.io.workbook_template.write_template

.. autofunction:: gpn_multiphase_solver.io.workbook_convert.convert_workbook

Сборка решателя
---------------

.. autoclass:: gpn_multiphase_solver.factory.SimulatorFactory
   :members: from_config

.. autofunction:: gpn_multiphase_solver.factory.create_pvt

.. autofunction:: gpn_multiphase_solver.factory.create_relperm

Решатель и история расчёта
--------------------------

.. autoclass:: gpn_multiphase_solver.simulator.Simulator
   :members: run, grid, pvt, relperm

.. autoclass:: gpn_multiphase_solver.state.SimulationState

.. autoclass:: gpn_multiphase_solver.state.WellData

.. autoclass:: gpn_multiphase_solver.state.SimulationHistory

Режим работы скважины и граничные условия
-----------------------------------------

.. autoclass:: gpn_multiphase_solver.bc.WellControl

.. autoclass:: gpn_multiphase_solver.bc.PressureControl
   :members: p_wf

.. autoclass:: gpn_multiphase_solver.bc.RateControl
   :members: q_oil, min_bhp

.. autoclass:: gpn_multiphase_solver.state.BoundaryConditions

Сетка
-----

.. autoclass:: gpn_multiphase_solver.grid.base.Grid
   :members:

.. autoclass:: gpn_multiphase_solver.grid.log_radial.LogRadialGrid

PVT и ОФП
---------

.. autoclass:: gpn_multiphase_solver.pvt.base.HydroPVT
   :members:

.. autoclass:: gpn_multiphase_solver.pvt.base.FullPVT
   :members:

.. autoclass:: gpn_multiphase_solver.pvt.base.DifferentiableHydroPVT
   :members:

.. autoclass:: gpn_multiphase_solver.pvt.base.RelPermModel
   :members:

.. autoclass:: gpn_multiphase_solver.pvt.base.DifferentiableRelPerm
   :members:

.. autoclass:: gpn_multiphase_solver.pvt.standing.StandingFullPVT

.. autoclass:: gpn_multiphase_solver.pvt.table_full.TableFullPVT

.. autoclass:: gpn_multiphase_solver.pvt.relperm.CoreyRP

.. autoclass:: gpn_multiphase_solver.pvt.prototype_adapter.PrototypeRPAdapter

Запись результатов и рисунки
----------------------------

.. autofunction:: gpn_multiphase_solver.io.output.save_csv

.. autofunction:: gpn_multiphase_solver.io.output.save_well_csv

.. autofunction:: gpn_multiphase_solver.io.output.save_npz

.. autofunction:: gpn_multiphase_solver.io.output.plot_profiles

.. autofunction:: gpn_multiphase_solver.io.output.plot_well_rate

.. autofunction:: gpn_multiphase_solver.io.output.plot_wellbore_dynamics

.. autofunction:: gpn_multiphase_solver.io.output.plot_pvt_properties

.. autofunction:: gpn_multiphase_solver.io.output.plot_relperm_curves

.. autofunction:: gpn_multiphase_solver.io.output.plot_energy_balance_series

.. autofunction:: gpn_multiphase_solver.io.output.pvt_table_nodes

.. autofunction:: gpn_multiphase_solver.io.figures.save_figure

.. autofunction:: gpn_multiphase_solver.io.figures.export_emf

Балансы
-------

.. autofunction:: gpn_multiphase_solver.energy.balance.compute_energy_balance

.. autofunction:: gpn_multiphase_solver.mass_balance.compute_mass_balance

Проверки
--------

.. autofunction:: gpn_multiphase_solver.diagnostics.closed_form.solve_closed

.. autofunction:: gpn_multiphase_solver.diagnostics.rs.front_radius

.. autofunction:: gpn_multiphase_solver.diagnostics.temperature.single_phase_asymptote

.. autofunction:: gpn_multiphase_solver.diagnostics.two_phase.compute_gor

.. autofunction:: gpn_multiphase_solver.diagnostics.two_phase.compute_free_gas_prediction

.. autofunction:: gpn_multiphase_solver.diagnostics.two_phase.predict_saturation

.. autofunction:: gpn_multiphase_solver.diagnostics.two_phase.dupuit_check

.. autofunction:: gpn_multiphase_solver.diagnostics.two_phase.degassing_front

.. autofunction:: gpn_multiphase_solver.report.relperm.report_relperm

Единицы
-------

.. automodule:: gpn_multiphase_solver.units
