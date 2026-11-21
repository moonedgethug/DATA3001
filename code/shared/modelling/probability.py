"""Shared categorical probability scores, including unresolved mass."""
import numpy as np

def score_distribution(probabilities, truth, unresolved=0.0):
  values = np.asarray(list(probabilities.values()), dtype=float)
  u = float(unresolved)

  if not np.isfinite(u) or not 0 <= u <= 1:
    raise ValueError("Invalid unresolved mass.")

  if (
    not np.isfinite(values).all()
    or (values < 0).any()
    or (values > 1).any()
  ):
    raise ValueError("Invalid probabilities.")

  if not np.isclose(
    values.sum() + u, 1.0, rtol=0, atol=1e-10
  ):
    raise ValueError("Probability mass must sum to one.")

  p_true = float(probabilities.get(truth, 0.0))
  complete = u == 0.0

  upper = -np.log(p_true) if p_true > 0 else np.inf
  lower_mass = p_true + u
  lower = -np.log(lower_mass) if lower_mass > 0 else np.inf

  base_brier = 1.0 - 2.0 *p_true + float(np.sum(values ** 2))

  return {
    "complete": complete,
    "true_probability": p_true,
    "unresolved_mass": u,
    "log_loss": float(upper) if complete else np.nan,
    "log_loss_lower": float(lower),
    "log_loss_upper": float(upper),
    "brier": base_brier if complete else np.nan,
    "brier_failure_penalized": base_brier + u ** 2,
  }


def check_scoring():
  correct = score_distribution({"A": 0.25, "B": 0.75}, "B")
  np.testing.assert_allclose(correct["true_probability"], 0.75)
  np.testing.assert_allclose(
    correct["log_loss"], -np.log(0.75)
  )
  np.testing.assert_allclose(correct["brier"], 0.125)

  wrong = score_distribution({"A":1.0}, "B")
  assert np.isinf(wrong["log_loss"])
  np.testing.assert_allclose(wrong["brier"], 2.0)

  unknown = score_distribution({}, "B", unresolved=1.0)
  assert not unknown["complete"]
  assert np.isnan(unknown["brier"])
  np.testing.assert_allclose(unknown["log_loss_lower"], 0.0)
  assert np.isinf(unknown["log_loss_upper"])
  np.testing.assert_allclose(
    unknown["brier_failure_penalized"], 2.0
  )

  print("Scoring checks passed.")
