#!/usr/bin/env python3
"""Verify every headline number in the paper against the saved checkpoints.

This script re-derives each reported quantity from the data files in ``data/`` and
checks it against the value printed in the manuscript. It does not solve any
optimization model, so it runs in seconds and needs no solver.

Run it after cloning to confirm the repository reproduces the reported results:

    python src/verify_results.py

Exit status is 0 if every check passes and 1 otherwise, so it can be used in CI.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "model"
GEO = MODEL / "optimization_solutions"
OPS = MODEL / "operational_resilient_solutions_v4"

# Baseline operational parameters (Table 2 of the paper).
CRUISE_KM_PER_MIN = 0.9          # 15 m/s
T_FIXED_MIN = 1.0                # dispatch and handling allowance
T_TARGET_MIN = 5.0               # response target
L_SAFE_KM = 20.0                 # safe round-trip distance
T_TURN_MIN = 30.0                # turnaround
N_MAX = 3                        # drones per hub
Q_BASELINE = 30                  # scenario workload, packages/hour
CRITICAL_SHARE = 0.20            # upper quintile defines the high-priority set
SERVICE_RANGE_KM = 5.0

_passed = 0
_failed: list[str] = []


def check(label: str, got, want, tol: float | None = None) -> None:
    """Record one comparison. ``tol`` enables approximate matching for floats."""
    global _passed
    if tol is None:
        ok = got == want
    else:
        ok = abs(float(got) - float(want)) <= tol
    if ok:
        _passed += 1
        print(f"  [ok]   {label:<62} {got}")
    else:
        _failed.append(f"{label}: got {got!r}, paper reports {want!r}")
        print(f"  [FAIL] {label:<62} got {got!r}, expected {want!r}")


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


# --------------------------------------------------------------------------
# Section 3.2 - data and geospatial framework
# --------------------------------------------------------------------------
def verify_data() -> dict:
    section("Section 3.2  Data and geospatial framework")

    med = read(MODEL / "medical_infrastructure_v1.csv")
    check("cleaned medical locations", len(med), 216)

    sizes = {}
    for res, expected in (("250m", 2192), ("500m", 556), ("1000m", 142)):
        grid = read(MODEL / f"hajj_demand_locations_{res}_v1.csv")
        sizes[res] = grid
        check(f"demand cells at {res}", len(grid), expected)

    hubs = read(MODEL / "candidate_drone_hubs_v1.csv")
    check("candidate hubs |J|", len(hubs), 59)
    cats = hubs["category"].value_counts().to_dict()
    check("  of which hospitals", cats.get("hospital", 0), 53)
    check("  of which seasonal health centres", cats.get("seasonal_health_center", 0), 5)
    check("  of which ambulance stations", cats.get("ambulance_station", 0), 1)

    dist = read(MODEL / "demand_to_candidate_hub_air_distance_km_v1.csv")
    dist = dist.set_index("demand_point_id").loc[sizes["500m"]["demand_point_id"]]
    check("distance matrix shape", tuple(dist.shape), (556, 59))
    check("demand-hub relationships", dist.shape[0] * dist.shape[1], 32804)

    demand = sizes["500m"]
    w = demand["proxy_demand_weight"].to_numpy(float)
    check("proxy weight range", (round(w.min(), 4), round(w.max(), 4)), (1.0, 5.0))

    thr = demand["proxy_demand_weight"].quantile(1 - CRITICAL_SHARE)
    n_crit = int((w >= thr).sum())
    check("high-priority cells |I^C|", n_crit, 112)

    return {"demand": demand, "w": w, "D": dist.to_numpy(float),
            "hub_ids": list(dist.columns), "crit_thr": thr}


# --------------------------------------------------------------------------
# Section 3.5.1 - how the scenario workload is realised
# --------------------------------------------------------------------------
def allocate_integer_demand(total_packages: int, w: np.ndarray) -> np.ndarray:
    """Largest-remainder allocation, as implemented in notebook 07."""
    raw = total_packages * w / w.sum()
    q = np.floor(raw).astype(int)
    remainder = int(total_packages - q.sum())
    if remainder > 0:
        q[np.argsort(-(raw - q))[:remainder]] += 1
    assert q.sum() == total_packages
    return q


def verify_demand_allocation(ctx: dict) -> np.ndarray:
    section("Section 3.5.1  Realised demand allocation")

    w = ctx["w"]
    active_sets = {}
    for Q in (15, 30, 45):
        q = allocate_integer_demand(Q, w)
        idx = np.where(q > 0)[0]
        active_sets[Q] = set(idx.tolist())
        check(f"Q={Q}: active demand locations", len(idx), Q)
        check(f"Q={Q}: every active location has q_i = 1", int(q.max()), 1)
        check(f"Q={Q}: sum of q_i", int(q.sum()), Q)
        top_q = set(np.argsort(-w, kind="stable")[:Q].tolist())
        check(f"Q={Q}: active set is the top-{Q} cells by w_i",
              active_sets[Q] == top_q, True)

    check("active sets are nested (15 subset 30 subset 45)",
          active_sets[15] <= active_sets[30] <= active_sets[45], True)

    # No tie straddles a cutoff, so the selection is deterministic.
    sw = np.sort(w)[::-1]
    for Q in (15, 30, 45):
        check(f"Q={Q}: no tie across the cutoff", bool(sw[Q - 1] != sw[Q]), True)

    return allocate_integer_demand(Q_BASELINE, w)


# --------------------------------------------------------------------------
# Section 4.1 - geographic benchmarks
# --------------------------------------------------------------------------
def verify_geographic() -> None:
    section("Section 4.1  Geographic facility-location benchmarks")

    runs = read(GEO / "optimization_run_summary_v1.csv")
    check("total geographic optimization runs", len(runs), 108)

    by_model = runs["model"].value_counts().to_dict()
    check("  p-median runs (unrestricted + 5-km restricted)", by_model.get("p-median", 0), 32)
    check("  p-center runs", by_model.get("p-center", 0), 8)
    check("  MCLP runs", by_model.get("MCLP", 0), 64)
    check("  LSCP runs", by_model.get("LSCP", 0), 4)

    # Table 4 panel (a). The manuscript uses the UNRESTRICTED p-median column.
    cross = read(GEO / "optimization_cross_model_summary_v1.csv").sort_values("p")
    expected = [
        (1, 6.348, 13.319, 48.16), (2, 3.869, 7.977, 76.56),
        (3, 2.441, 4.779, 100.00), (4, 2.177, 4.248, 100.00),
        (5, 2.007, 3.955, 100.00), (6, 1.862, 3.834, 100.00),
        (8, 1.676, 3.729, 100.00), (10, 1.523, 3.729, 100.00),
    ]
    for p, pmed, pcen, mclp in expected:
        row = cross[cross["p"] == p].iloc[0]
        check(f"p={p:<2} p-median weighted mean (km)",
              round(row["pmedian_proxy_weighted_mean_km"], 3), pmed, tol=5e-4)
        check(f"p={p:<2} p-center worst case (km)",
              round(row["pcenter_worst_km"], 3), pcen, tol=5e-4)
        check(f"p={p:<2} MCLP coverage at 5 km (%)",
              round(row["mclp_proxy_coverage_5km_pct"], 2), mclp, tol=5e-3)

    # Table 4 panel (b): LSCP is indexed by service range, not by p.
    lscp = runs[runs["model"] == "LSCP"]
    for rng, hubs, uncov in ((2.5, None, 47), (5.0, 3, 0), (7.5, 3, 0), (10.0, 2, 0)):
        row = lscp[lscp["range_km"] == rng].iloc[0]
        if hubs is None:
            check(f"LSCP at {rng} km is not achievable",
                  row["termination"] != "optimal", True)
        else:
            check(f"LSCP at {rng} km: minimum hubs", int(row["p"]), hubs)
        check(f"LSCP at {rng} km: cells with no candidate in range",
              int(row["uncoverable_points"]), uncov)

    sel = read(GEO / "optimization_selected_hubs_v1.csv")
    bench = sel[(sel["model"] == "LSCP") & (sel["range_km"] == SERVICE_RANGE_KM)]
    check("principal benchmark hub set",
          sorted(bench["hub_id"]), ["HUB_006", "HUB_007", "HUB_016"])


# --------------------------------------------------------------------------
# Section 4.2 - structural diagnostics and the operational network
# --------------------------------------------------------------------------
def verify_operational(ctx: dict, q: np.ndarray) -> dict:
    section("Section 4.2  From geographic coverage to operational feasibility")

    D = ctx["D"]
    battery = (2 * D) <= L_SAFE_KM
    response = (T_FIXED_MIN + D / CRUISE_KM_PER_MIN) <= T_TARGET_MIN
    feasible = battery & response

    check("effective response radius (km)",
          round((T_TARGET_MIN - T_FIXED_MIN) * CRUISE_KM_PER_MIN, 2), 3.60, tol=5e-3)
    check("battery half-range (km)", L_SAFE_KM / 2, 10.0)

    check("cells with no endurance-feasible hub", int((battery.sum(axis=1) == 0).sum()), 0)
    check("minimum endurance-feasible hubs per cell", int(battery.sum(axis=1).min()), 10)
    check("median endurance-feasible hubs per cell", float(np.median(battery.sum(axis=1))), 39.0)
    check("cells with no response-feasible hub", int((response.sum(axis=1) == 0).sum()), 2)
    check("median response-feasible hubs per cell", float(np.median(response.sum(axis=1))), 9.0)

    check("pairs allowed by endurance but excluded by response",
          int((battery & ~response).sum()), 13183)
    check("pairs allowed by response but excluded by endurance",
          int((response & ~battery).sum()), 0)
    check("response feasible set is a strict subset of endurance",
          bool((response & ~battery).sum() == 0), True)

    check("active-demand cells with no feasible hub",
          int(((feasible.sum(axis=1) == 0) & (q > 0)).sum()), 0)

    # Fleet lower bound, independent of siting.
    turnaround_only = Q_BASELINE * T_TURN_MIN
    check("turnaround-only workload (drone-min/h)", turnaround_only, 900.0)
    check("minimum drones ignoring flight", int(np.ceil(turnaround_only / 60)), 15)

    nearest = np.where(feasible, D, np.inf).min(axis=1)
    flight = float(sum(2 * nearest[i] / CRUISE_KM_PER_MIN * q[i]
                       for i in np.where(q > 0)[0] if np.isfinite(nearest[i])))
    total = turnaround_only + flight
    check("minimum theoretical workload (drone-min/h)", round(total, 2), 942.16, tol=5e-3)
    check("minimum theoretical drones", int(np.ceil(total / 60)), 16)
    check("minimum hubs from fleet capacity alone",
          int(np.ceil(np.ceil(total / 60) / N_MAX)), 6)

    three_hub_capacity = 3 * N_MAX * 60
    check("three-hub fleet capacity (drone-min/h)", three_hub_capacity, 540)
    check("three-hub capacity as % of requirement",
          round(100 * three_hub_capacity / total, 1), 57.3, tol=5e-2)

    # Fixed-p feasibility frontier.
    fp = read(OPS / "fixed_p_resilience_comparison_v4.csv").reset_index(drop=True)
    half = len(fp) // 2
    r1, r2 = fp.iloc[:half], fp.iloc[half:]
    check("r=1 infeasible hub counts",
          sorted(r1[r1["termination"] != "optimal"]["p"].astype(int)), [5, 6])
    check("r=1 smallest feasible p", int(r1[r1["termination"] == "optimal"]["p"].min()), 7)
    check("r=2 infeasible hub counts",
          sorted(r2[r2["termination"] != "optimal"]["p"].astype(int)), [5, 6, 7, 8, 9])
    check("r=2 smallest feasible p", int(r2[r2["termination"] == "optimal"]["p"].min()), 10)

    base = read(OPS / "baseline_endogenous_comparison_v4.csv")
    b1 = base[base["redundancy"] == 1].iloc[0]
    check("operational (r=1): active hubs", int(b1["minimum_hubs"]), 7)
    check("operational (r=1): drones", int(b1["minimum_drones"]), 19)
    check("operational (r=1): mean response (min)",
          round(b1["mean_response_min"], 3), 1.837, tol=5e-4)
    check("operational (r=1): max response (min)",
          round(b1["max_response_min"], 3), 3.029, tol=5e-4)
    check("operational (r=1): max one-way distance (km)",
          round(b1["max_oneway_distance_km"], 3), 1.826, tol=5e-4)

    return {"feasible": feasible, "base": base, "b1": b1}


# --------------------------------------------------------------------------
# Section 4.3 - the cost of resilient preparedness
# --------------------------------------------------------------------------
def verify_resilience(ctx: dict, ops: dict) -> None:
    section("Section 4.3  Infrastructure cost of resilient preparedness")

    base, b1 = ops["base"], ops["b1"]
    b2 = base[base["redundancy"] == 2].iloc[0]

    check("resilient (r=2): active hubs", int(b2["minimum_hubs"]), 10)
    check("resilient (r=2): drones", int(b2["minimum_drones"]), 21)
    check("resilient (r=2): mean response (min)",
          round(b2["mean_response_min"], 3), 2.082, tol=5e-4)
    check("resilient (r=2): max response (min)",
          round(b2["max_response_min"], 3), 4.858, tol=5e-4)
    check("resilient (r=2): max one-way distance (km)",
          round(b2["max_oneway_distance_km"], 3), 3.473, tol=5e-4)

    hub_pct = 100 * (b2["minimum_hubs"] - b1["minimum_hubs"]) / b1["minimum_hubs"]
    drone_pct = 100 * (b2["minimum_drones"] - b1["minimum_drones"]) / b1["minimum_drones"]
    check("resilience premium: hubs (%)", round(hub_pct, 1), 42.9, tol=5e-2)
    check("resilience premium: drones (%)", round(drone_pct, 1), 10.5, tol=5e-2)
    check("max response as % of the 5-min target",
          round(100 * b2["max_response_min"] / T_TARGET_MIN, 1), 97.2, tol=5e-2)

    # Backup accessibility of the high-priority cells under each network.
    feasible = ops["feasible"]
    hub_ids = ctx["hub_ids"]
    crit = np.where(ctx["w"] >= ctx["crit_thr"])[0]

    def backup_counts(row):
        cols = [hub_ids.index(h) for h in row["selected_hubs"].split(";")]
        return feasible[:, cols].sum(axis=1)[crit]

    c1, c2 = backup_counts(b1), backup_counts(b2)
    check("r=1 network: high-priority cells with >=2 feasible hubs", int((c1 >= 2).sum()), 103)
    check("  as a share of the high-priority set (%)",
          round(100 * (c1 >= 2).sum() / len(crit), 1), 92.0, tol=5e-2)
    check("r=1 network: cells with exactly one feasible hub", int((c1 == 1).sum()), 4)
    check("r=1 network: cells with no feasible hub", int((c1 == 0).sum()), 5)
    check("r=2 network: high-priority cells with >=2 feasible hubs", int((c2 >= 2).sum()), 112)
    check("cells remedied by the three additional hubs",
          int((c1 < 2).sum() - (c2 < 2).sum()), 9)

    # Fleet distribution: the added hubs are presence, not capacity.
    def alloc(row):
        return {k: int(v) for k, v in (p.split(":") for p in row["drone_allocation"].split(";"))}

    a1, a2 = alloc(b1), alloc(b2)
    check("r=1: hubs at the N_max cap", sum(1 for v in a1.values() if v == N_MAX), 5)
    check("r=1: hubs with a single drone", sum(1 for v in a1.values() if v == 1), 0)
    check("r=2: hubs at the N_max cap", sum(1 for v in a2.values() if v == N_MAX), 5)
    check("r=2: hubs with a single drone", sum(1 for v in a2.values() if v == 1), 4)

    # The three planning layers are not nested.
    sel = read(GEO / "optimization_selected_hubs_v1.csv")
    geo = set(sel[(sel["model"] == "LSCP") & (sel["range_km"] == SERVICE_RANGE_KM)]["hub_id"])
    s1, s2 = set(b1["selected_hubs"].split(";")), set(b2["selected_hubs"].split(";"))
    check("geographic set is NOT a subset of the operational set", geo <= s1, False)
    check("operational set is NOT a subset of the resilient set", s1 <= s2, False)
    check("hubs selected in all three layers", sorted(geo & s1 & s2), ["HUB_006"])


# --------------------------------------------------------------------------
# Sections 4.4 and 4.5 - sensitivity and spatial configuration
# --------------------------------------------------------------------------
def verify_sensitivity_and_layout() -> None:
    section("Section 4.4  Operational sensitivity analysis")

    sens = read(OPS / "endogenous_sensitivity_results_v4.csv")
    check("sensitivity scenarios", len(sens), 10)

    expected = {
        "S01": (8, 13), "S02": (10, 21), "S03": (11, 29), "S04": (10, 21),
        "S05": (10, 21), "S06": (8, 20), "S07": (7, 19), "S08": (8, 12),
        "S09": (12, 32), "S10": (7, 19),
    }
    for sid, (hubs, drones) in expected.items():
        row = sens[sens["scenario_id"] == sid].iloc[0]
        check(f"{sid}: hubs / drones",
              (int(row["minimum_hubs"]), int(row["minimum_drones"])), (hubs, drones))

    # Endurance is inert: S04 and S05 must equal the S02 baseline exactly.
    base_row = sens[sens["scenario_id"] == "S02"].iloc[0]
    cols = ["minimum_hubs", "minimum_drones", "mean_response_min",
            "max_response_min", "mean_oneway_distance_km", "max_oneway_distance_km"]
    for sid in ("S04", "S05"):
        row = sens[sens["scenario_id"] == sid].iloc[0]
        same = all(abs(float(row[c]) - float(base_row[c])) < 1e-9 for c in cols)
        check(f"{sid} is identical to the baseline on all reported statistics", same, True)

    spans = {}
    for fam in ("demand", "turnaround", "response", "battery", "redundancy"):
        rows = pd.concat([sens[sens["scenario_family"] == fam],
                          sens[sens["scenario_id"] == "S02"]]).drop_duplicates("scenario_id")
        spans[fam] = (int(rows["minimum_hubs"].max() - rows["minimum_hubs"].min()),
                      int(rows["minimum_drones"].max() - rows["minimum_drones"].min()))
    check("turnaround span (hubs, drones)", spans["turnaround"], (4, 20))
    check("demand span (hubs, drones)", spans["demand"], (3, 16))
    check("response span (hubs, drones)", spans["response"], (3, 2))
    check("redundancy span (hubs, drones)", spans["redundancy"], (3, 2))
    check("endurance span (hubs, drones)", spans["battery"], (0, 0))

    section("Section 4.5  Spatial configuration of the resilient network")

    hub_fleet = read(OPS / "selected_hubs_fleet_v4.csv")
    flows = read(OPS / "package_flows_v4.csv")
    hubs = hub_fleet[hub_fleet["scenario_id"] == "S02"]
    flow = flows[flows["scenario_id"] == "S02"]

    check("resilient baseline: active hubs", len(hubs), 10)
    check("resilient baseline: total drones", int(hubs["drones"].sum()), 21)
    check("resilient baseline: delivery locations", flow["demand_point_id"].nunique(), 30)

    by_zone = hubs["hajj_zone"].value_counts().to_dict()
    check("hubs in Mina", by_zone.get("Mina", 0), 4)
    check("hubs in Haram Makkah", by_zone.get("Haram_Makkah", 0), 3)
    check("hubs in Arafat", by_zone.get("Arafat", 0), 2)
    check("hubs in Greater Makkah", by_zone.get("Greater_Makkah", 0), 1)
    check("hubs in Muzdalifah", by_zone.get("Muzdalifah", 0), 0)

    cat = hubs["category"].value_counts().to_dict()
    check("hub types: hospitals", cat.get("hospital", 0), 8)
    check("hub types: seasonal health centre", cat.get("seasonal_health_center", 0), 1)
    check("hub types: ambulance station", cat.get("ambulance_station", 0), 1)

    serving = set(flow["hub_id"])
    prep_only = sorted(set(hubs["hub_id"]) - serving)
    check("hubs serving no packages (pure preparedness)", prep_only, ["HUB_035", "HUB_046"])
    check("  all of which are in Arafat",
          sorted(hubs[hubs["hub_id"].isin(prep_only)]["hajj_zone"].unique()), ["Arafat"])

    cycle = flow["mission_cycle_min"]
    flight_share_min = 100 * (cycle.min() - T_TURN_MIN) / cycle.min()
    flight_share_max = 100 * (cycle.max() - T_TURN_MIN) / cycle.max()
    check("flight as % of mission cycle: minimum", round(flight_share_min, 1), 0.9, tol=5e-2)
    check("flight as % of mission cycle: maximum", round(flight_share_max, 1), 20.5, tol=0.2)


def main() -> int:
    print("=" * 78)
    print("Verifying reported results against the saved checkpoints")
    print("=" * 78)

    missing = [p for p in (MODEL, GEO, OPS) if not p.exists()]
    if missing:
        print("\nERROR: expected data directories are absent:")
        for p in missing:
            print(f"  {p}")
        print("\nSee docs/REPRODUCTION.md for how to obtain the data.")
        return 1

    ctx = verify_data()
    q = verify_demand_allocation(ctx)
    verify_geographic()
    ops = verify_operational(ctx, q)
    verify_resilience(ctx, ops)
    verify_sensitivity_and_layout()

    print("\n" + "=" * 78)
    total = _passed + len(_failed)
    if _failed:
        print(f"FAILED: {len(_failed)} of {total} checks did not match the paper\n")
        for f in _failed:
            print(f"  - {f}")
        return 1
    print(f"All {total} checks reproduce the values reported in the paper.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
