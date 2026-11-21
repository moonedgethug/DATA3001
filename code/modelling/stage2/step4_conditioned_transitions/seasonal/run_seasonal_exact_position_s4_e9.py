"""Explicit E9 stages; no automatic retry or model substitution."""
import argparse
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_inputs as inputs


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','pilot'])
    parser.add_argument('run',nargs='?');args=parser.parse_args()
    if args.stage=='prepare':inputs.prepare();return
    from data3001.modelling.baselines.seasonal_exact_position_s4_e9_pipeline import pilot
    pilot(*inputs.context(args.run))

if __name__=='__main__':main()
