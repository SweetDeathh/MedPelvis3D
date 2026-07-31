"""Rebuild release-coordinate STL meshes from labelled NIfTI masks.

The pipeline uses Lewiner marching cubes, applies the NIfTI affine, converts
the first two axes from RAS to the release LPS convention, and removes only
zero-volume disconnected fragments. It does not smooth, decimate, or remesh
the surface. Source masks are never modified.

The label convention is fixed for the released dataset:
1 = LeftHipBone, 2 = RightHipBone, 3 = Sacrum.
"""
from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import nibabel as nib
import numpy as np
from skimage.measure import marching_cubes
import trimesh


LABELS = {1: "LeftHipBone", 2: "RightHipBone", 3: "Sacrum"}
EXPECTED_LABELS = {0, *LABELS}
MASK_SUFFIX = "-mask.nii.gz"


def case_id_from_path(path: Path) -> str:
    if not path.name.endswith(MASK_SUFFIX):
        raise ValueError(f"mask filename must end with {MASK_SUFFIX}: {path}")
    return path.name[: -len(MASK_SUFFIX)]


def edge_counts(faces: np.ndarray) -> tuple[int, int]:
    if len(faces) == 0:
        return 0, 0
    edges = np.sort(
        np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])),
        axis=1,
    )
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return int(np.count_nonzero(counts == 1)), int(np.count_nonzero(counts > 2))


def mesh_metrics(mesh: trimesh.Trimesh) -> dict[str, object]:
    boundary, nonmanifold = edge_counts(np.asarray(mesh.faces))
    areas = np.asarray(mesh.area_faces)
    degenerate = int(np.count_nonzero(~np.isfinite(areas) | (areas <= 1e-12)))
    canonical_faces = np.sort(np.asarray(mesh.faces), axis=1)
    duplicate = int(len(canonical_faces) - len(np.unique(canonical_faces, axis=0)))
    try:
        volume = float(abs(mesh.volume))
    except (TypeError, ValueError):
        volume = float("nan")
    return {
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "boundary_edges": boundary,
        "nonmanifold_edges": nonmanifold,
        "duplicate_faces": duplicate,
        "degenerate_faces": degenerate,
        "components": int(len(mesh.split(only_watertight=False))),
        "volume_mm3": volume if np.isfinite(volume) else "",
    }


def build_mesh(mask: np.ndarray, affine: np.ndarray, label: int) -> trimesh.Trimesh:
    binary = np.pad(mask == label, 1, mode="constant", constant_values=False)
    if not np.any(binary):
        raise ValueError(f"label {label} is absent from the mask")
    vertices, faces, _, _ = marching_cubes(
        binary.astype(np.uint8),
        level=0.5,
        method="lewiner",
        allow_degenerate=False,
    )
    vertices -= 1.0
    vertices = nib.affines.apply_affine(affine, vertices)
    # NIfTI coordinates are commonly RAS; the release uses patient-level LPS.
    vertices[:, :2] *= -1.0
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def drop_zero_volume_fragments(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, int, int]:
    """Remove only disconnected fragments with no enclosed volume."""
    if mesh.is_watertight:
        return mesh, 0, 0
    parts = mesh.split(only_watertight=False)
    kept = []
    for part in parts:
        try:
            volume = float(part.volume)
        except (TypeError, ValueError):
            volume = float("nan")
        if len(part.faces) > 2 and np.isfinite(volume) and abs(volume) > 1e-6:
            kept.append(part)
    if not kept:
        return mesh, 0, 0
    cleaned = trimesh.util.concatenate(kept)
    return cleaned, len(parts) - len(kept), len(mesh.faces) - len(cleaned.faces)


def verified_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load_mesh(path, process=True)
    if isinstance(loaded, trimesh.Scene):
        loaded = loaded.dump(concatenate=True)
    if not isinstance(loaded, trimesh.Trimesh):
        raise TypeError(f"not a triangular mesh: {path}")
    return loaded


def write_report(path: Path, rows: list[dict[str, object]]) -> None:
    fields = [
        "case_id", "structure", "status", "source", "output", "voxel_count",
        "vertices", "faces", "watertight", "winding_consistent",
        "boundary_edges", "nonmanifold_edges", "duplicate_faces",
        "degenerate_faces", "components", "volume_mm3", "removed_fragments",
        "removed_faces", "elapsed_seconds", "error",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mask-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--case-glob",
        default="*-mask.nii.gz",
        help="glob used to select mask files (default: %(default)s)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="allow replacing STL files already present in the output directory",
    )
    args = parser.parse_args()

    mask_dir = args.mask_dir.resolve()
    output_dir = args.output_dir.resolve()
    report = args.report.resolve()
    if not mask_dir.is_dir():
        raise SystemExit(f"mask directory does not exist: {mask_dir}")
    paths = sorted(mask_dir.glob(args.case_glob))
    if not paths:
        raise SystemExit(f"no mask files found under {mask_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for mask_path in paths:
        case_id = case_id_from_path(mask_path)
        image = nib.load(mask_path)
        mask = np.asanyarray(image.dataobj)
        present = set(np.unique(mask).astype(int).tolist())
        if present != EXPECTED_LABELS:
            raise ValueError(
                f"unexpected labels for {case_id}: {sorted(present)}; "
                f"expected {sorted(EXPECTED_LABELS)}"
            )

        for label, structure in LABELS.items():
            started = time.perf_counter()
            output = output_dir / f"{case_id}-{structure}.stl"
            if output.exists() and not args.overwrite:
                raise FileExistsError(
                    f"refusing to overwrite {output}; use --overwrite explicitly"
                )
            row: dict[str, object] = {
                "case_id": case_id,
                "structure": structure,
                "status": "error",
                "source": mask_path.name,
                "output": output.name,
                "voxel_count": int(np.count_nonzero(mask == label)),
                "removed_fragments": 0,
                "removed_faces": 0,
                "error": "",
            }
            try:
                mesh = build_mesh(mask, image.affine, label)
                mesh, removed_fragments, removed_faces = drop_zero_volume_fragments(mesh)
                row["removed_fragments"] = removed_fragments
                row["removed_faces"] = removed_faces
                mesh.export(output)
                checked = verified_mesh(output)
                metrics = mesh_metrics(checked)
                row.update(metrics)
                row["status"] = "pass" if (
                    metrics["watertight"]
                    and metrics["winding_consistent"]
                    and metrics["boundary_edges"] == 0
                    and metrics["nonmanifold_edges"] == 0
                    and metrics["duplicate_faces"] == 0
                    and metrics["degenerate_faces"] == 0
                ) else "fail"
            except Exception as exc:  # keep the report useful for batch runs
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            rows.append(row)
            write_report(report, rows)

        del mask

    passed = sum(row["status"] == "pass" for row in rows)
    failed = sum(row["status"] == "fail" for row in rows)
    errors = sum(row["status"] == "error" for row in rows)
    print(
        f"rebuilt {len(rows)} meshes; pass={passed}; fail={failed}; "
        f"error={errors}; report={report}"
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
