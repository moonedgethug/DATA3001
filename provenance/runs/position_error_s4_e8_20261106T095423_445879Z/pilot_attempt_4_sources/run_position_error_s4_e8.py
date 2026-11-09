"""Stage-separated E8 execution; full work requires a passing pilot receipt."""
import argparse
import traceback

from data3001.modelling.baselines import position_error_s4_e8_inputs as inputs
from data3001.modelling.baselines import position_error_s4_e8_pipeline as pipeline


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','pilot']);p.add_argument('--run')
    args=p.parse_args()
    if args.action=='prepare':inputs.prepare();return
    paths,run,cfg,approval,guard=inputs.context(args.run)
    try:
        if args.action=='pilot':pipeline.pilot(paths,run,cfg,approval)
    except Exception:
        traceback.print_exc();raise

if __name__=='__main__':main()
