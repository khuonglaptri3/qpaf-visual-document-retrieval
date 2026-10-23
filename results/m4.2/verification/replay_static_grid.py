"""Independent numeric audit of the SAME frozen grid; never updates fitted weights."""
import argparse
import csv
from datetime import datetime, timezone
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from qpaf.m42.active_primary import _train_records, read, require, sha, verify_files, write_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run',type=Path,required=True)
parser.add_argument('--pin',required=True)
parser.add_argument('--output',type=Path,required=True)
args = parser.parse_args()
verify_files(args.run,args.pin)
shared, fitted = read(args.run/'shared_inputs.json'),read(args.run/'train_fit.json')
splits = {role:(args.run/shared['inputs'][key]['path']).read_text(encoding='utf8').splitlines()
          for role,key in [('train','split_train'),('validation','split_validation'),('test','split_test')]}
records,_ = _train_records(args.run,shared['inputs'],splits)
weights = np.array([(a/10,b/10,(10-a-b)/10) for a in range(11) for b in range(11-a)])
require(len(weights)==66,'Frozen grid differs')
totals = np.zeros(66,dtype=np.float64)
discounts = [1/math.log2(i+2) for i in range(10)]
for record in records:
    raw = np.array(record.raw_scores,dtype=np.float64)
    low,span = raw.min(axis=0),np.ptp(raw,axis=0)
    norm = np.divide(raw-low,span,out=np.zeros_like(raw),where=span>0)
    scores = np.zeros((66,len(raw)),dtype=np.float64)
    # Separate ufuncs preserve the scalar reference's left-to-right arithmetic.
    for c in range(3): scores = scores+weights[:,c,None]*norm[None,:,c]
    # Pages are already ascending; stable sorting implements the frozen tie rule.
    order = np.argsort(-scores,axis=1,kind='stable')[:,:10]
    labels = np.array(record.labels,dtype=np.float64)[order]
    dcg = np.zeros(66,dtype=np.float64)
    for rank in range(labels.shape[1]): dcg = dcg+labels[:,rank]*discounts[rank]
    totals = totals+dcg/sum(discounts[:min(10,record.relevant_total)])
means = totals/len(records)
best,best_value = None,-math.inf
for i,value in enumerate(means):
    if value>best_value+1e-12: best,best_value=i,float(value)
require(weights[best].tolist()==fitted['weights'],'Independent best weights differ')
difference = abs(best_value-fitted['train_ndcg_at_10'])
require(difference<=1e-12,'Independent train objective differs')
require(not args.output.exists(),'Verification output already exists')
args.output.mkdir(parents=True,exist_ok=False)
with (args.output/'train_grid.csv').open('x',encoding='utf8',newline='') as stream:
    writer = csv.writer(stream,lineterminator='\n')
    writer.writerow(['bm25_weight','bge_m3_weight','colqwen25_weight','mean_train_ndcg_at_10','selected'])
    for i,(w,value) in enumerate(zip(weights,means)): writer.writerow([*w,float(value),i==best])
report = {'status':'PASS','verification':'independent_numeric_replay_of_the_same_frozen_grid',
          'checked_utc':datetime.now(timezone.utc).isoformat(),'grid_candidates':66,
          'train_queries':len(records),'weights':weights[best].tolist(),
          'train_ndcg_at_10':best_value,'objective_abs_difference':difference,
          'manifest_sha256':args.pin,'verifier_source_sha256':sha(Path(__file__)),
          'validation_metrics_computed':False,'test_labels_deserialized':False,
          'calibration_output_changed':False,'new_run_attempt_created':False}
write_json(args.output/'verification.json',report)
print(report)
