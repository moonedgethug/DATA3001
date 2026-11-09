"""Deterministic, resumable Step 5 E3 fitting. Callers supply only a fit pool.

There is deliberately no cohort loader, time-validation input, final-test path,
or scoring/selection-by-ES code here. A budget callback may raise to stop after
any saved batch. ``pause_after_epochs`` is a resumable execution prefix, not a
different optimizer/early-stopping configuration.
"""

from dataclasses import asdict, dataclass
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time

import numpy as np
import torch

from .conditional_mdn_s5_e3 import (
    CONTRACT_SHA256, MDN, Standardizer, canonical_integer, finite_pairs,
    mixture_nll, stable_seed,
)


BATCH_SIZE = 4096
MAX_EPOCHS = 500
BASE_SEEDS = (20261121, 20261122, 20261123)
PATIENCE = 30
MIN_IMPROVEMENT = 1e-4
CHECKPOINT_VERSION = 1


def _ids(values):
    values = np.asarray(values)
    if values.ndim != 1 or not len(values):
        raise ValueError("IDs must be a nonempty one-dimensional array")
    return np.asarray([int(canonical_integer(v)) for v in values], dtype=np.int64)


def partition_ids(ids):
    unique = sorted(set(_ids(ids).tolist()))
    if len(unique) < 2:
        raise ValueError("Whole-ID early stopping requires at least two IDs")
    ordered = sorted(unique, key=lambda identifier: (
        hashlib.sha256(f"mdn_s5_e3_stop_v1|{identifier}".encode("utf-8")).hexdigest(), identifier))
    stop = ordered[:math.ceil(0.1*len(ordered))]
    optimize = sorted(set(unique) - set(stop))
    return np.asarray(optimize, dtype=np.int64), np.asarray(stop, dtype=np.int64)


def drifter_equal_nll(losses, ids):
    losses, ids = np.asarray(losses, dtype=np.float64), _ids(ids)
    if losses.shape != ids.shape or not np.isfinite(losses).all():
        raise ValueError("Finite NLL and ID arrays must have equal shape")
    _, inverse, counts = np.unique(ids, return_inverse=True, return_counts=True)
    return float(np.mean(np.bincount(inverse, weights=losses)/counts))


@dataclass
class EarlyStopping:
    best_nll: float = math.inf
    best_epoch: int = 0
    patience_anchor: float = math.inf
    bad_epochs: int = 0

    def update(self, score, epoch):
        if not math.isfinite(score):
            raise FloatingPointError("Nonfinite early-stopping NLL")
        improved = score < self.best_nll
        if improved:
            self.best_nll, self.best_epoch = float(score), int(epoch)
        if self.patience_anchor - score >= MIN_IMPROVEMENT:
            self.patience_anchor, self.bad_epochs = float(score), 0
        else:
            self.bad_epochs += 1
        return improved

    @property
    def should_stop(self):
        return self.bad_epochs >= PATIENCE


@dataclass
class TrainingResult:
    model: MDN
    standardizer: Standardizer
    base_seed: int
    best_epoch: int
    best_nll: float | None
    epochs_completed: int
    status: str
    history: list
    checkpoint_path: Path
    purpose: str
    identity: dict

    def parameters(self, origins, batch_size=BATCH_SIZE):
        x = self.standardizer.transform_x(origins)
        self.model.eval()
        packets = []
        with torch.no_grad():
            for offset in range(0, len(x), batch_size):
                packets.append(self.standardizer.physical_parameters(
                    self.model(torch.from_numpy(x[offset:offset+batch_size]))))
        return {key: np.concatenate([packet[key] for packet in packets], axis=0)
                for key in ("pi", "mu", "cov")}


@dataclass
class RoleFitResult:
    fit: TrainingResult | None
    seed_results: list[TrainingResult]
    selected_seed: int
    requires_pause: bool


def make_optimizer(model):
    weights, biases = [], []
    for name, parameter in model.named_parameters():
        (weights if name.endswith(".weight") else biases).append(parameter)
    return torch.optim.AdamW([
        {"params": weights, "weight_decay": 1e-4},
        {"params": biases, "weight_decay": 0.},
    ], lr=0.001, betas=(0.9, 0.999), eps=1e-8)


def _atomic_json(path, payload):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _atomic_checkpoint(path, payload):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        torch.save(payload, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _array_digest(*arrays):
    digest = hashlib.sha256()
    for values in arrays:
        values = np.ascontiguousarray(values)
        digest.update(str(values.dtype).encode("ascii"))
        digest.update(json.dumps(values.shape).encode("ascii"))
        digest.update(memoryview(values).cast("B"))
    return digest.hexdigest()


def _identity(x, y, ids, k, role, seed, purpose, max_epochs, external_identity):
    if torch.__version__.split("+")[0] != "2.14.1":
        raise RuntimeError("The E3 contract requires PyTorch 2.14.1")
    if torch.get_num_threads() > 4:
        raise RuntimeError("The E3 contract permits at most four CPU training threads")
    external = json.loads(json.dumps(external_identity or {}, sort_keys=True, allow_nan=False))
    return dict(checkpoint_version=CHECKPOINT_VERSION, contract_sha256=CONTRACT_SHA256,
                data_sha256=_array_digest(x, y, ids), external=external,
                k=int(k), role=str(role), base_seed=int(seed), purpose=purpose,
                stream_seeds={name: stable_seed(name, role, k, seed) for name in ("init", "shuffle")},
                max_epochs=max_epochs, batch_size=BATCH_SIZE,
                architecture="2-64tanh-64tanh-6K", covariance_floor=0.001,
                optimizer=dict(name="AdamW", lr=.001, betas=[.9,.999], eps=1e-8,
                               weight_decay_weights_only=1e-4, clip_norm=5.),
                patience=PATIENCE, min_improvement=MIN_IMPROVEMENT,
                torch_version=str(torch.__version__), threads=torch.get_num_threads(),
                dtype="float64", device="cpu")


def _finite_model_optimizer(model, optimizer):
    if any(not torch.isfinite(p).all() for p in model.parameters()):
        raise FloatingPointError("Nonfinite MDN parameter; no fallback is permitted")
    for state in optimizer.state.values():
        if any(isinstance(value, torch.Tensor) and not torch.isfinite(value).all()
               for value in state.values()):
            raise FloatingPointError("Nonfinite AdamW state; no fallback is permitted")


def _result(payload, checkpoint_path):
    identity = payload["identity"]
    model = MDN(identity["k"], stable_seed("init", identity["role"], identity["k"], identity["base_seed"]))
    weights = (payload["best_model_state"] if identity["purpose"] == "early_stop"
               and payload["best_model_state"] is not None else payload["model_state"])
    model.load_state_dict(weights)
    model.eval()
    if any(not torch.isfinite(p).all() for p in model.parameters()):
        raise FloatingPointError("Nonfinite checkpoint parameters")
    progress, tracker = payload["progress"], payload["tracker"]
    return TrainingResult(model, Standardizer.from_state_dict(payload["standardizer"]),
                          identity["base_seed"], tracker["best_epoch"] if identity["purpose"] == "early_stop" else progress["epoch"],
                          tracker["best_nll"] if math.isfinite(tracker["best_nll"]) else None,
                          progress["epoch"], progress["status"], copy.deepcopy(progress["history"]),
                          Path(checkpoint_path), identity["purpose"], identity)


def load_model(checkpoint_path):
    """Load an E3-owned local checkpoint. Early-stop checkpoints return raw best."""
    checkpoint_path = Path(checkpoint_path)
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if payload["identity"]["checkpoint_version"] != CHECKPOINT_VERSION:
        raise ValueError("Unsupported E3 checkpoint identity version")
    if payload["identity"]["contract_sha256"] != CONTRACT_SHA256:
        raise ValueError("Checkpoint contract identity differs")
    return _result(payload, checkpoint_path)


def _train(x, y, ids, k, role, base_seed, outdir, *, purpose, max_epochs,
           budget_tick, resume, identity, pause_after_epochs=None):
    x, y, ids = finite_pairs(x, "Origins"), finite_pairs(y, "Own-pair displacements"), _ids(ids)
    if len(x) != len(y) or len(x) != len(ids):
        raise ValueError("Training input row counts differ")
    if base_seed not in BASE_SEEDS:
        raise ValueError("Training base seed is not one of the three frozen seeds")
    if not isinstance(max_epochs, int) or not 1 <= max_epochs <= MAX_EPOCHS:
        raise ValueError("Training epoch bound must be between 1 and 500")
    if pause_after_epochs is not None and (not isinstance(pause_after_epochs, int) or pause_after_epochs < 1):
        raise ValueError("Execution prefix must contain a positive integer number of epochs")
    if purpose == "early_stop":
        optimize_ids, stop_ids = partition_ids(ids)
        fit_mask = np.isin(ids, optimize_ids)
        stop_mask = ~fit_mask
    else:
        optimize_ids, stop_ids = np.unique(ids), np.empty(0, dtype=np.int64)
        fit_mask, stop_mask = np.ones(len(ids), dtype=bool), np.zeros(len(ids), dtype=bool)
    scaler = Standardizer.fit(x[fit_mask], y[fit_mask])
    run_identity = _identity(x, y, ids, k, role, base_seed, purpose, max_epochs, identity)
    run_identity["optimization_ids"] = optimize_ids.tolist()
    run_identity["stop_ids"] = stop_ids.tolist()
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = outdir / "checkpoint.pt"
    model = MDN(k, stable_seed("init", role, k, base_seed))
    optimizer = make_optimizer(model)
    shuffle = torch.Generator(device="cpu").manual_seed(stable_seed("shuffle", role, k, base_seed))
    tracker = EarlyStopping()
    best_model_state = None
    progress = dict(epoch=0, next_batch=0, eval_offset=0, order=None, eval_sums=None,
                    epoch_nll_sum=0., pairs_seen=0, batch_sizes=[], clipped_steps=0,
                    epoch_start_elapsed=0., elapsed_seconds=0., status="running", history=[])
    if checkpoint_path.exists():
        if not resume:
            raise FileExistsError("Checkpoint already exists; refusing to overwrite a training run")
        previous = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if previous["identity"] != run_identity:
            raise ValueError("Checkpoint identity differs from data, source, configuration, or runtime")
        if previous["standardizer"] != scaler.state_dict():
            raise ValueError("Checkpoint standardizer identity differs")
        if previous["progress"]["status"] == "numerical_failure":
            raise FloatingPointError("Numerically failed checkpoint requires investigation before resuming")
        model.load_state_dict(previous["model_state"])
        optimizer.load_state_dict(previous["optimizer_state"])
        shuffle.set_state(previous["rng"]["shuffle"])
        torch.set_rng_state(previous["rng"]["torch"])
        np.random.set_state(previous["rng"]["numpy"])
        random.setstate(previous["rng"]["python"])
        tracker = EarlyStopping(**previous["tracker"])
        best_model_state, progress = previous["best_model_state"], previous["progress"]
        if progress["status"] in ("early_stopped", "epoch_cap_reached", "complete"):
            return _result(previous, checkpoint_path)
        progress["status"] = "running"
    _finite_model_optimizer(model, optimizer)
    fit_x = torch.from_numpy(scaler.transform_x(x[fit_mask]))
    fit_y = torch.from_numpy(scaler.transform_y(y[fit_mask]))
    if purpose == "early_stop":
        stop_x = torch.from_numpy(scaler.transform_x(x[stop_mask]))
        stop_y = torch.from_numpy(scaler.transform_y(y[stop_mask]))
        _, stop_inverse, stop_counts = np.unique(ids[stop_mask], return_inverse=True, return_counts=True)
    accumulated = progress["elapsed_seconds"]
    started = time.monotonic()

    def elapsed():
        return accumulated + time.monotonic() - started

    def save():
        progress["elapsed_seconds"] = elapsed()
        payload = dict(identity=run_identity, standardizer=scaler.state_dict(),
                       model_state=model.state_dict(), optimizer_state=optimizer.state_dict(),
                       best_model_state=best_model_state, tracker=asdict(tracker), progress=progress,
                       rng=dict(shuffle=shuffle.get_state(), torch=torch.get_rng_state(),
                                numpy=np.random.get_state(), python=random.getstate()))
        _atomic_checkpoint(checkpoint_path, payload)
        readable = {key: value for key, value in progress.items() if key not in ("order", "eval_sums")}
        readable.update(k=k, role=role, base_seed=base_seed, purpose=purpose,
                        best_epoch=tracker.best_epoch,
                        best_nll=tracker.best_nll if math.isfinite(tracker.best_nll) else None,
                        optimization_pair_count=len(fit_x), stop_pair_count=int(stop_mask.sum()),
                        optimization_ids=optimize_ids.tolist(), stop_ids=stop_ids.tolist())
        _atomic_json(outdir / "progress.json", readable)
        return payload

    def checkpoint_tick():
        save()
        if budget_tick is not None:
            budget_tick()

    # This is also the rollback point if an asynchronous interruption happens
    # inside the first optimizer update, before that batch can be committed.
    save()
    try:
        while progress["epoch"] < max_epochs:
            if pause_after_epochs is not None and progress["epoch"] >= pause_after_epochs:
                progress["status"] = "prefix_paused"
                return _result(save(), checkpoint_path)
            if progress["order"] is None:
                progress["epoch_start_elapsed"] = elapsed()
                progress["order"] = torch.randperm(len(fit_x), generator=shuffle)
                progress["next_batch"] = 0
                progress["eval_offset"] = 0
                progress["eval_sums"] = np.zeros(len(stop_ids), dtype=np.float64)
                progress["epoch_nll_sum"] = 0.
                progress["pairs_seen"] = 0
                progress["batch_sizes"] = []
                progress["clipped_steps"] = 0
            model.train()
            while progress["next_batch"] < len(fit_x):
                offset = progress["next_batch"]
                index = progress["order"][offset:offset+BATCH_SIZE]
                optimizer.zero_grad(set_to_none=True)
                losses = mixture_nll(model(fit_x[index]), fit_y[index])
                if not torch.isfinite(losses).all():
                    raise FloatingPointError("Nonfinite training NLL")
                # Tail batch contributes b / 4096 of a full batch's mean loss.
                (losses.sum()/BATCH_SIZE).backward()
                if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                    raise FloatingPointError("Nonfinite training gradient")
                try:
                    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 5., error_if_nonfinite=True)
                except RuntimeError as exc:
                    raise FloatingPointError("Nonfinite aggregate gradient norm") from exc
                optimizer.step()
                _finite_model_optimizer(model, optimizer)
                progress["clipped_steps"] += int(norm > 5.)
                progress["epoch_nll_sum"] += float(losses.detach().sum())
                progress["pairs_seen"] += len(index)
                progress["batch_sizes"].append(len(index))
                progress["next_batch"] += len(index)
                checkpoint_tick()
            stop_score = None
            if purpose == "early_stop":
                model.eval()
                with torch.no_grad():
                    while progress["eval_offset"] < len(stop_x):
                        offset = progress["eval_offset"]
                        end = min(offset+BATCH_SIZE, len(stop_x))
                        losses = mixture_nll(model(stop_x[offset:end]), stop_y[offset:end]).numpy()
                        if not np.isfinite(losses).all():
                            raise FloatingPointError("Nonfinite complete stop-subset NLL")
                        progress["eval_sums"] += np.bincount(stop_inverse[offset:end], weights=losses, minlength=len(stop_ids))
                        progress["eval_offset"] = end
                        checkpoint_tick()
                stop_score = float(np.mean(progress["eval_sums"]/stop_counts))
                if tracker.update(stop_score, progress["epoch"]+1):
                    best_model_state = copy.deepcopy(model.state_dict())
            progress["epoch"] += 1
            progress["history"].append(dict(
                epoch=progress["epoch"], training_nll=progress["epoch_nll_sum"]/len(fit_x),
                stop_nll=stop_score, pairs_seen=progress["pairs_seen"],
                batch_sizes=progress["batch_sizes"].copy(), clipped_steps=progress["clipped_steps"],
                gradient_clip_rate=progress["clipped_steps"]/len(progress["batch_sizes"]),
                seconds=elapsed()-progress["epoch_start_elapsed"]))
            progress["order"] = None
            if purpose == "early_stop" and tracker.should_stop:
                progress["status"] = "early_stopped"
            elif progress["epoch"] == max_epochs:
                progress["status"] = "epoch_cap_reached" if purpose == "early_stop" else "complete"
            checkpoint_tick()
            if progress["status"] != "running":
                break
        return _result(save(), checkpoint_path)
    except BaseException as exc:
        if isinstance(exc, (FloatingPointError, torch.linalg.LinAlgError)):
            progress["status"] = "numerical_failure"
        else:
            # An interrupted tensor/optimizer operation may have changed only
            # part of the live state. Resume solely from the last atomic batch
            # commit, never from a partially updated optimizer or accumulator.
            committed = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
            model.load_state_dict(committed["model_state"])
            optimizer.load_state_dict(committed["optimizer_state"])
            shuffle.set_state(committed["rng"]["shuffle"])
            torch.set_rng_state(committed["rng"]["torch"])
            np.random.set_state(committed["rng"]["numpy"])
            random.setstate(committed["rng"]["python"])
            tracker = EarlyStopping(**committed["tracker"])
            best_model_state, progress = committed["best_model_state"], committed["progress"]
            if progress["status"] not in ("early_stopped", "epoch_cap_reached", "complete"):
                # A callback can raise after the final epoch was committed;
                # preserve that terminal decision when it already exists.
                progress["status"] = "interrupted"
        progress["last_exception"] = dict(type=type(exc).__name__, message=str(exc))
        save()
        raise


def train_seed(x, v, ids, k, role, base_seed, outdir, max_epochs=MAX_EPOCHS,
               budget_tick=None, resume=True, *, identity=None, pause_after_epochs=None):
    """Fit optimization IDs and select the raw-best complete stop-subset epoch."""
    return _train(x, v, ids, k, role, base_seed, outdir, purpose="early_stop",
                  max_epochs=max_epochs, budget_tick=budget_tick, resume=resume,
                  identity=identity, pause_after_epochs=pause_after_epochs)


def train_fixed_epochs(x, v, ids, k, role, base_seed, outdir, epochs, *,
                       purpose="full_refit", budget_tick=None, identity=None, resume=True,
                       pause_after_epochs=None):
    """Use all supplied fit rows; pilot output stays explicitly marked as pilot."""
    if purpose not in ("full_refit", "pilot"):
        raise ValueError("Fixed-epoch purpose must be full_refit or pilot")
    if purpose == "pilot" and epochs > 10:
        raise ValueError("The resource pilot is limited to ten epochs")
    return _train(x, v, ids, k, role, base_seed, outdir, purpose=purpose,
                  max_epochs=epochs, budget_tick=budget_tick, resume=resume,
                  identity=identity, pause_after_epochs=pause_after_epochs)


def select_seed(results):
    if not results or any(result.best_nll is None or not math.isfinite(result.best_nll) for result in results):
        raise ValueError("Seed selection requires all finite best stop NLLs")
    return min(results, key=lambda result: (result.best_nll, result.base_seed))


def requires_cap_pause(result):
    return (result.status == "epoch_cap_reached" and result.epochs_completed == 500
            and result.best_epoch > 470)


def fit_role(x, v, ids, k, role, outdir, budget_tick=None, *, identity=None, resume=True):
    """Three frozen seeds, then fresh full-pool refit at the selected epoch."""
    outdir = Path(outdir)
    results = [train_seed(x, v, ids, k, role, seed, outdir / f"seed_{seed}",
                          budget_tick=budget_tick, identity=identity, resume=resume)
               for seed in BASE_SEEDS]
    selected = select_seed(results)
    pause = requires_cap_pause(selected)
    _atomic_json(outdir / "seed_selection.json", dict(
        role=role, k=k, selected_seed=selected.base_seed, selected_epoch=selected.best_epoch,
        requires_pause=pause, reason="selected_seed_cap_best_last_30" if pause else None,
        seeds=[dict(base_seed=r.base_seed, best_nll=r.best_nll, best_epoch=r.best_epoch,
                    epochs_completed=r.epochs_completed, status=r.status) for r in results]))
    fit = None if pause else train_fixed_epochs(
        x, v, ids, k, role, selected.base_seed, outdir / "full_refit", selected.best_epoch,
        purpose="full_refit", budget_tick=budget_tick, identity=identity, resume=resume)
    return RoleFitResult(fit, results, selected.base_seed, pause)
