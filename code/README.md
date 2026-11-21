# Code navigation

Open the complete project in VS Code with an existing Python 3.12 notebook environment. Run the first configuration cell in [run_experiments.ipynb](run_experiments.ipynb): [environment/configure.py](environment/configure.py) installs locked packages into that Python and checks them. Then run the complete workflow, data preprocessing, Stage 1, Stage 2, or an individual model cell. [notebook_entry.py](notebook_entry.py) avoids repeating fits after a successful group run; [workflow.py](workflow.py) executes the original experiments and records their inputs and outputs. The root README gives the supported platform and usage details.

| Folder | Purpose |
|---|---|
| `data_preprocessing/` | Region selection, source acquisition, cleaning, approved repairs, qualification and pairing |
| `modelling/stage1/` | First-round model development and iterative propagation |
| `modelling/stage2/` | Five-step comparison of seven-day methods |
| `shared/` | Original shared functions and import compatibility |
| `reproduction/` | Delivery task registry, isolated workspaces and dependency binding |
| `environment/` | Current-Python package configuration, environment checks and verification |
| `reporting/` | Figures, regional distributions, supplementary analyses, website and document generation |
| `tests/` | Original scientific checks plus tests of new delivery boundaries |

Original scientific files retain their bytes and original module names. The task entry reconstructs their historical relative layout inside a new run directory; use the notebook or workflow entry to run them. `_compat/` and old source locations are links to the same implementations, not separately maintained models.

See the root [README](../README.md) for installation and the notebook sections, and [migration_manifest.json](../docs/migration_manifest.json) for each original/new path.

The earlier `setup.sh`, `launch.py`, and root `START_HERE.command` are retained for comparison with startup audit records. They are not part of the current notebook workflow.
