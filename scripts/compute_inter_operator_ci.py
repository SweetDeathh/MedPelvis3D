"""Compute inter-operator landmark reliability for a re-annotated case subset.

Given two sets of landmark CSVs from independent annotators (e.g. the
released annotations and a senior annotator's second pass on the same cases),
this script reports the per-landmark and pooled inter-operator agreement
metrics used in Supplementary Table S4 of the companion paper:

    - mean Euclidean distance (mm) between matched landmarks
    - 95% confidence interval of the mean (case-level n, t-distribution)
    - per-landmark stratified statistics
    - inter-operator ICC(2,1) on raw x / y / z coordinates

Usage
-----
    python scripts/compute_inter_operator_ci.py \\
        --rater1-dir annotations_release \\
        --rater2-dir annotations_second_pass \\
        --cases 600110,600111,600112 \\
        --out per_landmark_CI.csv

Both directories are expected to hold one CSV per case named
``<case>-Table-XYZ.CSV`` with columns ``short_name, X, Y, Z, ...``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def load_landmarks(dir_path: Path, case_id: str) -> pd.DataFrame:
    p = dir_path / f'{case_id}-Table-XYZ.CSV'
    if not p.exists():
        p = dir_path / f'{case_id}-Table-XYZ.csv'
    df = pd.read_csv(p, encoding='utf-8-sig')
    df['short_name'] = df['short_name'].astype(str).str.strip()
    return df.set_index('short_name')[['X', 'Y', 'Z']]


def case_distances(rater1: Path, rater2: Path, case_id: str) -> pd.DataFrame:
    """Return a DataFrame with per-landmark Euclidean distance for one case."""
    a = load_landmarks(rater1, case_id)
    b = load_landmarks(rater2, case_id)
    common = a.index.intersection(b.index)
    rows = []
    for name in common:
        d = float(np.linalg.norm(a.loc[name].values - b.loc[name].values))
        rows.append({'case_id': case_id, 'short_name': name, 'dist_mm': d,
                     'a_x': a.loc[name, 'X'], 'a_y': a.loc[name, 'Y'], 'a_z': a.loc[name, 'Z'],
                     'b_x': b.loc[name, 'X'], 'b_y': b.loc[name, 'Y'], 'b_z': b.loc[name, 'Z']})
    return pd.DataFrame(rows)


def mean_with_ci(values: np.ndarray, alpha: float = 0.05) -> dict:
    n = len(values)
    mu = float(values.mean())
    sd = float(values.std(ddof=1)) if n > 1 else float('nan')
    se = sd / np.sqrt(n) if n > 1 else float('nan')
    t = stats.t.ppf(1 - alpha / 2, df=n - 1) if n > 1 else float('nan')
    half = t * se if n > 1 else float('nan')
    return {'n': n, 'mean': mu, 'sd': sd, 'ci_lo': mu - half, 'ci_hi': mu + half}


def per_landmark_table(long_df: pd.DataFrame) -> pd.DataFrame:
    """Per-landmark mean/SD/95% CI across cases (case-level n)."""
    rows = []
    for name, group in long_df.groupby('short_name'):
        s = mean_with_ci(group['dist_mm'].values)
        s['short_name'] = name
        s['median'] = float(group['dist_mm'].median())
        s['min'] = float(group['dist_mm'].min())
        s['max'] = float(group['dist_mm'].max())
        rows.append(s)
    out = pd.DataFrame(rows)
    return out[['short_name', 'n', 'mean', 'sd',
                 'ci_lo', 'ci_hi', 'median', 'min', 'max']].sort_values('mean')


def coordinate_icc(long_df: pd.DataFrame, axis: str) -> dict:
    """Two-way random, single-rater absolute-agreement ICC(2,1)."""
    import pingouin as pg
    rater_a = long_df[['case_id', 'short_name', f'a_{axis}']].rename(
        columns={f'a_{axis}': 'value'}).assign(rater='A')
    rater_b = long_df[['case_id', 'short_name', f'b_{axis}']].rename(
        columns={f'b_{axis}': 'value'}).assign(rater='B')
    long = pd.concat([rater_a, rater_b], ignore_index=True)
    long['target'] = long['case_id'].astype(str) + '_' + long['short_name']
    icc = pg.intraclass_corr(data=long, targets='target', raters='rater',
                              ratings='value')
    row = icc[icc['Type'] == 'ICC2'].iloc[0]
    return {
        'axis': axis,
        'ICC(2,1)': float(row['ICC']),
        'CI_lo': float(row['CI95%'][0]),
        'CI_hi': float(row['CI95%'][1]),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    p.add_argument('--rater1-dir', required=True,
                   help='directory containing rater 1 CSVs (one per case)')
    p.add_argument('--rater2-dir', required=True,
                   help='directory containing rater 2 CSVs (one per case)')
    p.add_argument('--cases', required=True,
                   help='comma-separated case IDs')
    p.add_argument('--out', help='per-landmark CSV output path')
    args = p.parse_args()

    rater1 = Path(args.rater1_dir)
    rater2 = Path(args.rater2_dir)
    case_ids = [c.strip() for c in args.cases.split(',') if c.strip()]
    print(f'cases: {case_ids}')

    long = pd.concat([case_distances(rater1, rater2, cid) for cid in case_ids],
                      ignore_index=True)

    # Pooled mean ± 95% CI (case-level)
    case_means = long.groupby('case_id')['dist_mm'].mean().values
    pooled = mean_with_ci(case_means)
    print(f'\nPooled inter-operator agreement (case-level n = {pooled["n"]}):')
    print(f'  Mean ± SD:  {pooled["mean"]:.2f} ± {pooled["sd"]:.2f} mm')
    print(f'  95% CI:     [{pooled["ci_lo"]:.2f}, {pooled["ci_hi"]:.2f}] mm')

    # Coordinate-wise ICC
    print('\nCoordinate-wise ICC(2,1):')
    for axis in ('x', 'y', 'z'):
        try:
            r = coordinate_icc(long, axis)
            print(f'  {axis}: {r["ICC(2,1)"]:.4f}  '
                  f'95% CI [{r["CI_lo"]:.4f}, {r["CI_hi"]:.4f}]')
        except Exception as e:
            print(f'  {axis}: (skipped — {e})')

    # Per-landmark
    per_lm = per_landmark_table(long)
    print(f'\nPer-landmark table ({len(per_lm)} landmarks, head):')
    print(per_lm.head(10).round(2).to_string(index=False))

    if args.out:
        per_lm.round(4).to_csv(args.out, index=False)
        print(f'\nwrote {args.out}')


if __name__ == '__main__':
    main()
