# The model

## Conditional intensity

The rate of earthquakes above the reference magnitude $m_c$ at time $t$
and location $x$, given the past events $i$, is

$$
\lambda(t, x) = \mu + \sum_{i: t_i < t} g(m_i, t - t_i, |x - x_i|^2),
$$

with the triggering kernel

$$
g(m, t, r^2) = k_0 \, e^{a (m - m_c)}
    \cdot \frac{e^{-t / \tau}}{(t + c)^{1 + \omega}}
    \cdot \frac{1}{\left(r^2 + d \, e^{\gamma (m - m_c)}\right)^{1 + \rho}}.
$$

Magnitudes above $m_c$ follow the Gutenberg-Richter law with density
$\beta e^{-\beta (m - m_c)}$, where $\beta = b \ln 10$. In the code,
$m_c$ = `m_ref - delta_m / 2` (the lower edge of the lowest magnitude bin).

The kernel is the product of

- the **productivity** $k_0 e^{a (m - m_c)}$: an event of magnitude $m$
  triggers more aftershocks the larger it is;
- the **time kernel**, an Omori-Utsu law tapered by an exponential with
  time scale $\tau$;
- the **space kernel**, decaying with distance $r$ beyond an aftershock
  zone whose size $d \, e^{\gamma (m - m_c)}$ grows with magnitude.

## Parameters

| Parameter | Meaning | Unit | Default range |
|---|---|---|---|
| `log10_mu` | background rate $\mu$ | per day and km² | (-10, 0) |
| `log10_iota` | rate of the additional background term (`bg_term`) | per day and km² | (-10, 0) |
| `log10_k0` | productivity $k_0$ | | (-20, 10) |
| `a` | productivity exponent | per magnitude unit | (0.01, 20) |
| `log10_c` | Omori $c$ | days | (-8, 0) |
| `omega` | Omori exponent $\omega$ ($p = 1 + \omega$) | | (-0.99, 1) |
| `log10_tau` | taper time $\tau$ | days | (0.01, 12.26) |
| `log10_d` | aftershock zone size $d$ | km² | (-4, 3) |
| `gamma` | growth of the zone with magnitude $\gamma$ | per magnitude unit | (-1, 5) |
| `rho` | spatial decay exponent $\rho$ | | (0.01, 5) |

`alpha = a - rho * gamma` is the effective productivity exponent when the
kernel is integrated over space; the branching ratio is finite only for
$\alpha < \beta$ (see `etas.inversion.branching_ratio`).

For 3D catalogs (`three_dim`), distances are in units of
`space_unit_in_meters` instead of km.

## Inversion

The parameters are estimated with the expectation-maximization (EM)
algorithm (Mizrahi et al., 2021, SRL):

1. **Expectation step.** For each pair of a possible source *i* and target
   *j* (pairs further apart than a multiple of the rupture length of the
   source are ignored), the probability that *i* triggered *j*,
   $P_{ij} = g_{ij} / \lambda(t_j, x_j)$. From these: the expected number
   of background events $\hat n$ and of aftershocks per source
   $\hat l_i$.
2. **Maximization step.** $\mu = \hat n / (A \, T)$ for a region of area $A$
   and a primary window of length $T$; the other parameters maximize the
   expected complete-data log-likelihood.
3. Repeat until the parameters change by less than 0.001 in total, or
   `max_iterations` is reached.

With **varying completeness** (`mc = "var"` or `"positive"`), events below
the local completeness `mc_current` are missing. Their triggering and their
number are accounted for by the factors $1 + \xi$ and $1 + \zeta$
(Mizrahi et al., 2021, JGR, Section 3.1; see
`etas.inversion.responsibility_factor` and
`etas.inversion.observation_factor`).

## Coordinates and units

- Coordinates are **(latitude, longitude)** in degrees, in this order, for
  regions (`shape_coords`) and catalogs.
- Time is in days, distances in km, areas in km².
- `beta` is in natural-log units ($\beta = b \ln 10$).
