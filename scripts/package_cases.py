"""Create one ZIP archive per MedPelvis3D case.

Each archive contains the case-level CT volume, mask, three STL components,
point cloud, landmark table, and a one-row metadata CSV when available.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path


COMPONENTS = ("LeftHipBone", "RightHipBone", "Sacrum")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_metadata(path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    if not path.exists():
        return [], {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        if "case_id" not in fields:
            raise ValueError(f"metadata is missing case_id: {path}")
        rows = {str(row["case_id"]).strip(): row for row in reader}
    return fields, rows


def discover_case_ids(root: Path) -> list[str]:
    ids = set()
    for path in (root / "annotations").glob("*-Table-XYZ.*"):
        ids.add(path.name.split("-Table-XYZ", 1)[0])
    for path in (root / "ct_nifti").glob("*.nii.gz"):
        ids.add(path.name.removesuffix(".nii.gz"))
    return sorted(ids)


def case_files(root: Path, case_id: str) -> list[tuple[Path, str]]:
    annotation_matches = sorted((root / "annotations").glob(f"{case_id}-Table-XYZ.*"))
    annotation = annotation_matches[0] if annotation_matches else root / "annotations" / f"{case_id}-Table-XYZ.CSV"
    items = [
        (root / "ct_nifti" / f"{case_id}.nii.gz", f"{case_id}/{case_id}.nii.gz"),
        (root / "masks_nifti" / f"{case_id}-mask.nii.gz", f"{case_id}/{case_id}-mask.nii.gz"),
        (root / "point_clouds_50000" / f"{case_id}-points-50000.npy", f"{case_id}/{case_id}-points-50000.npy"),
        (annotation, f"{case_id}/{annotation.name}"),
    ]
    for component in COMPONENTS:
        name = f"{case_id}-{component}.stl"
        items.append((root / "stl_models" / name, f"{case_id}/{name}"))
    return items


def metadata_bytes(fields: list[str], row: dict[str, str]) -> bytes:
    import io

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    fields, metadata = read_metadata(root / "patient_metadata.csv")
    case_ids = discover_case_ids(root)
    if not case_ids:
        raise SystemExit(f"no case IDs found under {root}")

    manifest = []
    failures = 0
    for case_id in case_ids:
        files = case_files(root, case_id)
        missing = [str(path.relative_to(root)) for path, _ in files if not path.is_file()]
        if fields and case_id not in metadata:
            missing.append("patient_metadata.csv row")
        status = "complete" if not missing else "incomplete"
        if missing and not args.allow_missing:
            failures += 1
            manifest.append({"case_id": case_id, "status": status, "missing": missing})
            continue

        archive = output / f"{case_id}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for path, arcname in files:
                if path.is_file():
                    zf.write(path, arcname)
            if fields and case_id in metadata:
                zf.writestr(f"{case_id}/metadata.csv", metadata_bytes(fields, metadata[case_id]))
        manifest.append(
            {
                "case_id": case_id,
                "status": status,
                "missing": missing,
                "archive": archive.name,
                "bytes": archive.stat().st_size,
                "sha256": sha256(archive),
            }
        )

    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if failures:
        raise SystemExit(f"{failures} incomplete cases; see {manifest_path}")
    print(f"created {len(manifest)} case archives; manifest={manifest_path}")


if __name__ == "__main__":
    main()
