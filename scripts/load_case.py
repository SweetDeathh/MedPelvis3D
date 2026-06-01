"""Load a single MedPelvis3D case (CT, mask, STL meshes, landmarks, point cloud).

Usage
-----
    from scripts.load_case import load_case
    case = load_case('medpelvis3d', '600001')
    print(case.landmarks.head())
    print(f'CT shape: {case.ct.GetSize()}')
    print(f'Left hip vertices: {case.left_hip.vertices.shape[0]}')

The function returns a :class:`Case` namedtuple with handles to all
modalities released for that subject.  The dataset directory is expected to
follow the layout produced by unzipping the figshare archives::

    medpelvis3d/
      ct_nifti/<case_id>.nii.gz
      masks_nifti/<case_id>-mask.nii.gz
      stl_models/<case_id>-{LeftHipBone,RightHipBone,Sacrum}.stl
      annotations/<case_id>-Table-XYZ.CSV
      point_clouds_50000/<case_id>-points-50000.npy

Coordinates are in millimetres in the original CT (LPS) coordinate system.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class Case:
    """Container holding the parsed contents of a single case."""
    case_id: str
    ct: 'Optional[object]'                       # SimpleITK.Image
    mask: 'Optional[object]'                     # SimpleITK.Image
    left_hip: 'Optional[object]'                 # trimesh.Trimesh
    right_hip: 'Optional[object]'                # trimesh.Trimesh
    sacrum: 'Optional[object]'                   # trimesh.Trimesh
    landmarks: pd.DataFrame                       # 57 rows, columns short_name, X, Y, Z, ...
    points: Optional[np.ndarray]                  # (N, 3)


def load_case(root: str | Path, case_id: str,
              load_ct: bool = True,
              load_mask: bool = True,
              load_stl: bool = True,
              load_landmarks: bool = True,
              load_pointcloud: bool = True) -> Case:
    """Load all (or a subset of) modalities for ``case_id`` from ``root``.

    Pass ``load_ct=False`` etc. to skip individual modalities for speed when
    you do not need them.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f'dataset root not found: {root}')
    cid = str(case_id).strip()

    ct = None
    mask = None
    if load_ct:
        import SimpleITK as sitk
        ct_path = root / 'ct_nifti' / f'{cid}.nii.gz'
        if not ct_path.exists():
            raise FileNotFoundError(f'CT not found: {ct_path}')
        ct = sitk.ReadImage(str(ct_path))
    if load_mask:
        import SimpleITK as sitk
        mk_path = root / 'masks_nifti' / f'{cid}-mask.nii.gz'
        if not mk_path.exists():
            raise FileNotFoundError(f'mask not found: {mk_path}')
        mask = sitk.ReadImage(str(mk_path))

    left = right = sacrum = None
    if load_stl:
        import trimesh
        stl_dir = root / 'stl_models'
        left = trimesh.load_mesh(stl_dir / f'{cid}-LeftHipBone.stl')
        right = trimesh.load_mesh(stl_dir / f'{cid}-RightHipBone.stl')
        sacrum = trimesh.load_mesh(stl_dir / f'{cid}-Sacrum.stl')

    landmarks = None
    if load_landmarks:
        ann_path = root / 'annotations' / f'{cid}-Table-XYZ.CSV'
        if not ann_path.exists():
            ann_path = root / 'annotations' / f'{cid}-Table-XYZ.csv'
        if not ann_path.exists():
            raise FileNotFoundError(f'landmarks not found: {ann_path}')
        landmarks = pd.read_csv(ann_path, encoding='utf-8-sig')

    points = None
    if load_pointcloud:
        pc_path = root / 'point_clouds_50000' / f'{cid}-points-50000.npy'
        if not pc_path.exists():
            raise FileNotFoundError(f'point cloud not found: {pc_path}')
        points = np.load(pc_path)

    return Case(case_id=cid, ct=ct, mask=mask,
                left_hip=left, right_hip=right, sacrum=sacrum,
                landmarks=landmarks, points=points)


def _cli() -> None:
    p = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    p.add_argument('--root', required=True, help='dataset root directory')
    p.add_argument('--case', required=True, help='case ID, e.g. 600001')
    args = p.parse_args()
    case = load_case(args.root, args.case)
    print(f'CT image size:    {case.ct.GetSize()}')
    print(f'Mask image size:  {case.mask.GetSize()}')
    print(f'Left hip:         {case.left_hip.vertices.shape[0]} vertices')
    print(f'Right hip:        {case.right_hip.vertices.shape[0]} vertices')
    print(f'Sacrum:           {case.sacrum.vertices.shape[0]} vertices')
    print(f'Landmarks:        {len(case.landmarks)} rows')
    print(f'Point cloud:      {case.points.shape}')


if __name__ == '__main__':
    _cli()
