"""Audit STL topology and optionally apply conservative mesh repair.

The repair path removes duplicate and degenerate faces, removes unreferenced
vertices, fixes normals/winding, and optionally fills simple holes. It never
smooths, decimates, or remeshes the surface.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import trimesh


def connected_face_components(mesh: trimesh.Trimesh) -> int:
    count = len(mesh.faces)
    if count == 0:
        return 0
    parent = np.arange(count)

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = int(parent[index])
        return index

    for left, right in np.asarray(mesh.face_adjacency):
        a, b = find(int(left)), find(int(right))
        if a != b:
            parent[b] = a
    return len({find(index) for index in range(count)})


def topology_metrics(mesh: trimesh.Trimesh) -> dict[str, object]:
    areas = np.asarray(mesh.area_faces)
    tolerance = max(float(mesh.scale) ** 2 * 1e-12, 1e-18)
    degenerate = int(np.count_nonzero(~np.isfinite(areas) | (areas <= tolerance)))
    canonical_faces = np.sort(np.asarray(mesh.faces), axis=1)
    duplicate = int(len(canonical_faces) - len(np.unique(canonical_faces, axis=0)))
    _, edge_counts = np.unique(np.asarray(mesh.edges_sorted), axis=0, return_counts=True)
    return {
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "degenerate_faces": degenerate,
        "duplicate_faces": duplicate,
        "boundary_edges": int(np.count_nonzero(edge_counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(edge_counts > 2)),
        "connected_components": connected_face_components(mesh),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "volume_mm3": float(abs(mesh.volume)) if np.isfinite(mesh.volume) else "",
    }


def self_intersection_count(path: Path) -> tuple[object, str]:
    try:
        import pymeshlab

        mesh_set = pymeshlab.MeshSet()
        mesh_set.load_new_mesh(str(path))
        mesh_set.compute_selection_by_self_intersections_per_face()
        return int(mesh_set.current_mesh().selected_face_number()), "ok"
    except ImportError:
        return "", "pymeshlab_not_installed"
    except Exception as exc:
        return "", f"error:{type(exc).__name__}:{exc}"


def conservative_repair(mesh: trimesh.Trimesh, fill_holes: bool) -> trimesh.Trimesh:
    repaired = mesh.copy()
    repaired.merge_vertices()
    repaired.update_faces(repaired.unique_faces())
    repaired.update_faces(repaired.nondegenerate_faces())
    repaired.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(repaired, multibody=True)
    if fill_holes and not repaired.is_watertight:
        trimesh.repair.fill_holes(repaired)
    repaired.remove_unreferenced_vertices()
    return repaired


def audit(path: Path, with_self_intersections: bool) -> dict[str, object]:
    loaded = trimesh.load_mesh(path, process=False)
    if isinstance(loaded, trimesh.Scene):
        loaded = loaded.dump(concatenate=True)
    if not isinstance(loaded, trimesh.Trimesh):
        raise TypeError(f"not a triangular mesh: {path}")
    # STL stores triangles independently; merge coincident vertices before
    # connectivity metrics so closed surfaces are not reported as open.
    loaded.merge_vertices()
    metrics = topology_metrics(loaded)
    metrics["file"] = path.name
    if with_self_intersections:
        count, status = self_intersection_count(path)
        metrics["self_intersecting_faces"] = count
        metrics["self_intersection_status"] = status
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--repair-dir", type=Path)
    parser.add_argument("--fill-simple-holes", action="store_true")
    parser.add_argument("--self-intersections", action="store_true")
    args = parser.parse_args()

    paths = sorted(args.input_dir.glob("*.stl"))
    if not paths:
        raise SystemExit(f"no STL files found in {args.input_dir}")
    if args.repair_dir:
        args.repair_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for path in paths:
        before = audit(path, args.self_intersections)
        row = {f"before_{key}": value for key, value in before.items() if key != "file"}
        row["file"] = path.name
        if args.repair_dir:
            mesh = trimesh.load_mesh(path, process=False)
            if isinstance(mesh, trimesh.Scene):
                mesh = mesh.dump(concatenate=True)
            repaired = conservative_repair(mesh, args.fill_simple_holes)
            output_path = args.repair_dir / path.name
            repaired.export(output_path)
            after = audit(output_path, args.self_intersections)
            row.update({f"after_{key}": value for key, value in after.items() if key != "file"})
            before_volume = before.get("volume_mm3")
            after_volume = after.get("volume_mm3")
            if isinstance(before_volume, float) and before_volume:
                row["volume_change_percent"] = 100.0 * (float(after_volume) - before_volume) / before_volume
        rows.append(row)

    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"audited {len(rows)} STL files; report={args.report}")


if __name__ == "__main__":
    main()
