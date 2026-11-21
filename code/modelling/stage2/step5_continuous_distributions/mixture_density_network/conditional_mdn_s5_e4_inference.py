"""Predict the complete seven-day distribution from saved full-refit weights.

No training data, validation coordinates, or validation outcomes are read by
this module. Mixture parameters are east/north geodesic displacements in km,
not a Gaussian mixture directly in longitude/latitude coordinates. Samples
are mapped to WGS84 longitude/latitude without clipping or ocean rejection.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from data3001.paths import file_sha256
from .conditional_mdn_s5_e4 import K_CANDIDATES, finite_pairs
from .conditional_mdn_s5_e4_numerics import to_geographic
from .conditional_mdn_s5_e4_runtime import ROOT
from .conditional_mdn_s5_e4_training import load_model


def validate_origins(origins):
    values = np.asarray(origins, dtype=np.float64)
    if values.shape == (2,):
        values = values[None, :]
    values = finite_pairs(values, "Longitude/latitude origins")
    if (np.abs(values[:, 0]) > 180).any() or (np.abs(values[:, 1]) > 90).any():
        raise ValueError("Origins must be longitude [-180,180], latitude [-90,90]")
    return values


class Predictor:
    """One full-pool fit; no averaging over seeds or outcome-dependent fallback."""

    def __init__(self, fitted, *, metadata=None):
        if fitted.purpose != "full_refit" or fitted.status != "complete":
            raise ValueError("Inference requires a completed full-refit checkpoint")
        self._fit = fitted
        self.metadata = dict(metadata or {})
        self.metadata.update(K=fitted.model.k, horizon_days=7, role=fitted.identity["role"],
                             base_seed=fitted.base_seed, epochs=fitted.epochs_completed,
                             displacement_units="km", covariance_units="km^2",
                             coordinate_order="longitude,latitude", final_test_access=False)

    def mixture(self, origins):
        """Return all K weights, mean displacements, and full covariances.

        For Q origins, shapes are (Q,K), (Q,K,2), and (Q,K,2,2). The two
        displacement axes are east and north in the origin's WGS84 frame.
        """
        origins = validate_origins(origins)
        parameters = self._fit.parameters(origins)
        return dict(origins_lonlat=origins.copy(), weights=parameters["pi"],
                    means_km=parameters["mu"], covariances_km2=parameters["cov"])

    def sample(self, origins, count=1000, seed=0):
        """Return Q × count × 2 IID geographic endpoints with a local RNG."""
        if isinstance(count, (bool, np.bool_)) or not isinstance(count, (int, np.integer)) or count < 1:
            raise ValueError("Sample count must be a positive integer")
        parameters = self.mixture(origins)
        rng = np.random.default_rng(seed)
        samples = []
        for origin, weight, mean, covariance in zip(parameters["origins_lonlat"],
                parameters["weights"], parameters["means_km"], parameters["covariances_km2"]):
            components = rng.choice(len(weight), size=count, p=weight)
            normals = rng.standard_normal((count, 2))
            lower = np.linalg.cholesky(covariance)
            vectors = mean[components] + np.einsum("nij,nj->ni", lower[components], normals)
            samples.append(to_geographic(origin, vectors))
        return np.stack(samples)


def from_checkpoint(checkpoint_path, *, sha256=None):
    """Load a completed E4 or byte-preserved parent E3 full refit."""
    path = Path(checkpoint_path).resolve()
    if sha256 is not None and file_sha256(path) != sha256:
        raise ValueError("Saved model checkpoint checksum changed")
    import torch
    from .conditional_mdn_s5_e3_training import CONTRACT_SHA256 as parent_contract
    identity = torch.load(path, map_location='cpu', weights_only=False)['identity']
    if identity.get('contract_sha256') == parent_contract:
        from .conditional_mdn_s5_e3_inference import from_checkpoint as parent_loader
        return parent_loader(path, sha256=sha256)
    return Predictor(load_model(path), metadata={"checkpoint": str(path)})


def load_selected_model(run_name, *, root=ROOT):
    """Load the audited, inner-selected outer full refit without outcome files."""
    root = Path(root).resolve()
    if Path(run_name).name != run_name or not run_name.startswith("conditional_mdn_s5_e4_"):
        raise ValueError("Invalid MDN run name")
    base = root / "results/runs" / run_name / "formal_v1"
    audit_path = root / "provenance/runs" / run_name / "formal_v1/final_audit.json"
    audit = json.loads(audit_path.read_text())
    if (audit.get("status") != "complete" or audit.get("passed") is not True
            or audit.get("final_test_access") is not False):
        raise PermissionError("A completed passing final audit is required")
    choice_path = base / "selection.json"
    audited = audit.get("evidence_sha256", {})
    relative = choice_path.relative_to(root).as_posix()
    if audited.get(relative) != file_sha256(choice_path):
        raise ValueError("Audited inner selection checksum changed or missing")
    choice = json.loads(choice_path.read_text())
    k = choice.get("selected_k")
    if choice.get("status") != "complete" or isinstance(k, bool) or k not in K_CANDIDATES:
        raise ValueError("No completed registered inner selection")
    manifest_path = base / "C_outer" / f"K{k}" / "manifest.json"
    if audited.get(manifest_path.relative_to(root).as_posix()) != file_sha256(manifest_path):
        raise ValueError("Audited full-refit manifest checksum changed or missing")
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get("status") != "complete" or manifest.get("role") != "C_outer"
            or manifest.get("k") != k or manifest.get("final_test_access") is not False):
        raise ValueError("Saved selected-model identity differs")
    record = manifest["full_refit"]["checkpoint"]
    checkpoint = (base / record["path"]).resolve()
    if not checkpoint.is_relative_to(base.resolve()):
        raise ValueError("Checkpoint path escapes formal results")
    predictor = from_checkpoint(checkpoint, sha256=record["sha256"])
    if (predictor.metadata["K"] != k or predictor.metadata["role"] != "C_outer"
            or predictor.metadata["epochs"] != manifest["selected_epoch"]
            or predictor.metadata["base_seed"] != manifest["selected_seed"]):
        raise ValueError("Full-refit checkpoint differs from selected-model manifest")
    predictor.metadata.update(run=run_name, selected_k=k, audit=str(audit_path))
    return predictor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("longitude", type=float)
    parser.add_argument("latitude", type=float)
    parser.add_argument("--samples", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20261126)
    args = parser.parse_args()
    predictor = load_selected_model(args.run)
    origin = [args.longitude, args.latitude]
    result = {key: value.tolist() for key, value in predictor.mixture(origin).items()}
    result["metadata"] = predictor.metadata
    if args.samples:
        result["samples_lonlat"] = predictor.sample(origin, args.samples, args.seed)[0].tolist()
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
