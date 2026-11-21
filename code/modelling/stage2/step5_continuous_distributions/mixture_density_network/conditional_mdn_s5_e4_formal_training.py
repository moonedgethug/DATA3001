"""Formal full-pool MDN fits and immutable, outcome-blind forecast exports.

This orchestration retains the contracted 500-epoch/early-stop semantics. Wall
time is the supervisor's responsibility; no time budget, data thinning, model
fallback, or validation-endpoint reader is introduced here.
"""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import torch

from data3001.paths import file_sha256
from . import conditional_mdn_s5_e4_inputs as inp
from . import conditional_mdn_s5_e4_numerics as num
from . import conditional_mdn_s5_e4_training as training
from . import conditional_mdn_s5_e4_reuse as reuse
from .conditional_mdn_s5_e4 import COVARIANCE_FLOOR, K_CANDIDATES, finite_pairs
from .conditional_mdn_s5_e4_runtime import atomic_json


ROLES = ("C_T0", "C_T1", "C_outer")
SCHEMA_VERSION = 1
_MODEL_FOLDER = "src/data3001/modelling/continuous_models/"
_CORE_FILES = (
    *(_MODEL_FOLDER + name for name in (
        "conditional_mdn_s5_e4.py", "conditional_mdn_s5_e4_training.py",
        "conditional_mdn_s5_e4_inputs.py", "conditional_mdn_s5_e4_numerics.py",
        "conditional_mdn_s5_e4_runtime.py", "conditional_mdn_s5_e4_formal_training.py",
        "conditional_mdn_s5_e4_reuse.py", "conditional_mdn_s5_e3_formal_training.py")),
    "src/data3001/modelling/common/runtime.py", "src/data3001/paths.py",
    "configs/conditional_mdn_s5_e4.json",
)


class EpochCapPause(RuntimeError):
    """The chosen seed's raw best lies in the cap's last 30 epochs."""


def core_source_hashes():
    """Hash only dependencies that define training, data access, and exports."""
    return {name: file_sha256(inp.ROOT / name) for name in _CORE_FILES}


def _freeze_json(path, value):
    path = Path(path)
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError("Immutable formal receipt changed: " + str(path))
    else:
        atomic_json(path, value)


def _freeze_sources(provenance):
    hashes = core_source_hashes()
    folder = provenance / "training_sources"
    _freeze_json(folder / "hashes.json", hashes)
    for name, digest in hashes.items():
        source, target = inp.ROOT / name, folder / name
        if target.exists():
            if file_sha256(target) != digest:
                raise ValueError("Immutable training source snapshot changed: " + name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            if file_sha256(target) != digest:
                raise ValueError("Training source changed during snapshot: " + name)
    return hashes


def _artifact_path(formal_root, relative):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe formal artifact path")
    path = formal_root / relative
    if not path.resolve().is_relative_to(formal_root.resolve()):
        raise ValueError("Formal artifact escapes its results root")
    return path


def _artifact_record(path, formal_root):
    return {"path": Path(path).relative_to(formal_root).as_posix(),
            "sha256": file_sha256(path)}


def _verify_artifact(record, formal_root):
    path = _artifact_path(formal_root, record["path"])
    if not path.is_file() or file_sha256(path) != record["sha256"]:
        raise ValueError("Formal artifact checksum changed: " + str(path))
    return path


def _selection(formal_root, role, run):
    if role != "C_outer":
        return None, None
    path = formal_root / "selection.json"
    if not path.is_file():
        raise PermissionError("Completed inner selection is required before outer training")
    selection = json.loads(path.read_text())
    k = selection.get("selected_k")
    if (selection.get("status") != "complete" or isinstance(k, bool)
            or not isinstance(k, int) or k not in K_CANDIDATES):
        raise PermissionError("Inner selection must be complete with a frozen selected_k")
    evidence = selection.get('selection_inputs_sha256', {})
    if (selection.get('contract_sha256') != training.CONTRACT_SHA256 or
        selection.get('source_run_name') != run['results'].name or not evidence or
        selection.get('provisional_k') not in K_CANDIDATES):
        raise PermissionError('Inner selection requires current-run contract and scoring evidence')
    covered = set()
    for name, digest in evidence.items():
        item = Path(name) if Path(name).is_absolute() else inp.ROOT/name
        item = item.resolve()
        if not any(item.is_relative_to((base/'formal_v1').resolve()) for base in run.values()):
            raise PermissionError('Inner selection evidence belongs to another run')
        if file_sha256(item) != digest:
            raise PermissionError('Inner selection evidence changed')
        for inner in ('C_T0', 'C_T1'):
            if inner not in item.parts:
                continue
            if item.name == 'forecast_freeze.json':
                covered.add((inner, 'forecast'))
            if item.name == 'complete.json' and 'inner_energy' in item.parts:
                covered.add((inner, 'inner_energy'))
            if item.name == 'complete.json' and 'inner_regions' in item.parts:
                covered.add((inner, 'inner_regions'))
    required = {(inner, kind) for inner in ('C_T0', 'C_T1') for kind in
                (('forecast', 'inner_energy', 'inner_regions') if selection['provisional_k'] > 1
                 else ('forecast', 'inner_energy'))}
    if not required <= covered:
        raise PermissionError('Inner selection lacks complete forecast and scoring receipts')
    return k, file_sha256(path)


def _curve_receipt(result, formal_root):
    return {"base_seed": int(result.base_seed), "purpose": result.purpose,
            "status": result.status, "epochs_completed": int(result.epochs_completed),
            "best_epoch": int(result.best_epoch), "best_nll": result.best_nll,
            "history": result.history, "checkpoint": _artifact_record(result.checkpoint_path, formal_root),
            "standardizer": result.standardizer.state_dict(), "identity": result.identity}


def _training_receipt(result, formal_root, role, k):
    seeds = result.seed_results
    if tuple(seed.base_seed for seed in seeds) != training.BASE_SEEDS:
        raise ValueError("Formal training must retain all three declared seeds in order")
    if any(seed.status not in ("early_stopped", "epoch_cap_reached") for seed in seeds):
        raise RuntimeError("A formal early-stop fit is not terminal")
    selected = training.select_seed(seeds)
    if selected.base_seed != result.selected_seed:
        raise ValueError("Formal seed choice differs from the contracted NLL rule")
    pause = training.requires_cap_pause(selected)
    if pause != result.requires_pause:
        raise ValueError("Formal epoch-cap decision differs from the contracted rule")
    receipt = {"schema_version": SCHEMA_VERSION, "role": role, "k": k,
               "selected_seed": int(result.selected_seed), "selected_epoch": int(selected.best_epoch),
               "requires_pause": pause, "seeds": [_curve_receipt(seed, formal_root) for seed in seeds],
               "full_refit": None}
    if result.fit is not None:
        fit = result.fit
        if (pause or fit.status != "complete" or fit.purpose != "full_refit"
                or fit.base_seed != selected.base_seed or fit.epochs_completed != selected.best_epoch):
            raise RuntimeError("Full-pool refit does not match the frozen selected seed and epoch")
        receipt["full_refit"] = _curve_receipt(fit, formal_root)
    elif not pause:
        raise RuntimeError("Formal fit has no completed full-pool refit")
    return receipt


def _parameter_diagnostics(parameters, target_scale, history):
    pi, mu, cov = (np.asarray(parameters[key]) for key in ("pi", "mu", "cov"))
    if pi.ndim != 2 or mu.shape != (*pi.shape, 2) or cov.shape != (*pi.shape, 2, 2):
        raise ValueError("Invalid formal MDN parameter shapes")
    if any(value.dtype != np.dtype("float64") for value in (pi, mu, cov)):
        raise ValueError("Formal MDN parameters must use float64")
    if not all(np.isfinite(value).all() for value in (pi, mu, cov)):
        raise FloatingPointError("Nonfinite formal MDN parameters; no fallback is permitted")
    if (pi < 0).any() or np.max(np.abs(pi.sum(axis=1) - 1)) > 1e-10:
        raise FloatingPointError("Invalid formal mixture probabilities")
    scale = np.asarray(target_scale, dtype=np.float64)
    if scale.shape != (2,) or not np.isfinite(scale).all() or (scale <= 0).any():
        raise FloatingPointError("Nonfinite or nonpositive formal displacement scale")
    zcov = cov / scale[None, None, :, None] / scale[None, None, None, :]
    if not np.allclose(zcov, zcov.swapaxes(-1, -2), rtol=0, atol=1e-10):
        raise FloatingPointError("Formal covariance is not symmetric")
    minimum = np.linalg.eigvalsh(zcov)[..., 0]
    if np.min(minimum) < COVARIANCE_FLOOR - 1e-10:
        raise FloatingPointError("Formal standardized covariance floor failed")
    log_pi = np.zeros_like(pi)
    np.log(pi, where=pi > 0, out=log_pi)
    entropy = -(pi * log_pi).sum(axis=1)
    clip_count = sum(int(row["clipped_steps"]) for row in history)
    batch_count = sum(len(row["batch_sizes"]) for row in history)
    near_floor = (pi * (minimum <= 1.01 * COVARIANCE_FLOOR)).sum(axis=1)
    return {"prediction_count": len(pi), "mixture_entropy_mean_nats": float(entropy.mean()),
            "mixture_entropy_min_nats": float(entropy.min()),
            "mixture_entropy_max_nats": float(entropy.max()),
            "effective_components_mean": float(np.exp(entropy).mean()),
            "standardized_covariance_min_eigenvalue": float(minimum.min()),
            "covariance_floor": COVARIANCE_FLOOR,
            "near_floor_definition": "component minimum standardized eigenvalue <= 1.01 * floor",
            "near_floor_probability_mass_query_mean": float(near_floor.mean()),
            "near_floor_probability_mass_query_max": float(near_floor.max()),
            "full_refit_clipped_steps": clip_count, "full_refit_optimizer_steps": batch_count,
            "full_refit_gradient_clip_rate": clip_count / batch_count if batch_count else 0.}


def _freeze_parameters(path, arrays):
    if path.exists():
        with np.load(path, allow_pickle=False) as previous:
            if set(previous.files) != set(arrays) or any(
                previous[name].dtype != value.dtype or not np.array_equal(previous[name], value)
                for name, value in arrays.items()
            ):
                raise ValueError("Immutable formal parameters changed")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _verify_model(formal_root, role, k, identity, query):
    if k in reuse.PARENT_KS:
        return reuse.verify_import(formal_root, role, k, identity, query)
    folder = formal_root / role / f"K{k}"
    path = folder / "manifest.json"
    manifest = json.loads(path.read_text())
    if (manifest.get("status") != "complete" or manifest.get("role") != role
            or manifest.get("k") != k or manifest.get("identity") != identity):
        raise ValueError("Formal model identity changed: " + str(path))
    parameter_path = _verify_artifact(manifest["parameters"], formal_root)
    if parameter_path != folder / "parameters.npz":
        raise ValueError("Unexpected formal parameter archive path")
    _verify_artifact(manifest["training_receipt"], formal_root)
    for fit in [*manifest["seeds"], manifest["full_refit"]]:
        _verify_artifact(fit["checkpoint"], formal_root)
    with np.load(parameter_path, allow_pickle=False) as archive:
        if (archive["query_keys"].dtype != np.dtype("int64")
                or not np.array_equal(archive["query_keys"], query[inp.KEY].to_numpy(dtype=np.int64))
                or not np.array_equal(archive["origins"], query[["lon", "lat"]].to_numpy(dtype=np.float64))):
            raise ValueError("Formal prediction query roster changed")
        if archive["pi"].shape != (len(query), k):
            raise ValueError("Formal prediction count or candidate changed")
        _parameter_diagnostics(archive, archive["target_scale"], manifest["full_refit"]["history"])
    return {"manifest": path.relative_to(formal_root).as_posix(), "manifest_sha256": file_sha256(path),
            "parameters": parameter_path.relative_to(formal_root).as_posix(),
            "parameters_sha256": manifest["parameters"]["sha256"]}


def _verify_freeze(receipt, formal_root, role, identity, query):
    if (receipt.get("status") != "complete" or receipt.get("role") != role
            or receipt.get("identity") != identity
            or set(receipt.get("models", {})) != {str(k) for k in K_CANDIDATES}):
        raise ValueError("Formal role freeze identity changed")
    for k in K_CANDIDATES:
        actual = _verify_model(formal_root, role, k, identity, query)
        if actual != receipt["models"][str(k)]:
            raise ValueError("Frozen formal model manifest changed")


def train_role(run_name, role, formal_root=None):
    """Fit/import registered candidates sequentially and freeze every query distribution.

    ``formal_root`` optionally selects a results subfolder within the same run.
    Provenance remains in ``run['provenance']/formal_v1``. No validation targets
    are loaded, including after all registered outer distributions have been frozen.
    """
    if role not in ROLES:
        raise ValueError("Formal training role must be C_T0, C_T1, or C_outer")
    _, run, cfg, approval, guard = inp.context(run_name)
    formal_root = Path(formal_root) if formal_root is not None else run["results"] / "formal_v1"
    formal_root = formal_root.resolve()
    if not formal_root.is_relative_to(run["results"].resolve()):
        raise ValueError("Formal results must stay inside the authorized run")
    provenance = run["provenance"] / "formal_v1"
    role_provenance = provenance / role
    role_provenance.mkdir(parents=True, exist_ok=True)
    if tuple(cfg["candidates"]) != K_CANDIDATES or tuple(cfg["initialization_seeds"]) != training.BASE_SEEDS:
        raise ValueError("Formal candidate or seed roster differs from the contract")
    torch.set_num_threads(cfg["training_threads"])
    try:
        selected_k, selection_sha256 = _selection(formal_root, role, run)
        sources = _freeze_sources(provenance)
        roles = inp.cohorts(cfg)
        access = inp.freeze_access(run, roles)
        fit, query = roles[role]["fit"], roles[role]["query"]
        x = finite_pairs(fit[["lon", "lat"]].to_numpy(dtype=np.float64), "Formal fit origins")
        origins = finite_pairs(query[["lon", "lat"]].to_numpy(dtype=np.float64), "Formal query origins")
        identity = {"stage": "formal_training_v1", "schema_version": SCHEMA_VERSION,
                    "role": role, "contract_sha256": cfg["contract_sha256"], "source_hashes": sources,
                    "fit_key_sha256": inp.key_digest(fit), "query_key_sha256": inp.key_digest(query),
                    "fit_origins_sha256": training._array_digest(x),
                    "query_origins_sha256": training._array_digest(origins),
                    "fit_pairs": len(fit), "fit_ids": int(fit.id.nunique()),
                    "optimization_ids": access[role]["optimization_ids"],
                    "stop_ids": access[role]["stop_ids"], "selection_sha256": selection_sha256,
                    "input_source_hashes": {path: digest for path, digest in approval["protected_files"].items()
                                            if Path(path).name in ("training_coordinates.parquet",
                                                                   "query_coordinates.parquet", "roles.parquet")}}
        _freeze_json(role_provenance / "training_identity.json", identity)
        freeze_path = role_provenance / "forecast_freeze.json"
        if freeze_path.exists():
            receipt = json.loads(freeze_path.read_text())
            _verify_freeze(receipt, formal_root, role, identity, query)
            return receipt

        models = {}
        pending = []
        for k in K_CANDIDATES:
            if k in reuse.PARENT_KS:
                models[str(k)] = reuse.import_model(formal_root, role, k, identity, query)
            elif (formal_root / role / f"K{k}" / "manifest.json").exists():
                models[str(k)] = _verify_model(formal_root, role, k, identity, query)
            else:
                pending.append(k)
        if pending:
            # Endpoint keys were frozen above. Only this role's complete fit pool
            # may enter the existing guarded loader; query outcomes stay sealed.
            endpoints = inp.endpoints(cfg, run, role, fit, "fit")
            v = finite_pairs(num.to_vectors(x, endpoints), "Formal own-pair displacements")
            for k in pending:
                folder = formal_root / role / f"K{k}"
                result = training.fit_role(x, v, fit.id.to_numpy(dtype=np.int64), k, role, folder,
                                           identity=identity, resume=True)
                training_receipt = _training_receipt(result, formal_root, role, k)
                _freeze_json(folder / "training_receipt.json", training_receipt)
                if result.requires_pause:
                    raise EpochCapPause(f"{role} K={k}: selected seed reached 500 epochs with best epoch "
                                        f"{training_receipt['selected_epoch']} in the last 30; formal scoring paused")
                parameters = result.fit.parameters(origins)
                target_scale = np.asarray(result.fit.standardizer.y_std, dtype=np.float64)
                diagnostics = _parameter_diagnostics(parameters, target_scale, result.fit.history)
                if parameters["pi"].shape != (len(query), k):
                    raise ValueError("Formal parameter query count or candidate differs")
                archive = {**parameters, "origins": origins,
                           "query_keys": query[inp.KEY].to_numpy(dtype=np.int64), "target_scale": target_scale}
                _freeze_parameters(folder / "parameters.npz", archive)
                manifest = {"schema_version": SCHEMA_VERSION, "status": "complete", "role": role, "k": k,
                            "identity": identity, "query_key_sha256": identity["query_key_sha256"],
                            "query_count": len(query), "query_id_count": int(query.id.nunique()),
                            "parameter_count": 4352 + 390 * k, "target_scale": target_scale.tolist(),
                            "parameter_units": {"origins": "lon_lat_degrees", "mu": "displacement_km",
                                                "cov": "displacement_km_squared"},
                            "parameters": _artifact_record(folder / "parameters.npz", formal_root),
                            "training_receipt": _artifact_record(folder / "training_receipt.json", formal_root),
                            "selected_seed": training_receipt["selected_seed"],
                            "selected_epoch": training_receipt["selected_epoch"],
                            "seeds": training_receipt["seeds"], "full_refit": training_receipt["full_refit"],
                            "diagnostics": diagnostics, "outer_targets_read": False, "final_test_access": False}
                _freeze_json(folder / "manifest.json", manifest)
                models[str(k)] = _verify_model(formal_root, role, k, identity, query)
                print(json.dumps({"formal_training_role": role, "K": k, "status": "complete",
                                  "selected_seed": manifest["selected_seed"],
                                  "selected_epoch": manifest["selected_epoch"]}), flush=True)
        if guard.outer_read or guard.denied:
            raise PermissionError("Formal fit access guard detected an unexpected outcome read or denied access")
        receipt = {"schema_version": SCHEMA_VERSION, "status": "complete", "role": role, "identity": identity,
                   "query_count": len(query), "query_id_count": int(query.id.nunique()),
                   "query_key_sha256": identity["query_key_sha256"],
                   "models": {str(k): models[str(k)] for k in K_CANDIDATES},
                   "selected_k": selected_k, "selection_sha256": selection_sha256,
                   "outer_targets_read": False, "final_test_access": False}
        _freeze_json(freeze_path, receipt)
        atomic_json(role_provenance / "training_status.json", {"status": "complete", "role": role})
        return receipt
    except BaseException as exc:
        status = ("epoch_cap_pause" if isinstance(exc, EpochCapPause) else
                  "numerical_failure" if isinstance(exc, (FloatingPointError, np.linalg.LinAlgError)) else
                  "interrupted" if isinstance(exc, (KeyboardInterrupt, InterruptedError)) else "source_or_contract_failure")
        atomic_json(role_provenance / "training_status.json",
                    {"status": status, "role": role, "exception": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        atomic_json(role_provenance / "training_access.json",
                    {"outer_targets_read": bool(guard.outer_read), "denied": guard.denied,
                     "final_test_access": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("role", choices=ROLES)
    parser.add_argument("--formal-root", type=Path)
    args = parser.parse_args()
    receipt = train_role(args.run, args.role, args.formal_root)
    print(json.dumps({"status": receipt["status"], "role": receipt["role"],
                      "models": list(receipt["models"])}), flush=True)


if __name__ == "__main__":
    main()
