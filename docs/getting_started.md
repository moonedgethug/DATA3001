# Download and use the current data

The repository's `main` branch contains the actual cleaned Parquet files,
not data pointers: **3,224 development files in `data/train/` and 517 final-test
files in `data/test/`**. The current v7 release has 3,741 IDs, 39,099,193 hourly
records and 62 columns per ID. The data files total approximately 3.75 GB.
The published files preserve the exact checksums in `configs/dataset_manifest.json`.

## Get the files

Use your own GitHub account with access to the private repository.

For a new checkout:

```bash
git clone --depth 1 https://github.com/moonedgethug/DATA3001.git
cd DATA3001
```

For an existing clean checkout on `main`:

```bash
git pull --ff-only origin main
```

Wait for the transfer to complete. The `.parquet` files are the data; no
separate data service or Git LFS installation is required. Do not copy a
different dataset over them or add new feature columns during loading.

## Prepare the Python environment

Use Python 3.12.14 and the pinned dependencies. For macOS/Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r configs/requirements.lock.txt
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m data3001 verify-data
```

On Windows, create the environment with `py -3.12 -m venv .venv` and use
`.venv\Scripts\python.exe` in place of `.venv/bin/python` in the remaining
commands. The verifier checks every published track against its checksum,
schema and row count, and verifies its portable qualification evidence.
It does not train or score a model.

## Read one development drifter

```python
from data3001.dataset import read_track, development_ids

ids = development_ids()       # 3,224 development IDs; final test excluded
track = read_track(22165)     # all 2,317 retained rows and 62 columns for this ID
print(track[["id", "time_UTC", "lat", "lon", "sst", "drogue_status"]].head())
```

`sst` is in Kelvin. `drogue_status` is categorical: 1 drogued, 0 undrogued,
-1 unknown. Use numeric missingness checks; unresolved metadata and the
approved post-grounding SST NA values remain intentionally missing.
Use complete drifter IDs for development validation. Final-test access is
an explicit opt-in for authorized work, not model selection.

## Generate the existing labels

```bash
.venv/bin/python -m data3001 pair --id 139080 --days 7 --population R
```

This reports eligibility for endpoint occupancy and the stopped process.
It is not a trained prediction or a probability map. The frozen R/D definitions,
exact matching and drogue interval rules are unchanged.

The small files in `provenance/qualification/v7/` contain exact projections
of existing audit annotations, keyed to the current observations. The
manifest-backed reader and pair command use them without requiring the
original raw Zarr cache or complete 129-column backups. They do not add
columns to the active data or the normal `read_track` result.

`verify-data` is the appropriate check for a downloaded checkout. The deeper
`verify-migration` audit compares with complete historical parents and therefore
still requires the original local backup bundle. Raw data, caches and full
historical backups are not part of the team download.

Read [the Data Contract](contract/data_contract_v1.0.xlsx), [the column
dictionary](data_dictionary.md), and [the preprocessing handover](preprocessing.md)
before choosing model inputs. Retention in the data does not make retrospective
fields available at a forecast origin.
