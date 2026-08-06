"""Compute cohort-level geometric statistics for the MedPelvis3D dataset.

This reproduces Table 2 of the companion paper (inter-ASIS distance and total
pelvic bone volume), with optional bounding-box metrics (``--include-bbox``)
and sex stratification.

Usage
-----
    python scripts/compute_geometry_stats.py --root medpelvis3d
    python scripts/compute_geometry_stats.py --root medpelvis3d --by-sex
    python scripts/compute_geometry_stats.py --root medpelvis3d --include-bbox

Inputs read
-----------
    <root>/annotations/<case>-Table-XYZ.CSV
    <root>/stl_models/<case>-{LeftHipBone,RightHipBone,Sacrum}.stl
    <root>/point_clouds_50000/<case>-points-50000.npy   (only with --include-bbox)
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


def case_id_from_nifti(path: Path) -> str:
    """Return case ID from either ``600001.nii.gz`` or a standard suffix."""
    name = path.name
    if name.endswith('.nii.gz'):
        return name[:-7]
    return path.stem


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


def bone_volume_cm3(root: Path, case_id: str) -> float:
    """Total pelvic bone volume, in cm^3: sum of the enclosed volumes of the
    three STL components (LeftHipBone, RightHipBone, Sacrum). This matches the
    definition reported in the companion paper (Table 2).

    STL coordinates are in millimetres, so trimesh volumes are in mm^3; the
    conversion to cm^3 (division by 1000) is applied here."""
    import trimesh
    stl_dir = root / 'stl_models'
    total = 0.0
    for comp in ('LeftHipBone', 'RightHipBone', 'Sacrum'):
        mesh = trimesh.load_mesh(stl_dir / f'{case_id}-{comp}.stl', process=False)
        total += float(abs(mesh.volume)) / 1000.0
    return total


def case_metrics(root: Path, case_id: str, include_bbox: bool = False) -> dict:
    landmarks = load_landmarks(root, case_id)
    out = {
        'case_id': case_id,
        'inter_asis_mm': inter_asis_distance(landmarks),
        'bone_volume_cm3': bone_volume_cm3(root, case_id),
    }
    if include_bbox:
        pts_path = root / 'point_clouds_50000' / f'{case_id}-points-50000.npy'
        pts = np.load(pts_path)
        w, d, h = bbox_dimensions(pts)
        out.update({'bbox_width_mm': w, 'bbox_depth_mm': d, 'bbox_height_mm': h})
    return out


def summarise(df: pd.DataFrame, group_col: str = None,
              include_bbox: bool = False) -> pd.DataFrame:
    cols = ['inter_asis_mm', 'bone_volume_cm3']
    if include_bbox:
        cols += ['bbox_width_mm', 'bbox_depth_mm', 'bbox_height_mm']
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
    p.add_argument('--include-bbox', action='store_true',
                   help='also report point-cloud bounding-box extents (not part of '
                        'the published Table 2; coordinate-dependent, not anatomical)')
    p.add_argument('--out', help='write per-case CSV to this path')
    args = p.parse_args()

    root = Path(args.root)
    if args.cases:
        case_ids = [c.strip() for c in args.cases.split(',')]
    else:
        case_ids = sorted(case_id_from_nifti(p)
                          for p in (root / 'ct_nifti').glob('*.nii.gz'))
    print(f'cases: {len(case_ids)}')

    rows = [case_metrics(root, cid, include_bbox=args.include_bbox) for cid in case_ids]
    df = pd.DataFrame(rows)

    print('\n=== Cohort-level metrics (mean ± SD, n) ===')
    summary = summarise(df, include_bbox=args.include_bbox)
    print(summary.to_string())

    if args.by_sex:
        meta = pd.read_csv(root / 'patient_metadata.csv', dtype=str)
        meta['case_id'] = meta['case_id'].astype(str).str.strip()
        df = df.merge(meta[['case_id', 'sex']], on='case_id', how='left')
        print('\n=== Sex-stratified ===')
        print(summarise(df, group_col='sex', include_bbox=args.include_bbox).to_string())

    if args.out:
        df.round(4).to_csv(args.out, index=False)
        print(f'\nwrote {args.out}')


if __name__ == '__main__':
    main()
