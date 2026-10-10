"""Generate the tables of paper/main.tex and check the paper against the claim register.

Tables between "% BEGIN GENERATED: name" and "% END GENERATED: name" are written
from committed result bundles. A line "% claims: ID=value ..." states that each value
appears in the text that follows (up to the next blank line or claims line) and
rounds correctly from that row of the claim register. The check also requires every
citation to have a bibliography entry and the reverse, every figure to exist in
paper/figures, and every cross-reference to have a label.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'paper/main.tex'
BIB = ROOT / 'paper/references.bib'
FIGURES = ROOT / 'paper/figures'
REGISTER = ROOT / 'docs/research/claims/claim_evidence.csv'
SCIENTIFIC = ROOT / 'docs/research/results/track_r_scientific_2026-10-10'
REAL = ROOT / 'docs/research/results/real_2026-10-10'
BLOCK = re.compile(r'(% BEGIN GENERATED: (\w+)\n)(.*?)(% END GENERATED: \2)', re.S)
UNESCAPED_PERCENT = re.compile(r'(?<!\\)%')


def number(value: float, places: int = 4) -> str:
    text = f'{value:.{places}f}'
    if text.startswith('-') and float(text) == 0:
        text = text[1:]
    return f'${text}$' if text.startswith('-') else text


def losses_table() -> str:
    losses = pd.read_csv(SCIENTIFIC / 'losses.csv').set_index(['arm', 'condition']).mean_log_loss
    arms = [('singleton', 'History summary'), ('latest_metadata', 'Latest message'), ('grouped', 'Grouped history'),
            ('oracle_lineage_weight', 'Lineage-weighted')]
    columns = ['no_reuse', 'overlap_50', 'overlap_90', 'solution_reissue', 'exact_replay', 'burst_reissue', 'new_information']
    rows = [r'\begin{tabular}{lccccccc}', r'\toprule',
            r'Forecaster & No reuse & 50\% & 90\% & Reissue & Replay & Burst & New inf. \\', r'\midrule']
    for arm, label in arms:
        rows.append(label + ' & ' + ' & '.join(number(losses[arm, c]) for c in columns) + r' \\')
    return '\n'.join(rows + [r'\bottomrule', r'\end{tabular}']) + '\n'


def contrasts_table() -> str:
    d = pd.read_csv(SCIENTIFIC / 'decisions.csv').set_index('id')
    text = {'P1': r'Degradation of the history summary, 90\% overlap',
            'S1': r'History summary minus latest message, 90\% overlap',
            'S5': r'Degradation of the history summary, reissue',
            'S2': r'Grouped minus history summary, degradation',
            'S3': r'Lineage-weighted minus history summary, degradation',
            'S6': r'History summary minus latest message, reissue'}
    decision = {'material_degradation_confirmed': 'material', 'not_material': 'not material', 'inconclusive': 'inconclusive'}
    rows = [r'\begin{tabular}{l>{\raggedright\arraybackslash}p{5.0cm}rrcl}', r'\toprule',
            r' & Contrast & Null & Estimate & 95\% interval & Outcome \\', r'\midrule']
    for cid in ['P1', 'S1', 'S5', 'S2', 'S3', 'S6']:
        r = d.loc[cid]
        null = '--' if pd.isna(r['null']) else number(r['null'], 2)
        if cid == 'P1':
            outcome = decision[r['decision']]
        elif r['role'] == 'exploratory':
            outcome = 'not tested'
        else:
            outcome = 'null rejected' if bool(r['holm_rejected']) else 'not rejected'
        rows.append(f"{cid} & {text[cid]} & {null} & {number(r['mean'])} & [{number(r['lower'])}, {number(r['upper'])}] & {outcome}" + r' \\')
    return '\n'.join(rows + [r'\bottomrule', r'\end{tabular}']) + '\n'


def real_table() -> str:
    d = pd.read_csv(REAL / 'contrasts.csv')
    names = {'R1': 'R1: history summary $-$ latest message', 'R2': 'R2: grouped $-$ history summary',
             'R3': 'R3: latest message $-$ latest risk', 'R4': 'R4: gradient boosting $-$ latest message'}
    rows = [r'\begin{tabular}{>{\raggedright\arraybackslash}p{4.1cm}lrcc}', r'\toprule',
            r' & Split & Mean & Event interval & Mission interval \\', r'\midrule']
    for cid in ['R1', 'R2', 'R3', 'R4']:
        first = True
        for split, label in (('training_oof', 'training'), ('historical_test', 'test')):
            g = d[(d.id == cid) & (d.split == split)]
            if g.empty:
                continue
            r = g.iloc[0]
            rows.append(f"{names[cid] if first else ''} & {label} & {number(r['mean'])} & "
                        f"[{number(r.event_lower)}, {number(r.event_upper)}] & [{number(r.mission_lower)}, {number(r.mission_upper)}]" + r' \\')
            first = False
    return '\n'.join(rows + [r'\bottomrule', r'\end{tabular}']) + '\n'


TABLES = {'losses': losses_table, 'contrasts': contrasts_table, 'real': real_table}


def write_tables(tex: str) -> str:
    def replace(match):
        name = match.group(2)
        if name not in TABLES:
            raise ValueError(f'Unknown generated block {name}')
        return match.group(1) + TABLES[name]() + match.group(4)
    return BLOCK.sub(replace, tex)


def normalise(text: str) -> str:
    return (text.replace('\\%', '%').replace('{,}', ',').replace('\\,', '').replace('$', '')
            .replace('\u2212', '-'))


WORDS = {word: index for index, word in enumerate(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen '
    'seventeen eighteen nineteen twenty'.split())}


def parse_value(text: str) -> tuple[float, float]:
    """Numeric value and the tolerance implied by the number of decimals shown."""
    if text.lower() in WORDS:
        return float(WORDS[text.lower()]), 1e-12
    percent = text.endswith('%')
    core = text.rstrip('%').replace(',', '')
    decimals = len(core.split('.')[1]) if '.' in core else 0
    value = float(core)
    scale = 100 if percent else 1
    return value / scale, 0.5 * 10 ** -decimals / scale + 1e-12


def claim_scopes(tex: str):
    """Yield (line number, [(id, text)], scope text) for every claims comment."""
    lines = tex.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith('% claims:'):
            continue
        pairs = [tuple(token.split('=', 1)) for token in stripped[len('% claims:'):].split() if '=' in token]
        scope = []
        for following in lines[index + 1:]:
            if not following.strip() or following.strip().startswith('% claims:'):
                break
            # A LaTeX comment starts at an unescaped percent sign; "\%" is a literal percent.
            scope.append('' if following.lstrip().startswith('%') else UNESCAPED_PERCENT.split(following, maxsplit=1)[0])
        yield index + 1, pairs, ' '.join(scope)


def check(tex: str, register: pd.DataFrame, figures: Path = FIGURES, bib: str | None = None) -> list[str]:
    problems = []
    for match in BLOCK.finditer(tex):
        name = match.group(2)
        if name not in TABLES:
            problems.append(f'unknown generated block {name}')
        elif match.group(3) != TABLES[name]():
            problems.append(f'generated block {name} is out of date (run --write)')
    values = register.set_index('id')
    for line, pairs, scope in claim_scopes(tex):
        text = normalise(scope)
        for cid, shown in pairs:
            if cid not in values.index:
                problems.append(f'line {line}: {cid} is not in the claim register')
                continue
            expected = values.loc[cid, 'expected']
            if pd.isna(expected):
                problems.append(f'line {line}: {cid} has no regenerated value')
                continue
            value, tolerance = parse_value(shown)
            if not math.isclose(value, expected, abs_tol=tolerance) and abs(value - expected) > tolerance:
                problems.append(f'line {line}: {cid}={shown} does not round from {expected}')
            if shown not in text and not (shown.lower() in WORDS and re.search(rf'{shown}', text, re.I)):
                problems.append(f'line {line}: {shown} ({cid}) is not in the text that follows')
    cited = {key.strip() for group in re.findall(r'\\cite\{([^}]*)\}', tex) for key in group.split(',')}
    items = set(re.findall(r'\\bibitem\{([^}]*)\}', tex))
    problems += [f'citation {key} has no bibliography entry' for key in sorted(cited - items)]
    problems += [f'bibliography entry {key} is never cited' for key in sorted(items - cited)]
    if bib is not None:
        keys = set(re.findall(r'@\w+\{([^,\s]+),', bib))
        problems += [f'references.bib lacks {key}' for key in sorted(items - keys)]
        problems += [f'references.bib has {key}, which main.tex does not' for key in sorted(keys - items)]
    for name in re.findall(r'\\includegraphics(?:\[[^]]*\])?\{([^}]*)\}', tex):
        if not (figures / f'{name}.pdf').exists():
            problems.append(f'figure {name}.pdf is missing from {figures}')
    labels = set(re.findall(r'\\label\{([^}]*)\}', tex))
    for ref in re.findall(r'\\(?:eq)?ref\{([^}]*)\}', tex):
        if ref not in labels:
            problems.append(f'reference {ref} has no label')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paper', type=Path, default=PAPER)
    parser.add_argument('--write', action='store_true', help='regenerate the generated tables in place')
    args = parser.parse_args()
    tex = args.paper.read_text(encoding='utf-8')
    if args.write:
        tex = write_tables(tex)
        args.paper.write_text(tex, encoding='utf-8', newline='\n')
    bib = BIB.read_text(encoding='utf-8') if BIB.exists() else None
    problems = check(tex, pd.read_csv(REGISTER), bib=bib)
    for problem in problems:
        print('PROBLEM', problem)
    claims = sum(len(pairs) for _, pairs, _ in claim_scopes(tex))
    print(f'checked {claims} claimed values, {len(BLOCK.findall(tex))} generated tables; problems: {len(problems)}')
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
