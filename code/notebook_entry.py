"""Direct notebook cells with no repeated fits after a completed full/phase run."""
from pathlib import Path

import workflow


class NotebookRunner:
    def __init__(self, root, *, environment_ready):
        if not environment_ready:
            raise RuntimeError('Run the notebook configuration cell before starting an experiment.')
        self.root = Path(root).resolve()
        self.completed_suites = {}

    def _completed_result(self, task):
        full = self.completed_suites.get('full.refit')
        if (task in {'stage1.all', 'stage2.all'} and full
                and full.get('all_completed_experiments_selected')):
            return full
        for result in reversed(list(self.completed_suites.values())):
            for child in result.get('completed_tasks', []):
                matches = child['task'] == task
                # The twelve-count comparison trains all six parent networks.
                matches |= task == 'stage2.step5.mdn6' and child['task'] == 'stage2.step5.mdn12'
                if matches and child['status'] == 'complete':
                    return {'task': task, 'status': 'complete',
                            'output_directory': str(Path(child['receipt']).parent)}
        return None

    def run(self, task, **options):
        previous = self._completed_result(task) if not options else None
        if previous:
            print('Already completed by the full workflow or phase in this kernel.')
            print('Output:', previous['output_directory'])
            return previous

        title = workflow.REGISTRY[task].title
        print('Running:', title, flush=True)
        result = workflow.run_task(task, root=self.root, **options)
        if result.get('status') == 'complete' and task in {'full.refit', 'stage1.all', 'stage2.all'}:
            self.completed_suites[task] = result
        print('Status:', result.get('status'))
        print('Output:', result.get('output_directory'))
        return result
