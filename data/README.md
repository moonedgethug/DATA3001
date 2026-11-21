# Data navigation

Data files and metadata live here; executable processing programs are in `../code/data_preprocessing/`.

| Folder | Meaning |
|---|---|
| `train/` | 3,224 development drifters; temporal and cross-validation roles are defined separately |
| `test/` | 517 sealed final-test drifters; normal workflow tasks do not request their trajectories |
| `raw/` | Links to fixed GDP native source objects and hourly Zarr subset |
| `reference/` | Geometry, ocean/land masks, official status records and fixed presentation inputs |
| `metadata/` | Dataset/schema/qualification manifests and location indexes |
| `prepared/` | Frozen Markov counts, seven-day coordinates/roles/targets and report tables |

The seven-day development targets belong to 2020–2022 development validation, not the sealed final-test partition. These inputs retain their original identities and are linked to the reference runs. `metadata/prepared_links.json` records their sources; `metadata/delivery_links.json` records raw and auxiliary links. The retained archive currently supplies some original input locations.

Raw cleaning replay writes new development trajectories and qualification files under `results/reproduced/`. It uses the original cleaning functions and approved SST repair decisions. It does not re-run the SST imputation research. Shared raw storage chunks may include adjacent IDs; the replay requests only development IDs and records this storage scope.

Large native source objects and complete local model runs need a research input package when transferring the repository. The root README and execution input manifests specify those dependencies; environment installation only installs Python and packages.
