# Live full-run checkpoint

## COMPLETE — 7 November 2026

All stages finished successfully: full parameters, frozen forecasts, scoring,
primary precision gates, independent full reconstruction, fixed128 IID/donor
checks, paired inference, report and final release QA. No process remains to
resume and no stage should be rerun in this immutable run.

All33971 validation starts/45IDs and the265393-pair/338-ID training pool were
retained. All490 protected hashes were reverified. All60 focused tests passed.
The final source-backed report is results/runs/conditional_gaussian_s5_e1_full_20261107T061818Z/review.html;
model_manifest.json and gaussian_parameters.parquet are in the same folder.
release_manifest.json seals every result file. final_release_qa.json records
numeric/link/image QA, resource totals and the unverified browser-layout limit.

Full results (ES km / H90 / area km2):
ExactPoint134.2232256824 /0.9139213279 /215666.8894;
EndpointCI134.2231876184 /0.9139727581 /215723.9006;
LocalGaussian134.7765263211 /0.9154495482 /216104.2291.
G−A ES+0.5533006387km(+0.412224%), paired95%CI[-1.407579,2.626321];
hit+0.152822percentage points; meanarea+0.202785%.
Decision:NO_SUPPORTED_NONDEGRADING_IMPROVEMENT. Engineering and numerical
checks passed; scientific improvement criteria did not. Default unchanged.
No final-test access, model change, covariance repair, sample removal or new
experiment. EndpointCI unavailable-error mass6.212692% retained as point votes.

The remaining paragraphs preserve earlier execution checkpoints; they are
historical and superseded by this completion note.

User explicitly approved resource-only amendment: formal4h/audit2h/total6.5h, storagepreflight8GiB/hard10GiB. Scientific contract unchanged. New run conditional_gaussian_s5_e1_full_20261107T061818Z. Prior run conditional_gaussian_s5_e1_20261107T054457_277726Z stays immutable.

Completed: resourcepreflight128cases, matched alloldES, private2processparity. Updated singleprocessconservativeprojection formal119.61min, required2x239.23min<240; audit31.30min; storageproxy5.08GiB<8. Full parameters33971/33971 completed282sec; min5521pairs, max8000, min19donorIDs,max240;maxcondition57.9457,minEigen1057.108. No unsupported/singular rows.

Regions completed all33971 in2083.43sec, frozen before outer targets. Current process: full.py score; exec session3503, logs score.log. At checkpoint18560/33971 after123.7sec. DO NOT restart/overwrite. Read process/receipt if session lost. Targets were released only after the full forecast freeze.

Implementation files: core/_numerics/_inputs unchanged science; _full.py handlespreflight,parameters,regions(freezeall),score,audit. _reference.py independentfit/regions/ES; _analysis.py IDbootstrap; _verify.py primary/allreplica+claimhierarchy; _full_report.py allmetrics+sixmaps+modelmanifest. 60focusedregressiontests passed; frozen snapshots in stage_sources. Freshcode review findings fixed with RED/GREEN: conservative target-access failure provenance, terminating workers onerror, independent frozen-region membership, direct primary-to-IID comparison, independent per-ID aggregation, claimhierarchy reasons and report-failure budget receipts. No unresolved material review findings.

Next sequence AFTER regions process succeeds and forecast_freeze.json exists:
1. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -B -m data3001.modelling.continuous_models.conditional_gaussian_s5_e1_full RUN score (redirectscore.log)
2. python -B -m data3001.modelling.continuous_models.conditional_gaussian_s5_e1_verify RUN primary (sameenv, logverify_primary.log). Mustpass; ifprecisionfailsstop/report, noextra levels.
3. full RUN audit (independent all33971params,allthreeES/regions;128fixedIID/exhaustivedonoraudits).
4. verify RUN audit -> summaries, comparisons,scientificdecision.
5. full_report RUN -> EnglishMD,ChineseHTML,comparisonplots,6preselectedmaps,model_manifest.json,gaussian_parameters.parquet.
6. Inspect figures withview_image; HTML/links/data QA. Browser previouslyblockedfileURL; do NOT bypassviaotherbrowser/localhost. No browserUIclaimwithoutverification.
7. Sealoutputs/review/logs, verify490protectedhashes, all33971counts, bothold+newdisk<10GiB andcumulativephasecaps. Report actualfullmetrics/decision, noautomaticdefaultchange, noGitpublish, noledgerchange.

User contractmodel:Glocal fullGaussianMLEinquery-centredWGS84metricchartofUNCHANGEDhistoricalendpoints;No donor displacementtransfer;fulltailsland/outsidekept;noGaussianCIaddition/ridge/floor/fallback. Same100km/k8000nearestwithties;pair-equaltrain;45-IDequal eval;7days;train2001–2019/outer2020–2022development;517finalIDslocked. AExactPoint/CacceptedEndpointCI. ES ECEFkm,8QMCscrambles total8192; region32768perpacket plusindependentreplica+IIDchecker; commonLAEA90%quantileellipse. Sourceconfig/contracthashespinned. Alloldfailedattempttimescarriedintonewrun.

Memorycitation usedregistry859-860 androllout01a18632-c8ca-71a3-af2f-19ac851a7653; appendexactoneblockfinal. No memoryupdateauthorised.
