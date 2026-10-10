"""Scripted paper figures and tables (W02) from committed result bundles.

Reads only `docs/research/results/*` exports plus the simulator's window
definition, so a clone regenerates every figure without local run directories.
Writes PDF and PNG files, short captions and a provenance record with input
hashes. Figures follow paper conventions: no titles inside the plots (captions
in paper/main.tex carry them), embedded fonts, and descriptive file names that
the LaTeX source uses unchanged. Each figure is drawn at its printed size in the
IEEE two-column format (one column, or both for observation_windows), so text
prints at its nominal 7-8 pt. Evidence types stay separate: frozen scientific
(V04), exposed development simulation and exposed retrospective real data never
share an axis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from research.simulation import windows  # noqa: E402

RESULTS = Path('docs/research/results')
SURFACE, INK, INK2, MUTED, GRID, AXIS = '#ffffff', '#0b0b0b', '#52514e', '#8d8a82', '#e6e4dd', '#bdbab0'
# Validated categorical slots (colour-vision safe): orange marks the history summary and reused
# evidence, blue the latest message and new evidence, as on the web findings page.
BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'
# Printed widths in inches of an IEEEtran column (252 pt) and of the full text block (516 pt).
COLUMN, TEXT = 252 / 72.27, 516 / 72.27
CONDITION_ORDER = ['no_reuse', 'overlap_50', 'overlap_90', 'solution_reissue']
CONDITION_LABEL = {'no_reuse': 'No reuse', 'overlap_50': '50% overlap', 'overlap_90': '90% overlap',
                   'solution_reissue': 'Solution\nreissue', 'new_information': 'New\ninformation'}


def style():
    plt.rcParams.update({
        'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Liberation Sans', 'DejaVu Sans'], 'font.size': 8,
        'axes.titlesize': 8, 'axes.labelsize': 8, 'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5,
        'pdf.fonttype': 42, 'ps.fonttype': 42,
        'axes.facecolor': SURFACE, 'figure.facecolor': SURFACE, 'savefig.facecolor': SURFACE,
        'axes.edgecolor': AXIS, 'axes.linewidth': 0.8, 'axes.labelcolor': INK2,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6, 'grid.linestyle': '-',
        'xtick.color': MUTED, 'ytick.color': MUTED, 'xtick.labelcolor': INK2, 'ytick.labelcolor': INK2,
        'legend.frameon': False, 'legend.fontsize': 7, 'lines.linewidth': 1.5, 'lines.solid_capstyle': 'round'})


def read(name: str, inputs: dict) -> pd.DataFrame:
    path = RESULTS / name
    inputs[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pd.read_csv(path)


def save(fig, out: Path, stem: str, written: list):
    for suffix in ('pdf', 'png'):
        target = out / f'{stem}.{suffix}'
        fig.savefig(target, dpi=300, metadata={'CreationDate': None} if suffix == 'pdf' else None)
        written.append(target.name)
    plt.close(fig)


def runs(ids):
    """Consecutive runs of integer IDs as (start, length) pairs for broken_barh."""
    spans, start, previous = [], None, None
    for value in sorted(ids):
        if start is None:
            start = previous = value
        elif value == previous + 1:
            previous = value
        else:
            spans.append((start, previous - start + 1))
            start = previous = value
    if start is not None:
        spans.append((start, previous - start + 1))
    return spans


def fig_windows(out, written):
    """The design, from research.simulation.windows: new and reused observations of each message."""
    conditions = ['no_reuse', 'overlap_50', 'overlap_90', 'solution_reissue', 'new_information']
    fig, axes = plt.subplots(1, len(conditions), figsize=(TEXT, 2.05), sharey=True, layout='constrained')
    for ax, condition in zip(axes, conditions):
        seen: set[int] = set()
        for j, ids in enumerate(w.tolist() for w in windows(condition)):
            y = 5 - j
            ax.broken_barh(runs([i for i in ids if i not in seen]), (y - 0.3, 0.6), facecolors=BLUE, linewidth=0)
            ax.broken_barh(runs([i for i in ids if i in seen]), (y - 0.3, 0.6), facecolors=ORANGE, linewidth=0)
            seen.update(ids)
        name = CONDITION_LABEL[condition].replace('\n', ' ')
        ax.set_title(f'{name}\n{len(seen)} distinct', fontsize=8, color=INK)
        ax.set_xlim(0, 60)
        ax.set_xticks([0, 30, 60])
        ax.grid(axis='y', visible=False)
    axes[0].set_yticks(range(6), [f'm{6 - k}' for k in range(6)])
    fig.legend([Patch(color=BLUE), Patch(color=ORANGE)], ['New to the message', 'Used by an earlier message'],
               loc='outside upper center', ncols=2)
    fig.supxlabel('Observation identity (0–59 are visible to the messages)', fontsize=8, color=INK2)
    save(fig, out, 'observation_windows', written)
    return ('observation_windows', 'Observation windows of the six messages m1-m6 under five conditions, from the simulator.')


def fig_overlap_response(inputs, out, written):
    """Frozen run: mean clipped log loss by reuse condition."""
    losses = read('track_r_scientific_2026-10-10/per_bank_losses.csv', inputs)
    order = list(CONDITION_ORDER)
    fig, ax = plt.subplots(figsize=(COLUMN, 2.35), layout='constrained')
    x = list(range(len(order)))
    series = [('grouped', MUTED, 'Grouped and lineage-weighted history'), ('oracle_lineage_weight', MUTED, None),
              ('latest_metadata', BLUE, 'Latest message'), ('singleton', ORANGE, 'History summary')]
    for arm, color, label in series:
        g = losses[losses.arm == arm].groupby('condition').log_loss
        mean, low, high = g.mean().reindex(order), g.min().reindex(order), g.max().reindex(order)
        context = color == MUTED
        ax.plot(x, mean.to_numpy(), color=color, linewidth=1.0 if context else 1.6, marker='o', markersize=3.5 if context else 5,
                markeredgecolor=SURFACE, markeredgewidth=1.0, label=label, zorder=2 if context else 3)
        if not context:
            ax.vlines(x, low.to_numpy(), high.to_numpy(), color=color, linewidth=0.9, alpha=0.6, zorder=2)
    ax.legend(loc='lower right')
    ax.set_xticks(x, [CONDITION_LABEL[c] for c in order])
    ax.set_ylabel('Mean clipped log loss (nats)')
    ax.set_ylim(0, 0.18)
    save(fig, out, 'overlap_response', written)
    return ('overlap_response', 'Mean clipped log loss by reuse condition in the frozen evaluation.')


def fig_contrasts(inputs, out, written):
    """Frozen run: contrasts with bank-combined intervals, null values and the ten per-bank estimates."""
    d = read('track_r_scientific_2026-10-10/decisions.csv', inputs)
    banks = read('track_r_scientific_2026-10-10/bank_contrasts.csv', inputs)
    labels = {'P1': 'P1 degradation, 90% overlap', 'S5': 'S5 degradation, reissue',
              'S1': 'S1 advantage left, 90% overlap', 'S2': 'S2 grouped minus history',
              'S3': 'S3 lineage minus history', 'S6': 'S6 history minus latest, reissue'}
    order = ['P1', 'S5', 'S1', 'S2', 'S3', 'S6']
    d = d.set_index('id').loc[order]
    fig, ax = plt.subplots(figsize=(COLUMN, 2.45), layout='constrained')
    for i, cid in enumerate(order):
        row = d.loc[cid]
        y = len(order) - 1 - i
        color = MUTED if cid == 'S6' else INK
        per_bank = banks[banks.id == cid]['mean']
        ax.plot(per_bank, [y + 0.25] * len(per_bank), 'o', markersize=2.2, color=MUTED, alpha=0.85, zorder=1)
        ax.hlines(y, row['lower'], row['upper'], color=color, linewidth=1.6)
        ax.plot(row['mean'], y, 'o', color=color, markersize=5.5, markeredgecolor=SURFACE, markeredgewidth=1.0, zorder=3)
        if pd.notna(row['null']):
            ax.plot(row['null'], y, marker='|', color=ORANGE, markersize=11, markeredgewidth=1.8, zorder=2)
    ax.axvline(0, color=AXIS, linewidth=0.8, zorder=0)
    ax.set_yticks(range(len(order)), [labels[c] for c in reversed(order)], fontsize=7)
    ax.set_xlabel('Difference in mean clipped log loss (nats)')
    ax.grid(axis='y', visible=False)
    save(fig, out, 'frozen_contrasts', written)
    return ('frozen_contrasts', 'Frozen contrasts with bank-combined 95% intervals, null values and per-bank estimates.')


def fig_persistence(inputs, out, written):
    """Development: P1 per independent training bank and configuration (exposed, before the freeze)."""
    d = read('sensitivity_2026-10-10/bank_contrasts.csv', inputs)
    d = d[(d.id == 'P1') & (d.training_configuration == d.evaluation_configuration)]
    order = ['iso', 'aniso2', 'aniso8', 'noise2', 'bias']
    names = {'iso': 'Isotropic', 'aniso2': 'Anisotropic\nratio 2', 'aniso8': 'Anisotropic\nratio 8',
             'noise2': 'Doubled\nnoise', 'bias': 'Shared\nbias'}
    fig, ax = plt.subplots(figsize=(COLUMN, 2.3), layout='constrained')
    for i, cfg in enumerate(order):
        g = d[d.training_configuration == cfg].reset_index(drop=True)
        offsets = [(k - (len(g) - 1) / 2) * 0.09 for k in range(len(g))]
        ax.vlines([i + o for o in offsets], g.lower95, g.upper95, color=ORANGE, linewidth=0.9, alpha=0.6)
        ax.plot([i + o for o in offsets], g['mean'], 'o', color=ORANGE, markersize=4.2, markeredgecolor=SURFACE, markeredgewidth=0.8)
    ax.axhline(0.02, color=INK2, linewidth=0.9)
    ax.text(-0.45, 0.0215, 'margin 0.02', fontsize=7, color=INK2, ha='left', va='bottom')
    ax.set_xticks(range(len(order)), [names[c] for c in order], fontsize=7)
    ax.set_ylabel('P1 per training bank (nats)')
    ax.set_ylim(0, 0.1)
    save(fig, out, 'development_banks', written)
    return ('development_banks', 'Development: P1 for each independent training bank by simulator configuration.')


def fig_real_contrasts(inputs, out, written):
    """Exposed retrospective real data: R1-R4 with event and mission-cluster intervals."""
    d = read('real_2026-10-10/contrasts.csv', inputs)
    labels = {'R1': 'R1  history summary\nminus latest message', 'R2': 'R2  grouped minus\nhistory summary',
              'R3': 'R3  latest message\nminus latest risk', 'R4': 'R4  gradient boosting\nminus latest message'}
    fig, axes = plt.subplots(2, 1, figsize=(COLUMN, 3.4), layout='constrained')
    for ax, (split, title) in zip(axes, [('training_oof', 'Training cohort, out of fold'), ('historical_test', 'Historical test split')]):
        g = d[d.split == split].set_index('id')
        for i, cid in enumerate(['R1', 'R2', 'R3', 'R4']):
            y = 3 - i
            if cid not in g.index:
                ax.text(0.03, y, 'not evaluated', fontsize=7, color=MUTED, va='center', transform=ax.get_yaxis_transform())
                continue
            r = g.loc[cid]
            ax.hlines(y + 0.13, r.mission_lower, r.mission_upper, color=MUTED, linewidth=1.3)
            ax.hlines(y - 0.13, r.event_lower, r.event_upper, color=INK, linewidth=1.6)
            ax.plot(r['mean'], y - 0.13, 'o', color=INK, markersize=4.5, markeredgecolor=SURFACE, markeredgewidth=0.8, zorder=3)
        ax.axvline(0, color=AXIS, linewidth=0.8)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5, symmetric=True))
        ax.set_title(title, fontsize=8, color=INK)
        ax.set_yticks(range(4), [labels[c] for c in ['R4', 'R3', 'R2', 'R1']], fontsize=7)
        ax.set_ylim(-0.55, 3.55)
        ax.grid(axis='y', visible=False)
    axes[1].set_xlabel('Difference in mean clipped log loss (nats)')
    fig.legend([Line2D([], [], color=INK, linewidth=1.6), Line2D([], [], color=MUTED, linewidth=1.3)],
               ['Event-level 95% interval', 'Mission-cluster 95% interval'], loc='outside lower center', ncols=2)
    save(fig, out, 'real_contrasts', written)
    return ('real_contrasts', 'Paired contrasts on the exposed Kelvins data with event-level and mission-cluster intervals.')


def fig_frontier(inputs, out, written):
    """Exposed retrospective real data: missed positives against the fraction reviewed (training, out of fold)."""
    f = read('real_2026-10-10/frontiers.csv', inputs)
    m = read('real_2026-10-10/metrics.csv', inputs)
    f = f[f.split == 'training_oof']
    fig, ax = plt.subplots(figsize=(COLUMN, 2.35), layout='constrained')
    series = [('latest', MUTED, 'Latest risk and grouped history'), ('grouped', MUTED, None),
              ('causal_gbm', AQUA, 'Gradient boosting'), ('latest_metadata', BLUE, 'Latest message'),
              ('singleton', ORANGE, 'History summary')]
    for arm, color, label in series:
        g = f[f.arm == arm].sort_values('review_fraction')
        ax.step(g.review_fraction, g.missed, where='post', color=color, linewidth=1.0 if color == MUTED else 1.5, label=label)
        point = m[(m.split == 'training_oof') & (m.arm == arm)].iloc[0]
        if color != MUTED:
            ax.plot(point.reviewed_95 / point.n, point.missed_95, 'o', color=color, markersize=5, markeredgecolor=SURFACE,
                    markeredgewidth=0.8, zorder=3)
    positives = int(m[m.split == 'training_oof'].positives.iloc[0])
    ax.set_xlim(0, 0.6)
    ax.set_ylim(0, positives)
    ax.set_xlabel('Fraction of events reviewed')
    ax.set_ylabel(f'Missed positives (of {positives})')
    ax.legend(loc='upper right')
    save(fig, out, 'real_frontier', written)
    return ('real_frontier', 'Missed positives against the fraction of events reviewed on the exposed Kelvins training cohort.')


def tables(inputs, out):
    d = read('track_r_scientific_2026-10-10/decisions.csv', inputs)
    keep = d[['id', 'role', 'arm', 'comparator', 'condition', 'estimand', 'null', 'mean', 'lower', 'upper', 'p_value', 'holm_rejected', 'decision']]
    keep.to_csv(out / 'table1_frozen_results.csv', index=False)
    m = read('real_2026-10-10/metrics.csv', inputs)
    m[['split', 'arm', 'n', 'positives', 'log_loss', 'brier', 'roc_auc', 'average_precision', 'reviewed_95', 'missed_95']].to_csv(
        out / 'table2_real_metrics.csv', index=False)
    summary_path = RESULTS / 'pilot_2026-10-09/data_20261009_v2__data_summary.json'
    inputs['pilot_2026-10-09/data_20261009_v2__data_summary.json'] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    flow = pd.DataFrame([{'split': split, 'raw_events': summary[split]['raw_events'],
                          'prospectively_visible_events': summary[split]['prospectively_visible_events'],
                          'eligible_events_retrospective': summary[split]['eligible_events'],
                          'high_risk_eligible': summary[split]['high_risk_eligible'],
                          'visible_messages': summary[split]['visible_rows_after_canonical_ingestion']} for split in ('train', 'test')])
    flow.to_csv(out / 'table3_cohort_flow.csv', index=False)
    return ['table1_frozen_results.csv', 'table2_real_metrics.csv', 'table3_cohort_flow.csv']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('paper/figures'))
    parser.add_argument('--force', action='store_true', help='replace existing generated figures')
    args = parser.parse_args()
    if args.out.exists() and any(p.name != '.gitignore' for p in args.out.iterdir()) and not args.force:
        raise FileExistsError(f'{args.out} is not empty; use --force to regenerate')
    args.out.mkdir(parents=True, exist_ok=True)
    style()
    inputs, written, captions = {}, [], []
    captions.append(fig_windows(args.out, written))
    captions.append(fig_overlap_response(inputs, args.out, written))
    captions.append(fig_contrasts(inputs, args.out, written))
    captions.append(fig_persistence(inputs, args.out, written))
    captions.append(fig_real_contrasts(inputs, args.out, written))
    captions.append(fig_frontier(inputs, args.out, written))
    written += tables(inputs, args.out)
    (args.out / 'captions.md').write_text('# Figures (generated; full captions are in paper/main.tex)\n\n'
                                          + '\n\n'.join(f'**{stem}.** {text}' for stem, text in captions) + '\n', encoding='utf-8')
    (args.out / 'provenance.json').write_text(json.dumps({'generator': 'research/paper_figures.py', 'inputs_sha256': inputs,
                                                          'outputs': sorted(written + ['captions.md'])}, indent=2) + '\n', encoding='utf-8')
    print('WROTE', len(written), 'files to', args.out)


if __name__ == '__main__':
    main()
