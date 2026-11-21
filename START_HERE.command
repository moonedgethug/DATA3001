#!/bin/bash
# Finder can open this entry before Python, Jupyter or a kernel is installed.
project_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 1
printf '%s\n' 'DATA3001 — preparing the project and opening the notebook.' \
    'Python and packages are installed automatically. No experiments start during setup.' \
    'Keep this window open while using the notebook.'
/bin/bash "$project_root/code/environment/setup.sh" --launch
status=$?
if [[ "$status" -ne 0 ]]; then
    printf '\nSetup stopped. The reason is shown above.\n'
    if [[ -t 0 ]]; then
        read -r -p 'Press Return to close this window. ' _startup_response
    fi
fi
exit "$status"
