"""Shared read guards and immutable run I/O; no model fitting."""
import json
import os
from pathlib import Path
from data3001.paths import file_sha256

class ReadOnlyInputs:
    """Process-level evidence and guard against test reads/input mutations."""
    def __init__(self, root, run, *, data_root=None):
        self.root = root.resolve()
        self.data_root = (data_root or root / "data").resolve()
        self.allowed = [p.resolve() for p in run.values()]
        self.read_ids = set()
        self.denied = []
        self.active = True

    def __call__(self, event, args):
        if not self.active or event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        if not path.is_relative_to(self.root) and not path.is_relative_to(self.data_root):
            return
        relative = path.relative_to(self.root) if path.is_relative_to(self.root) else path.relative_to(self.data_root)
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
        locked = path.is_relative_to(self.data_root / "test") or "restricted_test" in relative.parts
        if locked or (writing and not any(path.is_relative_to(p) for p in self.allowed)):
            self.denied.append({"path": relative.as_posix(), "writing": bool(writing)})
            raise PermissionError("Nested CV cannot access final-test labels or modify existing project inputs.")
        if path.is_relative_to(self.data_root / "train") and path.suffix == ".parquet":
            self.read_ids.add(int(path.stem))


def save_frame(paths, path, table):
    if path.suffix == ".parquet":
        paths.publish(path, lambda stream: table.to_parquet(stream, index=False, compression="zstd"))
    else:
        payload = table.to_csv(index=False).encode("utf-8")
        paths.publish(path, lambda stream: stream.write(payload))


def save_json(paths, path, value):
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    paths.publish(path, lambda stream: stream.write(payload))



def validate_parent_receipt(receipt):
    if (receipt.get("completed") is not True or receipt.get("final_test_access") is not False
            or not isinstance(receipt.get("output_sha256"), dict)):
        raise ValueError("A complete, sealed development-only input run is required.")


def verified_run(paths, run_id):
    if Path(run_id).name != run_id or not run_id or run_id in (".", ".."):
        raise ValueError("Unsafe input run name.")
    receipt_path = paths.root / "provenance/runs" / run_id / "outputs.json"
    receipt = json.loads(receipt_path.read_text())
    validate_parent_receipt(receipt)
    for relative, checksum in receipt["output_sha256"].items():
        rel = Path(relative)
        if rel.is_absolute() or ".." in rel.parts or not rel.parts[:2] in (
                ("results", "runs"), ("provenance", "runs")) or rel.parts[2] != run_id:
            raise ValueError("Input receipt contains an unexpected path.")
        if file_sha256(paths.root / rel) != checksum:
            raise ValueError("Input run artifact checksum mismatch: " + relative)
    return receipt_path


def _source_hashes(paths):
    return {p.relative_to(paths.root).as_posix(): file_sha256(p)
            for p in (paths.root/"src/data3001").rglob("*.py")}


def _seal(paths, run, verification):
    save_json(paths, run["provenance"]/"verification.json", verification)
    files = [p for directory in run.values() for p in directory.rglob("*") if p.is_file()]
    save_json(paths, run["provenance"]/"outputs.json", {
        "completed": True, "final_test_access": False,
        "output_sha256": {p.relative_to(paths.root).as_posix(): file_sha256(p) for p in files}})
