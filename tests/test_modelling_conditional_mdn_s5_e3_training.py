"""Contract tests use synthetic positions/displacements only; no cohort is loaded."""

import hashlib
import importlib.util
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch
from scipy.special import logsumexp
from scipy.stats import multivariate_normal


MODEL = "data3001.modelling.continuous_models.conditional_mdn_s5_e3"
TRAINING = MODEL + "_training"


def modules():
    # Keep the first RED a meaningful assertion about the missing implementation.
    assert importlib.util.find_spec(MODEL), "The contracted MDN model is not implemented"
    assert importlib.util.find_spec(TRAINING), "The contracted training is not implemented"
    return __import__(MODEL, fromlist=["MDN"]), __import__(TRAINING, fromlist=["train_seed"])


def toy_pairs(n=19):
    rng = np.random.default_rng(507)
    x = rng.normal(size=(n, 2)) + [-75, 35]
    v = rng.normal(size=(n, 2)) * [3, 7] + [10, -20]
    ids = np.arange(n, dtype=np.int64) % 10 + 1
    return x, v, ids


class MDNTrainingTests(unittest.TestCase):
    def test_model_initial_distribution_and_determinism(self):
        model, _ = modules()
        a, b = model.MDN(4, 1234), model.MDN(4, 1234)
        x = torch.tensor([[0., 0.], [3., -4.]], dtype=torch.float64)
        log_pi, mu, cov = a(x)
        self.assertEqual(a.parameter_count, 5912)
        self.assertTrue(all(p.dtype == torch.float64 and p.device.type == "cpu" for p in a.parameters()))
        np.testing.assert_allclose(log_pi.exp().detach(), .25, rtol=0, atol=1e-15)
        np.testing.assert_allclose(cov.detach(), np.broadcast_to(np.eye(2), (2, 4, 2, 2)), atol=1e-15)
        self.assertGreater(float(mu.detach().max()-mu.detach().min()), 0)
        for left, right in zip(a.parameters(), b.parameters()):
            torch.testing.assert_close(left, right, rtol=0, atol=0)

    def test_nll_matches_independent_full_covariance_density_and_tail(self):
        model, _ = modules()
        logits = torch.tensor([[3., -11.], [3., -11.]], dtype=torch.float64, requires_grad=True)
        means = torch.tensor([[[1., -2.], [4., 5.]]] * 2, dtype=torch.float64, requires_grad=True)
        cov = torch.tensor([[[[2., .7], [.7, 1.]], [[.02, .001], [.001, .03]]]] * 2, dtype=torch.float64)
        y = torch.tensor([[.4, -1.], [1000., -1000.]], dtype=torch.float64)
        log_pi = torch.log_softmax(logits, dim=-1)
        got = model.mixture_nll((log_pi, means, cov), y)
        expected = [-logsumexp([log_pi[i, j].item() + multivariate_normal.logpdf(y[i], means[i,j].detach(), cov[i,j]) for j in range(2)]) for i in range(2)]
        np.testing.assert_allclose(got.detach(), expected, rtol=1e-12)
        got.mean().backward()
        self.assertTrue(torch.isfinite(logits.grad).all() and torch.isfinite(means.grad).all())

    def test_scaling_physical_packet_and_rejects_zero_scale(self):
        model, _ = modules()
        x = np.array([[-1., 1.], [1., 5.]])
        y = np.array([[8., 14.], [12., 26.]])
        scaler = model.Standardizer.fit(x, y)
        np.testing.assert_array_equal(scaler.transform_x(x), [[-1,-1],[1,1]])
        np.testing.assert_array_equal(scaler.transform_y(y), [[-1,-1],[1,1]])
        out = (torch.zeros((1,1), dtype=torch.float64), torch.tensor([[[1.,-1.]]], dtype=torch.float64), torch.tensor([[[[1.,.5],[.5,2.]]]], dtype=torch.float64))
        physical = scaler.physical_parameters(out)
        np.testing.assert_array_equal(physical["mu"], [[[12,14]]])
        np.testing.assert_array_equal(physical["cov"], [[[[4,6],[6,72]]]])
        with self.assertRaisesRegex(ValueError, "scale"):
            model.Standardizer.fit(np.ones((3,2)), np.arange(6).reshape(3,2))

    def test_stable_stream_exact_contract_bytes_and_canonical_query(self):
        model, _ = modules()
        raw = b"mdn_s5_e3_v1|init|C_T0|4|20261121||"
        expected = int.from_bytes(hashlib.sha256(raw).digest()[:8], "little")
        self.assertEqual(model.stable_seed("init", "C_T0", 4, 20261121), expected)
        self.assertEqual(model.canonical_query_key(123., 456., 7.), "123|456|7")
        with self.assertRaises(ValueError):
            model.canonical_query_key(123.5, 456, 7)
        self.assertNotEqual(model.stable_seed("init", "C_T0", 4, 20261121), model.stable_seed("shuffle", "C_T0", 4, 20261121))

    def test_whole_id_stop_partition_and_drifter_equal_score(self):
        _, training = modules()
        ids = np.repeat(np.arange(1, 22), np.arange(1, 22))
        optimize, stop = training.partition_ids(ids)
        expected = sorted(range(1,22), key=lambda i:(hashlib.sha256(f"mdn_s5_e3_stop_v1|{i}".encode()).hexdigest(),i))[:3]
        self.assertEqual(set(stop), set(expected))
        self.assertFalse(set(stop) & set(optimize))
        self.assertEqual(training.drifter_equal_nll(np.array([1.,1.,1.,9.]), np.array([2,2,2,3])), 5.)

    def test_raw_best_epoch_and_patience_anchor_are_separate(self):
        _, training = modules()
        tracker = training.EarlyStopping()
        for epoch, value in enumerate([3., 2.99994, 2.99989, 2.99988, 2.99988], 1):
            tracker.update(value, epoch)
        self.assertEqual(tracker.best_epoch, 4)
        self.assertEqual(tracker.bad_epochs, 2)
        for epoch in range(6,34):
            tracker.update(3., epoch)
        self.assertTrue(tracker.should_stop)

    def test_tail_batch_exact_weight_and_resume_preserve_optimizer(self):
        model, training = modules()
        x, v, ids = toy_pairs(19)
        class Pause(Exception):
            pass
        ticks = 0
        def tick():
            nonlocal ticks
            ticks += 1
            if ticks == 2:
                raise Pause()
        # A smaller batch is solely a toy monkeypatch, never a production option.
        with tempfile.TemporaryDirectory() as tmp, patch.object(training, "BATCH_SIZE", 8):
            whole = training.train_fixed_epochs(x,v,ids,2,"toy",20261121,Path(tmp)/"whole",2,purpose="pilot")
            with self.assertRaises(Pause):
                training.train_fixed_epochs(x,v,ids,2,"toy",20261121,Path(tmp)/"resume",2,purpose="pilot",budget_tick=tick)
            resumed = training.train_fixed_epochs(x,v,ids,2,"toy",20261121,Path(tmp)/"resume",2,purpose="pilot")
            self.assertEqual(resumed.history[-1]["pairs_seen"], 19)
            self.assertEqual(resumed.history[-1]["batch_sizes"], [8,8,3])
            for left, right in zip(whole.model.parameters(), resumed.model.parameters()):
                torch.testing.assert_close(left, right, rtol=0, atol=0)
            loaded = training.load_model(resumed.checkpoint_path)
            np.testing.assert_array_equal(loaded.parameters(x[:2])["mu"], resumed.parameters(x[:2])["mu"])
            # Independently reproduce the single-epoch batch loss/optimizer update.
            one = training.train_fixed_epochs(x,v,ids,2,"toy",20261121,Path(tmp)/"one",1,purpose="pilot")
            manual = model.MDN(2, model.stable_seed("init","toy",2,20261121))
            optimizer = training.make_optimizer(manual)
            gen = torch.Generator().manual_seed(model.stable_seed("shuffle","toy",2,20261121))
            order = torch.randperm(19, generator=gen)
            sx = torch.from_numpy(one.standardizer.transform_x(x))
            sy = torch.from_numpy(one.standardizer.transform_y(v))
            for start in range(0,19,8):
                idx = order[start:start+8]
                optimizer.zero_grad(set_to_none=True)
                (model.mixture_nll(manual(sx[idx]), sy[idx]).sum()/8).backward()
                torch.nn.utils.clip_grad_norm_(manual.parameters(),5,error_if_nonfinite=True)
                optimizer.step()
            for left,right in zip(one.model.parameters(),manual.parameters()):
                torch.testing.assert_close(left,right,rtol=0,atol=0)

    def test_checkpoint_rejects_changed_source_and_retains_full_fit_scaler(self):
        _, training = modules()
        x,v,ids = toy_pairs()
        with tempfile.TemporaryDirectory() as tmp:
            result = training.train_fixed_epochs(x,v,ids,1,"toy",20261121,tmp,1,purpose="pilot",identity={"source":"a"})
            np.testing.assert_allclose(result.standardizer.x_mean,x.mean(axis=0))
            with self.assertRaisesRegex(ValueError,"identity"):
                training.train_fixed_epochs(x,v,ids,1,"toy",20261121,tmp,1,purpose="pilot",identity={"source":"b"})
            changed = v.copy(); changed[0,0] += .001
            with self.assertRaisesRegex(ValueError,"identity"):
                training.train_fixed_epochs(x,changed,ids,1,"toy",20261121,tmp,1,purpose="pilot",identity={"source":"a"})

    def test_early_stop_scaler_excludes_stop_ids_and_nonfinite_input_fails(self):
        _, training = modules()
        x,v,ids = toy_pairs(20)
        opt_ids,stop_ids = training.partition_ids(ids)
        mask = np.isin(ids,opt_ids)
        x[~mask] += 100
        with tempfile.TemporaryDirectory() as tmp:
            result = training.train_seed(x,v,ids,1,"toy",20261121,tmp,max_epochs=2)
            np.testing.assert_allclose(result.standardizer.x_mean,x[mask].mean(axis=0))
            self.assertIn(result.best_epoch,(1,2))
            self.assertEqual(len(result.history),2)
            bad = v.copy(); bad[0,0]=np.nan
            with self.assertRaisesRegex(ValueError,"finite"):
                training.train_fixed_epochs(x,bad,ids,1,"toy",20261121,Path(tmp)/"bad",1,purpose="pilot")

    def test_seed_tie_break_cap_gate_and_resumable_prefix(self):
        _, training = modules()
        low = SimpleNamespace(base_seed=20261121,best_nll=2.,best_epoch=470,status="epoch_cap_reached",epochs_completed=500)
        high = SimpleNamespace(base_seed=20261123,best_nll=2.,best_epoch=471,status="epoch_cap_reached",epochs_completed=500)
        self.assertIs(training.select_seed([high,low]),low)
        self.assertFalse(training.requires_cap_pause(low))
        self.assertTrue(training.requires_cap_pause(high))
        x,v,ids=toy_pairs()
        with tempfile.TemporaryDirectory() as tmp:
            prefix=training.train_seed(x,v,ids,1,"toy",20261121,Path(tmp)/"prefix",max_epochs=3,pause_after_epochs=1)
            self.assertEqual(prefix.status,"prefix_paused")
            self.assertEqual(prefix.epochs_completed,1)
            resumed=training.train_seed(x,v,ids,1,"toy",20261121,Path(tmp)/"prefix",max_epochs=3)
            whole=training.train_seed(x,v,ids,1,"toy",20261121,Path(tmp)/"whole",max_epochs=3)
            self.assertEqual(len(resumed.history),3)
            for left,right in zip(resumed.model.parameters(),whole.model.parameters()):
                torch.testing.assert_close(left,right,rtol=0,atol=0)

    def test_budget_interrupt_after_final_epoch_preserves_completion(self):
        _,training=modules()
        x,v,ids=toy_pairs()
        ticks=0
        def tick():
            nonlocal ticks
            ticks+=1
            if ticks==2:
                raise TimeoutError("Synthetic budget pause after final epoch")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(TimeoutError):
                training.train_fixed_epochs(x,v,ids,1,"toy",20261121,tmp,1,purpose="pilot",budget_tick=tick)
            resumed=training.train_fixed_epochs(x,v,ids,1,"toy",20261121,tmp,1,purpose="pilot")
            self.assertEqual(resumed.status,"complete")
            self.assertEqual(len(resumed.history),1)

    def test_nonfinite_aggregate_gradient_norm_is_a_numeric_failure(self):
        _,training=modules()
        x,v,ids=toy_pairs()
        with tempfile.TemporaryDirectory() as tmp:
            # Inject the clipping library's documented nonfinite-norm failure;
            # the model, gradients, checkpoint and recovery path remain real.
            with patch.object(torch.nn.utils,"clip_grad_norm_",side_effect=RuntimeError("The total norm is non-finite")):
                with self.assertRaises(FloatingPointError):
                    training.train_fixed_epochs(x,v,ids,1,"toy",20261121,tmp,1,purpose="pilot")
            with self.assertRaises(FloatingPointError):
                training.train_fixed_epochs(x,v,ids,1,"toy",20261121,tmp,1,purpose="pilot")

    def test_interrupt_inside_optimizer_restores_last_committed_batch(self):
        _,training=modules()
        x,v,ids=toy_pairs()
        make_optimizer=training.make_optimizer
        def interrupting_optimizer(model):
            optimizer=make_optimizer(model)
            step=optimizer.step
            def interrupt(*args,**kwargs):
                step(*args,**kwargs)
                raise InterruptedError("Synthetic interrupt before the batch commit")
            optimizer.step=interrupt
            return optimizer
        with tempfile.TemporaryDirectory() as tmp:
            whole=training.train_fixed_epochs(x,v,ids,1,"toy",20261121,Path(tmp)/"whole",1,purpose="pilot")
            with patch.object(training,"make_optimizer",side_effect=interrupting_optimizer):
                with self.assertRaises(InterruptedError):
                    training.train_fixed_epochs(x,v,ids,1,"toy",20261121,Path(tmp)/"resume",1,purpose="pilot")
            resumed=training.train_fixed_epochs(x,v,ids,1,"toy",20261121,Path(tmp)/"resume",1,purpose="pilot")
            for left,right in zip(whole.model.parameters(),resumed.model.parameters()):
                torch.testing.assert_close(left,right,rtol=0,atol=0)


if __name__ == "__main__":
    unittest.main()
