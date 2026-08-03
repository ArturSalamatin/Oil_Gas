"""Smoke-тесты CLI — FEAT-008."""

from pathlib import Path

import numpy as np
import pytest

from src.main import load_config, build_objects, run


CONFIGS = Path(__file__).resolve().parent.parent / "configs"


class TestLoadConfig:
    def test_loads_baseline(self):
        cfg = load_config(CONFIGS / "baseline.json")
        assert "geometry" in cfg
        assert "pvt" in cfg
        assert "solver" in cfg

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.json")


class TestBuildObjects:
    def test_builds_from_baseline(self):
        cfg = load_config(CONFIGS / "baseline.json")
        fluid, rock, p_prof, t_prof, s_prof, solver_opts, beta_fixed = build_objects(cfg)
        assert fluid.p_b == cfg["initial_conditions"]["p_b"]
        assert p_prof.r_w == cfg["geometry"]["r_w"]
        assert t_prof.T_0 == cfg["initial_conditions"]["T_0"]
        assert s_prof.beta == cfg["profiles"]["beta"]
        assert "t_end" in solver_opts


@pytest.fixture(scope="module")
def run_result(tmp_path_factory):
    out = tmp_path_factory.mktemp("smoke")
    sol = run(str(CONFIGS / "test_short.json"), str(out))
    return sol, out


@pytest.mark.filterwarnings("ignore::scipy.integrate.IntegrationWarning")
class TestRun:
    def test_smoke_baseline(self, run_result):
        sol, out = run_result
        assert sol.y.shape[0] == 3
        assert sol.y[0, -1] > sol.y[0, 0]

        assert (out / "solution.csv").exists()
        assert (out / "rb_vs_t.png").exists()
        assert (out / "profiles.png").exists()

    def test_csv_columns(self, run_result):
        _, out = run_result
        with open(out / "solution.csv") as f:
            header = f.readline().strip()
        assert header == "t,r_b,Sg_w,dT_w"

    def test_csv_values_physical(self, run_result):
        _, out = run_result
        data = np.loadtxt(out / "solution.csv", delimiter=",",
                          skiprows=1)
        r_b = data[:, 1]
        Sg_w = data[:, 2]
        assert np.all(r_b > 0.1)
        assert np.all(Sg_w >= 0)
        assert np.all(Sg_w <= 1)
