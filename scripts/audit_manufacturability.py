"""Reproduce geometry-only manufacturing-clearance checks; never starts FDTD.

Run with the analysis Python environment (NumPy and Matplotlib):
  python scripts/audit_manufacturability.py --generator-dir D:/projects/Deta_Generator2.0

The tolerance levels are proposed investigations, not measured process capability.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
from dataclasses import replace
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle
import numpy as np


REPORT_ROOT = Path(__file__).resolve().parents[1] / "reports/2026-10-18_device_feasibility"
QUADRANTS = ("III", "II", "IV", "I")
OFFSETS = tuple((x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x, y) != (0, 0))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def polygon_distance_batch(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Exact Euclidean distance for batches of disjoint convex polygon boundaries.

    Inputs are (N, vertices, 2). For accepted generator geometries polygons are
    disjoint. Overlap needs a separate SAT check, as used for tapered variants.
    """
    def directed(points, polygon):
        edges = np.roll(polygon, -1, axis=1) - polygon
        delta = points[:, :, None, :] - polygon[:, None, :, :]
        t = np.clip(np.sum(delta * edges[:, None, :, :], axis=-1)
                    / np.sum(edges * edges, axis=-1)[:, None, :], 0, 1)
        distances = np.linalg.norm(delta - t[:, :, :, None] * edges[:, None, :, :], axis=-1)
        return distances.min(axis=(1, 2))
    return np.minimum(directed(a, b), directed(b, a))


def closest_points(a, b):
    """Distance and the two closest points, for plotting nonoverlapping polygons."""
    result = (float("inf"), None, None)
    for reverse, (points, polygon) in enumerate(((a, b), (b, a))):
        for point in points:
            for start, end in zip(polygon, np.roll(polygon, -1, axis=0)):
                edge = end - start
                t = np.clip(np.dot(point - start, edge) / np.dot(edge, edge), 0, 1)
                foot = start + t * edge
                distance = float(np.linalg.norm(point - foot))
                if distance < result[0]:
                    result = (distance, foot, point) if reverse else (distance, point, foot)
    return result


def audit_plan(geometries):
    vertices = np.asarray([g.vertices() for g in geometries])
    periods = np.asarray([g.p for g in geometries])
    intra = np.minimum.reduce([polygon_distance_batch(vertices[:, i], vertices[:, j])
                              for i in range(4) for j in range(i)])
    periodic = np.full(len(geometries), np.inf)
    for ix, iy in OFFSETS:
        shift = periods[:, None, None] * np.asarray([ix, iy])[None, None, :]
        for i in range(4):
            for j in range(4):
                periodic = np.minimum(periodic, polygon_distance_batch(vertices[:, i], vertices[:, j] + shift))
    margins_xy = periods[:, None] / 2 - np.abs(vertices).max(axis=(1, 2))
    return vertices, intra, periodic, margins_xy


def all_pairs_single(vertices, period):
    pairs = []
    for i in range(4):
        for j in range(i):
            distance, point_a, point_b = closest_points(vertices[i], vertices[j])
            pairs.append({"kind": "same_cell", "i": i, "j": j, "shift": (0, 0),
                          "distance": distance, "point_a": point_a, "point_b": point_b})
    for ix, iy in OFFSETS:
        for i in range(4):
            for j in range(4):
                other = vertices[j] + np.asarray([ix, iy]) * period
                distance, point_a, point_b = closest_points(vertices[i], other)
                pairs.append({"kind": "neighbor_cell", "i": i, "j": j, "shift": (ix, iy),
                              "distance": distance, "point_a": point_a, "point_b": point_b})
    return pairs


def statistics(values):
    return {"minimum": float(np.min(values)), "percentile_1": float(np.quantile(values, .01)),
            "percentile_5": float(np.quantile(values, .05)), "median": float(np.median(values)),
            "maximum": float(np.max(values))}


def pair_record(pair):
    return {"quadrants": [QUADRANTS[pair["i"]], QUADRANTS[pair["j"]]],
            "neighbor_translation_in_periods": list(pair["shift"]),
            "minimum_gap_nm": pair["distance"],
            "closest_points_nm": [pair["point_a"].tolist(), pair["point_b"].tolist()]}


def sidewall_audit(geometry, geometry_class, angles):
    top = np.asarray(geometry.vertices())
    centers = np.asarray(geometry.centers())[:, None, :]
    result = []
    for angle in angles:
        bottom_l = geometry.l + 2 * geometry.h * np.tan(np.deg2rad(angle))
        # This is a fabricated CD/taper perturbation: the centers remain fixed.
        bottom = (top - centers) * (bottom_l / geometry.l) + centers
        overlaps = any(geometry_class.polygons_touch(bottom[i], bottom[j])
                       for i in range(4) for j in range(i))
        intra = min(polygon_distance_batch(bottom[i][None, :, :], bottom[j][None, :, :])[0]
                    for i in range(4) for j in range(i)) if not overlaps else 0.0
        periodic_overlap = False
        periodic = float("inf")
        for ix, iy in OFFSETS:
            shift = np.asarray([ix, iy]) * geometry.p
            for i in range(4):
                for j in range(4):
                    other = bottom[j] + shift
                    touch = geometry_class.polygons_touch(bottom[i], other)
                    periodic_overlap |= touch
                    distance = 0 if touch else polygon_distance_batch(bottom[i][None], other[None])[0]
                    periodic = min(periodic, distance)
        result.append({"sidewall_angle_from_vertical_deg": float(angle),
                       "bottom_side_length_nm": float(bottom_l),
                       "bottom_width_increase_nm": float(bottom_l - geometry.l),
                       "minimum_intra_cell_bottom_gap_nm": float(intra),
                       "minimum_periodic_bottom_gap_nm": float(periodic),
                       "minimum_global_bottom_gap_nm": float(min(intra, periodic)),
                       "same_cell_overlap_or_touch": bool(overlaps),
                       "periodic_overlap_or_touch": bool(periodic_overlap)})
    return result


def draw_cell(ax, geometry, vertices, title):
    colors = ("#27659A", "#DA7948", "#DA7948", "#27659A")
    for shift in OFFSETS:
        for v in vertices:
            ax.add_patch(Polygon(v + np.asarray(shift) * geometry.p, facecolor="#E1E5E8",
                                 edgecolor="#AFB8BF", lw=.6))
    for i, (v, color) in enumerate(zip(vertices, colors)):
        ax.add_patch(Polygon(v, facecolor=color, alpha=.85, edgecolor="#1F2933", lw=.8))
        ax.text(*geometry.centers()[i], QUADRANTS[i], color="white", ha="center", va="center", fontsize=11,
                clip_on=True)
    ax.add_patch(Rectangle((-geometry.p / 2, -geometry.p / 2), geometry.p, geometry.p,
                           fill=False, edgecolor="#3E4850", lw=1, linestyle="--"))
    ax.set(xlabel="x (nm)", ylabel="y (nm)", title=title)
    ax.set_aspect("equal")
    ax.grid(alpha=.15)


def plot_clearance(path, sample, sample_vertices, risk, risk_vertices, risk_index):
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    draw_cell(axes[0], sample, sample_vertices, "Reported sample: actual rotated geometry")
    closest = min(all_pairs_single(sample_vertices, sample.p), key=lambda r: r["distance"])
    a, b = closest["point_a"], closest["point_b"]
    axes[0].plot([a[0], b[0]], [a[1], b[1]], "k.-", lw=2)
    axes[0].annotate(f"Minimum gap: {closest['distance']:.2f} nm", (a + b) / 2,
                     xytext=(25, 60), textcoords="offset points", arrowprops={"arrowstyle": "->"}, fontsize=11)
    axes[0].set_xlim(-sample.p * .55, sample.p * .55)
    axes[0].set_ylim(-sample.p * .55, sample.p * .55)
    draw_cell(axes[1], risk, risk_vertices, f"Plan candidate {risk_index}: narrowest periodic opening")
    narrow = min(all_pairs_single(risk_vertices, risk.p), key=lambda r: r["distance"])
    a, b = narrow["point_a"], narrow["point_b"]
    mid = (a + b) / 2
    axes[1].plot([a[0], b[0]], [a[1], b[1]], "k.-", lw=2)
    axes[1].set_xlim(mid[0] - 65, mid[0] + 65)
    axes[1].set_ylim(mid[1] - 65, mid[1] + 65)
    axes[1].annotate(f"{narrow['distance']:.3f} nm", mid, xytext=(10, 40), textcoords="offset points",
                     arrowprops={"arrowstyle": "->"}, fontsize=12, bbox={"facecolor": "white", "alpha": .9, "edgecolor": "none"})
    fig.suptitle("Geometry clearance audit | no FDTD or fabrication experiment", fontsize=16)
    fig.text(.5, .015, "Blue: odd quadrants; orange: even quadrants; gray: periodic replicas. Dashed line: cell boundary.",
             ha="center", fontsize=10)
    fig.tight_layout(rect=(0, .05, 1, .94))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_distribution(path, intra, periodic, seed):
    global_gap = np.minimum(intra, periodic)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    bins = np.arange(0, 251, 10)
    axes[0].hist(intra, bins, histtype="step", lw=2, label="Same-cell minimum")
    axes[0].hist(periodic, bins, histtype="step", lw=2, label="Neighbor-cell minimum")
    axes[0].set(xlabel="Minimum edge-to-edge gap (nm)", ylabel="Candidate count", title="Two distinct clearance checks")
    axes[0].legend()
    sorted_gap = np.sort(global_gap)
    axes[1].plot(sorted_gap, np.arange(1, len(global_gap) + 1) / len(global_gap) * 100, lw=2)
    for threshold, color in ((20, "#B64834"), (40, "#8D7137"), (50, "#56806C")):
        count = int(np.sum(global_gap < threshold))
        axes[1].axvline(threshold, color=color, ls="--", alpha=.8,
                        label=f"<{threshold} nm: {count}/{len(global_gap)}")
    axes[1].set(xlabel="Global minimum gap (nm)", ylabel="Candidates at or below gap (%)",
                title=f"Minimum = {sorted_gap[0]:.3f} nm", xlim=(0, 150), ylim=(0, 100))
    axes[1].legend(loc="lower right")
    for ax in axes:
        ax.grid(alpha=.2)
    fig.suptitle(f"First {len(global_gap)} valid geometries | seed {seed} | geometry only", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, .93))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_sidewall(path, rows, sample):
    angle = [r["sidewall_angle_from_vertical_deg"] for r in rows]
    gap = [r["minimum_global_bottom_gap_nm"] for r in rows]
    delta_l = [r["bottom_width_increase_nm"] for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].plot(angle, gap, "o-", ms=3, lw=2, color="#27659A")
    for threshold in (20, 30):
        axes[0].axhline(threshold, ls="--", lw=1, alpha=.7, label=f"Proposed {threshold} nm check")
    axes[0].set(xlabel="Outward sidewall angle from vertical (deg)", ylabel="Minimum bottom edge gap (nm)",
                title="Same centers; top square size held fixed", ylim=(-2, 60))
    axes[0].legend(fontsize=9)
    axes[1].plot(angle, delta_l, lw=2, color="#DA7948")
    axes[1].set(xlabel="Outward sidewall angle from vertical (deg)", ylabel="Bottom width increase (nm)",
                title="Bottom L = top L + 2 H tan(angle)")
    for ax in axes:
        ax.grid(alpha=.2)
    fig.suptitle(f"Hypothetical sidewall sensitivity | L(top)={sample.l:.2f} nm, H={sample.h:.2f} nm", fontsize=15)
    fig.text(.5, .015, "Suggested test angles; not measured process capability. Zero gap indicates contact/overlap.",
             ha="center", fontsize=10)
    fig.tight_layout(rect=(0, .05, 1, .93))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generator-dir", type=Path, required=True)
    parser.add_argument("--sample-count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261011)
    parser.add_argument("--report-dir", type=Path, default=REPORT_ROOT)
    args = parser.parse_args()
    generator = args.generator_dir.resolve()
    config_path = generator / "src/deta_generator2/assets/configs/as2se3_au_fine8.json"
    source_path = generator / "src/deta_generator2/config.py"
    sys.path.insert(0, str(generator / "src"))
    module = importlib.import_module("deta_generator2.config")
    cfg = replace(module.load_config(config_path), sample_count=args.sample_count, seed=args.seed)
    geometries = cfg.sample_geometries()
    vertices, intra, periodic, margins = audit_plan(geometries)
    global_gap = np.minimum(intra, periodic)
    square = np.asarray([[0., 0.], [1., 0.], [1., 1.], [0., 1.]])
    analytical_checks = [
        (float(polygon_distance_batch(square[None], (square + [4, 0])[None])[0]), 3.),
        (float(polygon_distance_batch(square[None], (square + [4, 5])[None])[0]), 5.),
    ]
    if not all(np.isclose(actual, expected, rtol=0, atol=1e-10) for actual, expected in analytical_checks):
        raise AssertionError("Polygon distance kernel failed analytical clearance checks")
    sample = geometries[0]
    sample_pairs = all_pairs_single(vertices[0], sample.p)
    source_npz = (args.report_dir.parent / "2026-10-18_topmetal_thick_substrate/data/pml_topmetal_sample0.npz")
    report_sample_provenance = None
    if source_npz.exists():
        with np.load(source_npz, allow_pickle=False) as data:
            saved_geometry = data["geometry_values"]
        if not np.allclose(cfg.geometry_values(sample), saved_geometry, rtol=0, atol=1e-8):
            raise ValueError("The existing reported sample does not match the first seeded geometry")
        report_sample_provenance = {"path_relative_to_report_repo": str(source_npz.relative_to(args.report_dir.parents[1])).replace("\\", "/"),
                                    "sha256": sha256(source_npz), "geometry_match_atol_nm_or_deg": 1e-8}
    risk_index = int(np.argmin(global_gap))
    for index in (0, risk_index):
        independently_computed_minimum = min(p["distance"] for p in all_pairs_single(vertices[index], geometries[index].p))
        if not np.isclose(independently_computed_minimum, global_gap[index], rtol=0, atol=1e-9):
            raise AssertionError("Batch and scalar distance implementations disagree")
    taper_rows = sidewall_audit(sample, module.Geometry, np.linspace(0, 5, 21))
    narrow_intra = module.Geometry(690, 210, 300, 90, 90, theta_odd_deg=45, theta_even_deg=45)
    narrow_periodic = module.Geometry(620, 210, 300, 620 - (1 + np.sqrt(2)) * 210 - .001,
                                      90, theta_odd_deg=45, theta_even_deg=45)
    counterexamples = []
    for label, geometry in (("3_nm_same_cell_gap", narrow_intra), ("0_001_nm_periodic_gap", narrow_periodic)):
        _, ii, pp, mm = audit_plan([geometry])
        counterexamples.append({"label": label, "passes_current_Geometry_validation": True,
                                "geometry_values": cfg.geometry_values(geometry).tolist(),
                                "intra_cell_gap_nm": float(ii[0]), "periodic_gap_nm": float(pp[0]),
                                "boundary_margins_xy_nm": mm[0].tolist()})
    data_dir = args.report_dir / "data"
    figure_dir = args.report_dir / "figures"
    data_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    audit = {
        "analysis_type": "geometry_only_no_fdtd_no_fabrication_experiment",
        "provenance": {"generator_directory": str(generator), "config_relative_path": str(config_path.relative_to(generator)).replace("\\", "/"),
                       "config_file_sha256": sha256(config_path), "config_py_sha256": sha256(source_path),
                       "audit_script_sha256": sha256(Path(__file__)),
                       "source_hashes_sha256": {name: sha256(source_path.parent / name) for name in ("config.py", "lumerical.py", "pipeline.py")},
                       "numpy_version": np.__version__, "matplotlib_version": matplotlib.__version__,
                       "reported_sample": report_sample_provenance},
        "method": {"sampling": "PipelineConfig.sample_geometries rejection sampling of the first N valid candidates; not completed FDTD samples",
                   "seed": args.seed, "valid_candidate_count": len(geometries),
                   "distance": "Minimum Euclidean distance of every vertex to every edge, in both directions, for disjoint rotated polygons",
                   "periodicity": "All polygon pairs in eight neighboring cells shifted by (i*P,j*P), i,j in {-1,0,1}, excluding (0,0)",
                   "overlap_check_for_sidewalls": "Geometry.polygons_touch separating-axis theorem; overlapping/touching polygons have zero physical clearance",
                   "sidewall_model": "Top CD held fixed; column centers held fixed; bottom L=top L+2*H*tan(beta), beta from vertical; polygons homothetically enlarged around each center",
                   "scope_limit": "Ideal straight polygon edges; no roughness, undercut, grains, adhesion layers, substrate topology, or measured process distributions"},
        "numerical_verification": {"analytical_axis_and_diagonal_separation_checks_passed": True,
                                   "scalar_and_batch_minima_agree_on_report_sample_and_narrowest_candidate": True,
                                   "scalar_batch_absolute_tolerance_nm": 1e-9},
        "parameter_names": list(cfg.parameter_names), "parameter_units": list(cfg.parameter_units),
        "bounds_nm": cfg.bounds_nm, "quadrant_rotation_bounds_deg": cfg.quadrant_rotation_bounds_deg,
        "existing_validation_gap": "Nonoverlap and strict cell containment are enforced; no positive minimum manufacturing gap is enforced",
        "reported_sample": {"geometry_values": cfg.geometry_values(sample).tolist(),
                            "centers_xy_nm": sample.centers(), "vertices_xy_nm": vertices[0].tolist(),
                            "envelope_min_xy_nm": vertices[0].min(axis=(0, 1)).tolist(),
                            "envelope_max_xy_nm": vertices[0].max(axis=(0, 1)).tolist(),
                            "boundary_margins_xy_nm": margins[0].tolist(),
                            "minimum_intra_cell_gap_nm": float(intra[0]), "minimum_periodic_gap_nm": float(periodic[0]),
                            "nearest_intra_cell_pair": pair_record(min((p for p in sample_pairs if p["kind"] == "same_cell"), key=lambda r: r["distance"])),
                            "nearest_periodic_pair": pair_record(min((p for p in sample_pairs if p["kind"] == "neighbor_cell"), key=lambda r: r["distance"])),
                            "height_over_side_length": sample.h / sample.l,
                            "height_over_minimum_opening": sample.h / min(intra[0], periodic[0]),
                            "top_area_fill_fraction": 4 * sample.l ** 2 / sample.p ** 2},
        "plan_statistics_nm": {"intra_cell_gap": statistics(intra), "periodic_gap": statistics(periodic),
                               "global_gap": statistics(global_gap), "boundary_margin": statistics(margins.min(axis=1))},
        "counts_below_global_gap_threshold_nm": {str(t): int(np.sum(global_gap < t)) for t in (5, 10, 20, 30, 40, 50)},
        "minimum_gap_candidate": {"zero_based_index": risk_index,
                                  "geometry_values": cfg.geometry_values(geometries[risk_index]).tolist(),
                                  "minimum_gap_nm": float(global_gap[risk_index])},
        "theoretical_same_cell_gap_lower_bound_nm": float(90 - (np.sqrt(2) - 1) * 210),
        "accepted_counterexamples_to_manufacturing_margin": counterexamples,
        "aspect_ratio_H_over_L_bounds": [240 / 210, 380 / 160],
        "hypothetical_sidewall_sensitivity": taper_rows,
        "suggested_tolerance_study": {"status": "proposed_levels_not_measured_or_validated_tolerances",
                                      "P_delta_nm": [-10, -5, 5, 10], "fixed_center_CD_delta_nm": [-10, -5, 5, 10],
                                      "H_delta_nm": [-20, -10, 10, 20], "placement_or_reference_gap_delta_nm": [-10, -5, 5, 10],
                                      "quadrant_angle_delta_deg": [-2, -1, 1, 2], "Au_thickness_nm": [90, 95, 100, 105, 110],
                                      "corner_radius_nm": [0, 5, 10, 20], "outward_sidewall_angles_deg": [0, 1, 2, 3, 5],
                                      "independent_column_position_delta_nm": [-5, -3, 3, 5],
                                      "independent_column_angle_delta_deg": [-2, -1, 1, 2],
                                      "important_CD_note": "Changing the generator L also moves centers; fabrication CD bias must instead keep centers fixed",
                                      "suggested_screening": "Prefer nominal global gaps >=50 nm for initial prototypes; 40 nm is a provisional looser screen. Also check the fabricated sidewall profile at every height for a proposed 20-30 nm surviving opening. These values require laboratory validation."}}
    json_path = data_dir / "geometry_audit.json"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    columns = ["candidate_index", *cfg.parameter_names, "intra_cell_min_gap_nm", "periodic_min_gap_nm",
               "global_min_gap_nm", "boundary_margin_x_nm", "boundary_margin_y_nm", "H_over_L",
               "proposed_global_gap_40nm_pass", "proposed_global_gap_50nm_pass"]
    with (data_dir / "candidate_geometry_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for i, geometry in enumerate(geometries):
            writer.writerow([i, *cfg.geometry_values(geometry), intra[i], periodic[i], global_gap[i],
                             *margins[i], geometry.h / geometry.l, bool(global_gap[i] >= 40), bool(global_gap[i] >= 50)])
    plot_clearance(figure_dir / "geometry_clearance.png", sample, vertices[0], geometries[risk_index], vertices[risk_index], risk_index)
    plot_distribution(figure_dir / "gap_distribution.png", intra, periodic, args.seed)
    plot_sidewall(figure_dir / "sidewall_sensitivity.png", taper_rows, sample)
    print(json.dumps({"audit": str(json_path), "minimum_gap_nm": float(global_gap.min()),
                      "candidate_count": len(geometries), "figures": 3, "fdtd_run_performed": False}, indent=2))


if __name__ == "__main__":
    main()
