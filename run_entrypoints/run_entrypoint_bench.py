from datetime import datetime, timedelta

import numpy as np
from shapely.geometry import Polygon
from shapely.wkt import dumps

from etas.oef import entrypoint_suiETAS
import json

"""
Performs a benchmark for the SUI model with different number
of cores and simulations.
The results are saved in a json file.

Note that we only perform a single run for each configuration.
As the code is not deterministic, the results may vary.
Because we test for a large number of simulations,
the execution times should be relatively stable.

Based on run_entrypoints/run_entrypoint_sui.py
The catalog is loaded from a file.
"""


def target(n_simulations, workers, catalog='full_catalog.xml'):
    print(f"Running with {n_simulations} simulations and {workers} workers")
    format = '%Y-%m-%d %H:%M:%S'
    auxiliary_start = datetime.strptime("1975-01-01 00:00:00", format)
    timewindow_start = datetime.strptime("1980-01-01 00:00:00", format)
    timewindow_end = datetime.now()

    polygon = Polygon(np.load('../etas/oef/data/ch_shape_buffer.npy'))

    forecast_duration = 30  # days

    # 'catalog.xml'
    with open(catalog, 'r') as f:
        qml = f.read()

    model_input = {
        'forecast_start': timewindow_end,
        'forecast_end': timewindow_end + timedelta(days=forecast_duration),
        'bounding_polygon': dumps(polygon),
        'depth_min': 0,
        'depth_max': 1,                         # always in WGS84
        'seismicity_observation': qml,
        'model_parameters': {
            "theta_0": {
                "log10_mu": -6.21,
                "log10_k0": -2.75,
                "a": 1.13,
                "log10_c": -2.85,
                "omega": -0.13,
                "log10_tau": 3.57,
                "log10_d": -0.51,
                "gamma": 0.15,
                "rho": 0.63
            },
            "mc": 2.2,
            "m_ref": 2.2,
            "delta_m": 0.1,
            "coppersmith_multiplier": 100,
            "earth_radius": 6.3781e3,
            "auxiliary_start": auxiliary_start,
            "timewindow_start": timewindow_start,
            "m_thr": 2.5,
            "n_simulations": n_simulations,
            "parallel": workers,
        },
    }

    start_time = datetime.now()
    results = entrypoint_suiETAS(model_input)
    end_time = datetime.now()

    execution_time = end_time - start_time

    print(f"Execution time: {execution_time}")

    return execution_time


def main():
    """
    Requires to install the package with 'hermes' extras.
    pip install -e .[hermes]
    """

    cores = [8, 16, 32]
    simulations = [1_000, 10_000]
    results = []

    for core in cores:
        for simulation in simulations:
            try:
                execution_time = target(simulation, core)
                results.append({
                    'cores': core,
                    'simulations': simulation,
                    'execution_time': execution_time.total_seconds(),
                })
            except Exception as e:
                results.append({
                    'cores': core,
                    'simulations': simulation,
                    'error': str(e)
                })
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'results_{timestamp}.json'
    with open(filename, 'w') as f:
        json.dump(results, f, indent=4)


if __name__ == "__main__":
    main()
