# The model

## Notation

A catalog is a list of earthquakes, called events $e_1, \dots, e_N$,
ordered by time. Each event $e_i$ has an occurrence time $t_i$ (in days), a
location $x_i$ (latitude and longitude, in degrees), and a magnitude $m_i$.
The examples on this page use the parameters with which the example catalog
`input_data/example_catalog.csv` was simulated
(`config/simulate_catalog_config.json`).

## Conditional intensity

The ETAS model describes the rate at which earthquakes occur, given the
earthquakes that have already happened. Each event can trigger aftershocks,
which in turn can trigger their own aftershocks, and events that are not
triggered by any other event are called background events. The conditional
intensity, that is, the expected number of events per day and km² at time
$t$ and location $x$, is

$$
\lambda(t, x) = \mu + \sum_{i: t_i < t} g(m_i, t - t_i, r_i^2(x)),
$$

where

- $\mu$ is the rate of background events, in events per day and km²,
  assumed constant in time and space;
- the sum goes over all events $e_i$ that occurred before $t$;
- $g$ is the triggering kernel (defined below), that is, the rate of
  aftershocks that event $e_i$ contributes at time $t$ and location $x$;
- $t - t_i$ is the time (in days) since event $e_i$;
- $r_i(x)$ is the distance (in km) between the location $x_i$ of event $e_i$
  and $x$.

Only events with magnitude at or above the reference magnitude $m_c$ are
modeled, both as triggering events and as aftershocks.

## Triggering kernel

The triggering kernel gives the rate of direct aftershocks of an event of
magnitude $m$, at a time delay $t$ (days) and a distance $r$ (km) after it.
It is the product of a productivity term, a time kernel and a space kernel,

$$
g(m, t, r^2) = k_0 \, e^{a (m - m_c)}
    \cdot \frac{e^{-t / \tau}}{(t + c)^{1 + \omega}}
    \cdot \frac{1}{\left(r^2 + d \, e^{\gamma (m - m_c)}\right)^{1 + \rho}},
$$

where

- $m_c$ is the reference magnitude, in the code `m_ref - delta_m / 2`, the
  lower edge of the lowest magnitude bin;
- $k_0$ is the productivity of an event of magnitude $m_c$ and $a$ the
  rate at which productivity increases with magnitude (per magnitude unit);
- $c$ (days), $\omega$ and $\tau$ (days) are the parameters of the time
  kernel: an Omori-Utsu law with offset $c$ and exponent $1 + \omega$,
  tapered by an exponential with time scale $\tau$;
- $d$ (km²), $\gamma$ and $\rho$ are the parameters of the space kernel:
  the size of the aftershock zone of an event of magnitude $m_c$ is $d$, it
  grows with magnitude at rate $\gamma$ (per magnitude unit), and $\rho$
  sets how fast the rate decays with distance beyond it.

In words, the three factors mean the following.

1. **Productivity**, $k_0 e^{a (m - m_c)}$: larger events trigger more
   aftershocks. With $a = 1.69$, an event one magnitude unit larger than
   another has an $e^{1.69} \approx 5.4$ times higher rate of direct
   aftershocks near its location. Its total number of direct aftershocks,
   integrated over space, grows more slowly (see the branching ratio
   below).
2. **Time kernel**: the aftershock rate decays roughly as $1/t$ (for
   $\omega$ close to 0) after a short delay $c$, and much faster after
   $\tau$. With $\log_{10} c = -2.95$ and $\log_{10} \tau = 3.99$, the decay
   starts after about 1.6 minutes, and the taper sets in after about 27
   years.
3. **Space kernel**: the rate is roughly constant within the aftershock zone
   of size $d \, e^{\gamma (m - m_c)}$ (km²) and decays with distance outside
   of it. With $\log_{10} d = -0.35$ and $\gamma = 1.22$, an event two
   magnitude units above $m_c$ has an aftershock zone of about 5 km², that
   is, of about 2.3 km in radius.

## Magnitudes

Magnitudes at or above $m_c$ follow the Gutenberg-Richter law, with
probability density

$$
f(m) = \beta \, e^{-\beta (m - m_c)}, \quad m \geq m_c,
$$

where $\beta = b \ln 10$ is the Gutenberg-Richter parameter in natural-log
units and $b$ is the usual b-value. For $b = 1$, $\beta \approx 2.30$, and
each magnitude unit has ten times fewer events than the one below it. All
`beta` values in the code are in these natural-log units.

## Parameters

| Parameter | Symbol | Meaning | Unit | Default range |
|---|---|---|---|---|
| `log10_mu` | $\log_{10} \mu$ | background rate | per day and km² | (-10, 0) |
| `log10_iota` | $\log_{10} \iota$ | rate of the additional background term (`bg_term`) | per day and km² | (-10, 0) |
| `log10_k0` | $\log_{10} k_0$ | productivity of an event of magnitude $m_c$ | | (-20, 10) |
| `a` | $a$ | increase of productivity with magnitude | per magnitude unit | (0.01, 20) |
| `log10_c` | $\log_{10} c$ | offset of the Omori-Utsu law | days | (-8, 0) |
| `omega` | $\omega$ | exponent of the Omori-Utsu law minus 1 ($p = 1 + \omega$) | | (-0.99, 1) |
| `log10_tau` | $\log_{10} \tau$ | time scale of the taper | days | (0.01, 12.26) |
| `log10_d` | $\log_{10} d$ | size of the aftershock zone of an event of magnitude $m_c$ | km² | (-4, 3) |
| `gamma` | $\gamma$ | increase of the aftershock zone with magnitude | per magnitude unit | (-1, 5) |
| `rho` | $\rho$ | decay of the rate with distance | | (0.01, 5) |

## Branching ratio

The branching ratio $\eta$ is the expected number of direct aftershocks of
an event, averaged over the Gutenberg-Richter distribution of magnitudes and
integrated over all space and time. Integrating the space kernel over the
plane gives a factor $e^{-\rho \gamma (m - m_c)}$, so that the number of
direct aftershocks grows with magnitude as $e^{\alpha (m - m_c)}$, with the
effective productivity exponent

$$
\alpha = a - \rho \gamma .
$$

The branching ratio is finite only if $\alpha < \beta$, that is, if the
number of aftershocks grows more slowly with magnitude than the number of
events decreases. For $\eta < 1$, every sequence eventually dies out, and
about a fraction $\eta$ of all events are aftershocks. With the example
parameters, $\alpha = 1.69 - 0.51 \cdot 1.22 \approx 1.07$, below
$\beta \approx 2.30$, and $\eta \approx 0.90$: about 90% of the events in
the example catalog are aftershocks. See `etas.inversion.branching_ratio`.

## Inversion

The parameters are estimated with the expectation-maximization (EM)
algorithm (Mizrahi et al., 2021, SRL), which alternates between two steps
until the parameters no longer change.

1. **Expectation step.** For each pair of a possible triggering event $e_i$
   and a possible aftershock $e_j$, the probability $p_{ij}$ that $e_j$ was
   triggered by $e_i$ is

    $$
    p_{ij} = \frac{g(m_i, t_j - t_i, r_{ij}^2)}{\lambda(t_j, x_j)},
    $$

    where $r_{ij}$ is the distance (km) between $e_i$ and $e_j$, and
    $\lambda(t_j, x_j)$ the conditional intensity at the time and location
    of $e_j$. The probability that $e_j$ is a background event is
    $p_j^{\mathrm{bg}} = \mu / \lambda(t_j, x_j)$, so that
    $p_j^{\mathrm{bg}} + \sum_i p_{ij} = 1$. Summing these probabilities
    gives the expected number of background events,
    $\hat n = \sum_j p_j^{\mathrm{bg}}$, and the expected number of direct
    aftershocks of each event $e_i$, $\hat l_i = \sum_j p_{ij}$. Pairs
    further apart than a multiple (`coppersmith_multiplier`) of the
    rupture length of $e_i$ are treated as unrelated.
2. **Maximization step.** The background rate is

    $$
    \hat \mu = \frac{\hat n}{A \, T},
    $$

    where $A$ is the area of the region (km²) and $T$ the length of the
    primary time window (days). For example, 146 expected background events
    in ten years ($T = 3652$ days) in a region of 959,823 km² give
    $\hat \mu \approx 4.2 \cdot 10^{-8}$ events per day and km², that is,
    $\log_{10} \hat \mu \approx -7.38$. The other parameters maximize the
    expected complete-data log-likelihood, given the probabilities
    $p_{ij}$.

The algorithm stops when the parameters change by less than 0.001 in total
from one iteration to the next, or after `max_iterations` iterations.

## Varying completeness

When the magnitude of completeness varies in space and time
(`mc = "var"` or `"positive"`), each event $e_i$ has its own completeness
$m_{c,i}$ (the column `mc_current`): events below $m_{c,i}$ at the time and
location of $e_i$ may be missing from the catalog. The reference magnitude
$m_{\mathrm{ref}}$ is the smallest completeness. Two factors account for
the missing events (Mizrahi et al., 2021, JGR, Section 3.1).

1. Each observed event $e_j$ stands for

    $$
    1 + \zeta_j = e^{\beta (m_{c,j} - m_{\mathrm{ref}})}
    $$

    events above $m_{\mathrm{ref}}$, including the unobserved ones. With
    $\beta = 2.30$ and $m_{c,j} - m_{\mathrm{ref}} = 0.5$, each observed
    event stands for about 3.2 events.
2. The triggering by an observed event $e_i$ is multiplied by

    $$
    1 + \xi_i = e^{(\beta - \alpha)(m_{c,i} - m_{\mathrm{ref}})},
    $$

    to include the triggering by the unobserved events with magnitudes
    between $m_{\mathrm{ref}}$ and $m_{c,i}$, where $\alpha = a - \rho
    \gamma$ as above. With $\alpha = 1.0$, the same completeness difference
    gives a factor of about 1.9.

See `etas.inversion.observation_factor` and
`etas.inversion.responsibility_factor`.

## Coordinates and units

- Coordinates are **(latitude, longitude)** in degrees, in this order, for
  regions (`shape_coords`) and catalogs.
- Time is in days, distances in km, areas in km². For 3D catalogs
  (`three_dim`), distances are in units of `space_unit_in_meters`.
- `beta` is in natural-log units, $\beta = b \ln 10$.
