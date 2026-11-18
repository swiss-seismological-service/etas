# Changelog

## Unreleased

### Fixed

- **Free-productivity inversion (`free_productivity=True`) crashed** with
  `UnboundLocalError` in `expected_aftershocks_free_prod`. A formatting change
  in February 2025 split a tuple assignment across lines without brackets.
- Free productivity combined with `bg_term` crashed with a `TypeError` in
  `optimize_parameters`.
- `ETASParameterCalculation.prepare()` logged "Preparation already done,
  aborting..." but then repeated the preparation. It now returns, as the
  message says and as `invert()` already did.
- `store_results` wrote the parameter ranges under the wrong names (shifted
  by one, e.g. `log10_k0_range` held the range of `log10_iota`). The ranges
  are now labelled correctly, and `log10_iota_range` was added.
- `download_catalog_sed`: the default `endtime` was the time the module was
  imported, not the time of the call. The default is now `None`, meaning
  "now".
- `etas.simulation` can now be imported without `seismostats`, which is only
  needed by `ETASSimulation.simulate_to_df` and is imported there.
- `etas.evaluation` can now be imported without `matplotlib` (unused imports
  removed).

### Changed

- The likelihood functions `neg_log_likelihood` and
  `neg_log_likelihood_free_prod` no longer add columns (`G`,
  `likelihood_term`) to the DataFrames passed to them. The `G` column of the
  source events is now set once after each optimization step. Stored results
  are unchanged.
- Declared dependencies that were used but missing: `joblib`, `pyproj`. New
  extras: `plot` (matplotlib, needed by `etas.plots`) and `test`.
- Replaced deprecated pandas usage (`inplace=True`, the `"d"` time unit). This
  removes about 1,800 deprecation warnings per inversion and keeps the code
  working with pandas 4.

### Added

- Test suite (`pytest`), inversion benchmark (`benchmarks/`) and continuous
  integration (`.github/workflows/tests.yml`).
