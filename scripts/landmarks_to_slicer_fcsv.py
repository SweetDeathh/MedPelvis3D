"""Open one MedPelvis3D case in 3D Slicer for inspection (no figure rendering).

This is a tiny convenience helper: it does NOT generate publication figures.
For visualisation we recommend 3D Slicer (free, https://www.slicer.org),
which can directly load .nii.gz, .stl, and .fcsv files.

Usage (Python, optional)
------------------------
The function below produces a *Slicer markups .fcsv* from the released
``<case>-Table-XYZ.CSV`` so the landmarks can be drag-dropped into Slicer
and visualised on top of the surface mesh.

    python scripts/landmarks_to_slicer_fcsv.py \\
        --landmarks medpelvis3d/annotations/600001-Table-XYZ.CSV \\
        --out 600001-landmarks.fcsv

Then in 3D Slicer:
    1. Drag-drop ``medpelvis3d/stl_models/600001-LeftHipBone.stl`` (and
       the right hip / sacrum STL) into the 3D view.
    2. Drag-drop ``600001-landmarks.fcsv`` into the same scene.
    3. The 57 landmarks appear on the bone surface, named by short_name.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


HEADER = (
    '# Markups fiducial file version = 4.11\n'
    '# CoordinateSystem = LPS\n'
    '# columns = id,x,y,z,ow,ox,oy,oz,vis,sel,lock,label,desc,associatedNodeID\n'
)


def csv_to_fcsv(landmarks_csv: str | Path, out_fcsv: str | Path) -> None:
    """Write a Slicer .fcsv from the released landmark CSV.

    The Slicer fiducial file format places (x, y, z) in LPS millimetre
    coordinates, identical to the released CSV's ``X, Y, Z``.
    """
    df = pd.read_csv(landmarks_csv, encoding='utf-8-sig')
    df['short_name'] = df['short_name'].astype(str).str.strip()
    df['anatomical_name_en'] = df['anatomical_name_en'].astype(str)

    lines = [HEADER]
    for i, row in enumerate(df.itertuples(index=False), start=1):
        x, y, z = float(row.X), float(row.Y), float(row.Z)
        label = row.short_name
        desc = row.anatomical_name_en
        lines.append(
            f'vtkMRMLMarkupsFiducialNode_{i},{x:.4f},{y:.4f},{z:.4f},'
            f'0.000,0.000,0.000,1.000,1,1,0,{label},{desc},\n'
        )
    Path(out_fcsv).write_text(''.join(lines), encoding='utf-8')


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    p.add_argument('--landmarks', required=True,
                   help='input landmark CSV (released format)')
    p.add_argument('--out', required=True,
                   help='output .fcsv path for 3D Slicer')
    args = p.parse_args()
    csv_to_fcsv(args.landmarks, args.out)
    print(f'wrote {args.out}')
    print('Drag-drop this file together with the case STL files into 3D Slicer.')


if __name__ == '__main__':
    main()
