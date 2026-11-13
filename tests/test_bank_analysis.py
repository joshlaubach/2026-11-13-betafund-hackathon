"""Coverage semantics and read-only behavior for the teammate's analysis."""
import copy
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.analyze_bank import analyze, negative_cases, save, write_csv


def problem(topic='a', problem_id='1', level=1, statement='Evaluate $1+1$.', key='2'):
    return {'topic':topic,'id':problem_id,'level':level,'statement':statement,
            'topic_title':topic,'course':'calc_i','unit':'unit',
            'answer':{'type':'numeric','latex':key,'sympy':key},'steps':['Add.']}


def test_all_four_levels_include_zero_cells_and_level_five_is_separate():
    report=analyze([problem(),problem(problem_id='2',level=5)])
    assert report['summary']['in_scope_1_4']==1
    assert report['summary']['level_5_out_of_scope']==1
    assert report['summary']['empty_topic_level_cells']==3
    assert report['summary']['thin_topic_level_cells']==1
    assert report['topics'][0]['level_4']==0


def test_ids_are_scoped_by_topic_not_globally_unique():
    report=analyze([problem('a'),problem('b')])
    assert report['summary']['reused_id_groups']==1
    assert report['summary']['rows_with_reused_id']==2
    assert report['summary']['duplicate_topic_id_keys']==0
    assert report['exact_statement_groups'][0]['references']==['a::1','b::1']


def test_duplicate_topic_id_is_reported():
    assert analyze([problem(),problem()])['summary']['duplicate_topic_id_keys']==1


def test_numeric_variants_are_review_candidates_not_exact_duplicates():
    report=analyze([problem(statement='Find $x^2$.',problem_id='1'),problem(statement='Find $x^3$.',problem_id='2')])
    assert report['summary']['exact_statement_groups']==0
    assert len(report['template_candidates'])==1


def test_excluded_figures_never_count_toward_available_pool():
    report=analyze([problem(statement='Use the figure below.')])
    assert report['summary']['eligible']==0
    assert report['summary']['eligible_topics']==0
    assert report['summary']['empty_topic_level_cells']==4


def test_analysis_preserves_bank_data():
    bank=[problem(),problem(level=5)]
    before=copy.deepcopy(bank)
    analyze(bank)
    assert bank==before


def test_three_row_threshold_does_not_claim_distinctness():
    report=analyze([problem(problem_id=str(i),level=l) for l in range(1,5) for i in range(3)])
    assert report['summary']['topics_with_three_at_every_level']==1
    assert report['summary']['exact_statement_groups']==1
    assert 'not guaranteed' in report['methodology']['three_problem_threshold']


def test_enum_missing_sympy_is_informational():
    p=problem();p['answer']={'type':'enum','latex':r'\text{diverges}'}
    report=analyze([p])
    assert report['summary']['eligible']==1
    assert report['metadata_findings'][0]['reasons']==['missing_sympy_string']


def test_negative_cases_use_actual_checker_and_skip_unverified_positives():
    p=problem('power_rule',statement="Find $f'(x)$ for $f(x) = x^{2}$.",key='2x')
    report=negative_cases([p])
    assert report['positive_accepted']==1
    assert report['case_count']==3
    assert report['detected']==3
    p['answer']['latex']='100'
    bad=negative_cases([p])
    assert bad['positive_accepted']==0
    assert bad['case_count']==0


def test_csv_preserves_lists_and_does_not_execute_formulas(tmp_path):
    path=tmp_path/'rows.csv';write_csv(path,[{'title':'=SUM(1,2)','refs':['a::1','b::1']}],['title','refs'])
    with path.open(encoding='utf-8-sig',newline='') as f: row=next(csv.DictReader(f))
    assert row['title'].startswith("'=")
    assert json.loads(row['refs'])==['a::1','b::1']


def test_cli_matches_existing_audit_and_does_not_modify_source(tmp_path):
    bank=ROOT/'docs/verified_problems.json';before=hashlib.sha256(bank.read_bytes()).hexdigest()
    result=subprocess.run([sys.executable,str(ROOT/'scripts/analyze_bank.py'),'--skip-negative-tests','--out',str(tmp_path/'out')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    report=json.loads((tmp_path/'out/report.json').read_text())
    assert report['summary']['eligible']==3405
    assert report['summary']['excluded']==45
    assert report['source']['sha256']==before
    assert hashlib.sha256(bank.read_bytes()).hexdigest()==before
    assert (tmp_path/'out/topic_coverage.csv').exists()


def test_html_report_embeds_data_without_script_injection(tmp_path):
    import importlib.util
    from html.parser import HTMLParser
    spec=importlib.util.spec_from_file_location('echo_render',ROOT/'analysis/render_report.py')
    renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
    report=analyze([problem()]);report['source']={'sha256':'test','snapshot_commit':None}
    report['topics'][0]['title']='</script><script>alert(1)</script>'
    path=tmp_path/'report.json';path.write_text(json.dumps(report))
    renderer.main(['--report',str(path),'--out',str(path.with_suffix('.html'))])
    html=path.with_suffix('.html').read_text()
    assert '</script><script>alert(1)</script>' not in html
    assert '\\u003c/script\\u003e' in html
    assert '__REPORT_DATA__' not in html
