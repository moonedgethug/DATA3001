#!/bin/bash
# Shared preparation entry for Terminal and the optional notebook setup cell.
# Official, versioned installer: https://docs.astral.sh/uv/getting-started/installation/
set -euo pipefail

usage() {
    printf '%s\n' 'Usage: bash code/environment/setup.sh --prepare|--launch' \
        '  --prepare  Prepare the locked Python environment and register its kernel.' \
        '  --launch   Prepare, then open code/run_experiments.ipynb in JupyterLab.'
}

die() { printf 'Environment setup: %s\n' "$*" >&2; exit 1; }

[[ $# -eq 1 ]] || { usage >&2; exit 2; }
case "$1" in
    --prepare|--launch) mode="$1" ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
project_root="$(CDPATH= cd -- "$script_dir/../.." && pwd -P)"
[[ "$(uname -s)" == Darwin ]] || die 'This delivery setup currently supports macOS only.'
[[ "$(uname -m)" == arm64 ]] || die 'The locked dependencies require native Apple Silicon (arm64); Intel and Rosetta are unsupported.'
macos_version="$(sw_vers -productVersion)"
macos_major="${macos_version%%.*}"
[[ "$macos_major" =~ ^[0-9]+$ ]] && (( macos_major >= 14 )) || die 'The locked dependencies require macOS 14 or later.'
# An unrelated Python tree must not affect installation, registration or launch.
unset PYTHONPATH PYTHONHOME

for manifest in pyproject.toml uv.lock .python-version; do
    [[ -f "$project_root/$manifest" ]] || die "Missing $manifest in $project_root."
done
python_pin="$(tr -d '[:space:]' < "$project_root/.python-version")"
[[ "$python_pin" =~ ^3\.12\.[0-9]+$ ]] || die '.python-version must pin one Python 3.12 patch release (for example 3.12.14).'
notebook="$project_root/code/run_experiments.ipynb"
[[ "$mode" != --launch || -f "$notebook" ]] || die "Missing notebook: $notebook"

# These system tools are needed by the original native scientific kernels.
# On a new Mac, let Apple's installer handle its own user confirmation.
compiler_ready() {
    xcrun --find clang++ >/dev/null 2>&1 && xcrun --sdk macosx --show-sdk-path >/dev/null 2>&1
}
if ! compiler_ready; then
    printf '%s\n' "Opening Apple's Command Line Tools installer. Click Install in the system dialog."
    xcode-select --install || true
    if [[ -t 0 ]]; then
        read -r -p 'After the system installation finishes, press Return to continue. ' _setup_response
    fi
    compiler_ready || die 'Finish the Apple Command Line Tools installation, then reopen START_HERE.command.'
fi

# Keep bootstrap tools local; do not change the user's shell configuration.
uv_version=0.13.9
uv_directory="$project_root/.tools/uv/$uv_version"
uv_binary="$uv_directory/uv"
pinned_uv() {
    local detected
    detected="$("$1" --version 2>/dev/null)" || return 1
    [[ "$detected" == "uv $uv_version" || "$detected" == "uv $uv_version "* ]]
}
if [[ ! -x "$uv_binary" ]] || ! pinned_uv "$uv_binary"; then
    candidate="$(command -v uv || true)"
    if [[ -n "$candidate" ]] && pinned_uv "$candidate"; then
        uv_binary="$candidate"
    else
        command -v curl >/dev/null 2>&1 || die 'curl is required to download the official uv installer.'
        installer="$(mktemp "${TMPDIR:-/tmp}/data3001-uv.XXXXXX")"
        trap 'rm -f "$installer"' EXIT
        printf 'Downloading the official uv %s installer.\n' "$uv_version"
        curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error \
            "https://astral.sh/uv/$uv_version/install.sh" --output "$installer"
        UV_UNMANAGED_INSTALL="$uv_directory" /bin/sh "$installer"
        [[ -x "$uv_binary" ]] || die 'The uv installer did not produce the expected executable.'
        pinned_uv "$uv_binary" || die 'The installed uv version does not match the pinned version.'
    fi
fi

# Ignore an unrelated active environment and always target this project's .venv.
unset VIRTUAL_ENV CONDA_PREFIX
export UV_PROJECT_ENVIRONMENT="$project_root/.venv"
export UV_PYTHON_INSTALL_DIR="$project_root/.tools/python"
export UV_PYTHON_INSTALL_BIN=0
cd -- "$project_root"
printf 'Preparing Python %s from pyproject.toml and uv.lock.\n' "$python_pin"
"$uv_binary" python install "$python_pin" --no-bin
"$uv_binary" sync --project "$project_root" --python "$python_pin" \
    --managed-python --locked --all-extras --all-groups

project_python="$project_root/.venv/bin/python"
[[ -x "$project_python" ]] || die 'The project Python executable was not created.'
"$project_python" -m ipykernel install --user --name data3001-py312 \
    --display-name 'DATA3001 (Python 3.12)'

# Record exactly what the successful locked sync installed for later read-only checks.
"$project_python" - "$project_root" "$python_pin" "$uv_version" <<'PY'
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
record = {
    "schema": 1,
    "python_pin": sys.argv[2],
    "uv_version": sys.argv[3],
    "manifests": {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in ("pyproject.toml", "uv.lock", ".python-version")
    },
    "packages": {
        re.sub(r"[-_.]+", "-", distribution.metadata["Name"]).lower(): distribution.version
        for distribution in importlib.metadata.distributions()
        if distribution.metadata["Name"]
    },
}
(root / ".venv/.data3001-environment.json").write_text(
    json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

"$project_python" -B "$script_dir/check.py"
if [[ "$mode" == --launch ]]; then
    exec "$project_python" "$script_dir/launch.py"
fi
printf '%s\n' 'Preparation complete. Select DATA3001 (Python 3.12) in the notebook.'
