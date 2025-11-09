import argparse
import os
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path

import etas
# from etas.commands.sim import sim, sim_time_inv
from etas import set_up_logger
from etas.inversion import ETASParameterCalculation
from etas.simulation import ETASSimulation

set_up_logger(level=logging.DEBUG)


def default_cfg_path():
    return Path(etas.__file__).parent.parent / 'input' / 'args.json'


def run(config=None, **kwargs):
    if config is None:
        config = default_cfg_path()

    config_dict = parse_args(config)

    if config_dict.keys() & {"theta", "final_parameters"}:
        parameters = config_dict
    else:
        calculation = ETASParameterCalculation(config_dict, **kwargs)
        calculation.prepare()
        calculation.invert()
        calculation.store_results(data_path=config_dict["data_path"] + '/')

        parameters_fn = (Path(config_dict["data_path"]) /
                         Path("parameters_{}.json".format(calculation.id))).resolve().as_posix()
        with open(parameters_fn, 'r') as f:
            parameters = json.load(f)

    etas_parameters = ETASParameterCalculation.load_calculation(parameters)

    simulation = ETASSimulation(etas_parameters)
    simulation.prepare()

    simulation.simulate_to_csep(fn_store=config_dict["forecast_path"],
                                n_simulations=config_dict["n_sims"],
                                forecast_n_days=config_dict["forecast_duration"],
                                m_threshold=config_dict.get("m_threshold", None),
                                seed=config_dict.get("seed", None))


def parse_args(config_path):
    p = Path(config_path)
    with p.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    start_date = datetime.fromisoformat(cfg['start_date'])
    end_date = datetime.fromisoformat(cfg['end_date'])

    cfg["timewindow_end"] = start_date
    cfg["forecast_duration"] = (end_date - start_date).days

    sim_folder = Path(etas.__path__[0]) / '../forecasts'
    sim_fn = f'etas_{start_date.date().isoformat()}_{end_date.date().isoformat()}.csv'
    cfg["forecast_path"] = (sim_folder / sim_fn).resolve().as_posix()

    if 'n_sims' in cfg.keys():
        cfg["n_simulations"] = cfg["n_sims"]

    # Modify input/state paths relative to config_path file
    config_dir = p.parent
    cfg["shape_coords"] = (config_dir / cfg["shape_coords"]).resolve().as_posix()
    cfg["data_path"] = (config_dir / cfg["data_path"]).resolve().as_posix()
    cfg["fn_catalog"] = (config_dir / cfg["fn_catalog"]).resolve().as_posix()

    return cfg


def main():
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    parser.add_argument('-c', '--config_path', help='Configuration file or parameter file'
                                                    ' of the simulation (default input/args.json)',
                        type=str)
    args = parser.parse_args()
    run(**vars(args))


if __name__ == '__main__':
    main()
