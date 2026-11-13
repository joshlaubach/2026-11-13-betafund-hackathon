"""Render an offline bank-analysis report, in English by default.

Presentation templates are separate from computation. Both languages embed the
same report.json, make no external requests, and preserve the original bank.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TEMPLATE_DIRECTORY = Path(__file__).resolve().parent / 'templates'


def localized_template(language: str) -> str:
    if language not in ('en', 'zh'):
        raise ValueError('Supported languages: en, zh')
    return (TEMPLATE_DIRECTORY / f'report.{language}.html').read_text(encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--report', type=Path, default=Path('build/bank_analysis/report.json'))
    parser.add_argument('--out', type=Path, default=None)
    parser.add_argument('--lang', choices=['en', 'zh'], default='en')
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text(encoding='utf-8'))
    # Prevent embedded data from terminating the inert JSON script element.
    data = json.dumps(report, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    filename = 'Echo_Bank_Analysis_Report.html' if args.lang == 'en' else 'report.html'
    output = args.out or args.report.with_name(filename)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(localized_template(args.lang).replace('__REPORT_DATA__', data), encoding='utf-8')
    print(output.resolve())


if __name__ == '__main__':
    main()
