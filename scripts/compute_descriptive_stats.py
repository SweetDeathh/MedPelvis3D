"""Compute full descriptive statistics (Min, Q1, Mean, SD, Median, IQR, Q3, Max).

Reproduces Supplementary Tables S2 / S3 of the companion paper, optionally
stratified by sex.

Usage
-----
    python scripts/compute_descriptive_stats.py --root medpelvis3d
    python scripts/compute_descriptive_stats.py --root medpelvis3d \\
        --by-sex --out supp_table_S3.csv

Inputs (same layout as compute_geometry_stats.py)::

    <root>/point_clouds_50000/<case>-points-50000.npy
    <root>/stl_models/<case>-{LeftHipBone,RightHipBone,Sacrum}.stl
    <root>/annotations/<case>-Table-XYZ.CSV
    <root>/patient_metadata.csv

Output
------
    Wide table with one row per metric; if ``--by-sex`` is given an
    additional column ``sex`` separates Male / Female / All.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# Reuse helpers from compute_geometry_stats.py
try:
    from compute_geometry_stats import case_id_from_nifti, case_metrics
except ImportError:  # when imported as scripts.compute_descriptive_stats
    from scripts.compute_geometry_stats import case_id_from_nifti, case_metrics


METRICS = ['inter_asis_mm', 'bbox_width_mm', 'bbox_depth_mm',
            'bbox_height_mm', 'bone_volume_ml']

PRETTY = {
    'inter_asis_mm':   'Inter-ASIS distance (mm)',
    'bbox_width_mm':   'Bounding-box width (mm)',
    'bbox_depth_mm':   'Bounding-box depth (mm)',
    'bbox_height_mm':  'Bounding-box height (mm)',
    'bone_volume_ml':  'Total pelvic bone volume (mL)',
}


def descriptive_row(values: np.ndarray) -> dict:
    """Compute the descriptive statistics for one metric across cases."""
    q1 = np.percentile(values, 25)
    q2 = np.percentile(values, 50)
    q3 = np.percentile(values, 75)
    return {
        'n':       len(values),
        'Min':     float(values.min()),
        'Q1':      float(q1),
        'Mean':    float(values.mean()),
        'SD':      float(values.std(ddof=1)),
        'Median':  float(q2),
        'IQR':     float(q3 - q1),
        'Q3':      float(q3),
        'Max':     float(values.max()),
    }


def build_table(df: pd.DataFrame, group: str | None = None) -> pd.DataFrame:
    """Return a long-format descriptive table, one row per (group, metric)."""
    rows = []
    if group is None:
        for m in METRICS:
            row = descriptive_row(df[m].values)
            row['Metric'] = PRETTY[m]
            row['Group'] = 'All'
            rows.append(row)
    else:
        for g, sub in df.groupby(group):
            for m in METRICS:
                row = descriptive_row(sub[m].values)
                row['Metric'] = PRETTY[m]
                row['Group'] = g
                rows.append(row)
    return pd.DataFrame(rows)[['Group', 'Metric', 'n', 'Min', 'Q1', 'Mean',
                                 'SD', 'Median', 'IQR', 'Q3', 'Max']]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    p.add_argument('--root', required=True)
    p.add_argument('--by-sex', action='store_true')
    p.add_argument('--out', help='write the descriptive table to this CSV')
    args = p.parse_args()

    root = Path(args.root)
    case_ids = sorted(case_id_from_nifti(p)
                      for p in (root / 'ct_nifti').glob('*.nii.gz'))
    print(f'cases: {len(case_ids)}')

    rows = [case_metrics(root, cid) for cid in case_ids]
    df = pd.DataFrame(rows)

    overall = build_table(df, group=None)
    print('\n=== Descriptive statistics (cohort) ===')
    print(overall.round(2).to_string(index=False))

    if args.by_sex:
        meta = pd.read_csv(root / 'patient_metadata.csv', dtype=str)
        meta['case_id'] = meta['case_id'].astype(str).str.strip()
        df = df.merge(meta[['case_id', 'sex']], on='case_id', how='left')
        per_sex = build_table(df, group='sex')
        result = pd.concat([overall, per_sex], ignore_index=True)
        print('\n=== Descriptive statistics (by sex) ===')
        print(per_sex.round(2).to_string(index=False))
    else:
        result = overall

    if args.out:
        result.round(4).to_csv(args.out, index=False)
        print(f'\nwrote {args.out}')


if __name__ == '__main__':
    main()
