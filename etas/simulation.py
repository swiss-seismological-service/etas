#!/usr/bin/env python
# coding: utf-8

##############################################################################
# simulation of earthquake catalogs using ETAS
#
# as described by Mizrahi et al., 2021
# Leila Mizrahi, Shyam Nandan, Stefan Wiemer;
# The Effect of Declustering on the Size Distribution of Mainshocks.
# Seismological Research Letters 2021; doi: https://doi.org/10.1785/0220200231
##############################################################################

import datetime as dt
import logging
import os
import pprint

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.special import gamma as gamma_func
from scipy.special import gammainccinv
from shapely.geometry import Polygon

from etas.inversion import (ETASParameterCalculation, branching_ratio,
                            expected_aftershocks, haversine,
                            parameter_dict2array, round_half_up, to_days,
                            upper_gamma_ext)
from etas.mc_b_est import simulate_magnitudes

logger = logging.getLogger(__name__)


def inverse_upper_gamma_ext(a, y):
    # TODO: find a more elegant way to do this
    if a > 0:
        return gammainccinv(a, y / gamma_func(a))
    else:
        import warnings

        from pynverse import inversefunc
        from scipy.optimize import minimize

        uge = (lambda x: upper_gamma_ext(a, x))

        # numerical inverse
        def num_inv(a, y):
            def diff(x, xhat):
                xt = upper_gamma_ext(a, x)
                return (xt - xhat) ** 2

            x = np.zeros(len(y))
            for idx, y_value in enumerate(y):
                res = minimize(diff,
                               1.0,
                               args=(y_value),
                               method='Nelder-Mead',
                               tol=1e-6)
                x[idx] = res.x[0]

            return x

        warnings.filterwarnings("ignore")
        result = inversefunc(uge, y)
        warnings.filterwarnings("default")

        # where inversefunc was unable to calculate a result, calculate
        # numerical approximation
        nan_idxs = np.argwhere(np.isnan(result)).flatten()
        if len(nan_idxs) > 0:
            num_res = num_inv(a, y[nan_idxs])
            result[nan_idxs] = num_res

        return result


def simulate_aftershock_time(log10_c, omega, log10_tau, size=1):
    # time delay in days
    c = np.power(10, log10_c)
    tau = np.power(10, log10_tau)
    y = np.random.uniform(size=size)

    return inverse_upper_gamma_ext(
        -omega,
        (1 - y) * upper_gamma_ext(-omega, c / tau)) * tau - c


def simulate_aftershock_place(log10_d, gamma, rho, mi, mc):
    # x and y offset in km
    d = np.power(10, log10_d)
    d_g = d * np.exp(gamma * (mi - mc))
    y_r = np.random.uniform(size=len(mi))
    r = np.sqrt(np.power(1 - y_r, -1 / rho) * d_g - d_g)
    phi = np.random.uniform(0, 2 * np.pi, size=len(mi))

    x = r * np.sin(phi)
    y = r * np.cos(phi)

    return x, y


def simulate_aftershock_radius(log10_d, gamma, rho, mi, mc):
    # x and y offset in km
    d = np.power(10, log10_d)
    d_g = d * np.exp(gamma * (mi - mc))
    y_r = np.random.uniform(size=len(mi))
    r = np.sqrt(np.power(1 - y_r, -1 / rho) * d_g - d_g)

    return r


def simulate_background_location(
        latitudes,
        longitudes,
        background_probs,
        scale=0.1,
        n=1):
    np.random.seed()
    keep_idxs = background_probs >= np.random.uniform(
        size=len(background_probs))

    sample_lats = latitudes[keep_idxs]
    sample_lons = longitudes[keep_idxs]

    choices = np.floor(
        np.random.uniform(
            0,
            len(sample_lats),
            size=n)).astype(int)

    lats = sample_lats.iloc[choices] + \
           np.random.normal(loc=0, scale=scale, size=n)
    lons = sample_lons.iloc[choices] + \
           np.random.normal(loc=0, scale=scale, size=n)

    return lats, lons


def generate_background_events(polygon, timewindow_start, timewindow_end,
                               parameters, beta, mc, delta_m=0,
                               background_lats=None, background_lons=None,
                               background_probs=None, gaussian_scale=None
                               ):
    from etas.inversion import polygon_surface, to_days

    theta = parameter_dict2array(parameters)
    theta_without_mu = theta[1:]

    area = polygon_surface(polygon)
    timewindow_length = to_days(timewindow_end - timewindow_start)

    # area of surrounding rectangle
    min_lat, min_lon, max_lat, max_lon = polygon.bounds
    coords = [[min_lat, min_lon],
              [max_lat, min_lon],
              [max_lat, max_lon],
              [min_lat, max_lon]]
    rectangle = Polygon(coords)
    rectangle_area = polygon_surface(rectangle)

    # number of background events
    expected_n_background = np.power(
        10, parameters["log10_mu"]) * area * timewindow_length
    n_background = np.random.poisson(lam=expected_n_background)

    # generate too many events, afterwards filter those that are in the polygon
    n_generate = int(np.round(n_background * rectangle_area / area * 1.2))

    logger.info(f"  number of background events needed: {n_background}")
    logger.info(
        f"  generating {n_generate} to throw away those outside the polygon")

    # define dataframe with background events
    catalog = pd.DataFrame(
        None,
        columns=[
            "latitude",
            "longitude",
            "time",
            "magnitude",
            "parent",
            "generation"])

    # generate lat, long
    if background_probs is not None:
        catalog["latitude"], catalog["longitude"] = \
            simulate_background_location(background_lats,
                                         background_lons,
                                         background_probs=background_probs,
                                         scale=gaussian_scale,
                                         n=n_generate
                                         )
    else:
        catalog["latitude"] = np.random.uniform(
            min_lat, max_lat, size=n_generate)
        catalog["longitude"] = np.random.uniform(
            min_lon, max_lon, size=n_generate)

    catalog = gpd.GeoDataFrame(
        catalog, geometry=gpd.points_from_xy(
            catalog.latitude, catalog.longitude))
    catalog = catalog[catalog.intersects(polygon)].head(n_background)

    # if not enough events fell into the polygon, do it again...
    while len(catalog) != n_background:
        logger.info("  didn't create enough events. trying again..")

        # define dataframe with background events
        catalog = pd.DataFrame(
            None,
            columns=[
                "latitude",
                "longitude",
                "time",
                "magnitude",
                "parent",
                "generation"])

        # generate lat, long
        catalog["latitude"] = np.random.uniform(
            min_lat, max_lat, size=n_generate)
        catalog["longitude"] = np.random.uniform(
            min_lon, max_lon, size=n_generate)

        catalog = gpd.GeoDataFrame(
            catalog, geometry=gpd.points_from_xy(
                catalog.latitude, catalog.longitude))
        catalog = catalog[catalog.intersects(polygon)].head(n_background)

    # generate time, magnitude
    catalog["time"] = [
        timewindow_start
        + dt.timedelta(days=d) for d in np.random.uniform(
            0,
            timewindow_length,
            size=n_background)]

    catalog["magnitude"] = simulate_magnitudes(
        n_background, beta=beta, mc=mc - delta_m / 2)

    # info about origin of event
    catalog["generation"] = 0
    catalog["parent"] = 0
    catalog["is_background"] = True

    # reindexing
    catalog = catalog.sort_values(by="time").reset_index(drop=True)
    catalog.index += 1
    catalog["gen_0_parent"] = catalog.index

    # simulate number of aftershocks
    catalog["expected_n_aftershocks"] = expected_aftershocks(
        catalog["magnitude"],
        params=[theta_without_mu, mc - delta_m / 2],
        no_start=True,
        no_end=True,
        # axis=1
    )
    catalog["n_aftershocks"] = np.random.poisson(
        lam=catalog["expected_n_aftershocks"])

    return catalog.drop("geometry", axis=1)


def generate_aftershocks(sources,
                         generation,
                         parameters,
                         beta,
                         mc,
                         timewindow_end,
                         timewindow_length,
                         auxiliary_end=None,
                         delta_m=0,
                         earth_radius=6.3781e3,
                         polygon=None):
    theta = parameter_dict2array(parameters)
    theta_without_mu = theta[1:]

    # random timedeltas for all aftershocks
    total_n_aftershocks = sources["n_aftershocks"].sum()

    all_deltas = simulate_aftershock_time(
        log10_c=parameters["log10_c"],
        omega=parameters["omega"],
        log10_tau=parameters["log10_tau"],
        size=total_n_aftershocks
    )

    aftershocks = sources.loc[sources.index.repeat(sources.n_aftershocks)]

    keep_columns = ["time", "latitude", "longitude", "magnitude"]
    aftershocks["parent"] = aftershocks.index

    for col in keep_columns:
        aftershocks["parent_" + col] = aftershocks[col]

    # time of aftershock
    aftershocks = aftershocks[[
        col for col in aftershocks.columns if "parent" in col]] \
        .reset_index(drop=True)
    aftershocks["time_delta"] = all_deltas
    aftershocks.query("time_delta <= @ timewindow_length", inplace=True)

    aftershocks["time"] = aftershocks["parent_time"] + \
                          pd.to_timedelta(aftershocks["time_delta"], unit='d')
    aftershocks.query("time <= @ timewindow_end", inplace=True)
    if auxiliary_end is not None:
        aftershocks.query("time > @ auxiliary_end", inplace=True)

    # location of aftershock
    aftershocks["radius"] = simulate_aftershock_radius(
        parameters["log10_d"],
        parameters["gamma"],
        parameters["rho"],
        aftershocks["parent_magnitude"],
        mc=mc)
    aftershocks["angle"] = np.random.uniform(
        0, 2 * np.pi, size=len(aftershocks))
    aftershocks["degree_lon"] = haversine(
        np.radians(aftershocks["parent_latitude"]),
        np.radians(aftershocks["parent_latitude"]),
        np.radians(0),
        np.radians(1),
        earth_radius
    )
    aftershocks["degree_lat"] = haversine(
        np.radians(aftershocks["parent_latitude"] - 0.5),
        np.radians(aftershocks["parent_latitude"] + 0.5),
        np.radians(0),
        np.radians(0),
        earth_radius
    )
    aftershocks["latitude"] = aftershocks["parent_latitude"] + (
            aftershocks["radius"] * np.cos(aftershocks["angle"])
    ) / aftershocks["degree_lat"]
    aftershocks["longitude"] = aftershocks["parent_longitude"] + (
            aftershocks["radius"] * np.sin(aftershocks["angle"])
    ) / aftershocks["degree_lon"]

    as_cols = [
        "parent",
        "gen_0_parent",
        "time",
        "latitude",
        "longitude"
    ]
    if polygon is not None:
        aftershocks = gpd.GeoDataFrame(
            aftershocks, geometry=gpd.points_from_xy(
                aftershocks.latitude, aftershocks.longitude))
        aftershocks = aftershocks[aftershocks.intersects(polygon)]

    aadf = aftershocks[as_cols].reset_index(drop=True)

    # magnitudes
    n_total_aftershocks = len(aadf.index)
    aadf["magnitude"] = simulate_magnitudes(
        n_total_aftershocks, beta=beta, mc=mc - delta_m / 2)

    # info about generation and being background
    aadf["generation"] = generation + 1
    aadf["is_background"] = False

    # info for next generation
    aadf["expected_n_aftershocks"] = expected_aftershocks(
        aadf["magnitude"],
        params=[theta_without_mu, mc - delta_m / 2],
        no_start=True,
        no_end=True,
    )
    aadf["n_aftershocks"] = np.random.poisson(
        lam=aadf["expected_n_aftershocks"])

    return aadf


def prepare_auxiliary_catalog(auxiliary_catalog, parameters, mc, delta_m=0):
    theta = parameter_dict2array(parameters)
    theta_without_mu = theta[1:]

    catalog = auxiliary_catalog.copy()

    catalog.loc[:, "generation"] = 0
    catalog.loc[:, "parent"] = 0
    catalog.loc[:, "is_background"] = False

    # reindexing
    catalog["evt_id"] = catalog.index.values
    catalog = catalog.sort_values(by="time").reset_index(drop=True)
    catalog.index += 1
    catalog["gen_0_parent"] = catalog.index

    # simulate number of aftershocks
    catalog["expected_n_aftershocks"] = expected_aftershocks(
        catalog["magnitude"],
        params=[theta_without_mu, mc - delta_m / 2],
        no_start=True,
        no_end=True,
        # axis=1
    )

    catalog["n_aftershocks"] = catalog["expected_n_aftershocks"].apply(
        np.random.poisson,
        # axis = 1
    )

    return catalog


def generate_catalog(polygon,
                     timewindow_start,
                     timewindow_end,
                     parameters,
                     mc,
                     beta_main,
                     beta_aftershock=None,
                     delta_m=0,
                     background_lats=None,
                     background_lons=None,
                     background_probs=None,
                     gaussian_scale=None):
    """
    Simulates an earthquake catalog.

    Optionally use coordinates and independence probabilities
    of observed events to simulate locations of background events.

    Parameters
    ----------
    polygon : Polygon
        Coordinates of boundaries in which catalog is generated.
    timewindow_start : datetime
        Simulation start.
    timewindow_end : datetime
         Simulation end.
    parameters : dict
        As estimated in the ETAS EM inversion.
    mc : float
        Completeness magnitude. If delta_m > 0, magnitudes are
        simulated above mc-delta_m/2.
    beta_main : float
        Beta used to generate background event magnitudes.
    beta_aftershock : float, optional
        Beta used to generate aftershock magnitudes. If none,
        beta_main is used.
    delta_m : float, default 0
        Bin size of magnitudes.
    background_lats : list, optional
        list of latitudes
    background_lons : list, optional
        list of longitudes
    background_probs : list, optional
        list of independence probabilities
        these three lists are assumed to be sorted
        such that corresponding entries belong to the same event
    gaussian_scale : float, optional
        sigma to be used when background loations are generated
    """

    if beta_aftershock is None:
        beta_aftershock = beta_main

    # generate background events
    logger.info("generating background events..")
    catalog = generate_background_events(
        polygon,
        timewindow_start,
        timewindow_end,
        parameters,
        beta=beta_main,
        mc=mc,
        delta_m=delta_m,
        background_lats=background_lats,
        background_lons=background_lons,
        background_probs=background_probs,
        gaussian_scale=gaussian_scale)

    theta = parameters["log10_mu"], parameters["log10_k0"], parameters["a"], \
            parameters["log10_c"], parameters["omega"], parameters[
                "log10_tau"], \
            parameters["log10_d"], parameters["gamma"], parameters["rho"]

    br = branching_ratio(theta, beta_main)

    logger.info(f'  number of background events: {len(catalog.index)}')
    logger.info(f'\n  branching ratio: {br}')
    logger.info('  expected total number of events (if time were infinite):',
                f'{len(catalog.index) * 1 / (1 - br)}')

    generation = 0
    timewindow_length = to_days(timewindow_end - timewindow_start)

    while True:
        logger.info(f'\n\nsimulating aftershocks of generation {generation}..')
        sources = catalog.query(
            "generation == @generation and n_aftershocks > 0").copy()

        # if no aftershocks are produced by events of this generation, stop
        logger.info(
            f'  number of events with aftershocks: {len(sources.index)}')

        if len(sources.index) == 0:
            break

        # an array with all aftershocks. to be appended to the catalog
        aftershocks = generate_aftershocks(
            sources,
            generation,
            parameters,
            beta_aftershock,
            mc,
            delta_m=delta_m,
            timewindow_end=timewindow_end,
            timewindow_length=timewindow_length,
        )

        aftershocks.index += catalog.index.max() + 1

        logger.info(
            f'  number of generated aftershocks: {len(aftershocks.index)}')

        catalog = pd.concat([
            catalog, aftershocks
        ], ignore_index=False, sort=True)

        generation = generation + 1

    logger.info(f'\n\ntotal events simulated: {len(catalog)}')
    catalog = gpd.GeoDataFrame(
        catalog, geometry=gpd.points_from_xy(
            catalog.latitude, catalog.longitude))
    catalog = catalog[catalog.intersects(polygon)]
    logger.info(f'inside the polygon: {len(catalog)}')

    return catalog.drop("geometry", axis=1)


def simulate_catalog_continuation(auxiliary_catalog,
                                  auxiliary_start,
                                  auxiliary_end,
                                  polygon,
                                  simulation_end,
                                  parameters,
                                  mc,
                                  beta_main,
                                  beta_aftershock=None,
                                  delta_m=0,
                                  background_lats=None,
                                  background_lons=None,
                                  background_probs=None,
                                  gaussian_scale=None,
                                  filter_polygon=True,
                                  ):
    """
    auxiliary_catalog : pd.DataFrame
        Catalog used for aftershock generation in simulation period
    auxiliary_start : datetime
        Start time of auxiliary catalog.
    auxiliary_end : datetime
        End time of auxiliary_catalog. start of simulation period.
    polygon : Polygon
        Polygon in which events are generated.
    simulation_end : datetime
        End time of simulation period.
    parameters : dict
        ETAS parameters
    mc : float
        Reference mc for ETAS parameters.
    beta_main : float
        Beta for main shocks. can be a map for spatially variable betas.
    beta_aftershock : float, optional
        Beta for aftershocks. if None, is set to be same as main shock beta.
    delta_m : float, default 0
        Bin size for discrete magnitudes.
    background_lats : list, optional
        Latitudes of background events.
    background_lons : list, optional
        Longitudes of background events.
    background_probs : list, optional
        Independence probabilities of background events.
    gaussian_scale : float, optional
        Extent of background location smoothing.
    """
    # preparing betas
    if beta_aftershock is None:
        beta_aftershock = beta_main

    background = generate_background_events(
        polygon,
        auxiliary_end,
        simulation_end,
        parameters,
        beta_main,
        mc,
        delta_m,
        background_lats=background_lats,
        background_lons=background_lons,
        background_probs=background_probs,
        gaussian_scale=gaussian_scale,
    )
    background["evt_id"] = ''
    background["xi_plus_1"] = 1
    auxiliary_catalog = prepare_auxiliary_catalog(
        auxiliary_catalog=auxiliary_catalog, parameters=parameters, mc=mc,
        delta_m=delta_m,
    )
    background.index += auxiliary_catalog.index.max() + 1
    background["evt_id"] = background.index.values

    catalog = pd.concat([background, auxiliary_catalog], sort=True)

    logger.debug(f'number of background events: {len(background.index)}')
    logger.debug(
        f'number of auxiliary events: {len(auxiliary_catalog.index)}')
    generation = 0
    timewindow_length = to_days(simulation_end - auxiliary_start)

    while True:
        logger.debug(f'generation {generation}')
        sources = catalog.query(
            "generation == @generation and n_aftershocks > 0").copy()

        # if no aftershocks are produced by events of this generation, stop
        logger.debug(
            f'number of events with aftershocks: {len(sources.index)}')
        if len(sources.index) == 0:
            break

        # an array with all aftershocks. to be appended to the catalog
        aftershocks = generate_aftershocks(
            sources,
            generation,
            parameters,
            beta_aftershock,
            mc,
            delta_m=delta_m,
            timewindow_end=simulation_end,
            timewindow_length=timewindow_length,
            auxiliary_end=auxiliary_end)

        aftershocks.index += catalog.index.max() + 1
        aftershocks.query("time>@auxiliary_end", inplace=True)

        logger.debug(f'number of aftershocks: {len(aftershocks.index)}')
        logger.debug('their number of aftershocks should be:'
                     f'{aftershocks["n_aftershocks"].sum()}')
        aftershocks["xi_plus_1"] = 1
        catalog = pd.concat([
            catalog, aftershocks
        ], ignore_index=False, sort=True)

        generation = generation + 1
    if filter_polygon:
        catalog = gpd.GeoDataFrame(
            catalog, geometry=gpd.points_from_xy(
                catalog.latitude, catalog.longitude))
        catalog = catalog[catalog.intersects(polygon)]
        return catalog.drop("geometry", axis=1)
    else:
        return catalog


class ETASSimulation:
    def __init__(self, inversion_params: ETASParameterCalculation,
                 gaussian_scale: float = 0.1):

        self.logger = logging.getLogger(__name__)

        self.inversion_params = inversion_params

        self.forecast_start_date = None
        self.forecast_end_date = None

        self.catalog = None
        self.target_events = None
        self.source_events = None

        self.polygon = None

        self.gaussian_scale = gaussian_scale

        self.logger.debug('using parameters calculated on {}\n'.format(
            inversion_params.calculation_date))
        self.logger.debug(pprint.pformat(self.inversion_params.theta),
                          indent=4)

        self.logger.info(
            'm_ref: {}, min magnitude in training catalog: {}'.format(
                self.inversion_params.m_ref,
                self.inversion_params.catalog['magnitude'].min()))

    def prepare(self):
        self.polygon = Polygon(self.inversion_params.shape_coords)
        # Xi_plus_1 is aftershock productivity inflation factor.
        # If not used, set to 1.
        self.source_events = self.inversion_params.source_events.copy()
        if 'xi_plus_1' not in self.source_events.columns:
            self.source_events['xi_plus_1'] = 1

        self.catalog = pd.merge(
            self.source_events,
            self.inversion_params.catalog[["latitude",
                                           "longitude", "time", "magnitude"]],
            left_index=True,
            right_index=True,
            how='left',
        )
        assert len(self.catalog) == len(self.source_events), \
            "lost/found some sources in the merge! " \
            f"{len(self.catalog)} -- " \
            f"{len(self.source_events)}"

        np.testing.assert_allclose(
            self.catalog.magnitude.min(),
            self.inversion_params.m_ref,
            err_msg="smallest magnitude in sources is "
                    f"{self.catalog.magnitude.min()} "
                    f"but I am supposed to simulate "
                    f"above {self.inversion_params.m_ref}")

        self.target_events = self.inversion_params.target_events.query(
            "magnitude>=@self.inversion_params.m_ref "
            "-@self.inversion_params.delta_m/2")
        self.target_events = gpd.GeoDataFrame(
            self.target_events, geometry=gpd.points_from_xy(
                self.target_events.latitude,
                self.target_events.longitude))
        self.target_events = self.target_events[
            self.target_events.intersects(self.polygon)]

    def simulate_once(self, fn_store, forecast_n_days, filter_polygon=True):
        start = dt.datetime.now()
        np.random.seed()

        # end of training period is start of forecasting period
        self.forecast_start_date = self.inversion_params.timewindow_end
        self.forecast_end_date = self.forecast_start_date \
                                 + dt.timedelta(days=forecast_n_days)

        continuation = simulate_catalog_continuation(
            self.catalog,
            auxiliary_start=self.inversion_params.auxiliary_start,
            auxiliary_end=self.forecast_start_date,
            polygon=self.polygon,
            simulation_end=self.forecast_end_date,
            parameters=self.inversion_params.theta,
            mc=self.inversion_params.m_ref - self.inversion_params.delta_m / 2,
            beta_main=self.inversion_params.beta,
            background_lats=self.target_events['latitude'],
            background_lons=self.target_events['longitude'],
            background_probs=self.target_events['P_background'],
            gaussian_scale=self.gaussian_scale,
            filter_polygon=filter_polygon
        )
        continuation.query(
            'time>=@self.forecast_start_date and '
            'time<=@self.forecast_end_date and '
            'magnitude>=@self.inversion_params.m_ref'
            '-@self.inversion_params.delta_m/2',
            inplace=True)

        self.logger.debug(f"took {dt.datetime.now() - start} to simulate "
                          f"1 catalog containing {len(continuation)} events.")

        continuation.magnitude = round_half_up(continuation.magnitude, 1)
        continuation.index.name = 'id'
        self.logger.debug("store catalog..")
        # os.makedirs(os.path.dirname(
        # 	simulation_config['fn_store_simulation']), exist_ok=True)
        continuation[["latitude", "longitude",
                      "time", "magnitude", "is_background"]] \
            .sort_values(by="time").to_csv(
            fn_store)
        self.logger.info("\nDONE simulating!")

    def simulate_many(self, fn_store, forecast_n_days, n_simulations,
                      m_thr=None, filter_polygon=True):
        start = dt.datetime.now()

        np.random.seed()
        if m_thr is None:
            m_thr = self.inversion_params.m_ref

        # end of training period is start of forecasting period
        self.forecast_start_date = self.inversion_params.timewindow_end
        self.forecast_end_date = self.forecast_start_date \
                                 + dt.timedelta(days=forecast_n_days)

        simulations = pd.DataFrame()
        for sim_id in np.arange(n_simulations):
            continuation = simulate_catalog_continuation(
                self.catalog,
                auxiliary_start=self.inversion_params.auxiliary_start,
                auxiliary_end=self.forecast_start_date,
                polygon=self.polygon,
                simulation_end=self.forecast_end_date,
                parameters=self.inversion_params.theta,
                mc=self.inversion_params.m_ref
                   - self.inversion_params.delta_m / 2,
                beta_main=self.inversion_params.beta,
                background_lats=self.target_events['latitude'],
                background_lons=self.target_events['longitude'],
                background_probs=self.target_events['P_background'],
                gaussian_scale=self.gaussian_scale,
                filter_polygon=filter_polygon,
            )
            continuation["catalog_id"] = sim_id
            simulations = pd.concat([
                simulations, continuation
            ], ignore_index=False)

            if sim_id % 10 == 0 or sim_id == n_simulations - 1:
                simulations.query(
                    'time>=@self.forecast_start_date and '
                    'time<=@self.forecast_end_date and '
                    'magnitude>=@m_thr-@self.inversion_params.delta_m/2',
                    inplace=True)
                simulations.magnitude = round_half_up(simulations.magnitude, 1)
                simulations.index.name = 'id'
                self.logger.debug(
                    "storing simulations up to {}".format(sim_id))
                self.logger.debug(
                    f'took {dt.datetime.now() - start} to simulate '
                    f'{sim_id + 1} catalogs.')
                # now filter polygon
                simulations = gpd.GeoDataFrame(
                    simulations, geometry=gpd.points_from_xy(
                        simulations.latitude, simulations.longitude))
                simulations = simulations[simulations.intersects(self.polygon)]
                simulations = simulations[
                    ['latitude', 'longitude', 'magnitude', 'time',
                     'catalog_id']]

                if not os.path.exists(fn_store) or sim_id == 0:
                    simulations.to_csv(fn_store, mode='w', header=True,
                                       index=False)
                else:
                    simulations.to_csv(fn_store, mode='a', header=False,
                                       index=False)
                simulations = pd.DataFrame()

        self.logger.info("\nDONE simulating!")
