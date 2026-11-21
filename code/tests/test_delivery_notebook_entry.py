"""Notebook navigation checks use a fake workflow; no research task runs."""
import ast
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from notebook_entry import NotebookRunner


class NotebookEntryTests(unittest.TestCase):
    def runner(self):
        return NotebookRunner(Path('/unused/project'), environment_ready=True)

    @staticmethod
    def completed(task, children=()):
        return {'task': task, 'status': 'complete', 'output_directory': '/unused/output',
                'all_completed_experiments_selected': task == 'full.refit',
                'completed_tasks': [{'task': name, 'status': 'complete',
                                     'receipt': '/unused/output/' + name + '/run.json'}
                                    for name in children]}

    def test_invalid_environment_stops_before_a_workflow_call(self):
        with patch('notebook_entry.workflow.run_task') as execute:
            with self.assertRaises(RuntimeError):
                NotebookRunner('/unused/project', environment_ready=False)
            execute.assert_not_called()

    def test_full_workflow_prevents_repeated_phase_and_model_fits(self):
        children = ['data.raw_cleaning', 'stage1.baselines', 'stage1.markov_inputs',
                    'stage2.step1', 'stage2.step5.mdn12', 'report.rebuild', 'presentation.export']
        with patch('notebook_entry.workflow.run_task', return_value=self.completed('full.refit', children)) as execute:
            runner = self.runner()
            runner.run('full.refit', with_raw_replay=True)
            for task in children + ['stage1.all', 'stage2.all', 'stage2.step5.mdn6']:
                runner.run(task)
            self.assertEqual(execute.call_count, 1)
            self.assertTrue(execute.call_args.kwargs['with_raw_replay'])

    def test_phase_completion_does_not_skip_the_other_phase(self):
        with patch('notebook_entry.workflow.run_task', side_effect=[
                self.completed('stage1.all', ['stage1.baselines']), self.completed('stage2.step1')]) as execute:
            runner = self.runner()
            runner.run('stage1.all')
            runner.run('stage1.baselines')
            runner.run('stage2.step1')
            self.assertEqual(execute.call_count, 2)

    def test_failure_does_not_mark_a_phase_completed(self):
        with patch('notebook_entry.workflow.run_task', side_effect=[
                RuntimeError('interrupted'), self.completed('stage1.baselines')]) as execute:
            runner = self.runner()
            with self.assertRaises(RuntimeError):
                runner.run('stage1.all')
            runner.run('stage1.baselines')
            self.assertEqual(execute.call_count, 2)

    def test_single_model_can_be_run_again_without_a_completed_suite(self):
        with patch('notebook_entry.workflow.run_task', return_value=self.completed('stage2.step1')) as execute:
            runner = self.runner()
            runner.run('stage2.step1')
            runner.run('stage2.step1')
            self.assertEqual(execute.call_count, 2)

    def test_different_report_options_run_a_new_analysis(self):
        with patch('notebook_entry.workflow.run_task', side_effect=[
                self.completed('full.refit', ['report.rebuild']), self.completed('report.rebuild')]) as execute:
            runner = self.runner()
            runner.run('full.refit', with_raw_replay=True)
            runner.run('report.rebuild', recompute_region=True)
            self.assertEqual(execute.call_count, 2)

    def test_partial_suite_does_not_count_as_a_whole_phase(self):
        partial = self.completed('full.refit', ['stage1.baselines'])
        partial['all_completed_experiments_selected'] = False
        with patch('notebook_entry.workflow.run_task', side_effect=[
                partial, self.completed('stage2.all', ['stage2.step1'])]) as execute:
            runner = self.runner()
            runner.run('full.refit', tasks=['stage1.baselines'])
            runner.run('stage2.all')
            self.assertEqual(execute.call_count, 2)

    def test_actual_notebook_order_does_not_repeat_completed_model_calls(self):
        from reproduction.full import task_plan

        plan = task_plan()
        children = ['data.raw_cleaning'] + plan['tasks'] + plan['followup_tasks']
        notebook = json.loads((Path(__file__).resolve().parents[1] / 'run_experiments.ipynb').read_text())

        def fake_execute(task, **options):
            return self.completed(task, children if task == 'full.refit' else ())

        with patch('notebook_entry.workflow.run_task', side_effect=fake_execute) as execute:
            runner = self.runner()
            for cell in notebook['cells']:
                if cell['cell_type'] != 'code':
                    continue
                for call in ast.walk(ast.parse(''.join(cell['source']))):
                    if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                            and isinstance(call.func.value, ast.Name)
                            and call.func.value.id == 'notebook' and call.func.attr == 'run'):
                        options = {item.arg: [[-78.0, 33.0]] if item.arg == 'origins'
                                   else ast.literal_eval(item.value) for item in call.keywords}
                        runner.run(ast.literal_eval(call.args[0]), **options)
            self.assertEqual([call.args[0] for call in execute.call_args_list],
                             ['full.refit', 'data.inspect', 'predict.final_mdn22', 'results.recover'])


if __name__ == '__main__':
    unittest.main()
