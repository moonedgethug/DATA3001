# MDN K refinement implementation plan

Authority: `docs/conditional_mdn_s5_e4_contract.md`; user explicitly instructed full fitting of K=3,6,12,18,20,22, with visualization deferred.

1. Freeze the E4 contract/config and isolate code on a local experiment branch. Preserve historical files. Add tests first for candidate registry, shared-K equivalence, parent import hash/identity checks, exact score reuse and complete rosters.
2. Derive an isolated E4 runtime from the verified E3 runtime. Keep mathematical operations and RNG namespaces unchanged. Add explicit parent checkpoint/score reuse and provenance-aware independent auditing. Exercise existing numerical fixtures without reduced-sample scientific evaluation.
3. Review the complete change and execute necessary tests. Freeze source/input hashes and initialize a new run with the existing cohort and authorization boundaries.
4. Run full two-window training and scoring for the new K, combine with validated parent candidates, reconstruct the unchanged selection, then run full outer training/scoring and independent checks. Monitor and resume only validated saved prefixes.
5. Independently verify all records, expose the selected checkpoint through inference, and report numeric results and limitations. No visual deliverables or publication in this task.

Review focus: source authenticity of imported checkpoints; ID/time isolation; all 12 candidates at selection; no premature outer target release; exact parent-row compatibility including integration streams; resumability and spawn safety; no implicit model/score/quality-rule changes.
