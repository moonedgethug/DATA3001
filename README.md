# Historical Drifter Destination Prediction — DATA3001

## Project overview

This project studies whether historical drifter trajectories help predict future destinations. It preserves both research rounds: seven-/thirty-day transition models and iterative propagation, followed by five modelling steps focused on seven-day predictions in the southern Gulf Stream corridor.

## Reproduce the project

Supported platform: **Apple Silicon Mac with macOS 14 or later**. Some model implementations depend on Apple's development tools. Use the complete project folder, including its data and saved models.

1. **Automatic setup:** double-click [START_HERE.command](START_HERE.command). It prepares Python 3.12 and the required packages, then opens the notebook in your browser. Follow any installation prompts and keep the startup window open.
2. **Existing Python environment:** prepare Python **3.12**, then open [code/run_experiments.ipynb](code/run_experiments.ipynb) in VS Code and select your Python 3.12 kernel.

Run **Environment and configuration** first to install and check packages, then run **Complete workflow** or the individual data/model cells you need.

## Research workflow

1. **Data preprocessing:** clean the drifter records and prepare prediction pairs.
2. **Stage 1:** build seven-day and thirty-day transition models and test iterative prediction.
3. **Stage 2:** compare seven-day prediction methods through five modelling steps, progressing from discrete grids to continuous distributions.

Models use the fixed inputs from the original experiments. The notebook also provides saved-model predictions and report figures.

- **Original results:** [results/reference/](results/reference/).
- **New results:** each run creates a separate folder under [results/reproduced/](results/reproduced/).

Methods and findings are described in the [final report](report/DATA3001_Final_Report_CN.docx). The Gaussian refit currently stops at its time-budget check; see the [reproduction notes](docs/reproduction_audit.md) for recorded checks and run limits.

## Project structure

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
