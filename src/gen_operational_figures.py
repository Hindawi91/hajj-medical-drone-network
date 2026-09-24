# %% [markdown]
# # 10 - Operational Manuscript Figures (V1)
#
# **Solver-free manuscript figure layer for Results Sections 4.2-4.5.**
#
# This script does **not** invoke Pyomo or HiGHS and does not rerun any optimization.
# It reads the saved Notebook 07 V4 checkpoints and the Notebook 05 geographic
# checkpoints, and writes the figures the manuscript actually includes.
#
# It is deliberately separate from Notebook 08 V3. Notebook 08 V3 remains the
# authoritative exploratory figure workflow and is not modified; this script produces
# only the subset of figures that go into `paper/figures/`, so a manuscript figure can
# be corrected without rerunning the whole V3 workflow.
#
# All values are read from CSV. Nothing is hardcoded, including the geographic
# benchmark hub count.

# %%
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent

MODEL_DIR = ROOT / "data" / "model"
PROCESSED_DIR = ROOT / "data" / "processed"
NB05_DIR = MODEL_DIR / "optimization_solutions"
NB07_DIR = MODEL_DIR / "operational_resilient_solutions_v4"
PAPER_FIG_DIR = ROOT / "paper" / "figures"
FIG_DIR = ROOT / "outputs" / "figures" / "manuscript_v1"

FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "figure.dpi": 120,
})

SERVICE_RANGE_KM = 5.0
HUB_COLOR = "#2c7fb8"
DRONE_COLOR = "#d95f02"


def rd(path):
    return pd.read_csv(path, encoding="utf-8-sig")


def savefig(fig, name, also_paper=None):
    png, pdf = FIG_DIR / (name + ".png"), FIG_DIR / (name + ".pdf")
    fig.savefig(png, dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    print("Saved:", png)
    if also_paper:
        PAPER_FIG_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(png, PAPER_FIG_DIR / (also_paper + ".png"))
        print("Copied to manuscript:", PAPER_FIG_DIR / (also_paper + ".png"))
    return png


# %% [markdown]
# ## 1. Load checkpoints
#
# The geographic hub count is read from the LSCP run rather than assumed, so this figure
# cannot drift from Section 4.1.

# %%
run_summary = rd(NB05_DIR / "optimization_run_summary_v1.csv")
baseline = rd(NB07_DIR / "baseline_endogenous_comparison_v4.csv")

lscp_5km = run_summary[
    (run_summary["model"] == "LSCP") & (run_summary["range_km"] == SERVICE_RANGE_KM)
].iloc[0]
n_geographic = int(lscp_5km["p"])

b1 = baseline[baseline["redundancy"] == 1].iloc[0]
b2 = baseline[baseline["redundancy"] == 2].iloc[0]

stages = ["Geographic\nbenchmark", "Operational\n($r=1$)", "Resilient\n($r=2$)"]
hubs = [n_geographic, int(b1["minimum_hubs"]), int(b2["minimum_hubs"])]
drones = [np.nan, int(b1["minimum_drones"]), int(b2["minimum_drones"])]

print("geographic hubs (from LSCP checkpoint):", n_geographic)
print("hubs  :", hubs)
print("drones:", drones)

# %% [markdown]
# ## Figure. Progressive infrastructure requirements
#
# Fixing the label collision in the earlier version. Previously both series were drawn in
# the same colour, and the hub count was annotated *above* each bar. On the resilient
# stage the bar top (10 hubs on a 0-13 left axis, 76.9% of axis height) and the drone
# marker (21 drones on a 0-26 right axis, 80.8%) sit within four percent of axis height
# of each other, so the "10" label landed on top of the drone marker.
#
# Two changes remove the collision structurally rather than by nudging offsets:
#
# 1. hub counts are drawn **inside** the bars, so they can never collide with anything
#    plotted above the bar top;
# 2. the two series are given distinct colours, with each axis label and tick set matching
#    its series, so a reader can tell at a glance which value belongs to which axis.

# %%
fig, ax1 = plt.subplots(figsize=(7.2, 4.6))
x = np.arange(len(stages))

bars = ax1.bar(x, hubs, width=.46, color=HUB_COLOR, zorder=3)
ax1.set_ylabel("Active hubs", color=HUB_COLOR)
ax1.tick_params(axis="y", colors=HUB_COLOR)
ax1.set_xticks(x)
ax1.set_xticklabels(stages)
ax1.set_ylim(0, 13)
ax1.yaxis.set_major_locator(MaxNLocator(integer=True))
ax1.grid(axis="y", alpha=.18, zorder=0)

# Hub counts inside the bars: structurally cannot collide with the drone series.
for rect, val in zip(bars, hubs):
    ax1.annotate(str(val), (rect.get_x() + rect.get_width() / 2, val),
                 xytext=(0, -8), textcoords="offset points",
                 ha="center", va="top", fontweight="bold",
                 fontsize=11, color="white", zorder=5)

ax2 = ax1.twinx()
line = ax2.plot(x[1:], drones[1:], marker="o", markersize=7, linewidth=2,
                color=DRONE_COLOR, zorder=4)[0]
ax2.set_ylabel("Minimum drones", color=DRONE_COLOR)
ax2.tick_params(axis="y", colors=DRONE_COLOR)
ax2.set_ylim(0, 26)
ax2.yaxis.set_major_locator(MaxNLocator(integer=True))

# Drone labels sit above their markers, well clear of the in-bar hub labels.
for xi, val in zip(x[1:], drones[1:]):
    ax2.annotate(str(int(val)), (xi, val), xytext=(0, 11),
                 textcoords="offset points", ha="center",
                 fontweight="bold", fontsize=11, color=DRONE_COLOR, zorder=5)

# The geographic models contain no fleet decision; say so on the figure rather than
# leaving an unexplained gap in the drone series. Placed above the bar on the left axis:
# inside the bar it would be orange-on-blue and effectively illegible.
ax1.annotate("no fleet decision\nin this layer", (x[0], hubs[0]), xytext=(0, 10),
             textcoords="offset points", ha="center", va="bottom",
             fontsize=7.5, color="0.40", style="italic")

ax1.legend(handles=[Patch(facecolor=HUB_COLOR, label="Active hubs"),
                    Line2D([0], [0], color=DRONE_COLOR, marker="o", markersize=6,
                           linewidth=2, label="Minimum drones")],
           loc="upper left", framealpha=.95)

fig.tight_layout()
savefig(fig, "fig_progressive_infrastructure_v1",
        also_paper="fig06_progressive_infrastructure")
plt.close(fig)

# %% [markdown]
# ## Figure. Resilience: feasibility frontier and what redundancy buys
#
# Panel (a) is a corrected fixed-$p$ frontier. The earlier version declared
# "x = infeasible configuration" in its legend but drew no such markers, so the
# infeasible configurations -- the substantive content -- were invisible, and the
# reader could not see that $p=7,8,9$ are feasible at $r=1$ yet infeasible at $r=2$.
# Infeasible runs are now plotted explicitly.
#
# Panel (b) quantifies the marginal cost of redundancy: how many high-priority cells
# actually gain backup accessibility in exchange for the three additional hubs.

# %%
fp = rd(NB07_DIR / "fixed_p_resilience_comparison_v4.csv").reset_index(drop=True)
# The file stacks the r=1 block then the r=2 block; infeasible rows carry no
# redundancy value, so split by position rather than by the redundancy column.
half = len(fp) // 2
blocks = {1: fp.iloc[:half], 2: fp.iloc[half:]}

# Recompute per-critical-cell backup availability for each solved network.
demand = rd(MODEL_DIR / "hajj_demand_locations_500m_v1.csv")
dist = rd(MODEL_DIR / "demand_to_candidate_hub_air_distance_km_v1.csv")
dist = dist.set_index("demand_point_id").loc[demand["demand_point_id"]]
Dm = dist.to_numpy(float)
all_hubs = list(dist.columns)
wts = demand["proxy_demand_weight"].to_numpy(float)

CRUISE, T_FIXED, T_TARGET, L_SAFE, N_MAX = 0.9, 1.0, 5.0, 20.0, 3
feasible_pair = (2 * Dm <= L_SAFE) & (T_FIXED + Dm / CRUISE <= T_TARGET)
crit_idx = np.where(wts >= demand["proxy_demand_weight"].quantile(0.8))[0]


def backup_counts(selected):
    cols = [all_hubs.index(h) for h in selected]
    return feasible_pair[:, cols].sum(axis=1)[crit_idx]


cnt1 = backup_counts(b1["selected_hubs"].split(";"))
cnt2 = backup_counts(b2["selected_hubs"].split(";"))

fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.1))

# --- panel (a): feasibility frontier -------------------------------------------
ax = axes[0]
styles = {1: (HUB_COLOR, "o", "$r=1$ (no backup)"),
          2: (DRONE_COLOR, "s", "$r=2$ (backup)")}
for r, blk in blocks.items():
    color, marker, label = styles[r]
    ok = blk[blk["termination"] == "optimal"]
    no = blk[blk["termination"] != "optimal"]
    ax.plot(ok["p"], ok["minimum_drones"], marker=marker, ms=6, lw=2,
            color=color, label=label, zorder=3)
    # Infeasible configurations, drawn on a floor row. p=5 and p=6 are infeasible for
    # BOTH r values, so offset the two series horizontally or the second would hide
    # the first entirely.
    dx = -0.09 if r == 1 else 0.09
    ax.scatter(no["p"] + dx, np.full(len(no), 17.6), marker="x", s=58, linewidths=2,
               color=color, zorder=3)

ax.axhline(17.6, color="0.85", lw=.8, zorder=1)
ax.text(4.92, 17.82, "infeasible", fontsize=7.5, color="0.35", va="bottom")
ax.set_xlabel("Active hubs, $p$")
ax.set_ylabel("Minimum drone fleet")
ax.set_title("(a) Fixed-$p$ feasibility frontier")
ax.set_xticks(sorted(fp["p"].unique()))
ax.set_ylim(17.2, 22.8)
ax.set_yticks([18, 19, 20, 21, 22])
ax.grid(alpha=.22, lw=.6, zorder=0)

# r=1 label goes below-right into empty space; r=2 label goes above-LEFT, since
# above-right would sit on the orange segment rising to (11, 22).
ax.annotate("first feasible\n$p=7$, 19 drones", (7, 19), xytext=(12, -6),
            textcoords="offset points", fontsize=7.5, color=HUB_COLOR,
            fontweight="bold", ha="left", va="top")
ax.annotate("first feasible\n$p=10$, 21 drones", (10, 21), xytext=(-12, 8),
            textcoords="offset points", fontsize=7.5, color=DRONE_COLOR,
            fontweight="bold", ha="right", va="bottom")
handles = [Line2D([0], [0], color=c, marker=m, ms=6, lw=2, label=l)
           for c, m, l in styles.values()]
handles.append(Line2D([0], [0], color="0.35", marker="x", ms=7, lw=0,
                      label="infeasible configuration"))
ax.legend(handles=handles, loc="lower right", framealpha=.95, fontsize=7.5)

# --- panel (b): what redundancy buys ------------------------------------------
ax = axes[1]
bins = np.arange(0, max(cnt1.max(), cnt2.max()) + 1)
h1 = np.array([(cnt1 == b).sum() for b in bins])
h2 = np.array([(cnt2 == b).sum() for b in bins])
width = .38
ax.bar(bins - width / 2, h1, width, color=HUB_COLOR, label="$r=1$ network (7 hubs)",
       zorder=3)
ax.bar(bins + width / 2, h2, width, color=DRONE_COLOR, label="$r=2$ network (10 hubs)",
       zorder=3)
ax.axvspan(-0.5, 1.5, color="#d62728", alpha=.07, zorder=0)
ax.text(0.5, max(h1.max(), h2.max()) * .96, "below\nrequirement", ha="center",
        va="top", fontsize=7.5, color="#a01d1d")
for b, v1, v2 in zip(bins, h1, h2):
    if v1:
        ax.annotate(str(v1), (b - width / 2, v1), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=7,
                    color=HUB_COLOR, fontweight="bold")
    if v2:
        ax.annotate(str(v2), (b + width / 2, v2), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=7,
                    color=DRONE_COLOR, fontweight="bold")
ax.set_xlabel("Operationally feasible active hubs per high-priority cell")
ax.set_ylabel("High-priority cells")
ax.set_title("(b) Backup accessibility of the %d high-priority cells" % len(crit_idx))
ax.set_xticks(bins)
ax.grid(axis="y", alpha=.22, lw=.6, zorder=0)
ax.legend(loc="upper right", framealpha=.95, fontsize=7.5)

fig.tight_layout()
savefig(fig, "fig_resilience_frontier_v1", also_paper="fig_resilience_frontier")
plt.close(fig)

print("\nBackup accessibility of the %d high-priority cells:" % len(crit_idx))
print("  r=1 network: %d with >=2 feasible hubs (%.1f%%), %d with 1, %d with 0"
      % ((cnt1 >= 2).sum(), 100 * (cnt1 >= 2).sum() / len(crit_idx),
         (cnt1 == 1).sum(), (cnt1 == 0).sum()))
print("  r=2 network: %d with >=2 feasible hubs (%.1f%%)"
      % ((cnt2 >= 2).sum(), 100 * (cnt2 >= 2).sum() / len(crit_idx)))
print("  cells remedied by the 3 additional hubs: %d"
      % ((cnt1 < 2).sum() - (cnt2 < 2).sum()))

# %% [markdown]
# ## Figure. Consolidated operational sensitivity
#
# One panel per varied assumption. The demand family is labelled by the number of active
# demand locations rather than by "intensity": at the workloads tested, every active
# location receives exactly one package per hour, so varying $Q$ varies how widely
# requests are spread, not how many packages each location requests.

# %%
sens = rd(NB07_DIR / "endogenous_sensitivity_results_v4.csv")
base_row = sens[sens["scenario_id"] == "S02"].iloc[0]
BASE_HUBS = int(base_row["minimum_hubs"])
BASE_DRONES = int(base_row["minimum_drones"])

families = [
    ("demand", "packages_per_hour", "Active demand\nlocations, $Q$"),
    ("turnaround", "turnaround_min", "Turnaround,\n$T^{turn}$ (min)"),
    ("response", "response_target_min", "Response target,\n$T^{max}$ (min)"),
    ("battery", "safe_roundtrip_km", "Safe round trip,\n$L^{safe}$ (km)"),
    ("redundancy", "redundancy", "Redundancy, $r$"),
]

fig, axes = plt.subplots(1, len(families), figsize=(13.6, 3.7), sharey=True)
for ax, (fam, param, label) in zip(axes, families):
    rows = pd.concat([sens[sens["scenario_family"] == fam],
                      sens[sens["scenario_id"] == "S02"]])
    rows = rows.drop_duplicates("scenario_id").sort_values(param)
    xs = np.arange(len(rows))
    ax.bar(xs - .2, rows["minimum_hubs"], .4, color=HUB_COLOR, zorder=3)
    ax.bar(xs + .2, rows["minimum_drones"], .4, color=DRONE_COLOR, zorder=3)
    for xi, (h, dr) in enumerate(zip(rows["minimum_hubs"], rows["minimum_drones"])):
        ax.annotate(str(int(h)), (xi - .2, h), xytext=(0, 2),
                    textcoords="offset points", ha="center", fontsize=7,
                    color=HUB_COLOR, fontweight="bold")
        ax.annotate(str(int(dr)), (xi + .2, dr), xytext=(0, 2),
                    textcoords="offset points", ha="center", fontsize=7,
                    color=DRONE_COLOR, fontweight="bold")
    # Mark the baseline column by shading it. A text label below the axis collided
    # with the axis title in every panel, so the highlight is positional instead.
    base_pos = list(rows["scenario_id"]).index("S02")
    ax.axvspan(base_pos - .45, base_pos + .45, color="0.90", zorder=0)
    ax.set_xticks(xs)
    ax.set_xticklabels([("%g" % v) for v in rows[param]])
    ax.set_xlabel(label, fontsize=8.5)
    ax.set_ylim(0, 36)
    ax.grid(axis="y", alpha=.22, lw=.6, zorder=0)
    span_h = int(rows["minimum_hubs"].max() - rows["minimum_hubs"].min())
    span_d = int(rows["minimum_drones"].max() - rows["minimum_drones"].min())
    ax.set_title("span: %d hubs, %d drones" % (span_h, span_d), fontsize=8)

axes[0].set_ylabel("Minimum infrastructure")
axes[0].legend(handles=[Patch(facecolor=HUB_COLOR, label="Hubs"),
                        Patch(facecolor=DRONE_COLOR, label="Drones"),
                        Patch(facecolor="0.90", label="Baseline scenario")],
               loc="upper left", fontsize=7.5, framealpha=.95)
fig.tight_layout()
savefig(fig, "fig_consolidated_sensitivity_v1", also_paper="fig_consolidated_sensitivity")
plt.close(fig)

print("\nSensitivity spans (max - min within family, baseline included):")
for fam, param, _ in families:
    rows = pd.concat([sens[sens["scenario_family"] == fam],
                      sens[sens["scenario_id"] == "S02"]]).drop_duplicates("scenario_id")
    print("  %-11s hubs %d..%d (span %d) | drones %d..%d (span %d)"
          % (fam, rows["minimum_hubs"].min(), rows["minimum_hubs"].max(),
             rows["minimum_hubs"].max() - rows["minimum_hubs"].min(),
             rows["minimum_drones"].min(), rows["minimum_drones"].max(),
             rows["minimum_drones"].max() - rows["minimum_drones"].min()))

# %% [markdown]
# ## Figure. Spatial configuration of the resilient baseline network
#
# The 10 active hubs sized by stationed fleet, the 30 active demand locations, and the
# assignments actually flown. Hubs that are activated purely to satisfy backup
# accessibility, and which serve no packages, are marked distinctly: they are the
# clearest visual statement of what the redundancy requirement buys.

# %%
import geopandas as gpd

PROCESSED_DIR = PROCESSED_DIR
zones = gpd.read_file(PROCESSED_DIR / "hajj_analytical_zones_v1.gpkg").to_crs(4326)
grid = gpd.read_file(PROCESSED_DIR / "hajj_demand_locations_500m_v1.gpkg").to_crs(4326)

hub_fleet = rd(NB07_DIR / "selected_hubs_fleet_v4.csv")
flows = rd(NB07_DIR / "package_flows_v4.csv")
hubs_s2 = hub_fleet[hub_fleet["scenario_id"] == "S02"].copy()
flows_s2 = flows[flows["scenario_id"] == "S02"].copy()

serving = set(flows_s2["hub_id"])
hubs_s2["serves"] = hubs_s2["hub_id"].isin(serving)
prep_only = hubs_s2[~hubs_s2["serves"]]
print("\npreparedness-only hubs (active, zero packages):",
      list(prep_only["hub_id"]), "| total hubs:", len(hubs_s2))

# Resolve publication labels from data, as in the geographic layer. Precedence:
# curated override, then OSM name:en, then OSM name.
candidates = rd(MODEL_DIR / "candidate_drone_hubs_v1.csv")
overrides = rd(PROCESSED_DIR / "hub_name_en_overrides_v1.csv")
ov = dict(zip(overrides["hub_id"], overrides["name_en_override"]))
meta = candidates.set_index("hub_id")[["name", "name_en", "category"]]


def label_for(hub_id):
    row = meta.loc[hub_id]
    if hub_id in ov:
        return ov[hub_id], "author_override"
    if isinstance(row["name_en"], str) and row["name_en"].strip():
        return row["name_en"], "osm_name_en"
    return row["name"], "osm_name"


pkgs = flows_s2.groupby("hub_id").size().to_dict()
tbl = hubs_s2[["hub_id", "hajj_zone", "drones"]].copy()
tbl["facility_label"] = [label_for(h)[0] for h in tbl["hub_id"]]
tbl["label_source"] = [label_for(h)[1] for h in tbl["hub_id"]]
tbl["category"] = [meta.loc[h, "category"] for h in tbl["hub_id"]]
tbl["packages_per_hour"] = [pkgs.get(h, 0) for h in tbl["hub_id"]]
tbl["preparedness_only"] = tbl["packages_per_hour"] == 0
tbl = tbl.sort_values(["packages_per_hour", "drones"], ascending=False)

TABLE_DIR = ROOT / "outputs" / "reports" / "manuscript_v1"
TABLE_DIR.mkdir(parents=True, exist_ok=True)
out = TABLE_DIR / "table_resilient_network_hubs_v1.csv"
tbl.to_csv(out, index=False, encoding="utf-8-sig")
print("Saved:", out)
print(tbl[["hub_id", "facility_label", "label_source", "category", "hajj_zone",
           "drones", "packages_per_hour", "preparedness_only"]].to_string(index=False))

cent = grid.set_index("demand_point_id").geometry.centroid
active_cells = flows_s2["demand_point_id"].unique()

ZONE_COLORS = {"Haram_Makkah": "tab:blue", "Mina": "tab:green",
               "Muzdalifah": "tab:purple", "Arafat": "tab:red"}

fig, ax = plt.subplots(figsize=(8.6, 7.0))
grid.plot(ax=ax, color="0.93", edgecolor="0.85", linewidth=.05, zorder=1)

# Critical cells provide the context for why the preparedness hubs exist.
crit_ids = demand["demand_point_id"].to_numpy()[crit_idx]
grid[grid["demand_point_id"].isin(crit_ids)].plot(
    ax=ax, color="#fde0c5", edgecolor="#f0b27a", linewidth=.12, zorder=2)

for _, zrow in zones.iterrows():
    gpd.GeoSeries([zrow.geometry], crs=4326).boundary.plot(
        ax=ax, color=ZONE_COLORS.get(zrow["zone"], "0.4"), linewidth=1.3, zorder=3)

# Assignments actually flown.
hub_xy = {r["hub_id"]: (r["longitude"], r["latitude"]) for _, r in hubs_s2.iterrows()}
for _, fr in flows_s2.iterrows():
    hx, hy = hub_xy[fr["hub_id"]]
    c = cent.loc[fr["demand_point_id"]]
    ax.plot([hx, c.x], [hy, c.y], color="0.45", lw=.55, alpha=.75, zorder=4)

ax.scatter([cent.loc[i].x for i in active_cells], [cent.loc[i].y for i in active_cells],
           s=17, color="#08519c", edgecolors="white", linewidths=.4, zorder=5)

for _, hr in hubs_s2.iterrows():
    serves = hr["serves"]
    ax.scatter(hr["longitude"], hr["latitude"],
               s=110 + 90 * int(hr["drones"]), marker="*",
               color="black" if serves else "none",
               edgecolors="black" if serves else "#c0392b",
               linewidths=1.0 if serves else 2.0, zorder=6)

ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title("Resilient baseline network: %d hubs, %d drones, %d delivery locations"
             % (len(hubs_s2), int(hubs_s2["drones"].sum()), len(active_cells)))

legend_handles = [
    Line2D([0], [0], marker="*", color="black", linestyle="None", markersize=13,
           label="Hub serving packages"),
    Line2D([0], [0], marker="*", color="none", markeredgecolor="#c0392b",
           markeredgewidth=1.8, linestyle="None", markersize=13,
           label="Preparedness-only hub (0 packages)"),
    Line2D([0], [0], marker="o", color="#08519c", linestyle="None", markersize=6,
           label="Active demand location"),
    Line2D([0], [0], color="0.45", lw=1, label="Assignment flown"),
    Patch(facecolor="#fde0c5", edgecolor="#f0b27a", label="High-priority cell"),
]
ax.legend(handles=legend_handles, loc="lower left", fontsize=7.6, framealpha=.95)
ax.text(.5, -.10, "Star size is proportional to drones stationed at the hub.",
        transform=ax.transAxes, ha="center", va="top", fontsize=7.4, color="0.35")

fig.tight_layout()
savefig(fig, "fig_resilient_configuration_v1", also_paper="fig_resilient_configuration")
plt.close(fig)

# %% [markdown]
# ## Verification
#
# Confirm the plotted values match the checkpoints exactly.

# %%
assert hubs[0] == int(lscp_5km["p"])
assert hubs[1] == int(b1["minimum_hubs"]) and drones[1] == int(b1["minimum_drones"])
assert hubs[2] == int(b2["minimum_hubs"]) and drones[2] == int(b2["minimum_drones"])
print("Plotted values match checkpoints:")
print("  geographic : %d hubs (LSCP at R=%g km)" % (hubs[0], SERVICE_RANGE_KM))
print("  operational: %d hubs, %d drones" % (hubs[1], drones[1]))
print("  resilient  : %d hubs, %d drones" % (hubs[2], drones[2]))
print("  hub increase geographic -> operational: +%.1f%%"
      % (100 * (hubs[1] - hubs[0]) / hubs[0]))
print("  hub increase operational -> resilient : +%.1f%%"
      % (100 * (hubs[2] - hubs[1]) / hubs[1]))
print("  drone increase operational -> resilient: +%.1f%%"
      % (100 * (drones[2] - drones[1]) / drones[1]))
