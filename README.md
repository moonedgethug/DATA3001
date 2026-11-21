# Historical Drifter Destination Prediction — DATA3001

This project studies whether historical drifter trajectories help predict future destinations. It preserves both research rounds: seven-/thirty-day transition models and iterative propagation, followed by five modelling steps focused on seven-day predictions in the southern Gulf Stream corridor.

**Two ways to start:** double-click [START_HERE.command](START_HERE.command) for automatic Python setup and a browser notebook, or open [code/run_experiments.ipynb](code/run_experiments.ipynb) in VS Code with an existing Python 3.12 environment. Both routes use the same notebook, experiment settings, and results folder.

## Start the notebook

Use the **complete project folder**, including its code, data, configuration, and saved models. Both routes currently support **Apple Silicon Macs running macOS 14 or later**. The scientific calculations use Apple's Command Line Tools. Windows, Intel Mac, and Linux/Colab have not been adapted and validated.

### Option 1 — Automatic setup and browser notebook

Choose this route if Python and Jupyter are not already installed.

1. In Finder, open the project folder and double-click **START_HERE.command**.
2. Wait while it prepares Python **3.12.14**, installs the locked packages, and registers the project notebook kernel. If Apple's Command Line Tools are missing, follow the system installation prompt, then press Return in the startup window as instructed.
3. The browser opens **JupyterLab** with `code/run_experiments.ipynb`. This notebook runs locally on your Mac. Keep the startup Terminal window open while using it.
4. Run **Environment and configuration** at the top of the notebook. It checks the packages and initializes the experiment controls. When it prints **Ready**, run **Complete workflow** or any named data/model cell.

This route requires no manually entered setup commands. It keeps the project environment in `.venv/` and the downloaded Python under `.tools/python/`. Setup opens the notebook without starting experiments. To reopen it later, double-click **START_HERE.command** again.

### Option 2 — Use an existing Python environment in VS Code

Choose this route if you already have a working Python **3.12** notebook environment.

1. Open the complete project folder in VS Code, then open **code/run_experiments.ipynb** with your existing Python 3.12 kernel. Microsoft Python and Jupyter extensions provide notebook support.
2. Run **Environment and configuration**. It installs missing or mismatched project packages into the Python running this notebook and checks the numerical libraries and compiler.
3. When it prints **Ready**, run **Complete workflow** or any named data/model cell.

This configuration cell manages packages and notebook controls; Python and the working kernel are supplied by your existing environment. If a package update affects a library already loaded in memory, follow the cell's instruction to restart the current kernel and rerun the configuration cell.

## Environment and package versions

Both routes use `pyproject.toml` for dependency definitions and `uv.lock` for their direct and indirect versions. Internet access is needed when Python, the installer, or packages must be downloaded.

The automatic route calls `code/environment/setup.sh --launch`, prepares the project `.venv/`, and uses the Python **3.12.14** pin in `.python-version`. The notebook configuration cell calls `code/environment/configure.py`; it accepts an existing Python **3.12**, records its actual version, and brings project packages to their locked versions while preserving unrelated packages. Neither route rewrites the dependency lock or changes the experimental settings.

The package installer is kept under `.tools/`. Its use of the current interpreter and locked requirements follows uv's [environment targeting](https://docs.astral.sh/uv/pip/environments/) and [lock export](https://docs.astral.sh/uv/concepts/projects/export/) documentation.

## Run from the notebook

The notebook has the following sections, in this order. After environment configuration, run the cell for the work you need.

| Section | Cells | What it does |
|---|---|---|
| Environment and configuration | One configuration cell | Installs/checks locked packages in the current Python and loads the notebook controls |
| Complete workflow | One execution cell | Replays development-data cleaning → report-covered Stage 1 → report-covered Stage 2 → report figures and presentation data |
| Data preprocessing only | Data inspection, cleaning, Markov input preparation | Runs the named preparation without fitting models |
| Stage 1 only | Whole-stage cell, then individual model cells | Reproduces the first-round models, comparisons, and diagnostics covered in W06, or one experiment |
| Stage 2 only | Whole-stage cell, then individual model cells under five steps | Reproduces the second-round experiments covered in W07–W11, or one experiment |
| Final model and report | Frozen prediction, figures, presentation data, final-model comparison summaries | Uses the final model or published results without refitting |

**Run All starts the complete report workflow.** The notebook's group buttons select the experiments covered by the report and preserve all data entries. After a complete workflow or whole stage succeeds, its individual model cells show the existing output instead of repeating those fits in the same kernel. To refit a model already completed by a group, restart the kernel, rerun the configuration cell, and run that model's cell. Every task prints its status and output folder.

The complete-workflow cell includes raw cleaning. Each model then uses its original fixed input snapshot; freshly cleaned files do not automatically replace those inputs. Figure generation uses the published predictions and frozen final model. The last Gaussian timing check exceeded its original computing-time limit; that fit currently stops at its budget check, and a complete end-to-end run remains unverified. Details are in [docs/reproduction_audit.md](docs/reproduction_audit.md).

The B0/B1/B2 baselines share their original fitting cell; the regularized-model comparison also recomputes the five-fold baseline scores in report Table 6. The twelve-count network comparison includes all six initial candidate component counts, so a whole-stage run fits those models once. The recorded-summary cell retrieves the final-model comparison reported in Table 11.

### Optional command-line use

Individual operations are also available through `code/workflow.py`. The command-line group aliases `stage1.all`, `stage2.all`, and `full.refit` retain the broader historical task lists; they do not apply the notebook's report-only selection. Use the notebook for the report workflow, or specify command-line tasks explicitly, for example `full.refit --tasks stage2.step1 stage2.step2.adaptive`.

For late model initialization without training, use `--prepare-only`, for example `python code/workflow.py run stage2.step5.gaussian --prepare-only`. A prepared run has verified setup and input contracts; it is not a completed fit.

List or inspect tasks before a long run:

```bash
python code/workflow.py list
python code/workflow.py inspect stage2.step1
```

Equivalent command-line examples:

```bash
python code/workflow.py run predict.final_mdn22 --longitude -78 --latitude 33
python code/workflow.py run stage2.step1
python code/workflow.py run report.rebuild
```

The notebook uses full method names above the execution cells. The command-line registry also records each task's scope, execution status, and last-successful receipt.

## Directory guide

Start with the notebook in `code/`. The main folders below separate data, programs, experimental settings, saved models, and results. The tree shows the project layout; local data and generated outputs have the delivery requirements described under **Transfer to another machine**.

```text
work_place/
├── README.md                             # Start here: setup and reproduction guide
├── START_HERE.command                    # Automatic setup and browser notebook
├── pyproject.toml                        # Python dependency definitions
├── uv.lock                               # Locked package versions
├── .python-version                       # Reference Python version
│
├── code/                                 # All executable research code
│   ├── run_experiments.ipynb              # Configuration and runnable report experiments
│   ├── environment/                      # Python/package setup and environment checks
│   ├── data_preprocessing/
│   │   ├── region_selection/             # Choose the study region
│   │   ├── download/                     # Acquire source data
│   │   ├── cleaning/                     # Clean records and apply approved repairs
│   │   └── pair_generation/              # Build qualified prediction pairs
│   ├── modelling/
│   │   ├── stage1/                       # First research round
│   │   │   ├── empirical_baselines/      # Fit and evaluate B0, B1, and B2
│   │   │   ├── regularization/           # Blend local and pooled information
│   │   │   ├── spatial_information/      # Share neighbouring endpoints/displacements
│   │   │   ├── drogue_comparison/        # Compare drogue states
│   │   │   ├── markov_iteration/         # Iterate transitions and diagnose propagation
│   │   │   └── hourly_continuous_models/ # Hourly Gaussian and mixture-density models
│   │   └── stage2/                       # Second research round: five steps
│   │       ├── step1_empirical_matrix/
│   │       ├── step2_regularized_matrix/
│   │       ├── step3_spatial_information/
│   │       ├── step4_conditioned_transitions/
│   │       └── step5_continuous_distributions/
│   ├── shared/                           # Common data access, geometry, and scoring
│   ├── reproduction/                     # Run tasks and record inputs/outputs
│   ├── reporting/                        # Generate analyses, figures, and presentation data
│   └── tests/                            # Scientific and delivery checks
│
├── data/                                 # Data and metadata; no executable code
│   ├── raw/                              # Original source data
│   ├── train/                            # Development trajectories, one file per drifter
│   ├── test/                             # Sealed final-test trajectories
│   ├── reference/                        # Region boundaries, land masks, and auxiliary data
│   ├── metadata/                         # Sources, schemas, splits, and qualification records
│   └── prepared/                         # Fixed model inputs and report analysis tables
├── configs/                              # Experimental parameters and settings
│   ├── data_preprocessing/
│   ├── stage1/
│   ├── stage2/
│   └── reporting/
├── saved_models/
│   ├── final_mdn22/                      # Frozen final 22-component model
│   ├── comparison_models/                # Saved comparison models
│   └── registry.json                     # Model identities and checksums
├── results/
│   ├── reference/                        # Recorded experiment results for comparison
│   └── reproduced/                       # New outputs from each notebook run
├── report/
│   ├── DATA3001_Final_Report_CN.docx      # Current Chinese report
│   ├── figures/                          # Report figures
│   └── presentation/                     # Website presentation
├── docs/                                 # Contracts, research records, and reproduction audit
├── provenance/                           # Source identities, migration maps, and check records
└── archive/                              # Preserved history and original inputs
```

`data/` contains data and explanatory metadata, not executable programs. First-round work is an active part of the research deliverable. Old source, configuration, and run locations retain compatibility links; the readable implementations are under `code/`.

## Data and experimental definitions

The current release is `per-drifter-cleaned-20261017-v7`: **3,741 drifters, 39,099,193 hourly records, 62 fields**. The 3,224 development drifters include the historical training and development-validation roles. These roles are distinct from the 517 sealed final-test drifters.

The final seven-day study uses 265,393 training pairs from 338 drifters in 2001–2019, and 33,971 development-validation pairs from 45 drifters in 2020–2022. The original contracts define pair qualification, exact-time matching, exit and unresolved states, weighting, and scores. They remain unchanged during migration.

- **First round:** B0 persistence, pooled-origin B1, origin-cell B2; regularization, spatial borrowing, drogue comparisons, and short-step iteration. The hourly continuous models belong to this round.
- **Step1 — Empirical transition matrix:** empirical B2 reference.
- **Step2 — Regularized / Bayesian matrix:** B1/B2 blending and drifter contribution weights.
- **Step3 — Spatially structured matrix:** neighbouring endpoint and displacement information.
- **Step4 — Time- and environment-dependent transitions:** seasonal comparisons, departure direction, exact origin, and position uncertainty.
- **Step5 — Memory-aware / latent-state models:** implemented here as Gaussian, Gaussian mixture, and conditional mixture-density distributions. Explicit latent-state sequence models were not implemented.

The final recommended network has 22 components after development review. The original contract selection returned one component; both identities are recorded in `saved_models/registry.json`. No final-test performance is claimed. Stopped exploratory branches remain stopped.

## Reproduction order and records

The scientific dependency order is:

1. Fixed raw source and auxiliary records → approved cleaning and repairs → current development trajectories and qualification.
2. Qualified pairs and development folds → first-round empirical and iterative models.
3. Empirical matrix → regularization → spatial sharing → time/position conditions.
4. Exact-origin coordinates and temporal roles → Gaussian → Gaussian mixture → initial six network component counts → twelve-count comparison.
5. Frozen final model and recorded comparisons → case figures, whole-region analysis, and report figures.

Individual model tasks may reuse a published upstream input snapshot; their scope and input manifest state that reuse. Reusing inputs is distinct from reusing a fitted model. Original source hashes and fixed input identities are enforced by the scientific programs.

Each task creates `results/reproduced/<run_id>/` with `run.json`, `input_manifest.json`, command logs, and outputs. Original programs run in an isolated reconstruction of their historical directory layout, preserving their relative paths and source checks. The migration does not change the model algorithms.

Read [docs/reproduction_audit.md](docs/reproduction_audit.md) for completed checks. The final idle Gaussian preflight passed all 128 numerical controls but projected 16,566.78 seconds including the original reserve, above its unchanged 14,400-second cap. The original gate therefore stops that full fit. Other long-duration model fits and the complete suite have not been rerun during this migration; their initialization checks are recorded separately. The full historical network fits took many hours; current runtime is recorded per execution. A successful frozen prediction or figure redraw is not labelled a full refit.

## Report figures and regional analysis

The report-figure cell uses the saved regional tables. To recompute the whole-region integration with the frozen model, replace that cell's call with:

```python
result = notebook.run("report.rebuild", recompute_region=True)
```

This uses the same frozen 22-component model and original integration rules. It does not retrain. The **0.8605277% unresolved whole-region release weight** represents wet-area release locations without eligible training-origin support and remains part of the total probability. It is not a grounding probability.

Presentation data can be regenerated with `python code/workflow.py run presentation.export`. Fixed geographic inputs and their source identities are in `data/reference/presentation_inputs/`.

The current Word report has not been rewritten by the migration. The website can be served locally from the project root:

```bash
python -m http.server 8000
```

Open `http://localhost:8000/report/presentation/`. Chinese figures use an available CJK font such as PingFang HK, Arial Unicode MS, or Noto Sans CJK SC.

## Verify implementation and inputs

```bash
python code/environment/configure.py
python code/environment/verify.py
```

Use the same Python as the notebook. The first command is the notebook's package configuration entry; the second reconstructs the original scientific test environment and runs the unchanged test suite. It does not supply the sealed drifter used by one historical SST regression case; that case remains skipped. Development-only regression fixtures and synthetic access-protection tests are included.

[docs/migration_manifest.json](docs/migration_manifest.json) maps original files to their new locations and records hashes. Migration backups and checks are under `provenance/migrations/code_delivery_20261122/`. `archive/` is retained unchanged.

## Transfer to another machine

The frozen final model is self-contained under `saved_models/`. Its inference path has passed in a separate directory with reads of the original workspace data and code blocked; the installed Python environment was shared. Full fitting and raw replay additionally need the registered trajectory, qualification, prepared-input, and historical evidence files. Large local run directories are not automatically published by moving them.

Use the data and migration manifests to transfer the required inputs with their relative locations and verify their hashes. This migration does not upload a data bundle or change the remote repository. Before distributing a GitHub-only submission, the release must include the necessary input package or a verified retrieval location; a code-only checkout must not be described as a complete research-data delivery.
