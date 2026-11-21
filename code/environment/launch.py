"""Open the notebook locally with the prepared project kernel, without running cells."""
import json
import os
from pathlib import Path
import sys


def prepare_notebook(root):
    path = root / 'code/run_experiments.ipynb'
    document = json.loads(path.read_text(encoding='utf-8'))
    metadata = document.setdefault('metadata', {})
    kernel = {'display_name': 'DATA3001 (Python 3.12)',
              'language': 'python', 'name': 'data3001-py312'}
    if metadata.get('kernelspec') != kernel:
        metadata['kernelspec'] = kernel
        path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return path


def main(root=None):
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[2]
    notebook = prepare_notebook(root)
    os.chdir(root)
    os.execv(sys.executable, [sys.executable, '-m', 'jupyterlab', str(notebook),
        '--ServerApp.root_dir=' + str(root), '--ServerApp.ip=127.0.0.1',
        '--ServerApp.open_browser=True',
        '--MappingKernelManager.default_kernel_name=data3001-py312',
        '--KernelSpecManager.allowed_kernelspecs=["data3001-py312"]'])


if __name__ == '__main__':
    main()
