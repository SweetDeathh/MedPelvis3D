"""Compute cohort-level geometric statistics for the MedPelvis3D dataset.

This reproduces Table 2 of the companion paper (inter-ASIS distance,
bounding-box width / depth / height, total bone volume), with optional
sex stratification.

Usage
-----
    python scripts/compute_geometry_stats.py --root medpelvis3d
    python scripts/compute_geometry_stats.py --root medpelvis3d --by-sex

Inputs read
-----------
    <root>/point_clouds_50000/<case>-points-50000.npy
    <root>/stl_models/<case>-{LeftHipBone,RightHipBone,Sacrum}.stl
    <root>/annotations/<case>-Table-XYZ.CSV
    <root>/patient_metadata.csv     (case_id, sex)

Output
------
    Prints a small summary table to stdout; optionally writes a CSV.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def load_landmarks(root: Path, case_id: str) -> pd.DataFrame:
    p = root / 'annotations' / f'{case_id}-Table-XYZ.CSV'
    if not p.exists():
        p = root / 'annotations' / f'{case_id}-Table-XYZ.csv'
    df = pd.read_csv(p, encoding='utf-8-sig')
    df['short_name'] = df['short_name'].astype(str).str.strip()
    return df


def inter_asis_distance(landmarks: pd.DataFrame) -> float:
    """Euclidean distance between Left and Right ASIS, in mm."""
    L = landmarks[landmarks['short_name'] == 'ASIS_L'][['X', 'Y', 'Z']].values[0]
    R = landmarks[landmarks['short_name'] == 'ASIS_R'][['X', 'Y', 'Z']].values[0]
    return float(np.linalg.norm(L - R))


def bbox_dimensions(points: np.ndarray) -> tuple[float, float, float]:
    """(width, depth, height) in mm = (X-extent, Y-extent, Z-extent) of point cloud."""
    mins = points.min(axis=0)
    maxs = points.max(axis=0)
    extents = maxs - mins
    return float(extents[0]), float(extents[1]), float(extents[2])


def bone_volume_ml(root: Path, case_id: str) -> float:
    """Total enclosed volume of the three pelvic STL meshes, in mL (= cm^3)."""
    import trimesh
    stl_dir = root / 'stl_models'
    pieces = [
        trimesh.load_mesh(stl_dir / f'{case_id}-LeftHipBone.stl'),
        trimesh.load_mesh(stl_dir / f'{case_id}-RightHipBone.stl'),
        trimesh.load_mesh(stl_dir / f'{case_id}-Sacrum.stl'),
    ]
    # Volume in mm^3; divide by 1000 for mL
    vol_mm3 = sum(abs(m.volume) for m in pieces if m.is_volume)
    return float(vol_mm3 / 1000.0)


def case_metrics(root: Path, case_id: str) -> dict:
    landmarks = load_landmarks(root, case_id)
    pts_path = root / 'point_clouds_50000' / f'{case_id}-points-50000.npy'
    pts = np.load(pts_path)
    w, d, h = bbox_dimensions(pts)
    return {
        'case_id': case_id,
        'inter_asis_mm': inter_asis_distance(landmarks),
        'bbox_width_mm': w,
        'bbox_depth_mm': d,
        'bbox_height_mm': h,
        'bone_volume_ml': bone_volume_ml(root, case_id),
    }


def summarise(df: pd.DataFrame, group_col: str = None) -> pd.DataFrame:
    cols = ['inter_asis_mm', 'bbox_width_mm', 'bbox_depth_mm',
            'bbox_height_mm', 'bone_volume_ml']
    if group_col:
        agg = df.groupby(group_col)[cols].agg(['mean', 'std', 'count'])
    else:
        agg = df[cols].agg(['mean', 'std', 'count'])
    return agg.round(2)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    p.add_argument('--root', required=True, help='dataset root')
    p.add_argument('--cases', help='comma-separated subset; default: all')
    p.add_argument('--by-sex', action='store_true',
                   help='also report male / female stratified statistics')
    p.add_argument('--out', help='write per-case CSV to this path')
    args = p.parse_args()

    root = Path(args.root)
    if args.cases:
        case_ids = [c.strip() for c in args.cases.split(',')]
    else:
        case_ids = sorted(p.stem for p in (root / 'ct_nifti').glob('*.nii.gz'))
    print(f'cases: {len(case_ids)}')

    rows = [case_metrics(root, cid) for cid in case_ids]
    df = pd.DataFrame(rows)

    print('\n=== Cohort-level metrics (mean ± SD, n) ===')
    summary = summarise(df)
    print(summary.to_string())

    if args.by_sex:
        meta = pd.read_csv(root / 'patient_metadata.csv', dtype=str)
        meta['case_id'] = meta['case_id'].astype(str).str.strip()
        df = df.merge(meta[['case_id', 'sex']], on='case_id', how='left')
        print('\n=== Sex-stratified ===')
        print(summarise(df, group_col='sex').to_string())

    if args.out:
        df.round(4).to_csv(args.out, index=False)
        print(f'\nwrote {args.out}')


if __name__ == '__main__':
    main()
