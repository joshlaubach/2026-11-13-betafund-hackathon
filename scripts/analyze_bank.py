"""Reproducible, read-only analysis of Echo's bank. No LLM calls.

Run from the repository root: python scripts/analyze_bank.py
Outputs are written to build/bank_analysis (never into the source bank).
The existing audit is the authority for eligibility; this script adds coverage,
metadata checks, duplicate candidates, and a power-rule negative-test dataset.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_bank import build_report, classify, load_bank, parse_level

SOURCE_COMMIT = "bc58c8aef0daf55e566176436895ee707197e7bf"
LEVELS = (1, 2, 3, 4)
MIN_POOL = 3  # The product asks for three problems; not a pedagogical quality score.


def normalize(text: str) -> str:
    """Conservative text normalization; not mathematical equivalence."""
    return " ".join(text.split())


def reference(problem: dict) -> str:
    return f"{problem['topic']}::{problem['id']}"


def structure_template(statement: str) -> str:
    """Number-masked text. Shared templates are expected, not proven duplicates."""
    return re.sub(r"(?<![A-Za-z])\d+(?:\.\d+)?", "<number>", normalize(statement))


def analyze(bank: list[dict]) -> dict:
    audit = build_report(bank)
    eligible = [p for p in bank if classify(p) is None]
    topic_map = defaultdict(list)
    for p in bank:
        topic_map[p['topic']].append(p)
    rows, gaps = [], []
    for topic, problems in sorted(topic_map.items()):
        raw_counts = Counter(parse_level(p) for p in problems if parse_level(p) in LEVELS)
        counts = Counter(parse_level(p) for p in problems if classify(p) is None)
        row = {'topic': topic, 'title': problems[0].get('topic_title', topic),
               'course': problems[0].get('course', ''), 'unit': problems[0].get('unit', ''),
               'total': len(problems), 'level_5': sum(parse_level(p) == 5 for p in problems),
               'eligible': sum(counts.values()), 'excluded_1_4': sum(raw_counts.values()) - sum(counts.values()),
               **{f'level_{level}': counts[level] for level in LEVELS}}
        row['all_levels_have_three'] = all(counts[level] >= MIN_POOL for level in LEVELS)
        rows.append(row)
        for level in LEVELS:
            if counts[level] < MIN_POOL:
                gaps.append({'topic': topic, 'title': row['title'], 'level': level,
                             'eligible_count': counts[level], 'gap_to_three': max(0, MIN_POOL-counts[level]),
                             'status': 'empty' if not counts[level] else 'fewer_than_three'})
    ids, topic_ids, statements, templates = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for p in bank:
        ids[str(p['id'])].append(p)
        topic_ids[(p['topic'], str(p['id']))].append(p)
    for p in eligible:
        statements[normalize(p['statement'])].append(p)
        templates[(p['topic'], structure_template(p['statement']))].append(p)
    duplicate_groups = []
    for statement, group in sorted(statements.items()):
        if len(group) < 2:
            continue
        # Different written keys require review, not an automatic accusation of error.
        keys = {normalize(str((p.get('answer') or {}).get('latex', ''))) for p in group}
        duplicate_groups.append({'statement': statement, 'count': len(group),
                                 'references': [reference(p) for p in group],
                                 'topics': sorted({p['topic'] for p in group}),
                                 'levels': sorted({parse_level(p) for p in group}),
                                 'written_answers': sorted(keys), 'different_written_answers': len(keys) > 1})
    template_groups = []
    for (topic, template), group in sorted(templates.items()):
        distinct = {normalize(p['statement']) for p in group}
        if len(distinct) < 2:
            continue
        template_groups.append({'topic': topic, 'template': template, 'count': len(group),
                                'distinct_statements': len(distinct),
                                'references': [reference(p) for p in group]})
    template_groups.sort(key=lambda g: (-g['count'], g['topic'], g['template']))
    collisions = [{'id': key, 'count': len(group), 'references': [reference(p) for p in group]}
                  for key, group in sorted(ids.items()) if len(group) > 1]
    repeated_keys = [{'topic': key[0], 'id': key[1], 'count': len(group)}
                     for key, group in sorted(topic_ids.items()) if len(group) > 1]
    metadata = []
    for p in bank:
        answer = p.get('answer') or {}
        reasons = []
        if not str(answer.get('latex') or '').strip(): reasons.append('missing_answer_latex')
        if not answer.get('type'): reasons.append('missing_answer_type')
        if not p.get('steps'): reasons.append('missing_steps')
        if not answer.get('sympy'): reasons.append('missing_sympy_string')
        if reasons:
            metadata.append({'reference': reference(p), 'level': parse_level(p),
                             'answer_type': answer.get('type'), 'reasons': reasons})
    eligible_id_rows = {(p['topic'], str(p['id']), parse_level(p)) for p in eligible}
    audit_id_rows = {(p['topic'], str(p['id']), p['level']) for p in audit['eligible']}
    if eligible_id_rows != audit_id_rows:
        raise ValueError('Eligibility does not agree with the existing audit')
    return {
        'methodology': {
            'scope': 'Coverage, text duplicate candidates and metadata; not a mathematical audit of all answers.',
            'eligibility': 'Exactly scripts.audit_bank.classify; heuristic self-containment checks, not complete correctness verification.',
            'three_problem_threshold': 'At least three eligible rows at the requested topic and level; distinct mathematical tasks and confirmed-answer-type matching are not guaranteed.',
            'exact_duplicates': 'Whitespace-normalized statement text across eligible levels 1–4; not symbolic equivalence.',
            'template_candidates': 'Same-topic statements equal after masking numbers; intentional practice variants are common. Manual review only.',
            'missing_sympy': 'Informational. Enum answers can legitimately omit a symbolic expression.',
            'difficulty': 'Existing ratings by one tutor. No independent difficulty validation performed.'},
        'summary': {'total': len(bank), 'topics': len(topic_map), 'in_scope_1_4': audit['audited_count'],
                    'level_5_out_of_scope': audit['level_5_count'], 'eligible': audit['eligible_count'],
                    'excluded': len(audit['excluded']), 'eligible_topics': sum(r['eligible'] > 0 for r in rows),
                    'topics_with_three_at_every_level': sum(r['all_levels_have_three'] for r in rows),
                    'empty_topic_level_cells': sum(g['eligible_count'] == 0 for g in gaps),
                    'thin_topic_level_cells': sum(0 < g['eligible_count'] < 3 for g in gaps),
                    'exact_statement_groups': len(duplicate_groups),
                    'exact_statement_rows': sum(g['count'] for g in duplicate_groups),
                    'same_topic_repeated_statement_groups': sum(len(g['topics']) == 1 for g in duplicate_groups),
                    'cross_topic_repeated_statement_groups': sum(len(g['topics']) > 1 for g in duplicate_groups),
                    'different_written_answer_groups': sum(g['different_written_answers'] for g in duplicate_groups),
                    'exact_statement_excess_rows': sum(g['count'] - 1 for g in duplicate_groups),
                    'number_masked_template_groups': len(template_groups),
                    'reused_id_groups': len(collisions),
                    'rows_with_reused_id': sum(c['count'] for c in collisions),
                    'reused_id_excess_rows': sum(c['count'] - 1 for c in collisions),
                    'duplicate_topic_id_keys': len(repeated_keys)},
        'eligible_by_level': audit['eligible_by_level'],
        'all_by_level': dict(sorted(Counter(str(parse_level(p)) for p in bank).items())),
        'all_answer_types': dict(sorted(Counter((p.get('answer') or {}).get('type', 'missing') for p in bank).items())),
        'eligible_answer_types': dict(sorted(Counter((p.get('answer') or {}).get('type', 'missing') for p in eligible).items())),
        'excluded_by_reason': audit['excluded_by_reason'],
        'topics': rows, 'coverage_gaps': gaps, 'excluded': audit['excluded'],
        'exact_statement_groups': duplicate_groups, 'template_candidates': template_groups,
        'id_collisions': collisions, 'duplicate_topic_id_keys': repeated_keys, 'metadata_findings': metadata,
    }


def negative_cases(bank: list[dict]) -> dict:
    """Use the existing checker/corruptor on the supported power_rule subset only.

    This is consistency testing against bank keys, not independent proof.
    Zero keys are skipped by the existing corruptor; do not relabel them wrong.
    """
    from core.corrupt import CORRUPTION_KINDS, corrupt_key
    from core.derivative_checker import check_derivative, parse_derivative_statement
    names = {0: 'add_one', 1: 'double', 2: 'negate'}
    cases, positives, skipped = [], [], []
    for p in bank:
        if classify(p) is not None or p['topic'] != 'power_rule':
            continue
        parsed = parse_derivative_statement(p['statement'])
        if parsed is None:
            skipped.append({'reference': reference(p), 'reason': 'unrecognized_statement'})
            continue
        key = (p.get('answer') or {}).get('latex', '')
        positive = check_derivative(parsed['function_latex'], key, parsed['at'])
        positives.append({'reference': reference(p), 'accepted': positive['ok'], 'reason': positive['reason']})
        if not positive['ok']:
            skipped.append({'reference': reference(p), 'reason': 'bank_key_not_accepted; no negative claim made'})
            continue
        for kind in CORRUPTION_KINDS:
            wrong = corrupt_key(key, kind)
            if wrong is None:
                skipped.append({'reference': reference(p), 'reason': f'{names[kind]}: existing corruptor returned no case'})
                continue
            verdict = check_derivative(parsed['function_latex'], wrong, parsed['at'])
            cases.append({'topic': p['topic'], 'id': str(p['id']), 'level': parse_level(p),
                          'statement': p['statement'], 'correct_key': key, 'mutation': names[kind],
                          'wrong_key': wrong, 'expected': 'wrong_key', 'observed': verdict['outcome'],
                          'detected': verdict['outcome'] == 'wrong_key', 'reason': verdict['reason']})
    return {'scope': 'Eligible power_rule only. Three existing mutations; not all error types or all calculus topics.',
            'positive_count': len(positives), 'positive_accepted': sum(p['accepted'] for p in positives),
            'case_count': len(cases), 'detected': sum(c['detected'] for c in cases),
            'positives': positives, 'cases': cases, 'skipped': skipped}


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    # JSON inside a CSV cell preserves list structure. Prevent formula execution on opening in Excel.
    def cell(value):
        if isinstance(value, (list, dict)): return json.dumps(value, ensure_ascii=False)
        if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')): return "'" + value
        return value
    with path.open('w', encoding='utf-8-sig', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows({k: cell(v) for k, v in row.items()} for row in rows)


def save(report: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    tables = {
        'topic_coverage': ('topics', ['topic', 'title', 'course', 'unit', 'total', 'level_5', 'eligible', 'excluded_1_4', 'level_1', 'level_2', 'level_3', 'level_4', 'all_levels_have_three']),
        'coverage_gaps': ('coverage_gaps', ['topic', 'title', 'level', 'eligible_count', 'gap_to_three', 'status']),
        'excluded_problems': ('excluded', ['topic', 'id', 'level', 'reason']),
        'exact_statement_groups': ('exact_statement_groups', ['statement', 'count', 'references', 'topics', 'levels', 'written_answers', 'different_written_answers']),
        'template_review_candidates': ('template_candidates', ['topic', 'template', 'count', 'distinct_statements', 'references']),
        'id_collisions': ('id_collisions', ['id', 'count', 'references']),
        'metadata_findings': ('metadata_findings', ['reference', 'level', 'answer_type', 'reasons']),
    }
    for filename, (key, fields) in tables.items(): write_csv(out/(filename+'.csv'), report[key], fields)
    if 'negative_tests' in report:
        write_csv(out/'negative_test_cases.csv', report['negative_tests']['cases'],
                  ['topic','id','level','statement','correct_key','mutation','wrong_key','expected','observed','detected','reason'])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--bank', type=Path, default=ROOT/'docs/verified_problems.json')
    parser.add_argument('--out', type=Path, default=ROOT/'build/bank_analysis')
    parser.add_argument('--skip-negative-tests', action='store_true', help='Coverage and data checks only; standard library only')
    args = parser.parse_args(argv)
    try:
        # Refuse any output path that could replace the source data.
        if args.out.resolve() == args.bank.resolve() or args.bank.resolve().is_relative_to(args.out.resolve()):
            raise ValueError('Choose an output folder separate from the source bank')
        raw = args.bank.read_bytes()
        bank = load_bank(args.bank)
        report = analyze(bank)
        report['source'] = {'file': 'docs/verified_problems.json' if args.bank.resolve() == (ROOT/'docs/verified_problems.json').resolve() else args.bank.name,
                            'sha256': hashlib.sha256(raw).hexdigest(),
                            'snapshot_commit': SOURCE_COMMIT if args.bank.resolve() == (ROOT/'docs/verified_problems.json').resolve() else None,
                            'snapshot_note': 'Imported from this GitHub commit; SHA-256 identifies the actual bytes analyzed. Later local edits are not guaranteed to match that commit.'}
        if not args.skip_negative_tests: report['negative_tests'] = negative_cases(bank)
        save(report, args.out)
    except (OSError, ValueError, KeyError) as error:
        print(f'analyze_bank: {error}', file=sys.stderr)
        return 1
    s = report['summary']
    print(f"Bank: {s['total']} rows / {s['topics']} topics")
    print(f"Levels 1–4: {s['in_scope_1_4']}; eligible {s['eligible']}; excluded {s['excluded']}; level 5 out of scope {s['level_5_out_of_scope']}")
    print(f"Topics with eligible rows: {s['eligible_topics']}; with >=3 at all four levels: {s['topics_with_three_at_every_level']}")
    print(f"Topic × level cells: {s['empty_topic_level_cells']} empty, {s['thin_topic_level_cells']} with 1–2 rows")
    print(f"Exact repeated-statement groups: {s['exact_statement_groups']} (review, not automatic deletion)")
    if 'negative_tests' in report:
        n=report['negative_tests'];print(f"Power-rule baseline keys accepted: {n['positive_accepted']}/{n['positive_count']}; deliberately wrong cases caught: {n['detected']}/{n['case_count']}")
    print(f'Results: {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
