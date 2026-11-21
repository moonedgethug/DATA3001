"""Compatibility entry; implementation: data3001.modelling.baselines.run_neighbourhood."""
if __name__ == "__main__":
    from runpy import run_module
    run_module("data3001.modelling.baselines.run_neighbourhood", run_name="__main__")
else:
    from importlib import import_module
    import sys
    sys.modules[__name__] = import_module("data3001.modelling.baselines.run_neighbourhood")
