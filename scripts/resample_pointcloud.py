"""Resample the surface mesh of a case to N approximately uniform points.

This utility samples the union of LeftHipBone, RightHipBone, and Sacrum STL
meshes with Trimesh's even surface sampler, falling back to uniform surface
sampling if needed. It can generate point clouds at any N (e.g. 25,000 /
75,000) for downstream model training.

Usage
-----
    python scripts/resample_pointcloud.py \\
        --root medpelvis3d \\
        --case 600001 \\
        --n 25000 \\
        --out 600001-points-25000.npy
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def union_pelvis_mesh(root: Path, case_id: str):
    """Return a single trimesh combining the three anatomical meshes."""
    import trimesh
    stl_dir = root / 'stl_models'
    pieces = [
        trimesh.load_mesh(stl_dir / f'{case_id}-LeftHipBone.stl'),
        trimesh.load_mesh(stl_dir / f'{case_id}-RightHipBone.stl'),
        trimesh.load_mesh(stl_dir / f'{case_id}-Sacrum.stl'),
    ]
    return trimesh.util.concatenate(pieces)


def sample_points(mesh, n: int, seed: int = 0) -> np.ndarray:
    """Approximately even surface sample, falling back to uniform if needed.

    Returns an (n, 3) ndarray of points in mm world coordinates.
    """
    import trimesh
    rng = np.random.default_rng(seed)
    try:
        pts, _ = trimesh.sample.sample_surface_even(mesh, n, seed=seed)
        if pts.shape[0] >= n:
            return pts[:n]
    except Exception:
        pass
    pts, _ = trimesh.sample.sample_surface(mesh, n, seed=seed)
    return pts[:n]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    p.add_argument('--root', required=True)
    p.add_argument('--case', required=True)
    p.add_argument('--n', type=int, default=50000)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--out', default=None,
                   help='output .npy path (default: <case>-points-<n>.npy)')
    args = p.parse_args()

    root = Path(args.root)
    cid = str(args.case).strip()
    mesh = union_pelvis_mesh(root, cid)
    pts = sample_points(mesh, args.n, seed=args.seed)
    out = Path(args.out) if args.out else Path(f'{cid}-points-{args.n}.npy')
    np.save(out, pts)
    print(f'wrote {out}: {pts.shape[0]} points, '
          f'extent X[{pts[:,0].min():.1f},{pts[:,0].max():.1f}] '
          f'Y[{pts[:,1].min():.1f},{pts[:,1].max():.1f}] '
          f'Z[{pts[:,2].min():.1f},{pts[:,2].max():.1f}] mm')


if __name__ == '__main__':
    main()
