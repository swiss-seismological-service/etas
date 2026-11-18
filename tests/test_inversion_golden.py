"""Characterization tests: the inversion must keep producing the results
stored in ``tests/data/golden_inversion_short.json`` (within tolerance).

Integer bookkeeping (number of pairs, sources, targets) and the geometry
of the distance table must match tightly; fitted parameters may move
slightly when the numerics are reorganised (e.g. a faster optimizer).
"""
import json

import numpy as np
import pytest

from tests.conftest import DATA
from tests.generate_snapshots import golden_from_calc

GOLDEN = json.loads((DATA / "golden_inversion_short.json").read_text())

# tolerance on fitted parameters (absolute, parameters are mostly log10)
PARAM_ATOL = 0.02


@pytest.fixture(scope="module")
def result(short_inversion):
    return golden_from_calc(short_inversion)


@pytest.mark.parametrize(
    "key", ["n_pairs", "n_targets", "n_sources", "n_iterations"])
def test_counts(result, key):
    if key == "n_iterations":
        # convergence path may change, but should stay similar
        assert abs(result[key] - GOLDEN[key]) <= 3
    else:
        assert result[key] == GOLDEN[key]


@pytest.mark.parametrize(
    "key", ["area", "beta", "sum_spatial_distance_squared",
            "sum_time_distance"])
def test_data_preparation(result, key):
    assert result[key] == pytest.approx(GOLDEN[key], rel=1e-9)


@pytest.mark.parametrize(
    "key", ["n_hat", "sum_pij", "sum_p_triggered", "sum_l_hat"])
def test_expectation_quantities(result, key):
    assert result[key] == pytest.approx(GOLDEN[key], rel=1e-3)


@pytest.mark.parametrize("name", sorted(GOLDEN["theta"]))
def test_parameters(result, name):
    expected = GOLDEN["theta"][name]
    if expected is None:
        assert result["theta"][name] is None
    else:
        assert result["theta"][name] == pytest.approx(expected,
                                                      abs=PARAM_ATOL)


def test_pij_consistency(short_inversion):
    """Each target's triggering + background probability sums to one."""
    te = short_inversion.target_events
    total = te["P_triggered"] + te["P_background"]
    np.testing.assert_allclose(total, 1, atol=1e-8)
    # and expected aftershocks equal the sum of triggering probabilities
    assert short_inversion.source_events["l_hat"].sum() == pytest.approx(
        short_inversion.pij["Pij"].sum())
