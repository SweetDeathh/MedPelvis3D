# MedPelvis3D — basic usage walkthrough

This document shows the typical workflow against a single example case
(600001) from the **samples/** folder of the Zenodo release.

After downloading and extracting `samples.zip`, your directory looks like

```
medpelvis3d/
├── samples/
│   └── 600001/
│       ├── 600001.nii.gz
│       ├── 600001-mask.nii.gz
│       ├── 600001-LeftHipBone.stl
│       ├── 600001-RightHipBone.stl
│       ├── 600001-Sacrum.stl
│       ├── 600001-Table-XYZ.csv
│       └── 600001-points-50000.npy
└── landmark_anatomical_mapping.csv
```

You can run every example below against just the **samples** folder before
downloading the full 13.8 GB CT archive.

---

## 1. Load a case in Python

```python
from scripts.load_case import load_case

case = load_case('medpelvis3d/samples', '600001')

print(f'CT image size:   {case.ct.GetSize()}')
print(f'Mask image size: {case.mask.GetSize()}')
print(f'Left hip mesh:   {case.left_hip.vertices.shape[0]} vertices')
print(f'Sacrum mesh:     {case.sacrum.vertices.shape[0]} vertices')
print(f'Landmarks:       {len(case.landmarks)} rows')
print(f'Point cloud:     {case.points.shape}')

# Inspect landmark coordinates
print(case.landmarks[['short_name', 'X', 'Y', 'Z']].head())
```

## 2. Open in 3D Slicer for visualisation

Convert the released CSV to a Slicer fiducial file once:

```bash
python scripts/landmarks_to_slicer_fcsv.py \
    --landmarks medpelvis3d/samples/600001/600001-Table-XYZ.csv \
    --out 600001-landmarks.fcsv
```

Open Slicer (https://www.slicer.org), drag-drop:

1. `600001-LeftHipBone.stl`, `600001-RightHipBone.stl`, `600001-Sacrum.stl`
2. `600001-landmarks.fcsv`

The 57 landmarks appear on the bone surface, named by `short_name`.

## 3. Re-sample the point cloud

```bash
python scripts/resample_pointcloud.py \
    --root medpelvis3d/samples \
    --case 600001 \
    --n 25000 \
    --out 600001-points-25000.npy
```

This generates an approximately uniform/even surface sample at any density
`N`. The released 50,000-point clouds provide the reference representation;
this script is a reproducible utility for creating alternative resolutions.

## 4. Reproduce the geometric statistics

For the full cohort (after downloading all 99 cases):

```bash
python scripts/compute_geometry_stats.py --root medpelvis3d
python scripts/compute_geometry_stats.py --root medpelvis3d --by-sex
python scripts/compute_descriptive_stats.py --root medpelvis3d \
    --by-sex --out supp_S2_S3.csv
```

These reproduce **Table 2** of the companion paper and Supplementary
Tables S2 / S3.

## 5. Compute annotation reliability

If you have repeated annotation CSVs in the same per-case format, the same
script can be used for intra-operator or inter-operator reliability:

```bash
python scripts/compute_annotation_reliability.py \
    --annotation-a-dir annotations_release \
    --annotation-b-dir annotations_repeat \
    --cases 600110,600111,600112,600114,600115,600116,600119,600120,600121,600122 \
    --out supp_S4_per_landmark_CI.csv
```

This reports the pooled mean Euclidean distance and 95% CI, the
coordinate-wise ICC(2,1), and the per-landmark stratified table that
underlies Supplementary Table S4.

## 6. Use anatomical metadata

```python
import pandas as pd
from scripts.apply_anatomical_mapping import join_with_mapping

raw = pd.read_csv('medpelvis3d/samples/600001/600001-Table-XYZ.csv',
                  encoding='utf-8-sig')
enriched = join_with_mapping(raw, 'medpelvis3d/landmark_anatomical_mapping.csv')
print(enriched[['short_name', 'anatomical_name_en', 'region', 'side']].head())
```

The mapping table groups landmarks by `region`
(`Left hemipelvis` / `Right hemipelvis` / `Sacrum`) and `side`
(`Left` / `Right` / `Midline`).
