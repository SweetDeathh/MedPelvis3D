"""Join landmark CSVs with the repository-level anatomical mapping table.

The released ``annotations/<case>-Table-XYZ.CSV`` files already include the
``short_name`` and ``anatomical_name_en`` columns.  Use this script if you
want to enrich them with extra metadata held in
``landmark_anatomical_mapping.csv`` (region, side) or to translate a
short_name to its full English term programmatically.

Example
-------
    from scripts.apply_anatomical_mapping import join_with_mapping

    df = pd.read_csv('annotations/600001-Table-XYZ.CSV', encoding='utf-8-sig')
    enriched = join_with_mapping(df, 'medpelvis3d/landmark_anatomical_mapping.csv')
    print(enriched[['short_name', 'anatomical_name_en', 'region', 'side']])
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def join_with_mapping(landmarks: pd.DataFrame,
                      mapping_csv: str | Path) -> pd.DataFrame:
    """Left-join landmark rows with the mapping table on ``short_name``.

    Returns a copy of ``landmarks`` with extra columns (``region``, ``side``)
    where available.  The mapping CSV columns are::

        short_name, anatomical_name_en, region, side
    """
    mapping = pd.read_csv(mapping_csv, encoding='utf-8-sig')
    mapping['short_name'] = mapping['short_name'].astype(str).str.strip()

    out = landmarks.copy()
    out['short_name'] = out['short_name'].astype(str).str.strip()
    cols_to_add = [c for c in ['region', 'side'] if c in mapping.columns]
    out = out.merge(
        mapping[['short_name'] + cols_to_add],
        on='short_name', how='left',
    )
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    p.add_argument('--landmarks', required=True, help='per-case CSV path')
    p.add_argument('--mapping', required=True,
                   help='landmark_anatomical_mapping.csv path')
    p.add_argument('--out', required=True, help='output CSV path')
    args = p.parse_args()

    df = pd.read_csv(args.landmarks, encoding='utf-8-sig')
    enriched = join_with_mapping(df, args.mapping)
    enriched.to_csv(args.out, index=False, encoding='utf-8-sig')
    print(f'wrote {args.out}: {len(enriched)} rows, {len(enriched.columns)} cols')
    print(enriched.head().to_string(index=False))


if __name__ == '__main__':
    main()
