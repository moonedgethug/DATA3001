# Step 5 E2 — resource-only amendment for review

Status: **Awaiting user approval. No new resource limit has been applied.**

The approved contract remains unchanged. The user's direct-full-run instruction removed the resource pilot. Actual full-run measurements now show that the inner-stage budget is insufficient. This proposal changes time limits only; the models, complete cohorts, donors, weights, deterministic EM starts, covariance/support thresholds, selection procedure, N=M=65,536, scoring and acceptance criteria remain fixed.

## Completed and preserved

- All **86,373** inner queries fitted at K=1,2,3; both complete parameter freezes verified.
- **2,176** first-window queries have complete ES batch receipts; all hashes verified.
- No orphan score outputs. Earlier attempts and all completed work are retained and charged.
- Outer fitting, outer scoring and full independent auditing are still pending. No outer targets or final-test data have been accessed. Predictive superiority cannot yet be assessed.
- Active compute so far: **2.910 h**, including **2.821 h** charged to the inner stage. Coding and approval wait time are excluded.

## Measured cost and conditional estimates

Formal ES: mean **0.2288 worker-seconds/query**, batch p95 **0.2514**, measured across 68 complete batches. At two workers, the remaining complete inner ES is approximately **2.68–2.94 h**.

The whole-inner independent parameter/selection audit is estimated at **0.81 h**, based on the retained-record independent arithmetic check plus an allowance for the 128 independent refits and I/O. This is an extrapolation, not a guarantee.

If K=2 reaches the quality gate, complete G1/K2 region reconstruction adds approximately **3.48–3.96 h**. This is a historical E1 M=65,536 cost proxy scaled by continuous component count; it has not been newly benchmarked. K=3 already exceeds the fixed 5% fallback limit in both complete windows, but its complete ES remains required and will be computed.

Estimated inner total: **6.31 h** without the optional K2 regions, or **9.79 h** with them. Applying the contract's 1.5 reserve to remaining p95/proxy costs gives **14.38 h** including consumed time. Both routes exceed the original 6 h inner cap.

For planning, the entire experiment is roughly **9–16 h including consumed time**, conditional on whether K2 reaches and passes the quality gate. This range is an estimate. The requested limits below are ceilings, not scheduled runtime; stop accounting immediately on completion.

## Proposed time limits

| Phase | Current cap | Proposed cap |
|---|---:|---:|
| Checks | 0.5 h | 0.5 h |
| Complete inner selection | 6 h | 15 h |
| Outer experiment | 4 h | 6 h |
| Independent outer audit | 3 h | 3 h |
| Reporting | 0.5 h | 0.5 h |
| Total, including prior attempts | 14 h | 25 h |

Memory remains 8 GiB, E2 storage 8 GiB and the E1/E2 family 10 GiB. No data are removed and no precision or sample count is reduced. The larger outer ceiling covers the conditional K2 component cost with reserve; the actual outer setup remains frozen until training-only selection completes.

Approval would permit only these time-limit changes and resumption from verified checkpoints. Existing parameter fits and completed scores will not be repeated. A separate approval receipt and versioned resource configuration will preserve the original configuration and all previous consumption. Any numerical, covariance, support or storage problem continues to trigger the existing stop/report rules.
