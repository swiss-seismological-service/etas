import copy
from importlib import resources

import numpy as np
import pandas as pd
import math

from etas.inversion import (parameter_dict2array, responsibility_factor,
                            round_half_up)
from etas.simulation import parameters_from_standard_formulation

try:
    from hermes_model import ModelInput, validate_entrypoint
except ImportError:
    raise ImportError(
        "The hermes package is required to run the model. "
        "Please install this package with the 'hermes' extra requirements.")

from seismostats import Catalog, ForecastCatalog
from shapely import Polygon, wkt

from etas.inversion import ETASParameterCalculation
from etas.simulation import ETASSimulation


@validate_entrypoint(induced=False)
def entrypoint_suiETAS(model_input: ModelInput) -> list[ForecastCatalog]:
    """
    Introduces a standardized interface to run the suiETAS model.

    More information under https://gitlab.seismo.ethz.ch/indu/hermes-model

    """

    # Prepare seismic data from QuakeML
    catalog = Catalog.from_quakeml(model_input.seismicity_observation)

    # Prepare model input
    polygon = np.array(
        wkt.loads(model_input.bounding_polygon).exterior.coords)
    polygon[:, [0, 1]] = polygon[:, [1, 0]]

    model_parameters = \
        model_input.model_parameters | model_input.model_settings
    model_parameters['shape_coords'] = polygon
    model_parameters['catalog'] = catalog
    model_parameters['timewindow_end'] = model_input.forecast_start
    model_parameters['b_positive'] = True

    # Run ETAS Parameter Inversion
    etas_parameters = ETASParameterCalculation(model_parameters)
    etas_parameters.prepare()
    etas_parameters.invert()

    # Run ETAS Simulation
    simulation = ETASSimulation(etas_parameters, m_max=7.6)
    simulation.prepare()

    # prepare background grid for simulation of locations
    with resources.open_binary("etas.oef.data", "SUIhaz2015_rates.csv") as f:
        bg_grid = pd.read_csv(f, index_col=0)

    background_lats = bg_grid.query("in_poly")["latitude"].copy()
    background_lons = bg_grid.query("in_poly")["longitude"].copy()
    background_probs = 1000 * bg_grid.query("in_poly")["rate_2.5"].copy()

    simulation.bg_grid = True
    simulation.background_lats = background_lats
    simulation.background_lons = background_lons
    simulation.background_probs = background_probs
    simulation.bsla = round_half_up(
        np.min(np.diff(np.sort(np.unique(background_lats)))),
        4
    )
    simulation.bslo = round_half_up(
        np.min(np.diff(np.sort(np.unique(background_lons)))),
        4
    )

    forecast_duration = model_input.forecast_end - model_input.forecast_start

    results = simulation.simulate_to_df(
        forecast_duration.days, model_parameters['n_simulations'],
        m_threshold=model_parameters['m_thr'])

    # Add required additional columns and attributes
    results['depth'] = 0
    results.starttime = model_input.forecast_start
    results.endtime = model_input.forecast_end
    results.n_catalogs = model_parameters['n_simulations']
    results.bounding_polygon = model_input.bounding_polygon
    results.depth_min = model_input.depth_min
    results.depth_max = model_input.depth_max
    return [results]


@validate_entrypoint(induced=False)
def entrypoint_genETAS(model_input: ModelInput) -> list[ForecastCatalog]:
    """
    Introduces a standardized interface to run the genETAS model for Switzerland.

    More information under https://gitlab.seismo.ethz.ch/indu/hermes-model

    """

    # Prepare seismic data from QuakeML
    catalog = Catalog.from_quakeml(model_input.seismicity_observation)

    # Prepare model input
    polygon = np.array(
        wkt.loads(model_input.bounding_polygon).exterior.coords)
    polygon[:, [0, 1]] = polygon[:, [1, 0]]

    model_parameters = \
        model_input.model_parameters | model_input.model_settings
    model_parameters['shape_coords'] = polygon
    model_parameters['catalog'] = catalog
    model_parameters['timewindow_end'] = model_input.forecast_start
    model_parameters['b_positive'] = True

    # Run ETAS Parameter Inversion
    etas_parameters = ETASParameterCalculation(model_parameters)
    etas_parameters.prepare()
    etas_parameters.invert()

    # Run ETAS Simulation
    simulation_deep = ETASSimulation(copy.deepcopy(etas_parameters), m_max=7.6)
    simulation_deep.prepare()
    simulation_shallow = ETASSimulation(copy.deepcopy(etas_parameters),
                                        m_max=7.6)
    simulation_shallow.prepare()

    # prepare background grid for simulation of locations
    with resources.open_binary("etas.oef.data", "SUIhaz2015_rates.csv") as f:
        bg_grid = pd.read_csv(f, index_col=0)

    background_lats = bg_grid.query("in_poly")["latitude"].copy()
    background_lons = bg_grid.query("in_poly")["longitude"].copy()
    background_probs = 1000 * bg_grid.query("in_poly")["rate_2.5"].copy()

    log10_mu_inverted = simulation_deep.inversion_params.theta["log10_mu"]
    parameters_inverted_deep = simulation_deep.inversion_params.theta
    parameters_inverted_shallow = simulation_shallow.inversion_params.theta
    standard_deep = {
        'a': -2.23,
        'p': 1.08,
        'alpha': 1.0,
        'log10_c': -2.06
    }
    standard_shallow = {
        'a': -2.46,
        'p': 0.96,
        'alpha': 1.0,
        'log10_c': -2.76
    }
    parameters_deep = parameters_from_standard_formulation(
        standard_deep, parameters_inverted_deep,
        delta_m_ref=simulation_deep.inversion_params.m_ref - 4.5,
        dm_max_st=7.6 - 4.5
    )
    parameters_shallow = parameters_from_standard_formulation(
        standard_shallow, parameters_inverted_shallow,
        delta_m_ref=simulation_shallow.inversion_params.m_ref - 4.5,
        dm_max_st=7.6 - 4.5
    )
    parameters_deep["log10_mu"] = log10_mu_inverted
    parameters_shallow["log10_mu"] = log10_mu_inverted

    simulation_deep.inversion_params.theta = parameters_deep
    simulation_shallow.inversion_params.theta = parameters_shallow

    for simulation in [simulation_deep, simulation_shallow]:
        simulation.bg_grid = True
        simulation.background_lats = background_lats
        simulation.background_lons = background_lons
        simulation.background_probs = background_probs
        simulation.bsla = round_half_up(
            np.min(np.diff(np.sort(np.unique(background_lats)))),
            4
        )
        simulation.bslo = round_half_up(
            np.min(np.diff(np.sort(np.unique(background_lons)))),
            4
        )

    forecast_duration = model_input.forecast_end - model_input.forecast_start

    n_simulations_deep = model_parameters['n_simulations'] // 2
    n_simulations_shallow = model_parameters['n_simulations'] - \
        n_simulations_deep

    results_deep = simulation_deep.simulate_to_df(
        forecast_duration.days, n_simulations_deep,
        m_threshold=model_parameters['m_thr'])
    results_shallow = simulation_shallow.simulate_to_df(
        forecast_duration.days, n_simulations_shallow,
        m_threshold=model_parameters['m_thr'])
    results_shallow['catalog_id'] += n_simulations_deep
    results = pd.concat([results_deep, results_shallow])

    # Add required additional columns and attributes
    results['depth'] = 0
    results.starttime = model_input.forecast_start
    results.endtime = model_input.forecast_end
    results.n_catalogs = model_parameters['n_simulations']
    results.bounding_polygon = model_input.bounding_polygon
    results.depth_min = model_input.depth_min
    results.depth_max = model_input.depth_max
    return [results]


@validate_entrypoint(induced=False)
def entrypoint_europe(model_input: ModelInput) -> list[ForecastCatalog]:
    # Prepare seismic data from QuakeML
    catalog = Catalog.from_quakeml(model_input.seismicity_observation)

    catalog = catalog.sort_values(by="time").reset_index(drop=True)

    # Prepare model input
    model_parameters = \
        model_input.model_parameters | model_input.model_settings
    model_parameters["catalog"] = catalog

    polygon = np.array(
        wkt.loads(model_input.bounding_polygon).exterior.coords)
    polygon[:, [0, 1]] = polygon[:, [1, 0]]
    model_input.bounding_polygon = wkt.dumps(Polygon(polygon))

    # Load ETAS inversion object but adjust to simulation properties
    etas_parameters = ETASParameterCalculation(model_parameters)

    etas_parameters.timewindow_end = model_input.forecast_start
    etas_parameters.catalog["mc_current"] = model_parameters["mc"]
    etas_parameters.theta = model_parameters["theta"]
    etas_parameters.m_ref = model_parameters["m_ref"]
    mc_above_ref = etas_parameters.catalog["mc_current"] - \
        model_parameters["m_ref"]

    etas_parameters.catalog["magnitude"] = round_half_up(
        etas_parameters.catalog.magnitude / 0.2) * 0.2

    theta = parameter_dict2array(etas_parameters.theta)
    etas_parameters.catalog["xi_plus_1"] = responsibility_factor(
        theta,
        etas_parameters.beta,
        mc_above_ref
    )

    # Run 1 step to assign ellipses to all events prior to simulation timewindow
    etas_parameters.catalog["aspect_ratio"] = 1.0
    etas_parameters.catalog["orientation"] = 0.0

    def ar_max(x):
        if x < 3: return 1
        if x < 5: return 1.25
        if x < 10: return 1.5
        if x < 20: return 2
        if x < 30: return 5
        if x < 50: return 8
        if x < 100: return 10 
        return 10

    if len(etas_parameters.catalog) > 0:
        try:
            etas_parameters.distances = etas_parameters.calculate_distances()
            etas_parameters.target_events = etas_parameters.prepare_target_events()
            etas_parameters.source_events = etas_parameters.prepare_source_events()

            mc_min = model_parameters["m_ref"] - model_parameters["delta_m"] / 2
            (
                etas_parameters.pij,
                etas_parameters.target_events,
                etas_parameters.source_events,
                etas_parameters.n_hat,
                etas_parameters.i_hat,
            ) = etas_parameters.expectation_step(theta, mc_min)

            grouped = etas_parameters.pij.groupby('source_id')
            aspect_ratios = {}
            orientations = {}

            for source, targets in grouped:
                target_ids = targets['index']
                Pij_values = targets['Pij'] * targets['zeta_plus_1']
                afters = etas_parameters.catalog.loc[target_ids]
                
                if Pij_values.sum() > 1 and len(afters) > 3:
                    
                    x = afters['longitude']
                    y = afters['latitude']
                    min_pij = np.max([Pij_values.min(), 1e-10])
                    w = Pij_values / min_pij
                    w = w.astype(int)
                    covariance_matrix = np.cov(x, y, fweights=w)
                    val, vec = np.linalg.eigh(covariance_matrix)

                    lam1, lam2 = np.sqrt(val[0]), np.sqrt(np.abs(val[1]))
                    if lam1 != 0 and lam2 != 0:
                        if lam1 > lam2:
                            aspect_ratios[source] = (lam1 / lam2)
                            orientations[source] = (np.arctan2(vec[1, 0] , vec[0, 0]))
                        else:
                            aspect_ratios[source] = (lam2 / lam1)
                            orientations[source] = (np.arctan2(vec[1, 1] , vec[0, 1]))

                        # Cap aspect ratio at ar_max(n_potential_aftershocks)
                        aspect_ratios[source] = max(aspect_ratios[source], ar_max(len(afters)))
                    else:
                        aspect_ratios[source] = 1.0
                        orientations[source] = 0.0
                else:
                    aspect_ratios[source] = 1.0
                    orientations[source] = 0.0

            # Map values back to source_events
            etas_parameters.source_events['aspect_ratio'] = etas_parameters.source_events.index.map(aspect_ratios)
            etas_parameters.source_events['orientation'] = etas_parameters.source_events.index.map(orientations)

            # Default to circle in case of NaN
            etas_parameters.source_events['aspect_ratio'] = etas_parameters.source_events['aspect_ratio'].fillna(1.0)
            etas_parameters.source_events['orientation'] = etas_parameters.source_events['orientation'].fillna(0.0)

            updated_sources = etas_parameters.source_events
            etas_parameters.catalog['aspect_ratio'] = updated_sources['aspect_ratio']
            etas_parameters.catalog['orientation'] = updated_sources['orientation']

        except ValueError as e:
            if "No objects to concatenate" in str(e):
                print("No highly clustered event pairs found; defaults stay as circles.")
                pass 
            else:
                raise e

    # Prepare catalogue for simulation
    etas_parameters.catalog = etas_parameters.catalog[["longitude",
                                                       "latitude",
                                                       "time",
                                                       "magnitude",
                                                       "mc_current",
                                                       "xi_plus_1",
                                                       "aspect_ratio",
                                                       "orientation"]].copy()

    etas_parameters.source_events = etas_parameters.catalog

    # prepare background grid for simulation of locations
    with resources.open_binary("etas.oef.data", "europe_rate_map.csv") as f:
        bg_grid = pd.read_csv(f, index_col=0)

    background_lats = bg_grid.latitude
    background_lons = bg_grid.longitude
    background_probs = bg_grid.total / bg_grid.total.max()

    # Run ETAS Simulation
    simulation = ETASSimulation(etas_parameters, m_max=10.0)
    simulation.bg_grid = True
    simulation.background_lats = background_lats
    simulation.background_lons = background_lons
    simulation.background_probs = background_probs
    simulation.bsla = round_half_up(
        np.min(np.diff(np.sort(np.unique(background_lats)))),
        4
    )
    simulation.bslo = round_half_up(
        np.min(np.diff(np.sort(np.unique(background_lons)))),
        4
    )
    simulation.catalog = etas_parameters.catalog
    simulation.source_events = etas_parameters.source_events
    simulation.forecast_start_date = model_input.forecast_start
    simulation.forecast_end_date = model_input.forecast_end
    simulation.polygon = wkt.loads(model_input.bounding_polygon)

    forecast_duration = model_input.forecast_end - model_input.forecast_start
    #simulation.catalog.to_csv("catalog_europe.csv")

    results = simulation.simulate_to_df(
        forecast_duration.days, model_parameters['n_simulations'], info_cols=["is_background", "parent_id"])

    # Add required additional columns and attributes
    results['depth'] = 0
    results.starttime = model_input.forecast_start
    results.endtime = model_input.forecast_end
    results.n_catalogs = model_parameters['n_simulations']
    results.bounding_polygon = model_input.bounding_polygon
    results.depth_min = model_input.depth_min
    results.depth_max = model_input.depth_max

    return [results]
