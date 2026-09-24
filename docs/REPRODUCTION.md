# Reproduction guide

Three levels of reproduction, from fastest to slowest. Pick the one that matches what
you need.

| Level | What it does | Time | Needs a solver |
|---|---|---|---|
| **1a. Verify** | Re-derive every reported number from the checkpoints | seconds | no |
| **1b. Validate** | Prove the solutions correct from first principles | seconds | no |
| **2. Regenerate figures** | Rebuild all manuscript figures, maps and tables | ~2 min | no |
| **3. Re-solve** | Re-run the optimization models from raw data | hours | yes |

---

## 0. Environment

```bash
conda env create -f environment.yml
conda activate hajj-drone
python -c "import pandas, geopandas, matplotlib, folium, contextily; print('ok')"
```

Confirm the solver is available only if you intend to do level 3:

```bash
python -c "import pyomo.environ as pyo, highspy; print('solver ok')"
```

### Windows note

If `python` on your PATH resolves to the Microsoft Store stub, call your interpreter by
absolute path, for example:

```powershell
& "$env:LOCALAPPDATA\anaconda3\envs\hajj-drone\python.exe" src\verify_results.py
```

---

## 1. Verify the reported results

```bash
python src/verify_results.py
```

This reads only `data/` and checks 147 quantities against the values printed in the
paper. It is the fastest way to confirm a clean clone is intact. The script is grouped
by manuscript section, so a failure tells you which result diverged.

What it covers:

- **Section 3.2** — 216 medical locations; demand grids of 2,192 / 556 / 142 cells;
  59 candidate hubs split 53 / 5 / 1; the 556 × 59 distance matrix; 112 high-priority cells.
- **Section 3.5.1** — that the allocation yields exactly *Q* active locations with
  *q_i* = 1 each, that the active set is the top-*Q* by weight, that the sets are nested,
  and that no tie straddles a cutoff.
- **Section 4.1** — all 108 runs by model; every cell of the benchmark table; the LSCP
  result at each service range; the identity of the three benchmark hubs.
- **Section 4.2** — the feasibility screens, the 13,183 / 0 asymmetry between endurance
  and response, the fleet lower bound of 16 drones and 6 hubs, and the fixed-*p*
  feasibility frontier.
- **Section 4.3** — the resilience premium, backup coverage of 103 / 112 cells, the
  single-drone hub counts, and the non-nestedness of the three layers.
- **Sections 4.4–4.5** — all ten sensitivity scenarios, the influence spans, the zone
  distribution, and the two preparedness-only hubs.

Exit status is 0 on success and 1 on any mismatch.

## 1b. Validate the solutions independently

```bash
python src/validate_solutions.py
```

`verify_results.py` reads the solver's own output and compares it to the paper, so on
its own it cannot show the optimization is right. This script closes that gap. It takes
the reported *solutions* and checks them from first principles against the raw distance
matrix and the model constraints, never trusting a reported objective value.

It establishes, with no solver:

- **Three hubs is provably the minimum** for complete 5-km coverage. All 1,711 hub
  pairs are enumerated; the best covers 400 of 556 cells, and the reported three-hub
  set covers all 556.
- **Complete coverage at 2.5 km is structurally impossible**: 47 cells have no
  candidate facility within that distance.
- **Both operational networks satisfy every MILP constraint** - demand satisfaction,
  endurance, response time, per-hub drone-minutes, the three-drone cap and
  critical-area redundancy - and their reported mean and maximum response times
  recompute exactly from the assignments.
- **The three-hub benchmark fails on capacity alone**: nine drones supply 540
  drone-minutes per hour against 900 needed for turnaround, whatever the siting.

What it cannot establish is *optimality* of the 7- and 10-hub networks; that would mean
ruling out all 45 million six-hub subsets. Optimality rests on the solver, which is
level 3 below.

A note on the model's semantics that the script documents: the backup constraint is
added only when `r > 1`. Setting `r = 1` therefore means *no* backup requirement rather
than "at least one feasible hub", which is why the nonredundant network leaves some
high-priority cells with no feasible active hub.

---

## 2. Regenerate the figures

```bash
make figures
```

or equivalently:

```bash
python src/gen_geographic_benchmark.py
python src/gen_operational_figures.py
```

| Script | Produces | Manuscript |
|---|---|---|
| `gen_geographic_benchmark.py` | benchmark performance plot, analytical 3-hub map, interactive Folium map, selected-hub table, composite figure | Section 4.1 |
| `gen_operational_figures.py` | progressive infrastructure, resilience frontier, consolidated sensitivity, resilient network layout, hub table | Sections 4.2–4.5 |

Outputs land in `outputs/figures/`, `outputs/maps/`, `outputs/reports/`, and manuscript
copies in `paper/figures/`.

Both scripts assert their plotted values against the checkpoints as they run, so a
figure cannot silently drift from the numbers in the text.

### Basemap tiles

The composite figure fetches tiles from Esri. Two providers are deliberately avoided and
you should not substitute them:

- **CartoDB** now requires an API key and stamps `API KEY REQUIRED` across every tile.
- **OpenStreetMap Mapnik** blocks the default `contextily` user agent and returns a 403
  notice **as an image**, so nothing raises and a broken figure ships silently.

Without network access the script completes with a plain background.

---

## 3. Re-solve the optimization models

Only necessary if you change model assumptions or input data. **Running the solver
notebooks overwrites the checkpoints in `data/model/` that everything else depends on.**
Commit or back up first.

### Pipeline order

Each stage consumes the previous stage's output.

| # | Notebook | Produces | Solver |
|---|---|---|---|
| 01 | `01_medical_infrastructure.ipynb` | 216 cleaned medical locations, facility distance matrix | no |
| 02 | `02_zones_and_validation.ipynb` | four analytical Hajj zones, zoned facilities | no |
| 03 | `03_demand_grids_and_proxy.ipynb` | demand grids at 250 / 500 / 1000 m with the OSM proxy weights | no |
| 04 | `04_candidate_hubs_and_distances.ipynb` | 59 candidate hubs, 556 × 59 distance matrix, coverage tables | no |
| 05 | `05_geographic_benchmarks.ipynb` | `optimization_solutions/` — 108 runs | **yes** |
| 06 | `06_data_figures.ipynb` | data-description figures | no |
| 07 | `07_operational_resilient_model.ipynb` | `operational_resilient_solutions_v4/` — 28 runs | **yes** |
| 08 | `08_operational_results.ipynb` | exploratory operational figures | no |
| 09 | `09_geographic_paper_figures.ipynb` | Section 4.1 figures (mirrors `src/gen_geographic_benchmark.py`) | no |
| 10 | `10_operational_paper_figures.ipynb` | Sections 4.2–4.5 figures (mirrors `src/gen_operational_figures.py`) | no |

Approximate solve times on a modern laptop: notebook 05 about 1–2 hours for the 108
runs; notebook 07 about 20–30 minutes for the 16 fixed-*p*, 2 baseline and 10
sensitivity runs.

### What the solver notebooks run

**Notebook 05 — geographic benchmarks.** 108 runs decomposing as:

- 16 p-median, unrestricted assignment (8 values of *p* × 2 weightings)
- 16 p-median, restricted to a 5 km service range
- 8 p-center
- 64 MCLP (8 *p* × 4 service ranges × 2 weightings)
- 4 LSCP (one per service range)

> The **range-restricted p-median variant is a second experiment** whose results are not
> reported in the paper. When reading `optimization_run_summary_v1.csv`, select the
> unrestricted variant with `range_km.isna()` — never by row order. At *p* = 3 with proxy
> weights the two variants give different solutions.

**Notebook 07 — operational-resilient model.** 16 fixed-*p* diagnostic runs (*p* = 5…12
at *r* = 1 and *r* = 2), 2 endogenous baseline runs (*r* = 1 and *r* = 2), and 10
one-factor-at-a-time sensitivity scenarios.

### After re-solving

```bash
python src/verify_results.py
```

If you changed assumptions deliberately, this will fail — that is the point. It tells you
exactly which reported numbers your change moved.

---

## Rebuilding the OSM layer from scratch

`data/raw/osm/medical_emergency_raw.gpkg` is the extract the reported analysis used.
Notebook 01 can re-query OpenStreetMap instead, but **a fresh extract will not reproduce
the reported numbers**: OSM is continuously edited, so facility counts and activity
features drift. The committed extract is the version of record.

If you do re-query, expect the 216-facility count and every downstream number to change,
and re-run the whole pipeline from notebook 01.

---

## Troubleshooting

**`FileNotFoundError` on a `data/model/...` path.** You are running from the wrong
directory, or the clone is incomplete. The scripts resolve paths from their own location,
so `python src/verify_results.py` works from the repository root. Check
`data/model/optimization_solutions/` contains six CSV files.

**`verify_results.py` fails after you edited a notebook.** Expected if you re-solved with
changed assumptions. The failure lines name each quantity that moved.

**Figures look different from the paper.** Most likely the basemap fell back to a plain
background because tiles were unreachable. The analytical panels do not use tiles and
should match exactly.

**Arabic facility names render as boxes.** Some OSM records have no `name:en` tag. The
reported labels come from `data/processed/hub_name_en_overrides_v1.csv`, which records
each author translation and its justification. The figure code reads that table; it does
not hardcode names.

**Solver not found in notebook 05 or 07.** Install the solver stack with
`conda env create -f environment.yml`, which includes Pyomo and HiGHS. Levels 1 and 2
need no solver at all.

**Windows: `FileNotFoundError` on a file that `dir` clearly shows.** You have hit the
260-character `MAX_PATH` limit. The repository's own paths are short, but a deep clone
location plus a long checkpoint filename can cross the limit, and the symptom is
confusing: directory listings show the file while opening it fails. Either clone
somewhere shallow (`C:\hajj-drone`), or enable long paths:

```powershell
# Administrator PowerShell, then restart the shell
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' `
  -Name LongPathsEnabled -Value 1 -Type DWord
git config --system core.longpaths true
```
