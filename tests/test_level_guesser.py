"""Behavior tests: abstention, no requested-label leakage, and grouped holdout."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from levels.guesser import LevelGuesser,Reference,features,family_key,prepare
from scripts.evaluate_levels import evaluate


def refs(labels,topic='topic'):
    return [Reference(topic,str(i),level,f'Find $x+{i+1}$.','1',(float(i+3),1.,0.,1.),f'family-{i}') for i,level in enumerate(labels)]


def test_strict_majority_and_evidence():
    result=LevelGuesser(refs([3,3,3,2,1,4])).estimate('topic','Find $x$.','1')
    assert result['estimated_level']==3
    assert len(result['neighbors'])==5
    assert result['votes']['3']==3


def test_two_two_one_is_not_a_majority():
    result=LevelGuesser(refs([1,1,2,2,3,4])).estimate('topic','Find $x$.','1')
    assert result['estimated_level'] is None
    assert result['status']=='no_majority'


def test_unknown_topic_never_borrows_another_topic():
    result=LevelGuesser(refs([1]*6)).estimate('other','Find $x$.','1')
    assert result['status']=='insufficient_neighbors'


def test_requested_level_does_not_choose_neighbors_or_force_the_prediction():
    guesser=LevelGuesser(refs([3]*6+[2]*6))
    accepted=guesser.check_requested_level('topic','Find $x$.','1',3)
    mismatch=guesser.check_requested_level('topic','Find $x$.','1',2)
    assert accepted['estimated_level']==mismatch['estimated_level']==3
    assert accepted['passes_requested_level'] is True
    assert mismatch['passes_requested_level'] is False
    assert accepted['neighbors']==mismatch['neighbors']


def test_requested_level_needs_five_reference_rows():
    result=LevelGuesser(refs([1]*8+[3]*4)).check_requested_level('topic','Find $x$.','1',3)
    assert result['status']=='insufficient_requested_level_pool'
    assert result['passes_requested_level'] is False


def test_equal_distance_at_cutoff_abstains_instead_of_using_id_order():
    references=refs([1]*6)
    references=[Reference(r.topic,r.problem_id,r.level,r.statement,r.key_latex,(1.,0.,0.,1.),r.family) for r in references]
    result=LevelGuesser(references).estimate('topic','Find $x$.','1')
    assert result['status']=='neighbor_boundary_tie'


def test_self_and_number_variants_are_excluded():
    group=family_key('Find $x+99$.')
    references=[Reference(r.topic,r.problem_id,r.level,r.statement,r.key_latex,r.vector,group) for r in refs([1]*6)]
    assert LevelGuesser(references).estimate('topic','Find $x+5$.','1')['status']=='insufficient_neighbors'


def test_invalid_input_abstains_without_running_math_text():
    result=LevelGuesser([]).estimate('topic','Find $'+ '(' * 41+'x'+')'*41+'$.','1')
    assert result['status']=='unsupported_input'


def test_bank_level_five_is_never_a_reference():
    p={'topic':'t','id':'1','level':5,'statement':'Find $x$.','answer':{'latex':'1'}}
    references,excluded=prepare([p])
    assert not references and excluded[0]['reason']=='level_5'


def test_evaluation_keeps_a_family_in_one_fold_and_counts_abstentions():
    bank=[{'topic':'t','id':str(i),'level':1+i%4,'statement':f'Find $x+{i}$.','answer':{'latex':'1'}} for i in range(12)]
    report=evaluate(bank)
    assert len({r['fold'] for r in report['predictions']})==1
    assert report['summary']['predicted']==0
    assert report['summary']['accuracy_all']==0
    assert report['summary']['accuracy_when_predicted'] is None
