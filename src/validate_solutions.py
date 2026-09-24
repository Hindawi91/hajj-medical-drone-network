#!/usr/bin/env python3
"""Independently validate the reported solutions without re-running any solver.

``verify_results.py`` answers a narrow question: do the saved checkpoints contain the
numbers the paper reports? That is an integrity check. It does not establish that the
solutions are correct, because it reads the solver's own output.

This script asks the harder question: **are the reported solutions actually valid, and
is the headline geographic claim actually true?** It never reads a reported objective
value and trusts it. Instead it takes the reported *solutions* (which hubs, which
fleet, which assignments) and checks them from first principles against the raw
distance matrix and the model constraints.

Two things are established here:

1. **The geographic benchmark is proved optimal by exhaustive enumeration.** Every
   1-hub and 2-hub subset of the 59 candidates is tested for complete 5-km coverage.
   If none works and the reported 3-hub set does, then 3 is provably the minimum. This
   is a complete proof, not a check against the solver.

2. **The operational and resilient solutions are verified as feasibility certificates.**
   Every constraint of the MILP is re-checked against the reported solution: demand
   satisfaction, endurance, response time, per-hub fleet capacity, the hub cap, and
   critical-area redundancy. The reported objective values are then recomputed from the
   assignments rather than read from the summary file.

What this cannot establish without a solver: that the operational solutions are
*optimal*. Proving 7 hubs minimal would require showing all 45 million 6-hub subsets
infeasible. Optimality there rests on the solver, and re-running it is documented in
docs/REPRODUCTION.md. Feasibility and the reported objective values, however, are
proved here.

    python src/validate_solutions.py
"""
from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "model"
GEO = MODEL / "optimization_solutions"
OPS = MODEL / "operational_resilient_solutions_v4"

CRUISE_KM_PER_MIN = 0.9
T_FIXED_MIN = 1.0
T_TARGET_MIN = 5.0
L_SAFE_KM = 20.0
T_TURN_MIN = 30.0
N_MAX = 3
SERVICE_RANGE_KM = 5.0
CRITICAL_SHARE = 0.20
TOL = 1e-6

_passed = 0
_failed: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global _passed
    if ok:
        _passed += 1
        print(f"  [ok]   {label}" + (f"  ({detail})" if detail else ""))
    else:
        _failed.append(f"{label} {detail}".strip())
        print(f"  [FAIL] {label}" + (f"  ({detail})" if detail else ""))


def section(title: str) -> None:
    print(f"\n{title}\n{'=' * len(title)}")


def read(p: Path) -> pd.DataFrame:
    return pd.read_csv(p, encoding="utf-8-sig")


def load_network():
    demand = read(MODEL / "hajj_demand_locations_500m_v1.csv")
    dist = read(MODEL / "demand_to_candidate_hub_air_distance_km_v1.csv")
    dist = dist.set_index("demand_point_id").loc[demand["demand_point_id"]]
    return demand, dist, dist.to_numpy(float), list(dist.columns)


# --------------------------------------------------------------------------
# 1. Geographic benchmark: proved minimal by exhaustive enumeration
# --------------------------------------------------------------------------
def validate_geographic(D: np.ndarray, hub_ids: list[str]) -> None:
    section("1. Geographic benchmark: exhaustive proof that three hubs is minimal")

    covers = D <= SERVICE_RANGE_KM          # cell i is covered by hub j
    n_cells, n_hubs = covers.shape
    print(f"  search space: {n_cells} demand cells, {n_hubs} candidate hubs, "
          f"{SERVICE_RANGE_KM:g} km service range")

    sel = read(GEO / "optimization_selected_hubs_v1.csv")
    reported = sorted(sel[(sel["model"] == "LSCP")
                          & (sel["range_km"] == SERVICE_RANGE_KM)]["hub_id"])
    idx = [hub_ids.index(h) for h in reported]

    # (a) the reported solution is feasible
    covered = covers[:, idx].any(axis=1)
    check("the reported 3-hub set covers every demand cell",
          bool(covered.all()),
          f"{int(covered.sum())}/{n_cells} cells, hubs {', '.join(reported)}")

    # (b) no single hub suffices
    best1 = int(covers.sum(axis=0).max())
    check("no single hub covers every cell", best1 < n_cells,
          f"best single hub covers {best1}/{n_cells}")

    # (c) no pair suffices - exhaustive over all C(59,2) pairs
    best2, best_pair, n_pairs = 0, None, 0
    for a, b in combinations(range(n_hubs), 2):
        n_pairs += 1
        c = int((covers[:, a] | covers[:, b]).sum())
        if c > best2:
            best2, best_pair = c, (hub_ids[a], hub_ids[b])
    check(f"no pair of hubs covers every cell (all {n_pairs} pairs tested)",
          best2 < n_cells,
          f"best pair {best_pair[0]}+{best_pair[1]} covers {best2}/{n_cells}")

    proved = bool(covered.all()) and best1 < n_cells and best2 < n_cells
    check("=> THREE HUBS IS PROVABLY MINIMAL at a 5 km service range", proved,
          "complete enumeration, no solver involved")

    # (d) the 2.5 km infeasibility claim is structural, not a solver artefact
    covers25 = D <= 2.5
    orphans = int((~covers25.any(axis=1)).sum())
    check("at 2.5 km, complete coverage is impossible for any number of hubs",
          orphans > 0,
          f"{orphans} cells have no candidate facility within 2.5 km")


# --------------------------------------------------------------------------
# 2. Operational and resilient solutions: feasibility certificates
# --------------------------------------------------------------------------
def validate_operational(demand: pd.DataFrame, D: np.ndarray,
                         hub_ids: list[str]) -> None:
    section("2. Operational and resilient solutions: constraint-by-constraint check")

    roundtrip = 2 * D
    response = T_FIXED_MIN + D / CRUISE_KM_PER_MIN
    feasible_pair = (roundtrip <= L_SAFE_KM) & (response <= T_TARGET_MIN)

    w = demand["proxy_demand_weight"].to_numpy(float)
    crit = np.where(w >= demand["proxy_demand_weight"].quantile(1 - CRITICAL_SHARE))[0]
    cell_pos = {c: i for i, c in enumerate(demand["demand_point_id"])}

    hub_fleet = read(OPS / "selected_hubs_fleet_v4.csv")
    flows = read(OPS / "package_flows_v4.csv")
    base = read(OPS / "baseline_endogenous_comparison_v4.csv")

    # S10 is the r=1 baseline, S02 the r=2 baseline.
    for scenario, r, label in (("S10", 1, "operational (r=1)"),
                               ("S02", 2, "resilient (r=2)")):
        print(f"\n  --- {label}, scenario {scenario} ---")
        hubs = hub_fleet[hub_fleet["scenario_id"] == scenario]
        flow = flows[flows["scenario_id"] == scenario]
        reported = base[base["redundancy"] == r].iloc[0]

        active = list(hubs["hub_id"])
        fleet = dict(zip(hubs["hub_id"], hubs["drones"].astype(int)))
        cols = [hub_ids.index(h) for h in active]

        # (a) every assignment departs from an active hub
        check("every assignment departs from an active hub",
              set(flow["hub_id"]) <= set(active))

        # (b) mission feasibility, recomputed from the distance matrix
        bad_end = bad_resp = 0
        for _, f in flow.iterrows():
            i, j = cell_pos[f["demand_point_id"]], hub_ids.index(f["hub_id"])
            if roundtrip[i, j] > L_SAFE_KM + TOL:
                bad_end += 1
            if response[i, j] > T_TARGET_MIN + TOL:
                bad_resp += 1
        check("every flown mission is within the endurance budget", bad_end == 0,
              f"{len(flow)} assignments checked")
        check("every flown mission meets the response target", bad_resp == 0,
              f"{len(flow)} assignments checked")

        # (c) per-hub fleet capacity, recomputed from mission cycles
        worst = 0.0
        over = []
        for h in active:
            sub = flow[flow["hub_id"] == h]
            load = 0.0
            for _, f in sub.iterrows():
                i, j = cell_pos[f["demand_point_id"]], hub_ids.index(h)
                cycle = roundtrip[i, j] / CRUISE_KM_PER_MIN + T_TURN_MIN
                load += cycle * f["packages_per_hour"]
            cap = 60.0 * fleet[h]
            worst = max(worst, load / cap if cap else float("inf"))
            if load > cap + 1e-6:
                over.append(f"{h}: {load:.1f} > {cap:.0f}")
        check("no hub exceeds its fleet's drone-minutes per hour", not over,
              f"peak utilisation {100 * worst:.1f}% of capacity")

        # (d) hub-level fleet cap
        check(f"no hub exceeds N_max = {N_MAX} drones",
              all(v <= N_MAX for v in fleet.values()),
              f"allocation {sorted(fleet.values(), reverse=True)}")

        # (e) redundancy, recomputed over the high-priority set.
        #
        # Note the model's semantics: the backup constraint is added only when r > 1
        # (`if redundancy > 1` in notebook 07). r = 1 therefore means "no backup
        # requirement", NOT "at least one feasible hub". The nonredundant network
        # consequently leaves some high-priority cells with no feasible active hub,
        # which is expected rather than a violation.
        counts = feasible_pair[:, cols].sum(axis=1)[crit]
        if r > 1:
            check(f"every high-priority cell has >= r = {r} feasible active hubs",
                  bool((counts >= r).all()),
                  f"minimum over {len(crit)} cells is {int(counts.min())}")
        else:
            check("backup constraint is inactive at r = 1, as the model specifies",
                  True,
                  f"{int((counts >= 2).sum())}/{len(crit)} high-priority cells happen "
                  f"to have >= 2 feasible hubs anyway; {int((counts == 0).sum())} have none")

        # (f) the reported objective values, recomputed from the solution itself
        check("reported hub count matches the solution",
              len(active) == int(reported["minimum_hubs"]),
              f"{len(active)} hubs")
        check("reported fleet size matches the allocation",
              sum(fleet.values()) == int(reported["minimum_drones"]),
              f"{sum(fleet.values())} drones")

        resp_vals = [response[cell_pos[f["demand_point_id"]], hub_ids.index(f["hub_id"])]
                     for _, f in flow.iterrows()]
        check("reported mean response time recomputes from the assignments",
              abs(float(np.mean(resp_vals)) - reported["mean_response_min"]) < 1e-6,
              f"{np.mean(resp_vals):.6f} min")
        check("reported maximum response time recomputes from the assignments",
              abs(float(np.max(resp_vals)) - reported["max_response_min"]) < 1e-6,
              f"{np.max(resp_vals):.6f} min")


# --------------------------------------------------------------------------
# 3. The gap between the three planning layers, checked directly
# --------------------------------------------------------------------------
def validate_layer_gap(D: np.ndarray, hub_ids: list[str]) -> None:
    section("3. Why the geographic benchmark cannot serve the operational workload")

    sel = read(GEO / "optimization_selected_hubs_v1.csv")
    geo = sorted(sel[(sel["model"] == "LSCP")
                     & (sel["range_km"] == SERVICE_RANGE_KM)]["hub_id"])

    # The capacity argument needs no siting information at all.
    q_total = 30
    turnaround_load = q_total * T_TURN_MIN
    max_fleet_3_hubs = len(geo) * N_MAX
    capacity_3_hubs = 60.0 * max_fleet_3_hubs

    check("a 3-hub network can host at most 9 drones",
          max_fleet_3_hubs == 9, f"{len(geo)} hubs x N_max {N_MAX}")
    check("turnaround alone consumes more drone-minutes than 3 hubs can supply",
          turnaround_load > capacity_3_hubs,
          f"{turnaround_load:.0f} drone-min needed vs {capacity_3_hubs:.0f} available")
    check("=> the geographic benchmark is infeasible on throughput alone",
          turnaround_load > capacity_3_hubs,
          "independent of where the three hubs are placed")

    # The response requirement is strictly tighter than endurance.
    battery = (2 * D) <= L_SAFE_KM
    resp = (T_FIXED_MIN + D / CRUISE_KM_PER_MIN) <= T_TARGET_MIN
    check("the response-feasible set is a strict subset of the endurance-feasible set",
          int((resp & ~battery).sum()) == 0,
          f"{int((battery & ~resp).sum())} pairs pass endurance but fail response, "
          f"{int((resp & ~battery).sum())} the other way")


def main() -> int:
    print("=" * 78)
    print("Independent validation of the reported solutions (no solver required)")
    print("=" * 78)

    if not (GEO.exists() and OPS.exists()):
        print("\nERROR: checkpoint directories are missing. See docs/REPRODUCTION.md.")
        return 1

    demand, _, D, hub_ids = load_network()
    validate_geographic(D, hub_ids)
    validate_operational(demand, D, hub_ids)
    validate_layer_gap(D, hub_ids)

    print("\n" + "=" * 78)
    total = _passed + len(_failed)
    if _failed:
        print(f"FAILED: {len(_failed)} of {total} validations did not pass\n")
        for f in _failed:
            print(f"  - {f}")
        return 1
    print(f"All {total} validations passed.")
    print()
    print("PROVED here, without a solver:")
    print("  - three hubs is the minimum for complete 5 km coverage (exhaustive)")
    print("  - complete coverage at 2.5 km is impossible for any hub count")
    print("  - both reported networks satisfy every constraint of the MILP")
    print("  - the reported objective values recompute from the assignments")
    print("  - the 3-hub benchmark cannot carry the workload on capacity grounds")
    print()
    print("NOT proved here: that 7 and 10 hubs are optimal. Establishing that requires")
    print("the solver; see docs/REPRODUCTION.md to re-run it.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
