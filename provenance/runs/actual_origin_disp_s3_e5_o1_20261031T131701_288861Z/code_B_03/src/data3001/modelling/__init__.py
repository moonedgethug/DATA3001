"""Model families and shared services. Flat historical imports remain supported.

New code imports common, baselines, markov_models or continuous_models.
The package-local compatibility path contains forwarding modules only;
it neither edits sys.path nor imports optional neural dependencies.
"""
from pathlib import Path

__path__.append(str(Path(__file__).with_name("_compat")))
