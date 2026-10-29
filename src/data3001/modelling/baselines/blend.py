"""Fixed-base probability mixing and Brier-based lambda selection"""

import numpy as np

from data3001.modelling.common.probability import score_distribution

def mix_forecasts(b2, b1, lam, *, u2=0.0, u1=0.0):
    """Preserve physical probabilities and explicitly unresolved mass."""
    lam = float(lam)

    if not np.isfinite(lam) or not 0.0 <= lam <= 1.0:
        raise ValueError("Lambda must be finite and between zero and one.")

    score_distribution(b2, -1, unresolved=u2)
    score_distribution(b1, -1, unresolved=u1)

    cells = sorted(set(b2) | set(b1))
    probabilities = {
        cell: (1.0 - lam) * float(b2.get(cell, 0.0))
        + lam * float(b1.get(cell, 0.0))
        for cell in cells
    }
    unresolved = (1.0 - lam) * float(u2) + lam * float(u1)

    score_distribution(probabilities, -1, unresolved=unresolved)
    return probabilities, unresolved


def brier_terms(b2, b1, truth, *, u2=0.0, u1=0.0):
    """Return A, B, C such that penalized Brier = A*l^2+B*l+C."""
    score2 = score_distribution(b2, truth, unresolved=u2)
    score_distribution(b1, truth, unresolved=u1)

    cells = sorted(set(b2) | set(b1))
    q = np.array([b2.get(cell, 0.0) for cell in cells], dtype=float)
    r = np.array([b1.get(cell, 0.0) for cell in cells], dtype=float)

    d = r - q
    du = float(u1) - float(u2)
    truth_delta = float(b1.get(truth, 0.0)) - float(b2.get(truth, 0.0))

    A = float(d @ d + du * du)
    B = float(2.0 * (q @ d + float(u2) * du - truth_delta))
    C = float(score2["brier_failure_penalized"])

    return A, B, C


def select_lambdas(terms, weights):
    """Select both methods on the SAME inner out-of-fold cases and weights"""
    terms = np.asarray(terms, dtype=float)
    weights = np.asarray(weights, dtype=float)

    if terms.ndim != 2 or terms.shape[1] != 3 or len(terms) == 0:
        raise ValueError("Expected a nonempty array with columns A, B, C.")

    if weights.shape != (len(terms),):
        raise ValueError("One weight is required per coefficient row.")

    if (
        not np.isfinite(terms).all()
        or not np.isfinite(weights).all()
        or (weights <= 0).any()
        or (terms[:, 0] < 0).any()
    ):
        raise ValueError("Coefficient and positive weights must be finite.")

    A, B, C = np.average(terms, axis=0, weights=weights)

    def loss(lam):
        return float((A * lam + B) * lam + C)

    grid = [k / 10.0 for k in range(11)]
    grid_scores = [
        {"lambda": lam, "selection_brier": loss(lam)}
        for lam in grid
    ]

    minimum = min(row["selection_brier"] for row in grid_scores)

    # Select the smallest lambda when scores ties within numerical tolerance.
    grid_lambda = next(
        row["lambda"]
        for row in grid_scores
        if abs(row["selection_brier"] - minimum) <= 1e-12
    )

    if A == 0.0:
        if abs(B) > 1e-12:
            raise ValueError("Identical forecasts produced a nonconstant loss.")
        analytic_lambda = 0.0
    else:
        analytic_lambda = float(np.clip(-B / (2.0 * A), 0.0, 1.0))

    analytic_brier = loss(analytic_lambda)
    grid_brier = loss(grid_lambda)

    if analytic_brier > grid_brier + 1e-12:
        raise RuntimeError("Analytic optimum is worse on identical tuning cases.")

    return {
        "grid_lambda": grid_lambda,
        "analytic_lambda": analytic_lambda,
        "grid_brier": grid_brier,
        "analytic_brier": analytic_brier,
        "grid_scores": grid_scores,
        "mean_coefficients": {
            "A": float(A),
            "B": float(B),
            "C": float(C),
        },
        "selection_metric": "brier_failure_penalized",
    }
