"""Evaluate the frozen five-neighbor baseline on deterministic held-out families.

Run: python scripts/evaluate_levels.py
No labels are fitted or tuned; no bank or core checker file is modified.
"""
from __future__ import annotations
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from levels.guesser import LevelGuesser,prepare
from scripts.audit_bank import load_bank


def evaluate(bank,folds=5):
    references,excluded=prepare(bank)
    fold_for=lambda r:int(r.family[:16],16)%folds
    rows=[]
    for fold in range(folds):
        train=[r for r in references if fold_for(r)!=fold]
        test=[r for r in references if fold_for(r)==fold]
        assert not ({r.family for r in train}&{r.family for r in test})
        guesser=LevelGuesser(train)
        for r in test:
            result=guesser.estimate(r.topic,r.statement,r.key_latex)
            votes=Counter(item.level for item in train if item.topic==r.topic)
            baseline=min(votes,key=lambda level:(-votes[level],level)) if votes else None
            predicted=result['estimated_level']
            rows.append({'topic':r.topic,'id':r.problem_id,'family':r.family,'fold':fold,'true_level':r.level,
                         'predicted_level':predicted,'status':result['status'],'correct':predicted==r.level,
                         'baseline_level':baseline,'baseline_correct':baseline==r.level,
                         'neighbors':result['neighbors']})
    answered=[r for r in rows if r['predicted_level'] is not None]
    correct=sum(r['correct'] for r in rows)
    confusion=[[sum(r['true_level']==truth and r['predicted_level']==pred for r in rows) for pred in (1,2,3,4)] for truth in (1,2,3,4)]
    total=len(rows)
    topics=[]
    for topic in sorted({r['topic'] for r in rows}):
        part=[r for r in rows if r['topic']==topic];n_answer=sum(r['predicted_level'] is not None for r in part)
        topics.append({'topic':topic,'tested':len(part),'predicted':n_answer,'correct':sum(r['correct'] for r in part),'accuracy_all':sum(r['correct'] for r in part)/len(part)})
    return {'method':'Frozen source-structure 5-neighbor baseline; 5-fold number-masked-statement-family holdout; same-topic neighbors; strict 3/5 majority; cutoff-distance ties abstain.',
            'limitations':['Source tokens and delimiter nesting are proxies, not semantic expression ASTs required by the final plan.','Eligibility reuses heuristic audit only; per-topic task/answer-type adapters are not implemented.','Same-family variants are held together, but undetected mathematical equivalents may still cross folds.','Targets are one tutor’s bank ratings, not independent ground truth.','No accuracy claim is made for new AI-generated problems.','This module is not wired into core.entry or drafting; bank eligibility/checker behavior is unchanged.'],
            'summary':{'bank_rows':len(bank),'feature_supported':total,'feature_topics':len(topics),'excluded_rows':len(excluded),'predicted':len(answered),'abstained':total-len(answered),'correct':correct,
                       'coverage':len(answered)/total if total else None,'accuracy_all':correct/total if total else None,
                       'accuracy_when_predicted':correct/len(answered) if answered else None,
                       'within_one_when_predicted':sum(abs(r['true_level']-r['predicted_level'])<=1 for r in answered)/len(answered) if answered else None,
                       'majority_baseline_accuracy_all':sum(r['baseline_correct'] for r in rows)/total if total else None},
            'abstention_reasons':dict(Counter(r['status'] for r in rows if r['predicted_level'] is None)),
            'confusion_matrix':{'row_true_levels':[1,2,3,4],'column_predicted_levels':[1,2,3,4],'counts':confusion,'note':'Abstentions are reported separately, not hidden in accuracy_all.'},
            'per_topic':topics,'excluded':excluded,'predictions':rows}


def main():
    path=ROOT/'docs/verified_problems.json';report=evaluate(load_bank(path))
    report['bank_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    out=ROOT/'build/level_guesser';out.mkdir(parents=True,exist_ok=True)
    (out/'evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
    fields=['topic','id','fold','true_level','predicted_level','status','correct','baseline_level','baseline_correct']
    with (out/'predictions.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(report['predictions'])
    print(json.dumps(report['summary'],indent=2));print('Results:',out)

if __name__=='__main__':main()
