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

The geographic benchmarks use p-median, p-center, MCLP and LSCP. The operational and
resilient layers use a mixed-integer linear program that jointly decides active hubs,
the drone fleet at each hub, and package assignments, optimized lexicographically:
hubs, then fleet, then response time.

## Installation

```bash
conda env create -f environment.yml
conda activate hajj-drone
```

A MILP solver is only needed to re-solve the models. Everything else runs from the
saved checkpoints.

## Usage

```bash
python src/verify_results.py        # check the results against the paper
python src/validate_solutions.py    # check the solutions satisfy the model constraints
python src/gen_geographic_benchmark.py   # Section 4.1 figures
python src/gen_operational_figures.py    # Section 4.2-4.5 figures
```

To re-solve the optimization models, run `notebooks/05_geographic_benchmarks.ipynb`
and `notebooks/07_operational_resilient_model.ipynb`. This overwrites the checkpoints
in `data/model/`. See [docs/REPRODUCTION.md](docs/REPRODUCTION.md).

## Structure

```
data/
  raw/osm/            OpenStreetMap extract the study is built from
  processed/          cleaned facilities, analytical Hajj zones, demand grids
  model/              optimization-ready matrices
    optimization_solutions/              geographic benchmark results
    operational_resilient_solutions_v4/  operational and resilient results

notebooks/            the analysis pipeline, in order
  01_medical_infrastructure.ipynb      216 medical locations
  02_zones_and_validation.ipynb        four analytical Hajj zones
  03_demand_grids_and_proxy.ipynb      demand grids and OSM activity proxy
  04_candidate_hubs_and_distances.ipynb  59 candidate hubs, 556x59 distances
  05_geographic_benchmarks.ipynb       108 runs, needs a solver
  06_data_figures.ipynb                data-description figures
  07_operational_resilient_model.ipynb 28 runs, needs a solver
  08_operational_results.ipynb         operational result figures
  09_geographic_paper_figures.ipynb    generated from src/gen_geographic_benchmark.py
  10_operational_paper_figures.ipynb   generated from src/gen_operational_figures.py

src/
  verify_results.py             reported values vs the checkpoints
  validate_solutions.py         solutions vs the model constraints
  gen_geographic_benchmark.py   Section 4.1 figures, maps and tables
  gen_operational_figures.py    Section 4.2-4.5 figures and tables

outputs/              figures, interactive maps, result tables
paper/figures/        figures as used in the paper
docs/REPRODUCTION.md  step-by-step reproduction guide
```

All inputs and solver checkpoints are committed, so the results can be reproduced from
a clone with no downloads. Notebooks 09 and 10 are generated from the scripts in
`src/`; edit the scripts rather than the notebooks.

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
