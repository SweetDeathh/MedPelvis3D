# MedPelvis3D

A 3D pelvic anatomy dataset for anatomical landmark detection.

This repository contains **example scripts and utilities** for working with the
**MedPelvis3D** dataset. The dataset itself (CT volumes, segmentation masks,
surface meshes, landmark coordinates, point clouds, and metadata) is hosted on
Zenodo and is not stored in this repository.

- **Dataset DOI**: [10.5281/zenodo.20473746](https://doi.org/10.5281/zenodo.20473746)
- **Companion paper**: *MedPelvis3D: a 3D pelvic anatomy dataset for anatomical landmark detection* (Scientific Data, under review)

## Overview

MedPelvis3D contains **99 de-identified pelvic CT cases** retrospectively
collected at a tertiary clinical center. For each case, the dataset provides:

- De-identified CT volume (NIfTI, `.nii.gz`)
- Pelvic segmentation mask (NIfTI; labels: `1` = LeftHipBone, `2` = RightHipBone, `3` = Sacrum)
- Three surface meshes in STL format named after the anatomical component
- 57 expert-annotated 3D anatomical landmarks (CSV)
- A 50,000-point reference point cloud sampled from the surface mesh (`.npy`)

All coordinates are expressed in **millimetres** in the original patient-level
CT (LPS) coordinate system.

## Repository contents

```
MedPelvis3D/
├── README.md                          (this file)
├── LICENSE                            (MIT for the code in this repository)
├── requirements.txt
├── scripts/
│   ├── load_case.py                   load CT/mask/STL/landmarks for a case
│   ├── resample_pointcloud.py         resample the surface mesh to N points
│   ├── compute_geometry_stats.py      inter-ASIS, bounding box, bone volume
│   ├── compute_descriptive_stats.py   Min/Q1/Mean/SD/Median/IQR/Q3/Max
│   ├── compute_annotation_reliability.py
│   │                                  intra- and inter-operator reliability statistics
│   ├── rebuild_stl_from_masks.py      reconstruct STL surfaces from labelled NIfTI masks
│   ├── mesh_qc_and_repair.py           audit STL topology and optionally apply conservative repair
│   ├── package_cases.py                create one complete ZIP archive per subject
│   └── apply_anatomical_mapping.py    join CSV landmarks with the mapping table
└── examples/
    └── basic_usage.ipynb              walk through the typical workflow
```

The dataset itself is **not** included; download it from Zenodo and unzip
the archives into a working directory before running these scripts.

## Quick start

### 1. Download the dataset

```bash
# Each archive is downloaded separately from Zenodo:
#   ct_nifti_part{1..4}of4.zip            (~13.8 GB total)
#   masks_nifti.zip                       (~29 MB)
#   stl_models.zip                        (~2.1 GB)
#   point_clouds_50000.zip                (~55 MB)
#   annotations.zip                       (~220 KB)
#   patient_metadata.csv
#   landmark_anatomical_mapping.csv
#   samples.zip                           (5 example cases, uncompressed after extraction)
```

Unzip into a single directory:

```
medpelvis3d/
  ct_nifti/                  600001.nii.gz, 600002.nii.gz, ...
  masks_nifti/               600001-mask.nii.gz, ...
  stl_models/                600001-LeftHipBone.stl, 600001-RightHipBone.stl, 600001-Sacrum.stl, ...
  point_clouds_50000/        600001-points-50000.npy, ...
  annotations/               600001-Table-XYZ.CSV, ...
  patient_metadata.csv
  landmark_anatomical_mapping.csv
  samples/                   600001/, 600002/, 600003/, 600004/, 600052/  (from samples.zip)
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Load a case and inspect

```python
from scripts.load_case import load_case

case = load_case('medpelvis3d', '600001')
print(case.landmarks.head())
print(f'Mesh vertices: {case.left_hip.vertices.shape[0]}')
print(f'Point cloud shape: {case.points.shape}')
```

### 4. Reproduce the geometric statistics

```bash
python scripts/compute_geometry_stats.py --root medpelvis3d
python scripts/compute_descriptive_stats.py --root medpelvis3d
```

These reproduce Table 2 (geometric parameters) and Supplementary Tables S2/S3
(full descriptive statistics) in the companion paper.

### 5. Rebuild STL surfaces from segmentation masks

The release mesh-generation procedure is reproducible from the labelled NIfTI
masks. The script uses the Lewiner marching-cubes implementation in
`scikit-image`, applies each NIfTI affine, converts the result to the release
LPS coordinate convention, and removes only disconnected zero-volume fragments.
It does not smooth, decimate, or remesh the surface, and it never modifies the
input masks. The released label convention is `1 = LeftHipBone`,
`2 = RightHipBone`, and `3 = Sacrum`.

Write rebuilt meshes to a separate directory and inspect the report before
using them to replace any released files:

```bash
python scripts/rebuild_stl_from_masks.py \
  --mask-dir medpelvis3d/masks_nifti \
  --output-dir rebuilt_stl \
  --report rebuilt_stl/mesh_qc.csv
```

The command refuses to overwrite an existing STL unless `--overwrite` is
provided explicitly. The script assumes that the mask labels already follow
the stated anatomical convention; it does not infer left/right side labels
from landmarks.

### 6. Audit or conservatively repair STL meshes

```bash
python scripts/mesh_qc_and_repair.py \
  --input-dir rebuilt_stl \
  --report rebuilt_stl/mesh_qc_with_self_intersections.csv \
  --self-intersections
```

To write repaired copies without modifying the source files, add
`--repair-dir repaired_stl --fill-simple-holes`. The repair sequence removes
duplicate and degenerate faces, removes unreferenced vertices, fixes normals
and winding, and optionally fills simple holes. It does not smooth, decimate,
or remesh the surfaces. Review the CSV report before replacing any released
mesh.

### 7. Create one archive per subject

```bash
python scripts/package_cases.py \
  --root medpelvis3d \
  --output-dir case_archives
```

The command requires every case-level modality, writes `<case_id>.zip` files,
adds a one-row `metadata.csv` to each archive, and records archive hashes and
missing-file checks in `manifest.json`.

## Landmark naming

Each landmark includes anatomical naming fields in the released CSVs:

| Column | Example |
|---|---|
| `short_name` | `ASIS_L` |
| `anatomical_name_en` | `Left anterior superior iliac spine` |

`short_name` is the primary identifier column used in the released landmark CSV files.
`landmark_anatomical_mapping.csv` provides the full table linking each
short name to its English anatomical term, region (`Left hemipelvis` /
`Right hemipelvis` / `Sacrum`), and side (`Left` / `Right` / `Midline`).

## Citation

If you use MedPelvis3D, please cite the dataset and the companion paper:

```bibtex
@dataset{guo2026medpelvis3d_dataset,
  author    = {Guo, Na and Pan, Jiachen and Zhang, Gang and Wang, Jiaxi and
               Su, Xiuyun and Qi, Yansong and Liu, Mingfa and Zhang, Qinjian
               and Hao, Ming},
  title     = {MedPelvis3D: a 3D pelvic anatomy dataset for anatomical
               landmark detection},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.20473746}
}
```

The companion *Scientific Data* paper citation will be added once the article
is published.

## License

- **Code in this repository**: MIT License (see [LICENSE](LICENSE))
- **Dataset on Zenodo**: CC-BY-4.0 (per the Zenodo deposit)

## Contact

For questions about the dataset or the analysis code, please open an issue on
this repository or contact the corresponding authors listed in the companion
paper.
