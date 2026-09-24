# From Geographic Coverage to Operational Resilience

Official implementation of the paper *"From Geographic Coverage to Operational
Resilience: Data-Driven Medical-Drone Hub Planning for Hajj."*

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Data: ODbL](https://img.shields.io/badge/Data-ODbL%201.0-lightgrey.svg)](DATA_LICENSE.md)

<p align="center">
  <img src="docs/research_framework.png" width="100%"
       alt="Six-stage research framework, from open geospatial data to a medical-drone
            deployment strategy.">
</p>

## About

Medical-supply drone hub planning for Hajj, evaluated across three planning layers on
the same geospatial network built from OpenStreetMap data.

| Layer | Requirement | Result |
|---|---|---|
| Geographic | Complete coverage within 5 km | 3 hubs |
| Operational | + fleet capacity, endurance, 5-min response, 30-min turnaround | 7 hubs, 19 drones |
| Resilient | + two independently feasible hubs for high-priority cells | 10 hubs, 21 drones |

## Setup

```bash
conda env create -f environment.yml
conda activate hajj-drone
```

Then run the notebooks in order. Notebooks 05 and 07 call the solver; the rest build
the data.

## Notebooks

| Notebook | What it does | Output |
|---|---|---|
| `01_medical_infrastructure` | Extracts and cleans medical facilities from OpenStreetMap | 216 medical locations |
| `02_zones_and_validation` | Defines the four analytical Hajj zones and assigns facilities | zone geometries, zoned facilities |
| `03_demand_grids_and_proxy` | Builds the demand grids and the OSM activity proxy `w_i` | grids of 2,192 / 556 / 142 cells |
| `04_candidate_hubs_and_distances` | Selects candidate hubs and computes air distances | 59 hubs, 556 x 59 distance matrix |
| `05_geographic_benchmarks` | Solves p-median, p-center, MCLP and LSCP | `optimization_solutions/`, 108 runs |
| `07_operational_resilient_model` | Solves the operational-resilient MILP | `operational_resilient_solutions_v4/`, 28 runs |

Each stage reads the previous stage's output from `data/`. Running 05 or 07 overwrites
the saved results in `data/model/`.

## The optimization model

Notebook 07 is the main contribution. The model is built with
[Pyomo](https://pyomo.org/) and solved with [HiGHS](https://highs.dev/):

```python
solver = pyo.SolverFactory("highs")
```

### Decision variables

| Variable | Meaning | Domain |
|---|---|---|
| `m.y[j]` | hub `j` is active | Binary |
| `m.n[j]` | drones stationed at hub `j` | Integer, 0 to `MAX_DRONES_PER_HUB` |
| `m.x[i,j]` | packages per hour sent from hub `j` to demand cell `i` | Non-negative integer |

### Constraints

| Name in code | Enforces |
|---|---|
| `m.demand` | every cell receives exactly its demand: `sum_j x[i,j] == q[i]` |
| `m.link` | packages only flow from active hubs: `x[i,j] <= q[i] * y[j]` |
| `m.fleet_lower` / `m.fleet_upper` | an active hub holds 1 to `N_max` drones, an inactive hub none |
| `m.forbidden` | assignment is blocked where the mission is infeasible: `x[i,j] == 0` |
| `m.capacity` | mission-cycle minutes cannot exceed the fleet: `sum_i cycle[i,j] * x[i,j] <= 60 * n[j]` |
| `m.backup` | each high-priority cell reaches at least `r` feasible active hubs |

Mission feasibility is precomputed rather than expressed as constraints. A
demand-hub pair is feasible only if the round trip fits the endurance budget **and**
the one-way flight meets the response target:

```python
RESPONSE_MIN = FIXED_RESPONSE_OVERHEAD_MIN + D / CRUISE_SPEED_KM_PER_MIN

def feasibility_matrix(safe_roundtrip_km, response_target_min):
    return (ROUNDTRIP_KM <= safe_roundtrip_km) & (RESPONSE_MIN <= response_target_min)
```

Infeasible pairs are then fixed to zero through `m.forbidden`, which is equivalent to
imposing the endurance and response constraints but keeps the model smaller.

Note that `m.backup` is added only when `r > 1`. Setting `r = 1` therefore means *no*
backup requirement rather than "at least one feasible hub".

### Objectives

Three objectives are optimized lexicographically, each stage fixing the previous
optimum before the next is solved:

| Stage | Objective in code | Then fixed by |
|---|---|---|
| 1 | `m.objective_hubs` - minimize `sum_j y[j]` | `m.hub_fix` |
| 2 | `m.objective_drones` - minimize `sum_j n[j]` | `m.fleet_fix` |
| 3 | `m.objective_response` - minimize `sum_ij RESPONSE_MIN[i,j] * x[i,j]` | - |

Each stage calls `solver.solve(m)`, deactivates its objective, and adds an equality
constraint pinning the value just found. Response time is therefore minimized only
within the smallest hub count and fleet, so it can never be improved by adding
infrastructure.

### Baseline parameters

Set at the top of notebook 07:

```python
MAX_DRONES_PER_HUB = 3
CRUISE_SPEED_MPS = 15.0
FIXED_RESPONSE_OVERHEAD_MIN = 1.0
CRITICAL_SHARE = 0.20
BASELINE_PACKAGES_PER_HOUR = 30
BASELINE_SAFE_ROUNDTRIP_KM = 20.0
BASELINE_RESPONSE_TARGET_MIN = 5.0
BASELINE_TURNAROUND_MIN = 30.0
BASELINE_REDUNDANCY = 2
```

## Structure

```
data/
  raw/osm/       OpenStreetMap extract the study is built from
  processed/     cleaned facilities, analytical zones, demand grids
  model/         optimization-ready matrices
    optimization_solutions/               geographic benchmark results
    operational_resilient_solutions_v4/   operational and resilient results
notebooks/       the pipeline, in order
```

All inputs and saved results are committed, so the notebooks can be inspected without
re-running the solver.

## Citation

If you use this code, please cite our paper:

```bibtex
@article{alhindawi2026hajj,
  title={From Geographic Coverage to Operational Resilience: Data-Driven
         Medical-Drone Hub Planning for Hajj},
  author={Al-Hindawi, Firas and Alhomaidhi, Esam},
  note={Manuscript in preparation},
  year={2026}
}
```

The paper is in preparation. This entry and [CITATION.cff](CITATION.cff) will be
updated once it is published.

## License

Code is released under the [MIT License](LICENSE). Data products derived from
OpenStreetMap are © OpenStreetMap contributors, available under the
[ODbL 1.0](DATA_LICENSE.md).

## Contact

Firas Al-Hindawi, Industrial and Systems Engineering Department, King Fahd University
of Petroleum and Minerals — <firas.hindawi@kfupm.edu.sa>
