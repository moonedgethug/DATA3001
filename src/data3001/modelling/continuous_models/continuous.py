"""One-hour continuous-state Gaussian mixtures. No data access or fitted globals.

State = (fixed-chart x, y, east velocity, north velocity). Targets are position
residuals around one-hour Euler motion and the joint velocity increment.
"""
import math
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

A = 6378137.0
E2 = 6.6943799901413165e-3
RAD = math.pi / 180
COS0 = math.cos(37.5 * RAD)
HOUR = 3600.0


def to_state(lon, lat, ve, vn):
    return np.stack([A * COS0 * (np.asarray(lon) + 44.5) * RAD,
                     A * (np.asarray(lat) - 37.5) * RAD, ve, vn], axis=-1)


def to_lonlat(state):
    return np.stack([state[..., 0] / (A * COS0 * RAD) - 44.5,
                     state[..., 1] / (A * RAD) + 37.5], axis=-1)


def drift(state):
    """WGS84 local EN velocity mapped to the FIXED angular-metre chart."""
    lat = state[..., 1] / A + 37.5 * RAD
    if isinstance(state, torch.Tensor):
        c = (1 - E2 * torch.sin(lat).square()).sqrt()
        return torch.stack([COS0 * c / torch.cos(lat) * state[..., 2],
                            c.pow(3) / (1 - E2) * state[..., 3]], dim=-1)
    c = np.sqrt(1 - E2 * np.sin(lat)**2)
    return np.stack([COS0 * c / np.cos(lat) * state[..., 2],
                     c**3 / (1 - E2) * state[..., 3]], axis=-1)


def residual(origin, endpoint):
    r = endpoint - origin
    r[..., :2] -= HOUR * drift(origin)
    return r


def advance(state, increment):
    out = state + increment
    out[..., :2] += HOUR * drift(state)
    return out


def hour_pairs(time, position_ok, mapping_ok, inside, finite_velocity):
    """Exact adjacent hour, valid origin in D; retain observed exits from D.

    No artificial connection over a gap. Observed exits must still have a
    valid global water mapping, matching the frozen stopped-label rules.
    No temperature/drogue filtering.
    """
    good0 = position_ok[:-1] & mapping_ok[:-1] & inside[:-1] & finite_velocity[:-1]
    good1 = position_ok[1:] & finite_velocity[1:] & mapping_ok[1:]
    return np.flatnonzero(good0 & good1 & (np.diff(time) == HOUR))


class TransitionMixture(nn.Module):
    def __init__(self, components=1, width=32, floor=0.03):
        super().__init__()
        if components < 1 or floor <= 0:
            raise ValueError('Positive mixture size and covariance floor required')
        self.components, self.width, self.floor = components, width, floor
        self.net = nn.Sequential(nn.Linear(4, width), nn.Tanh(),
                                 nn.Linear(width, width), nn.Tanh(),
                                 nn.Linear(width, components * 15))
        # Start near a unit residual covariance, not at a collapsed density.
        with torch.no_grad():
            self.net[-1].weight.mul_(0.1)
            self.net[-1].bias.zero_()
            bias = self.net[-1].bias.view(components, 15)
            for j in (5, 7, 10, 14):
                bias[:, j] = math.log(math.expm1(1.0))

    def forward(self, x):
        raw = self.net(x).reshape(-1, self.components, 15)
        logits, mean = raw[..., 0], raw[..., 1:5]
        # Construct LL' + floor^2 I; true eigenvalue floor in standard units.
        entries, k = [], 5
        for i in range(4):
            row = []
            for j in range(4):
                if j <= i:
                    z = raw[..., k]; k += 1
                    row.append(F.softplus(z) if j == i else z)
                else:
                    row.append(torch.zeros_like(raw[..., 0]))
            entries.append(torch.stack(row, dim=-1))
        base = torch.stack(entries, dim=-2)
        cov = base @ base.transpose(-1, -2)
        cov = cov + self.floor**2 * torch.eye(4, device=x.device)
        # Four-dimensional Cholesky explicitly avoids device-specific LAPACK
        # fallbacks; it is algebraically the same positive-definite factor.
        rows = []
        for i in range(4):
            row = []
            for j in range(4):
                if j > i:
                    row.append(torch.zeros_like(raw[..., 0]))
                else:
                    z = cov[..., i, j]
                    if j:
                        z = z - sum(row[t] * (row[t] if i == j else rows[j][t]) for t in range(j))
                    row.append(z.clamp_min(1e-12).sqrt() if i == j else z / rows[j][j])
            rows.append(row)
        chol = torch.stack([torch.stack(row, dim=-1) for row in rows], dim=-2)
        return torch.log_softmax(logits, dim=-1), mean, chol


def mixture_nll(output, target, dimensions=4):
    logpi, mean, chol = output
    delta = target[:, None, :dimensions] - mean[..., :dimensions]
    solved = []
    for i in range(dimensions):
        z = delta[..., i]
        if i:
            z = z - sum(chol[..., i, j] * solved[j] for j in range(i))
        solved.append(z / chol[..., i, i])
    quadratic = sum(z.square() for z in solved)
    logdet = sum(chol[..., i, i].log() for i in range(dimensions))
    component = -0.5 * (dimensions * math.log(2 * math.pi) + quadratic) - logdet
    return -torch.logsumexp(logpi + component, dim=-1)


def mixture_draw(output, generator=None):
    logpi, mean, chol = output
    n, k = logpi.shape
    u = torch.rand(n, 1, device=logpi.device, generator=generator)
    component = (u > logpi.exp().cumsum(-1)).sum(-1).clamp_max(k - 1)
    row = torch.arange(n, device=logpi.device)
    noise = torch.randn(n, 4, device=logpi.device, generator=generator)
    return mean[row, component] + (chol[row, component] @ noise[..., None])[..., 0]


def particle_brier(draws, truth):
    """Unbiased integration of the frozen S, including unresolved mass as U.

    U is an explicit failure atom, never removed from the denominator.
    """
    a = np.asarray(draws)
    y = np.asarray(truth)
    if a.ndim != 2 or a.shape[1] < 2 or y.shape != (len(a),):
        raise ValueError('At least two particles per observed target required')
    sorted_a = np.sort(a, axis=1)
    # Equal-label unordered pairs; loop over small M, vectorize over queries.
    pairs = np.zeros(len(a), dtype=float)
    for lag in range(1, a.shape[1]):
        pairs += (sorted_a[:, lag:] == sorted_a[:, :-lag]).sum(axis=1)
    return 1 - 2 * (a == y[:, None]).mean(axis=1) + 2 * pairs / (a.shape[1] * (a.shape[1] - 1))
