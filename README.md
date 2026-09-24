<div align="center">

# Medical-Drone Hub Planning for Hajj

### Geographic Coverage, Fleet Capacity, and Backup Accessibility

Official implementation

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Data: ODbL](https://img.shields.io/badge/Data-ODbL%201.0-lightgrey.svg)](DATA_LICENSE.md)
[![Paper: in preparation](https://img.shields.io/badge/paper-in%20preparation-orange.svg)](#citation)

</div>

---

## Graphical abstract

<p align="center">
  <img src="docs/research_framework.png" width="100%"
       alt="Six-stage research framework: define the study area and analytical Hajj
            zones, identify medical infrastructure and candidate hubs, construct the
            OSM-informed spatial demand proxy, build the demand-hub geospatial network,
            run progressive network optimization and sensitivity analysis, and derive
            the medical-drone deployment strategy.">
</p>

---

## Summary

Severe crowding and road congestion during Hajj can delay urgent medical-supply
movement, and drone delivery has recently moved from a concept to an operational option
in the holy sites. Planning such a network is difficult because fine-grained demand data
are not publicly available.

This study builds a reproducible geospatial and optimization framework for drone-hub
planning under that data scarcity. Medical infrastructure extracted from OpenStreetMap
is combined with analytical Hajj zones, multi-resolution demand grids, an
activity-based demand proxy, candidate hubs drawn from existing medical facilities, and
a demand-to-hub air-distance matrix.

The same network is then analysed under three planning scenarios. Four
classical facility-location models establish a geographic benchmark. A mixed-integer
linear program then adds operational planning requirements: finite
drone fleets, return-to-origin missions, endurance, a response-time target, and
turnaround between flights. A final layer requires backup accessibility for
high-priority areas.

### Results

| Planning layer | Requirement added | Minimum network |
|---|---|:---:|
| **Geographic** | Complete coverage within 5 km | **3 hubs** |
| **Operational** | Fleet capacity, endurance, 5-min response, 30-min turnaround | **7 hubs, 19 drones** |
| **Backup coverage** | Two feasible active hubs for high-priority cells | **10 hubs, 21 drones** |

Three findings follow:

- **Fleet capacity rules out the three-hub network under the operational assumptions.**
  Nine drones provide 540 drone-minutes per hour: 60% of the turnaround-only
  requirement and 57.3% of the lower bound including flight. The 3 / 7 / 10
  comparison uses different coverage scopes and is a progressive scenario comparison.
- **Turnaround drives fleet requirements over the tested ranges.** Halving turnaround
  reduces the backup-coverage fleet from 21 to 12 drones. Increasing turnaround to
  45 minutes also increases mean delivery distance and modeled delivery time.
- **Backup accessibility adds geographic preparedness.** The nonredundant case imposes
  no critical-area coverage requirement. Introducing two-hub accessibility for all
  112 critical cells raises the network from seven hubs and 19 drones to ten hubs
  and 21 drones. This includes first coverage for five previously uncovered cells.

Delivery times assume an available drone and exclude queueing. Backup accessibility
counts reachable active hubs; post-failure capacity and reassignment are not modeled.

---

## Repository structure

```
data/
  raw/osm/        OpenStreetMap extract the study is built from
  processed/      cleaned facilities, analytical zones, demand grids
  model/          optimization-ready matrices
    optimization_solutions/               geographic benchmark results
    operational_resilient_solutions_v4/   operational and resilient results
notebooks/        the analysis pipeline, in order
```

Inputs and saved results are both committed, so the notebooks can be read and inspected
without re-running the solver.

---

## Notebooks

Run in order. Each stage reads the previous stage's output from `data/`.

| # | Notebook | What it does | Output |
|:---:|---|---|---|
| 01 | `medical_infrastructure` | Extracts and cleans medical facilities from OpenStreetMap | 216 medical locations |
| 02 | `zones_and_validation` | Defines the four analytical Hajj zones and assigns facilities | zone geometries |
| 03 | `demand_grids_and_proxy` | Builds demand grids and the OSM activity proxy | grids of 2,192 / 556 / 142 cells |
| 04 | `candidate_hubs_and_distances` | Selects candidate hubs and computes air distances | 59 hubs, 556 × 59 matrix |
| 05 | `geographic_benchmarks` | Solves p-median, p-center, MCLP and LSCP | 108 runs |
| 07 | `operational_resilient_model` | Solves the operational-resilient MILP | 28 runs |

Notebooks **05** and **07** call the solver. The model is built with
[Pyomo](https://pyomo.org/) and solved with [HiGHS](https://highs.dev/). Notebook 07
decides which hubs are active, how many drones each holds, and how packages are
assigned, optimizing three objectives in order: fewest hubs, then smallest fleet, then
fastest response. Running either notebook overwrites the saved results in `data/model/`.

---

## Getting started

```bash
git clone https://github.com/Hindawi91/hajj-medical-drone-network.git
cd hajj-medical-drone-network
conda env create -f environment.yml
conda activate hajj-drone
jupyter lab
```

---

## Citation

If you use this code, please cite our paper:

```bibtex
@article{alhindawi2026hajj,
  title={Medical-Drone Hub Planning for Hajj: Integrating Geographic Coverage, Fleet Capacity, and Backup Accessibility},
  author={Al-Hindawi, Firas and Alhomaidhi, Esam},
  note={Manuscript in preparation},
  year={2026}
}
```

The paper is in preparation. This entry and [CITATION.cff](CITATION.cff) will be updated
once it is published.

---

## License

Code is released under the [MIT License](LICENSE). Data products derived from
OpenStreetMap are © OpenStreetMap contributors, available under the
[ODbL 1.0](DATA_LICENSE.md).

## Contact

**Firas Al-Hindawi** — <firas.hindawi@kfupm.edu.sa>
Industrial and Systems Engineering Department, King Fahd University of Petroleum and
Minerals, Dhahran, Saudi Arabia.
