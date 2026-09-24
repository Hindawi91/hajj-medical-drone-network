# %% [markdown]
# # 09 - Geographic Benchmark Publication Results (V1)
#
# **Solver-free publication layer for the classical facility-location benchmarks.**
#
# This notebook does **not** invoke Pyomo or HiGHS and does not rerun any optimization.
# It reads the saved Notebook 05 checkpoints in
# `data/model/optimization_solutions/` and produces:
#
# 1. the geographic benchmark performance figure
#    (panel a: p-median weighted mean + p-center worst case vs p;
#     panel b: MCLP 5-km coverage vs p);
# 2. an analytical map of the LSCP three-hub / 5-km solution;
# 3. an interactive Folium map with actual facility names, analytical zones,
#    and 5-km service circles;
# 4. a selected-hub CSV carrying exact facility metadata;
# 5. a two-panel composite matching `fig:geographic_benchmark` in the manuscript.
#
# All facility names, coordinates, and metrics are read from CSV. Nothing is hardcoded.

# %%
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent

MODEL_DIR = ROOT / "data" / "model"
PROCESSED_DIR = ROOT / "data" / "processed"
NB05_DIR = MODEL_DIR / "optimization_solutions"
NB07_DIR = MODEL_DIR / "operational_resilient_solutions_v4"
PAPER_FIG_DIR = ROOT / "paper" / "figures"
FIG_DIR = ROOT / "outputs" / "figures" / "geographic_paper_v1"
MAP_DIR = ROOT / "outputs" / "maps" / "geographic_paper_v1"
TABLE_DIR = ROOT / "outputs" / "reports" / "geographic_paper_v1"

for d in (FIG_DIR, MAP_DIR, TABLE_DIR):
    d.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "figure.dpi": 120,
})

# Local UTM zone for metric buffering around Makkah.
UTM_CRS = 32637
SERVICE_RANGE_KM = 5.0


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
# ## 1. Load Notebook 05 checkpoints

# %%
run_summary = rd(NB05_DIR / "optimization_run_summary_v1.csv")
cross_model = rd(NB05_DIR / "optimization_cross_model_summary_v1.csv")
selected_hubs = rd(NB05_DIR / "optimization_selected_hubs_v1.csv")
mclp_coverage = rd(NB05_DIR / "optimization_mclp_coverage_v1.csv")
uncoverable = rd(NB05_DIR / "optimization_lscp_uncoverable_points_v1.csv")

print("run_summary   :", run_summary.shape)
print("cross_model   :", cross_model.shape)
print("selected_hubs :", selected_hubs.shape)
print("mclp_coverage :", mclp_coverage.shape)
print("uncoverable   :", uncoverable.shape)

# p-median was run in two variants: unrestricted assignment (range_km is NaN) and
# assignment restricted to a 5-km service range (range_km == 5.0). The cross-model
# summary and the manuscript table use the UNRESTRICTED variant, so select it
# explicitly rather than relying on row order.
pmed_unrestricted = run_summary[
    (run_summary["model"] == "p-median") & (run_summary["range_km"].isna())
]
pmed_restricted = run_summary[
    (run_summary["model"] == "p-median") & (run_summary["range_km"] == SERVICE_RANGE_KM)
]
print("\np-median unrestricted runs:", len(pmed_unrestricted),
      "| 5-km-restricted runs:", len(pmed_restricted))

# %% [markdown]
# ## 2. Verify the LSCP solution against the checkpoints
#
# The principal geographic benchmark is the minimum-hub solution giving complete
# coverage at a 5-km service range. It is read, not assumed.

# %%
lscp_runs = run_summary[run_summary["model"] == "LSCP"].copy()
print("LSCP runs by service range:")
print(lscp_runs[["range_km", "p", "termination", "uncoverable_points"]].to_string(index=False))

lscp_5km = lscp_runs[lscp_runs["range_km"] == SERVICE_RANGE_KM].iloc[0]
n_hubs_lscp = int(lscp_5km["p"])
print("\nPrincipal benchmark: %d hubs at R = %g km" % (n_hubs_lscp, SERVICE_RANGE_KM))
print("Termination:", lscp_5km["termination"])
print("Hub ids from run summary:", lscp_5km["selected_hubs"])

benchmark_hubs = selected_hubs[
    (selected_hubs["model"] == "LSCP")
    & (selected_hubs["range_km"] == SERVICE_RANGE_KM)
].copy().sort_values("hub_id").reset_index(drop=True)

# Cross-check that the two checkpoint files agree on hub identity.
ids_from_summary = sorted(str(lscp_5km["selected_hubs"]).split(";"))
ids_from_hubs = sorted(benchmark_hubs["hub_id"].tolist())
assert ids_from_summary == ids_from_hubs, (ids_from_summary, ids_from_hubs)
assert len(benchmark_hubs) == n_hubs_lscp
print("\nRun summary and selected-hub checkpoints agree on hub identity.")

# %% [markdown]
# ## 3. Attach full candidate-hub metadata
#
# `optimization_selected_hubs_v1.csv` carries the solver's view of each facility. The
# candidate-hub table supplies the remaining facility metadata. The documented
# English-name override table covers facilities whose OSM record has no `name:en`
# tag (currently HUB_007 only).

# %%
candidates = rd(MODEL_DIR / "candidate_drone_hubs_v1.csv")
overrides = rd(PROCESSED_DIR / "hub_name_en_overrides_v1.csv")

meta_cols = [
    "hub_id", "name", "name_en", "display_name", "category",
    "hajj_zone", "latitude", "longitude",
    "demand_cells_within_5km", "proxy_coverage_share_5km",
]
drop_dupes = [c for c in ("hub_name", "hub_category", "hajj_zone", "latitude", "longitude")
              if c in benchmark_hubs.columns]
benchmark_hubs = benchmark_hubs.drop(columns=drop_dupes).merge(
    candidates[meta_cols], on="hub_id", how="left", validate="one_to_one")

# Publication label: prefer OSM name:en, then the documented override, then OSM name.
ov = dict(zip(overrides["hub_id"], overrides["name_en_override"]))


def has_en(value):
    return isinstance(value, str) and value.strip() != ""


# Precedence: curated override first, then OSM name:en, then the OSM name. The override
# must win over name:en because some records carry a name:en that exists but is an
# unusable raw transliteration (e.g. HUB_035's "MarkazSihhiMawsimiRaqmSittat`Ashar").
benchmark_hubs["facility_label"] = [
    ov.get(r["hub_id"]) or (r["name_en"] if has_en(r["name_en"]) else r["name"])
    for _, r in benchmark_hubs.iterrows()
]
benchmark_hubs["label_source"] = [
    "author_override" if r["hub_id"] in ov
    else ("osm_name_en" if has_en(r["name_en"]) else "osm_name")
    for _, r in benchmark_hubs.iterrows()
]

print(benchmark_hubs[
    ["hub_id", "facility_label", "label_source", "category", "hajj_zone",
     "latitude", "longitude"]
].to_string(index=False))

# %% [markdown]
# ## Deliverable 4. Selected-hub CSV with exact metadata

# %%
export_cols = [
    "hub_id", "facility_label", "label_source", "name", "name_en",
    "category", "hajj_zone", "latitude", "longitude",
    "demand_cells_within_5km", "proxy_coverage_share_5km",
]
benchmark_table = benchmark_hubs[export_cols].copy()
benchmark_table.insert(0, "model", "LSCP")
benchmark_table.insert(1, "service_range_km", SERVICE_RANGE_KM)

out_csv = TABLE_DIR / "table_geographic_benchmark_selected_hubs_v1.csv"
benchmark_table.to_csv(out_csv, index=False, encoding="utf-8-sig")
print("Saved:", out_csv)
print(benchmark_table.to_string(index=False))

# %% [markdown]
# ## Deliverable 1. Geographic benchmark performance figure
#
# Panel (a) reports distance-based accessibility: the proxy-weighted p-median mean
# assignment distance and the p-center worst-case distance against p.
# Panel (b) reports the MCLP proxy-weighted coverage share at a 5-km service range.
#
# Values come from `optimization_cross_model_summary_v1.csv`, the same source as the
# manuscript table, so figure and table cannot drift apart.

# %%
cm = cross_model.sort_values("p").reset_index(drop=True)

pmed_uniform = pmed_unrestricted[
    pmed_unrestricted["demand_scenario"] == "uniform"].sort_values("p")
mclp_uniform = run_summary[
    (run_summary["model"] == "MCLP")
    & (run_summary["demand_scenario"] == "uniform")
    & (run_summary["range_km"] == SERVICE_RANGE_KM)
].sort_values("p")

fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.9))

ax = axes[0]
ax.plot(cm["p"], cm["pmedian_proxy_weighted_mean_km"], marker="o", lw=1.8,
        color="tab:blue", label="p-median, proxy-weighted mean")
ax.plot(pmed_uniform["p"], pmed_uniform["weighted_mean_distance_km"], marker="s",
        ms=4, lw=1.1, ls="--", color="tab:blue", alpha=.55,
        label="p-median, uniform mean")
ax.plot(cm["p"], cm["pcenter_worst_km"], marker="^", lw=1.8,
        color="tab:red", label="p-center, worst case")
ax.axhline(SERVICE_RANGE_KM, color="0.45", lw=1.0, ls=":")
ax.text(10.2, SERVICE_RANGE_KM + .18, "%g-km service range" % SERVICE_RANGE_KM,
        ha="right", va="bottom", fontsize=7.5, color="0.35")
ax.axvline(n_hubs_lscp, color="tab:green", lw=1.0, ls="-.", alpha=.8)
# Sits in the empty strip just above the x-axis, right of the benchmark line:
# the only region that clears both the legend and the p-center curve.
ax.text(n_hubs_lscp + .15, .4, "LSCP benchmark (%d hubs)" % n_hubs_lscp,
        fontsize=7.5, color="tab:green", va="bottom", ha="left")
ax.set_xlabel("Number of hubs, $p$")
ax.set_ylabel("Assignment distance (km)")
ax.set_title("(a) Distance-based accessibility")
ax.set_xticks(cm["p"])
ax.set_ylim(0, 14.4)
ax.grid(alpha=.25, lw=.6)
ax.legend(loc="upper right", framealpha=.92)

ax = axes[1]
ax.plot(cm["p"], cm["mclp_proxy_coverage_5km_pct"], marker="o", lw=1.8,
        color="tab:purple", label="MCLP, proxy-weighted")
ax.plot(mclp_uniform["p"], mclp_uniform["weighted_coverage_pct"], marker="s",
        ms=4, lw=1.1, ls="--", color="tab:purple", alpha=.55,
        label="MCLP, uniform")
ax.axhline(100, color="0.45", lw=1.0, ls=":")
ax.axvline(n_hubs_lscp, color="tab:green", lw=1.0, ls="-.", alpha=.8)
ax.text(n_hubs_lscp + .18, 52, "complete coverage\nfrom $p=%d$" % n_hubs_lscp,
        fontsize=7.5, color="tab:green", va="top")
# Annotate only the sub-saturation points; p >= 3 is already labelled by the
# benchmark line, and a label at 100% would collide with the gridline.
for _, r in cm.iterrows():
    if r["p"] <= 2:
        ax.annotate("%.1f%%" % r["mclp_proxy_coverage_5km_pct"],
                    (r["p"], r["mclp_proxy_coverage_5km_pct"]),
                    textcoords="offset points", xytext=(8, 7),
                    ha="left", fontsize=7.5, color="tab:purple",
                    fontweight="bold")
ax.set_xlabel("Number of hubs, $p$")
ax.set_ylabel("Demand covered within %g km (%%)" % SERVICE_RANGE_KM)
ax.set_title("(b) Coverage at a %g-km service range" % SERVICE_RANGE_KM)
ax.set_xticks(cm["p"])
ax.set_ylim(30, 105)
ax.grid(alpha=.25, lw=.6)
ax.legend(loc="lower right", framealpha=.92)

fig.tight_layout()
savefig(fig, "fig_geographic_benchmark_performance_v1")
plt.close(fig)

# %% [markdown]
# ## 4. Load spatial layers for the maps

# %%
zones = gpd.read_file(PROCESSED_DIR / "hajj_analytical_zones_v1.gpkg").to_crs(4326)
demand_grid = gpd.read_file(PROCESSED_DIR / "hajj_demand_locations_500m_v1.gpkg").to_crs(4326)

ZONE_COLORS = {
    "Haram_Makkah": "tab:blue",
    "Mina": "tab:green",
    "Muzdalifah": "tab:purple",
    "Arafat": "tab:red",
}

hubs_gdf = gpd.GeoDataFrame(
    benchmark_hubs,
    geometry=gpd.points_from_xy(benchmark_hubs["longitude"], benchmark_hubs["latitude"]),
    crs=4326,
)

# Geodesic 5-km service areas, buffered in a metric CRS.
service_areas = hubs_gdf.to_crs(UTM_CRS).copy()
service_areas["geometry"] = service_areas.buffer(SERVICE_RANGE_KM * 1000)
service_areas = service_areas.to_crs(4326)

# Independent check: every demand cell centroid inside at least one service circle.
cover_union = service_areas.to_crs(UTM_CRS).union_all()
inside = demand_grid.to_crs(UTM_CRS).geometry.centroid.within(cover_union)
print("Demand cells covered by the %d-hub / %g-km solution: %d / %d"
      % (n_hubs_lscp, SERVICE_RANGE_KM, int(inside.sum()), len(demand_grid)))
print("Independent geometric check reproduces complete coverage:", bool(inside.all()))


def zone_boundaries(ax, label=False):
    for _, row in zones.iterrows():
        gpd.GeoSeries([row.geometry], crs=zones.crs).boundary.plot(
            ax=ax, color=ZONE_COLORS.get(row["zone"], "0.4"), linewidth=1.4)
        if label:
            txt = ax.annotate(
                row["zone"].replace("_", " "),
                (row["longitude"], row["latitude"] + row["radius_m"] / 111000.0 * 1.04),
                ha="center", va="bottom", fontsize=7.5,
                color=ZONE_COLORS.get(row["zone"], "0.4"), fontweight="bold")
            txt.set_path_effects([pe.withStroke(linewidth=2, foreground="white")])


# %% [markdown]
# ## Deliverable 2. Analytical map of the LSCP three-hub / 5-km solution

# %%
def draw_analytical(ax, show_key=True, colorbar=True):
    # The proxy weights are strongly right-skewed: most cells sit near the
    # 1.0 floor, so a plain linear ramp at low alpha renders the surface almost
    # invisible. Full opacity plus a power-law norm keeps the low end legible
    # while still separating the high-activity cells.
    demand_layer = demand_grid.plot(
        ax=ax, column="proxy_demand_weight", cmap="YlGnBu",
        norm=matplotlib.colors.PowerNorm(gamma=.55, vmin=1, vmax=5),
        linewidth=.04, edgecolor="0.75", alpha=.95)
    if colorbar:
        sm = plt.cm.ScalarMappable(
            cmap="YlGnBu",
            norm=matplotlib.colors.PowerNorm(gamma=.55, vmin=1, vmax=5))
        cb = ax.get_figure().colorbar(sm, ax=ax, fraction=.036, pad=.02,
                                      ticks=[1, 2, 3, 4, 5])
        cb.set_label("Proxy demand weight $w_i$", fontsize=8)
        cb.ax.tick_params(labelsize=7.5)
    zone_boundaries(ax, label=True)

    service_areas.boundary.plot(ax=ax, color="tab:orange", linewidth=1.5,
                                linestyle="--", alpha=.95)
    service_areas.plot(ax=ax, color="tab:orange", alpha=.055)

    for k, (_, h) in enumerate(hubs_gdf.iterrows(), start=1):
        ax.scatter(h["longitude"], h["latitude"], s=330, marker="*",
                   color="black", edgecolors="white", linewidths=1.1, zorder=5)
        ax.annotate(str(k), (h["longitude"], h["latitude"]), ha="center", va="center",
                    fontsize=8.5, fontweight="bold", color="white", zorder=6)

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    handles = [
        Line2D([0], [0], marker="*", color="black", linestyle="None", markersize=13,
               markeredgecolor="white", label="Selected hub"),
        Line2D([0], [0], color="tab:orange", lw=1.5, ls="--",
               label="%g-km service area" % SERVICE_RANGE_KM),
        Patch(facecolor="#41b6c4", alpha=.95, label="Proxy demand (500 m cells)"),
    ]
    ax.legend(handles=handles, loc="lower left", framealpha=.93)

    if show_key:
        key = "    ".join(
            "%d=%s %s" % (k, r["hub_id"], r["facility_label"])
            for k, (_, r) in enumerate(hubs_gdf.iterrows(), start=1))
        ax.text(.5, -.115, key, transform=ax.transAxes, ha="center", va="top",
                fontsize=7.2)


fig, ax = plt.subplots(figsize=(7.6, 6.4))
draw_analytical(ax)
ax.set_title("LSCP benchmark: %d hubs, complete coverage within %g km"
             % (n_hubs_lscp, SERVICE_RANGE_KM))
fig.tight_layout()
savefig(fig, "fig_geographic_benchmark_3hub_analytical_v1")
plt.close(fig)

# %% [markdown]
# ## Deliverable 3. Interactive Folium map
#
# Actual facility names, analytical Hajj zones, the proxy-demand surface, and
# 5-km service circles. Intended for the public repository and as the geographic
# reference for the composite figure.

# %%
import folium
from branca.element import Element

m = folium.Map(
    location=[float(hubs_gdf["latitude"].mean()), float(hubs_gdf["longitude"].mean())],
    zoom_start=11, control_scale=True,
)

zg = folium.FeatureGroup(name="Hajj analytical zones", show=True).add_to(m)
for _, r in zones.iterrows():
    c = ZONE_COLORS.get(r["zone"], "#777777")
    folium.GeoJson(
        r.geometry.__geo_interface__,
        style_function=lambda feature, c=c: {
            "color": c, "weight": 2, "fillColor": c, "fillOpacity": .05},
        tooltip="%s (%g km analytical radius)"
                % (r["zone"].replace("_", " "), r["radius_m"] / 1000.0),
    ).add_to(zg)

dg = folium.FeatureGroup(name="Proxy-demand cells", show=True).add_to(m)
for _, r in demand_grid.iterrows():
    w = float(r["proxy_demand_weight"])
    opacity = .08 + .35 * (w - 1) / 4
    folium.GeoJson(
        r.geometry.__geo_interface__,
        style_function=lambda feature, opacity=opacity: {
            "color": "#777777", "weight": .25,
            "fillColor": "#555555", "fillOpacity": opacity},
        tooltip="%s | proxy weight %.2f" % (r["demand_point_id"], w),
    ).add_to(dg)

sg = folium.FeatureGroup(name="%g-km service areas" % SERVICE_RANGE_KM,
                         show=True).add_to(m)
for _, r in service_areas.iterrows():
    folium.GeoJson(
        r.geometry.__geo_interface__,
        style_function=lambda feature: {
            "color": "#e8791a", "weight": 2, "dashArray": "6,4",
            "fillColor": "#e8791a", "fillOpacity": .06},
        tooltip="%s: %g-km service area" % (r["hub_id"], SERVICE_RANGE_KM),
    ).add_to(sg)

hg = folium.FeatureGroup(name="Selected benchmark hubs", show=True).add_to(m)
for _, h in hubs_gdf.iterrows():
    popup_html = (
        "<b>%s</b><br>%s<br>OSM name: %s<br>Category: %s<br>Zone: %s<br>"
        "Coordinates: %.5f, %.5f"
        % (h["hub_id"], h["facility_label"], h["name"], h["category"],
           str(h["hajj_zone"]).replace("_", " "), h["latitude"], h["longitude"])
    )
    folium.CircleMarker(
        [h["latitude"], h["longitude"]],
        radius=9, color="#111111", weight=1.4,
        fill=True, fill_color="#111111", fill_opacity=.85,
        tooltip="%s: %s" % (h["hub_id"], h["facility_label"]),
        popup=folium.Popup(popup_html, max_width=360),
    ).add_to(hg)

folium.LayerControl(collapsed=False).add_to(m)

legend_html = (
    '<div style="position:fixed;bottom:30px;left:30px;z-index:9999;'
    'background:white;border:2px solid #777;border-radius:6px;'
    'padding:10px 14px;font-size:12px">'
    "<b>Geographic benchmark (LSCP)</b><br>"
    "%d active hubs<br>Complete coverage within %g km<br>"
    "Dashed circles = %g-km service areas</div>"
    % (n_hubs_lscp, SERVICE_RANGE_KM, SERVICE_RANGE_KM)
)
m.get_root().html.add_child(Element(legend_html))

folium_path = MAP_DIR / ("geographic_benchmark_%dhub_%gkm_folium.html"
                         % (n_hubs_lscp, SERVICE_RANGE_KM))
m.save(folium_path)
print("Saved:", folium_path)

# %% [markdown]
# ## Deliverable 5. Composite figure for the manuscript
#
# The manuscript's `fig:geographic_benchmark` is described as a geographic panel plus
# an analytical panel. The geographic panel uses a contextily basemap so the figure is
# reproducible without a manual browser capture. If tile download is unavailable the
# panel degrades to a plain background and the run still completes.

# %%
fig, axes = plt.subplots(1, 2, figsize=(13.2, 6.0))

ax = axes[0]
hubs_3857 = hubs_gdf.to_crs(3857)
zones_3857 = zones.to_crs(3857)
svc_3857 = service_areas.to_crs(3857)

svc_3857.boundary.plot(ax=ax, color="tab:orange", lw=1.6, ls="--", alpha=.95)
svc_3857.plot(ax=ax, color="tab:orange", alpha=.07)
for _, row in zones_3857.iterrows():
    gpd.GeoSeries([row.geometry], crs=3857).boundary.plot(
        ax=ax, color=ZONE_COLORS.get(row["zone"], "0.4"), lw=1.6)
# Hub numbers only: the facility key printed beneath the figure carries the names,
# so inline name labels here would collide with the service circles.
for k, (_, h) in enumerate(hubs_3857.iterrows(), start=1):
    ax.scatter(h.geometry.x, h.geometry.y, s=340, marker="*", color="black",
               edgecolors="white", linewidths=1.2, zorder=5)
    ax.annotate(str(k), (h.geometry.x, h.geometry.y), ha="center", va="center",
                fontsize=9, fontweight="bold", color="white", zorder=6)

# Basemap provider choice, verified by fetching real tiles for this bounding box:
#   - CartoDB.*            now requires an API key and stamps "API KEY REQUIRED"
#                          across every tile when none is supplied.
#   - OpenStreetMap.Mapnik blocks contextily's default user agent and returns a
#                          403 "Access blocked" notice *as an image*, so it never
#                          raises and would silently ship a broken figure.
# Esri serves keyless tiles for this extent. WorldTopoMap carries the place names
# that make the panel legible as geographic context; WorldGrayCanvas is the
# low-clutter fallback.
basemap_ok = False
try:
    import contextily as cx
    providers = [
        ("Esri.WorldTopoMap", cx.providers.Esri.WorldTopoMap),
        ("Esri.WorldGrayCanvas", cx.providers.Esri.WorldGrayCanvas),
    ]
    for label, source in providers:
        try:
            cx.add_basemap(ax, source=source, attribution_size=5)
            print("Basemap provider:", label)
            basemap_ok = True
            break
        except Exception as exc:
            print("  provider %s failed: %s" % (label, type(exc).__name__))
except Exception as exc:
    print("contextily unavailable:", type(exc).__name__, exc)

if not basemap_ok:
    print("No basemap tiles; using plain background.")
    ax.set_facecolor("#f4f4f2")

ax.set_axis_off()
ax.set_title("(a) Geographic setting")

ax = axes[1]
draw_analytical(ax, show_key=False)
ax.set_title("(b) Analytical demand grid and service areas")

key = "        ".join(
    "%d. %s - %s (%s)" % (k, r["hub_id"], r["facility_label"],
                          str(r["hajj_zone"]).replace("_", " "))
    for k, (_, r) in enumerate(hubs_gdf.iterrows(), start=1))
fig.text(.5, .015, key, ha="center", va="bottom", fontsize=8.2)
fig.tight_layout(rect=(0, .045, 1, 1))
savefig(fig, "fig_geographic_benchmark_3hub_composite_v1",
        also_paper="fig_geographic_benchmark_3hub")
plt.close(fig)
print("Basemap tiles used:", basemap_ok)

# %% [markdown]
# ## 5. Reproducibility summary of the reported Section 4.1 numbers

# %%
check = cm.rename(columns={
    "pmedian_proxy_weighted_mean_km": "p-median weighted mean (km)",
    "pcenter_worst_km": "p-center worst case (km)",
    "mclp_proxy_coverage_5km_pct": "MCLP 5-km coverage (%)",
}).round({"p-median weighted mean (km)": 3,
          "p-center worst case (km)": 3,
          "MCLP 5-km coverage (%)": 2})
out = TABLE_DIR / "table_geographic_benchmark_performance_v1.csv"
check.to_csv(out, index=False, encoding="utf-8-sig")
print("Saved:", out)
print(check.to_string(index=False))

n_uncov = int(lscp_runs[lscp_runs["range_km"] == 2.5]["uncoverable_points"].iloc[0])
print("\nLSCP at 2.5 km: infeasible, %d of %d cells uncoverable (%d rows in checkpoint)."
      % (n_uncov, len(demand_grid), len(uncoverable)))
print("LSCP minimum hubs by service range:")
print(lscp_runs[["range_km", "p", "termination"]].to_string(index=False))
