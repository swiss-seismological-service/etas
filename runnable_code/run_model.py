from datetime import datetime
import logging

from pydantic import BaseModel
from shapely import from_wkt
from numpy import array, where

from seismostats.seismicity.catalog import ForecastCatalog, Catalog
from etas.inversion import ETASParameterCalculation
from etas.simulation import ETASSimulation

logger = logging.getLogger(__name__)


class GeometryExtent(BaseModel):
    bounding_polygon: str


class Theta0(BaseModel):
    log10_mu: float
    log10_k0: float
    a: float
    log10_c: float
    omega: float
    log10_tau: float
    log10_d: float
    gamma: float
    rho: float


class ModelConfig(BaseModel):
    theta_0: Theta0
    mc: float
    delta_m: float
    coppersmith_multiplier: int
    earth_radius: float
    auxiliary_start: datetime  # "1992-01-01 00:00:00",
    timewindow_start: datetime
    n_simulations: int


class ModelInput(BaseModel):
    # Pydantic classes are solely used for easy validation of the input dict
    forecast_start: datetime
    forecast_end: datetime
    geometry: GeometryExtent
    seismic_catalog: str
    model_config: dict


def main(input: dict, *args, **kwargs) -> list[ForecastCatalog]:

    ModelInput.model_validate(input)
    model_config = input["model_config"]
    wkt_polygon = input['geometry']['bounding_polygon']
    polygon = from_wkt(wkt_polygon)
    coords = array(list(polygon.exterior.coords))

    catalog_quakeml = input['seismic_catalog']
    catalog_df = Catalog.from_quakeml(catalog_quakeml)
    catalog_df['mc_current'] = where(
        catalog_df.time < datetime(
            1992, 1, 1), 2.7, 2.3)

    input_dict = {
        'catalog': catalog_df,
        'auxiliary_start': model_config['auxiliary_start'],
        'timewindow_start': model_config['timewindow_start'],
        'timewindow_end': input['forecast_start'],
        'theta_0': model_config['theta_0'],
        'mc': model_config['mc'],
        'delta_m': model_config['delta_m'],
        'coppersmith_multiplier': model_config['coppersmith_multiplier'],
        'earth_radius': model_config['earth_radius'],
        'shape_coords': coords}  # I think this is wkt needed

    # fit
    parameters = ETASParameterCalculation(input_dict)
    parameters.prepare()
    parameters.invert()

    # predict
    simulation = ETASSimulation(parameters)
    simulation.prepare()
    forecast_duration = input['forecast_end'] - input['forecast_start']
    results = simulation.simulate_to_df(
        forecast_duration.days, input['model_config']['n_simulations'])
    # parse results
    # Check the expected number of catalogs based on the inputs
    grouped = results.groupby('catalog_id')
    num_empty_catalogs = input['model_config']['n_simulations'] \
        - grouped.ngroups
    results.empty_catalogs = num_empty_catalogs
    logger.info("Number of empty catalogs inferred from what expected: "
                f"{num_empty_catalogs}")
    results.starttime = input['forecast_start']
    results.endtime = input['forecast_end']

    # The model does not give depth,
    # but depth required to create a quakeml,
    # so just add dummy depth as 0
    results['depth'] = 0.0
    results['magnitude_type'] = 'M'  # Unspecified magnitude?
    return [results]
