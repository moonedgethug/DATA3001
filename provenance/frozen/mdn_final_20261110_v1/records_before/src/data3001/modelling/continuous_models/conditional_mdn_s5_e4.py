"""Step 5 E3's fixed conditional mixture model, without data access."""

from dataclasses import dataclass
import hashlib
import math

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


K_CANDIDATES = (1, 2, 3, 4, 6, 8, 12, 16, 18, 20, 22, 32)
COVARIANCE_FLOOR = 0.001
CONTRACT_SHA256 = "1ce5b54029b51d4561676f374b2cdbe3d2f55e1d8de7406803d416f1604522b2"


def canonical_integer(value):
    """Reject fractional/nonfinite identifiers instead of silently truncating."""
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("Boolean is not a canonical integer identifier")
    if isinstance(value, (str, int, np.integer)):
        try:
            return str(int(value))
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("Expected an integer decimal identifier") from exc
    if isinstance(value, (float, np.floating)) and math.isfinite(value) and value == int(value):
        return str(int(value))
    raise ValueError("Expected a finite integer identifier")


def canonical_query_key(identifier, origin_source_obs, horizon_days):
    return "|".join(canonical_integer(v) for v in (identifier, origin_source_obs, horizon_days))


def stable_seed(purpose, role="", k=None, base_seed=None, query_key="", replicate=None):
    """Contract UTF-8 stream identity; callers needing 32 bits take modulo 2**32."""
    if purpose not in ("init", "shuffle", "ES", "region", "IID", "audit"):
        raise ValueError("Unknown random-stream purpose")
    if isinstance(query_key, (tuple, list, np.ndarray)):
        query_key = canonical_query_key(*query_key)
    fields = ["mdn_s5_e3_v1", purpose, str(role),
              "" if k is None else canonical_integer(k),
              "" if base_seed is None else canonical_integer(base_seed), str(query_key),
              "" if replicate is None else canonical_integer(replicate)]
    return int.from_bytes(hashlib.sha256("|".join(fields).encode("utf-8")).digest()[:8], "little")


def finite_pairs(values, name):
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 2 or result.shape[1] != 2 or not len(result):
        raise ValueError(f"{name} must be a nonempty N by 2 array")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite")
    return np.ascontiguousarray(result)


@dataclass(frozen=True)
class Standardizer:
    x_mean: np.ndarray
    x_std: np.ndarray
    y_mean: np.ndarray
    y_std: np.ndarray

    @classmethod
    def fit(cls, x, y):
        x, y = finite_pairs(x, "Origins"), finite_pairs(y, "Own-pair displacements")
        if len(x) != len(y):
            raise ValueError("Origin and displacement row counts differ")
        result = cls(x.mean(axis=0), x.std(axis=0, ddof=0),
                     y.mean(axis=0), y.std(axis=0, ddof=0))
        if any(not np.isfinite(a).all() or np.any(a <= 0) for a in (result.x_std, result.y_std)):
            raise ValueError("Zero or nonfinite standardization scale")
        if not np.isfinite(result.x_mean).all() or not np.isfinite(result.y_mean).all():
            raise ValueError("Nonfinite standardization mean")
        return result

    def transform_x(self, x):
        return (finite_pairs(x, "Origins") - self.x_mean) / self.x_std

    def transform_y(self, y):
        return (finite_pairs(y, "Own-pair displacements") - self.y_mean) / self.y_std

    def state_dict(self):
        return {name: getattr(self, name).tolist() for name in ("x_mean", "x_std", "y_mean", "y_std")}

    @classmethod
    def from_state_dict(cls, state):
        result = cls(**{name: np.asarray(state[name], dtype=np.float64)
                        for name in ("x_mean", "x_std", "y_mean", "y_std")})
        if any(a.shape != (2,) or not np.isfinite(a).all()
               for a in (result.x_mean, result.x_std, result.y_mean, result.y_std)):
            raise ValueError("Invalid standardizer checkpoint")
        if np.any(result.x_std <= 0) or np.any(result.y_std <= 0):
            raise ValueError("Invalid checkpoint scale")
        return result

    def physical_parameters(self, output):
        log_pi, mean, covariance = (a.detach().cpu().numpy() if isinstance(a, torch.Tensor)
                                    else np.asarray(a, dtype=np.float64) for a in output)
        result = {"pi": np.exp(log_pi), "mu": self.y_mean + mean * self.y_std,
                  "cov": covariance * self.y_std[:, None] * self.y_std[None, :]}
        if not all(np.isfinite(a).all() for a in result.values()):
            raise FloatingPointError("Nonfinite physical MDN parameters")
        if np.any(np.abs(result["pi"].sum(axis=-1) - 1) > 1e-10):
            raise FloatingPointError("MDN mixture probabilities do not sum to one")
        return result


class MDN(nn.Module):
    """2 -> 64 tanh -> 64 tanh -> 6K; all parameters on CPU in float64."""

    def __init__(self, k, seed):
        super().__init__()
        if k not in K_CANDIDATES:
            raise ValueError(f"K must be one of {K_CANDIDATES}")
        self.k = int(k)
        self.seed = int(seed)
        # Initialization never changes the caller's global random stream.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(self.seed)
            self.hidden1 = nn.Linear(2, 64, dtype=torch.float64, device="cpu")
            self.hidden2 = nn.Linear(64, 64, dtype=torch.float64, device="cpu")
            self.logit_head = nn.Linear(64, k, dtype=torch.float64, device="cpu")
            self.mean_head = nn.Linear(64, 2*k, dtype=torch.float64, device="cpu")
            self.covariance_head = nn.Linear(64, 3*k, dtype=torch.float64, device="cpu")
            for layer in (self.hidden1, self.hidden2):
                nn.init.xavier_uniform_(layer.weight)
                nn.init.zeros_(layer.bias)
            nn.init.normal_(self.mean_head.weight, std=0.01)
            nn.init.normal_(self.mean_head.bias, std=0.5)
            nn.init.zeros_(self.logit_head.weight)
            nn.init.zeros_(self.logit_head.bias)
            nn.init.zeros_(self.covariance_head.weight)
            diagonal = math.log(math.expm1(math.sqrt(1 - COVARIANCE_FLOOR)))
            with torch.no_grad():
                self.covariance_head.bias.reshape(k, 3).copy_(
                    torch.tensor([diagonal, 0., diagonal], dtype=torch.float64).expand(k, 3))

    @property
    def parameter_count(self):
        return sum(p.numel() for p in self.parameters())

    def forward(self, x):
        if x.dtype != torch.float64 or x.device.type != "cpu":
            raise ValueError("MDN inference requires CPU float64 inputs")
        h = torch.tanh(self.hidden2(torch.tanh(self.hidden1(x))))
        log_pi = F.log_softmax(self.logit_head(h), dim=-1)
        means = self.mean_head(h).reshape(-1, self.k, 2)
        parameters = self.covariance_head(h).reshape(-1, self.k, 3)
        a, b, c = parameters.unbind(dim=-1)
        z = torch.zeros_like(a)
        lower = torch.stack((F.softplus(a), z, b, F.softplus(c)), dim=-1).reshape(-1, self.k, 2, 2)
        covariance = lower @ lower.transpose(-1, -2)
        covariance = covariance + COVARIANCE_FLOOR * torch.eye(2, dtype=torch.float64)
        return log_pi, means, covariance


def mixture_nll(output, target):
    """Per-pair NLL in standardized displacement coordinates, without clipping."""
    log_pi, means, covariance = output
    lower = torch.linalg.cholesky(covariance)
    difference = (target[:, None, :] - means).unsqueeze(-1)
    white = torch.linalg.solve_triangular(lower, difference, upper=False).squeeze(-1)
    logdet = 2 * torch.log(torch.diagonal(lower, dim1=-2, dim2=-1)).sum(dim=-1)
    component_logp = -math.log(2*math.pi) - 0.5*(logdet + white.square().sum(dim=-1))
    return -torch.logsumexp(log_pi + component_logp, dim=-1)
