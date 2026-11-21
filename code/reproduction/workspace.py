"""Construct real, isolated historical-layout execution views from the delivery map."""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    os.replace(temporary, path)


def safe_relative(value):
    path = PurePosixPath(str(value))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("An input must be a project-relative path without traversal")
    if "restricted_test" in path.parts or "test" in path.parts:
        raise PermissionError("Final-test data are excluded from delivery execution views")
    return path.as_posix()


class DeliveryMap:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / "docs/migration_manifest.json"
        document = json.loads(self.path.read_text())
        if document.get("schema_version") != 1:
            raise ValueError("Unsupported migration manifest")
        self.entries = document["files"]
        self.by_source = {entry["source"]: entry for entry in self.entries}

    def resolve(self, relative):
        relative = safe_relative(relative)
        entry = self.by_source.get(relative)
        if entry:
            target = self.root / safe_relative(entry["target"])
        else:
            parents = [item for item in self.entries if item.get("kind") == "directory"
                       and relative.startswith(item["source"].rstrip("/") + "/")]
            if parents:
                entry = max(parents, key=lambda item: len(item["source"]))
                suffix = relative[len(entry["source"].rstrip("/")) + 1:]
                target = self.root / safe_relative(entry["target"]) / suffix
            else:
                # Unmoved registered assets are legitimate sources, recorded by bind().
                target = self.root / relative
        resolved = target.resolve()
        if not resolved.is_relative_to(self.root):
            raise PermissionError("Input resolves outside the delivery repository: " + relative)
        safe_relative(resolved.relative_to(self.root).as_posix())
        if not target.exists():
            raise FileNotFoundError(f"Required delivery input is absent: {relative} -> {target}")
        return target


def independent_copy(source, destination):
    """Use APFS copy-on-write when available; never hard-link mutable run files."""
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    if sys.platform == "darwin":
        library = ctypes.CDLL(None, use_errno=True)
        clone = getattr(library, "clonefile", None)
        if clone is not None:
            clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
            clone.restype = ctypes.c_int
            if clone(os.fsencode(source), os.fsencode(destination), 0) == 0:
                return "apfs_clone"
    needed = source.stat().st_size + (256 << 20)
    if shutil.disk_usage(destination.parent).free < needed:
        raise OSError("Insufficient disk space for an independent input copy; no hard-link fallback")
    shutil.copy2(source, destination)
    return "copy"


class ExecutionWorkspace:
    def __init__(self, root, run_id=None):
        self.root = Path(root).resolve()
        self.mapping = DeliveryMap(self.root)
        run_id = run_id or datetime.now(timezone.utc).strftime("delivery_%Y%m%dT%H%M%S_%fZ")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", run_id):
            raise ValueError("Run ID must be a safe single path component")
        output = self.root / "results/reproduced"
        # Internal aliases are unsafe too: results/reproduced -> archive would
        # pass a repository-containment check but mutate preserved evidence.
        if any(path.is_symlink() for path in (output.parent, output)) or output.resolve() != output:
            raise PermissionError("Reproduction output must be the real results/reproduced directory")
        output.mkdir(parents=True, exist_ok=True)
        self.directory = output / run_id
        self.directory.mkdir(exist_ok=False)
        self.path = self.directory / "workspace"
        self.path.mkdir()
        self.records = {}
        self.status = {"schema_version": 1, "run_id": run_id, "status": "preparing",
                       "created_utc": datetime.now(timezone.utc).isoformat(),
                       "migration_manifest_sha256": sha256(self.mapping.path),
                       "final_test_access": False, "new_fits": [], "reused_inputs": []}
        delivery_sources = [Path(__file__).parents[1] / "workflow.py", *Path(__file__).parent.glob("*.py")]
        self.status["delivery_source_sha256"] = {path.name: sha256(path) for path in delivery_sources if path.is_file()}
        write_json(self.directory / "run.json", self.status)

    def bind(self, relative, *, expected_sha256=None):
        relative = safe_relative(relative)
        source = self.mapping.resolve(relative)
        if source.is_dir():
            if expected_sha256:
                raise ValueError("Directory inputs require per-file identities")
            result = []
            for base, directories, filenames in os.walk(source, followlinks=False):
                directories[:] = sorted(name for name in directories
                                         if name not in {"test", "restricted_test", "__pycache__", ".git"})
                for name in sorted(filenames):
                    if name in {".DS_Store"} or name.endswith((".pyc", ".pyo")):
                        continue
                    suffix = (Path(base) / name).relative_to(source).as_posix()
                    result.extend(self.bind(relative + "/" + suffix))
            return result
        destination = self.path / relative
        digest = sha256(source)
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("Input identity mismatch: " + relative)
        if relative in self.records:
            if self.records[relative]["sha256"] != digest:
                raise ValueError("Bound input identity changed: " + relative)
            return [destination]
        if destination.exists():
            raise FileExistsError("Unrecorded file occupies execution input: " + relative)
        method = independent_copy(source, destination)
        if sha256(destination) != digest:
            raise ValueError("Copied input checksum mismatch: " + relative)
        self.records[relative] = {"source": source.relative_to(self.root).as_posix(),
                                  "execution_path": relative, "sha256": digest,
                                  "bytes": source.stat().st_size, "method": method,
                                  "role": "reused_input"}
        return [destination]

    def materialize_sources(self):
        for entry in self.mapping.entries:
            source = entry["source"]
            if source.startswith(("src/", "tests/", "configs/")) and entry.get("kind") != "directory":
                self.bind(source, expected_sha256=entry.get("sha256"))
        if not (self.path / "src/data3001").is_dir():
            raise FileNotFoundError("Migration manifest contains no historical scientific package")
        self.save_inventory()

    def bind_assets(self, names):
        catalog = json.loads(self.mapping.resolve("configs/assets.json").read_text())
        for name in sorted(set(names)):
            item = catalog["assets"][name]
            if item.get("split") == "test":
                raise PermissionError("Requested a locked asset: " + name)
            self.bind(item["path"], expected_sha256=item.get("sha256") if item.get("kind") == "file" else None)

    def save_inventory(self):
        write_json(self.directory / "input_manifest.json", {
            "schema_version": 1, "final_test_trajectory_files_copied": False,
            "shared_raw_chunks_may_contain_other_ids": self.status.get("shared_raw_chunks_may_contain_other_ids", False),
            "final_test_trajectories_requested": False,
            "files": [self.records[key] for key in sorted(self.records)],
            "logical_input_bytes": sum(record["bytes"] for record in self.records.values())})

    def finish(self, status, **details):
        self.save_inventory()
        self.status.update(status=status, **details)
        write_json(self.directory / "run.json", self.status)
        return dict(self.status, output_directory=str(self.directory))
