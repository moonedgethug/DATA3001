# Full verification and reporting review

The fresh review also covered the verification and reporting modules added after
the initial execution review. The following findings were resolved before the
full outer target release:

1. Compare the primary hit indicator with the independently calculated membership
   of the original frozen region, not only with a reconstructed region.
2. Check the fixed 128-case IID reference directly against both primary and audit
   Gaussian ES estimates, and assert the exact prespecified case positions.
3. Reconstruct all 45 × 3 per-ID aggregates independently and retain the audit
   differences and numerical standard errors.
4. Include the primary-before-companion superiority condition in report reasons.
5. Preserve resource accounting and a stopped receipt if reporting fails.

Meaningful regression failures and passing checks are retained in
`verification_review_red.txt`, `iid_direct_red.txt`, and
`verification_review_green.txt`. The final focused suite contains 60 passing
tests. The earlier `fresh_review_resolution.json` records the two execution
findings and the then-current 53-test count; it is retained as an earlier receipt.

No model law, training weight, donor selection, sample roster, numerical level,
metric, or scientific acceptance condition was changed by these corrections.
Full numerical and independent-data checks remain separate execution gates.
