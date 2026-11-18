"""Regenerate the stored reference data used by the regression tests.

Run deliberately, and only when a change in behaviour is intended:

    python -m tests.generate_snapshots api      # public API snapshot
    python -m tests.generate_snapshots golden   # inversion golden values

Every regeneration of golden values must be explained in CHANGELOG.md.
"""
import json
import sys

from tests.api_snapshot import collect
from tests.conftest import DATA, SHORT_INVERSION_CONFIG


def golden_from_calc(calc):
    pij = calc.pij
    return {
        "theta": {k: (None if v is None else float(v))
                  for k, v in calc.theta.items()},
        "beta": float(calc.beta),
        "n_hat": float(calc.n_hat),
        "area": float(calc.area),
        "n_iterations": int(calc.i),
        "n_pairs": int(len(calc.distances)),
        "n_targets": int(len(calc.target_events)),
        "n_sources": int(len(calc.source_events)),
        "sum_spatial_distance_squared":
            float(calc.distances["spatial_distance_squared"].sum()),
        "sum_time_distance": float(calc.distances["time_distance"].sum()),
        "sum_pij": float(pij["Pij"].sum()),
        "sum_p_triggered": float(calc.target_events["P_triggered"].sum()),
        "sum_l_hat": float(calc.source_events["l_hat"].sum()),
    }


def main(what):
    if what in ("api", "all"):
        with open(DATA / "public_api.json", "w") as f:
            json.dump(collect(), f, indent=1, sort_keys=True)
    if what in ("golden", "all"):
        from etas.inversion import ETASParameterCalculation
        calc = ETASParameterCalculation(dict(SHORT_INVERSION_CONFIG))
        calc.prepare()
        calc.invert()
        with open(DATA / "golden_inversion_short.json", "w") as f:
            json.dump(golden_from_calc(calc), f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
