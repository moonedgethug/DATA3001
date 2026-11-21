"""Repair summary indexing without changing or rerunning any saved forecast/score."""
import io
import json
import sys
import traceback
import numpy as np
import pandas as pd
from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_json
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_formal_io as fio
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_formal_analysis as old
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_formal_analysis_v2 as corrected


class ReuseIdenticalOutputs:
    def __init__(self,paths):self.paths=paths;self.reused=[]
    def publish(self,path,writer):
        if path.exists():
            buffer=io.BytesIO();writer(buffer)
            assert path.read_bytes()==buffer.getvalue(),str(path)
            self.reused.append(str(path.relative_to(fio.ROOT)))
        else:self.paths.publish(path,writer)


def main(name):
    paths,run,cfg,approval,guard,budget=fio.context(name,'formal');completed=False
    try:
        source_dir=fio.ROOT/'src/data3001/modelling/baselines'
        sources=[source_dir/'seasonal_exact_position_s4_e9_formal_analysis_v2.py',source_dir/'seasonal_exact_position_s4_e9_formal_aggregate_resume.py']
        for p in sources:paths.publish(run['provenance']/'sources'/p.name,lambda f,p=p:f.write(p.read_bytes()))
        values=pd.Series([30.,10.,20.],index=[3,8,20]);weights=np.array([.2,.5,.3])
        reproduced=False
        try:old.weighted_quantile(values,weights,.5)
        except KeyError:reproduced=True
        assert reproduced
        for q,expected in [(.1,10.),(.5,10.),(.9,30.)]:assert corrected.weighted_quantile(values,weights,q)==expected
        cases_path=run['results']/'case_scores.parquet';before=file_sha256(cases_path);cases=pd.read_parquet(cases_path)
        assert len(cases)==33971*4 and cases.id.nunique()==45
        adapter=ReuseIdenticalOutputs(paths);corrected.analyze(adapter,run,cases)
        assert file_sha256(cases_path)==before
        summary=pd.read_csv(run['results']/'summary.csv').set_index('model')
        for name,g in cases.groupby('model'):
            pairs=sorted(zip(g.area90_km2.to_numpy(),g.weight.to_numpy()),key=lambda item:item[0])
            for q in [.1,.5,.9]:
                threshold=q*sum(w for _,w in pairs);cumulative=0.
                for value,w in pairs:
                    cumulative+=w
                    if cumulative>=threshold:break
                assert value==summary.loc[name,f'area_q{int(100*q)}']
        save_json(paths,run['provenance']/'aggregation_recovery.json',dict(
            cause='numpy.argsort preserved a pandas Series index; quantile lookup interpreted a position as an index label.',
            fix='Convert values to a NumPy array before sorting. No other mathematical change.',
            old_failure_reproduced=True,gapped_index_fixtures_passed=True,all_reported_area_quantiles_independently_verified=True,
            existing_summaries_byte_identical=adapter.reused,case_score_sha256_unchanged=before,
            source_sha256=fio.hashes(sources),all_cases_retained=True,forecasts_or_scores_rerun=False,
            model_or_weight_change=False,final_test_access=False))
        budget.check(storage=True);completed=True
        print(summary[['energy_km','h90','area90_km2']].to_string(),flush=True)
    except BaseException as error:
        save_json(paths,run['provenance']/'aggregate_resume_failure.json',dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
        raise
    finally:budget.finish('aggregate_resume',completed)


if __name__=='__main__':main(sys.argv[1])
