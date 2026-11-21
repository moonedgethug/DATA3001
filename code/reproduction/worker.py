"""Small isolated workers; run only inside a materialized execution workspace."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def summarize_gaussian_support(records, *, expected_cases=33971, expected_ids=45):
    import math
    if (len(records) != expected_cases or {r["query_position"] for r in records} != set(range(expected_cases))
            or len({r["id"] for r in records}) != expected_ids):
        raise ValueError("Gaussian support inventory has an incomplete or duplicated roster")
    eigenvalues = [v for r in records for v in r["gaussian"]["eigenvalues"]]
    conditions = [r["gaussian"]["condition_number"] for r in records]
    if (not all(math.isfinite(x) and x > 0 for x in eigenvalues)
            or not all(math.isfinite(x) and 1 <= x <= 1e12 for x in conditions)):
        raise ValueError("Gaussian covariance violates the original support gate")
    return {"cases": len(records), "ids": expected_ids, "min_eigenvalue": min(eigenvalues),
            "condition_max": max(conditions), "pairs_min": min(r["pairs"] for r in records),
            "pairs_max": max(r["pairs"] for r in records),
            "donor_ids_min": min(r["independent_ids"] for r in records),
            "donor_ids_max": max(r["independent_ids"] for r in records),
            "passed": True, "outer_targets_read": False, "final_test_access": False,
            "recomputed_from_fresh_parameters": True}


def gaussian_support(request):
    from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_inputs as inp
    from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_full as full
    from data3001.modelling.common.runtime import save_json
    paths, run, config, approval, guard = inp.context(request["run_name"])
    records = [record for path in sorted((run["results"] / "parameters").glob("*.json.gz"))
               for record in full.read_bundle(path)]
    result = summarize_gaussian_support(records)
    if guard.outcomes_read or guard.denied:
        raise PermissionError("Support inventory must precede outcome access")
    save_json(paths, run["provenance"] / "full_support_check.json", result)
    print(json.dumps(result))


def predict(request):
    import numpy as np
    from data3001.modelling.continuous_models.conditional_mdn_s5_e4_inference import from_checkpoint
    predictor = from_checkpoint(request["checkpoint"], sha256=request["sha256"])
    if predictor.metadata["K"] != 22 or predictor.metadata["role"] != "C_outer":
        raise ValueError("The requested checkpoint is not the final outer K22 model")
    parameters = predictor.mixture(request["origins"])
    samples = predictor.sample(request["origins"], request["samples"], request["seed"])
    if not np.isfinite(samples).all() or not np.allclose(parameters["weights"].sum(axis=1), 1, atol=1e-12):
        raise ArithmeticError("Invalid predictive distribution")
    output = Path(request["output"]); output.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(output / "mixture_parameters.npz", **parameters)
    np.save(output / "endpoint_samples_lonlat.npy", samples, allow_pickle=False)
    document = {key: value.tolist() for key, value in parameters.items()}
    document.update(metadata=predictor.metadata, checkpoint_sha256=request["sha256"],
                    sample_count=request["samples"], seed=request["seed"],
                    training_performed=False, validation_outcomes_read=False, final_test_access=False)
    (output / "prediction.json").write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "complete", "K": 22, "origins": len(parameters["weights"]),
                      "samples_per_origin": request["samples"], "output": str(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["predict", "gaussian_support"])
    parser.add_argument("request", type=Path)
    arguments = parser.parse_args()
    {"predict": predict, "gaussian_support": gaussian_support}[arguments.operation](json.loads(arguments.request.read_text()))
