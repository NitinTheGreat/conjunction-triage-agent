"""Scripted paper figures and tables (W02) from committed result bundles.

Reads only `docs/research/results/*` exports plus the simulator's window
definition, so a clone regenerates every figure without local run directories.
Writes PDF and PNG files, captions and a provenance record with input hashes.
Evidence types stay separate: frozen scientific (V04), exposed development
simulation, and exposed retrospective real data never share an axis.
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

from research.simulation import windows  # noqa: E402

RESULTS = Path('docs/research/results')
SURFACE, INK, INK2, MUTED, GRID, AXIS = '#fcfcfb', '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7'
BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'  # validated light-mode slots 1-3
CONDITION_ORDER = ['no_reuse', 'overlap_50', 'overlap_90', 'solution_reissue']
CONDITION_LABEL = {'no_reuse': 'No reuse', 'overlap_50': '50% overlap', 'overlap_90': '90% overlap',
                   'solution_reissue': 'Solution\nreissue', 'new_information': 'New\ninformation'}


def style():
    plt.rcParams.update({
        'font.family': 'sans-serif', 'font.sans-serif': ['Segoe UI', 'DejaVu Sans'], 'font.size': 9,
        'axes.facecolor': SURFACE, 'figure.facecolor': SURFACE, 'savefig.facecolor': SURFACE,
        'axes.edgecolor': AXIS, 'axes.linewidth': 0.8, 'axes.labelcolor': INK2, 'axes.titlecolor': INK,
        'axes.titlesize': 10, 'axes.titleweight': 'semibold', 'axes.spines.top': False, 'axes.spines.right': False,
        'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6, 'grid.linestyle': '-',
        'xtick.color': MUTED, 'ytick.color': MUTED, 'xtick.labelcolor': INK2, 'ytick.labelcolor': INK2,
        'legend.frameon': False, 'legend.fontsize': 8, 'lines.linewidth': 1.5, 'lines.solid_capstyle': 'round'})


def read(name: str, inputs: dict) -> pd.DataFrame:
    path = RESULTS / name
    inputs[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pd.read_csv(path)


def save(fig, out: Path, stem: str, written: list):
    for suffix in ('pdf', 'png'):
        target = out / f'{stem}.{suffix}'
        fig.savefig(target, dpi=200, bbox_inches='tight', metadata={'CreationDate': None} if suffix == 'pdf' else None)
        written.append(target.name)
    plt.close(fig)


def fig_overlap_response(inputs, out, written):
    """V04: mean clipped log loss across reuse conditions; history emphasized, latest-only flat."""
    losses = read('track_r_scientific_2026-10-10/per_bank_losses.csv', inputs)
    order = [c for c in CONDITION_ORDER]
    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    x = range(len(order))
    series = [('grouped', MUTED, 'Grouped'), ('oracle_lineage_weight', MUTED, 'Oracle lineage weights'),
              ('latest_metadata', ORANGE, 'Latest message (comparator)'), ('singleton', BLUE, 'History summary (singleton)')]
    for arm, color, label in series:
        g = losses[losses.arm == arm].groupby('condition').log_loss
        mean, low, high = (g.mean().reindex(order), g.min().reindex(order), g.max().reindex(order))
        width = 1.0 if color == MUTED else 1.5
        ax.plot(x, mean.to_numpy(), color=color, linewidth=width, marker='o', markersize=4 if color == MUTED else 5,
                markeredgecolor=SURFACE, markeredgewidth=1.0, label=label, zorder=3 if color != MUTED else 2)
        if color != MUTED:
            ax.vlines(list(x), low.to_numpy(), high.to_numpy(), color=color, linewidth=0.8, alpha=0.6, zorder=2)
            ax.annotate(label, (len(order) - 1, mean.iloc[-1]), xytext=(6, 0), textcoords='offset points',
                        va='center', fontsize=8, color=INK2)
    ax.set_xticks(list(x), [CONDITION_LABEL[c] for c in order])
    ax.set_ylabel('Mean clipped log loss (nats)')
    ax.set_ylim(bottom=0)
    ax.set_title('Observation reuse degrades history-based forecasts')
    ax.legend(loc='lower right', ncols=1)
    save(fig, out, 'fig1_overlap_response', written)
    return ('fig1_overlap_response', 'Frozen scientific evaluation (V04; held-out configuration, 10 independent training banks x 5,000 '
            'evaluation scenarios). Mean clipped log loss by reuse condition; whiskers span the 10 bank means. The latest-message '
            'comparator is invariant by construction. Grouped and oracle-weighted history arms (gray) track the history summary. '
            'Source: track_r_scientific_2026-10-10/per_bank_losses.csv (run track_r_scientific_20261010_v1).')


def fig_contrasts(inputs, out, written):
    """V04: frozen contrasts with bank-combined intervals against their own nulls."""
    d = read('track_r_scientific_2026-10-10/decisions.csv', inputs)
    labels = {'P1': 'P1 degradation at 90% overlap\n(primary; margin 0.02)', 'S5': 'S5 degradation, solution reissue\n(null <= 0.02)',
              'S1': 'S1 remaining advantage at 90% overlap\n(null <= -0.02)', 'S2': 'S2 grouped minus singleton\n(null <= -0.01)',
              'S3': 'S3 oracle weights minus singleton\n(null <= -0.01)', 'S6': 'S6 history minus latest, reissue\n(exploratory)'}
    order = ['P1', 'S5', 'S1', 'S2', 'S3', 'S6']
    d = d.set_index('id').loc[order]
    fig, ax = plt.subplots(figsize=(5.8, 3.6))
    for i, cid in enumerate(order):
        row = d.loc[cid]
        y = len(order) - 1 - i
        color = BLUE if cid != 'S6' else MUTED
        ax.hlines(y, row['lower'], row['upper'], color=color, linewidth=1.5)
        ax.plot(row['mean'], y, 'o', color=color, markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.0, zorder=3)
        if pd.notna(row['null']):
            ax.plot(row['null'], y, marker='|', color=INK2, markersize=12, markeredgewidth=1.5, zorder=2)
    ax.axvline(0, color=AXIS, linewidth=0.8, zorder=1)
    ax.set_yticks(range(len(order)), [labels[c] for c in reversed(order)], fontsize=7.5)
    ax.set_xlabel('Difference in mean clipped log loss (nats)')
    ax.set_title('Frozen contrasts: estimate and 95% interval vs. null (|)')
    ax.grid(axis='y', visible=False)
    save(fig, out, 'fig2_frozen_contrasts', written)
    return ('fig2_frozen_contrasts', 'Frozen scientific evaluation (V04). Points: estimates averaged over 10 independent training banks and '
            '5,000 scenarios; bars: frozen bank-combined 95% intervals (studentized bootstrap, B = 9,999, plus a training-bank term); '
            'vertical ticks: each hypothesis null. P1 is the primary contrast (material degradation confirmed); S1, S5, S2 and S3 '
            'are the Holm family (all rejected); S6 is exploratory. Source: track_r_scientific_2026-10-10/decisions.csv.')


def fig_persistence(inputs, out, written):
    """Exposed development: P1 per independent training bank and configuration."""
    d = read('sensitivity_2026-10-10/bank_contrasts.csv', inputs)
    d = d[(d.id == 'P1') & (d.training_configuration == d.evaluation_configuration)]
    order = ['iso', 'aniso2', 'aniso8', 'noise2', 'bias']
    names = {'iso': 'Isotropic', 'aniso2': 'Anisotropy 2', 'aniso8': 'Anisotropy 8', 'noise2': 'Doubled noise', 'bias': 'Shared bias'}
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    for i, cfg in enumerate(order):
        g = d[d.training_configuration == cfg].reset_index(drop=True)
        offsets = [(k - (len(g) - 1) / 2) * 0.08 for k in range(len(g))]
        ax.vlines([i + o for o in offsets], g.lower95, g.upper95, color=BLUE, linewidth=0.9, alpha=0.7)
        ax.plot([i + o for o in offsets], g['mean'], 'o', color=BLUE, markersize=4.5, markeredgecolor=SURFACE, markeredgewidth=0.8)
    ax.axhline(0.02, color=INK2, linewidth=0.9)
    ax.text(-0.45, 0.0215, '0.02 margin', fontsize=7.5, color=INK2, ha='left', va='bottom')
    ax.set_xticks(range(len(order)), [names[c] for c in order])
    ax.set_ylabel('P1 (nats), per training bank')
    ax.set_ylim(bottom=0)
    ax.set_title('Development: reuse degradation per independent training bank')
    save(fig, out, 'fig3_development_persistence', written)
    return ('fig3_development_persistence', 'Exposed development simulation (sensitivity_20261010_v1), not confirmation. P1 for each '
            'independently generated training bank (6 isotropic, 2 per other configuration) with in-configuration training, '
            'evaluated on a fresh 2,000-scenario bank; whiskers are per-bank t-intervals conditional on the fitted bank. '
            'Source: sensitivity_2026-10-10/bank_contrasts.csv.')


def fig_windows(out, written):
    """Mechanism schematic generated from the simulator's window definition."""
    conditions = ['no_reuse', 'overlap_50', 'overlap_90', 'solution_reissue', 'new_information']
    fig, axes = plt.subplots(1, len(conditions), figsize=(7.8, 2.6), sharey=True)
    fig.subplots_adjust(wspace=0.35, bottom=0.22)
    for ax, condition in zip(axes, conditions):
        for j, ids in enumerate(windows(condition)):
            y = 5 - j
            color = BLUE if j == 5 else MUTED
            ax.barh(y, len(ids), left=ids.min(), height=0.62, color=color, alpha=0.9 if j == 5 else 0.55, linewidth=0)
        ax.set_xlim(0, 60)
        ax.set_title(CONDITION_LABEL[condition].replace('\n', ' '), fontsize=8.5)
        ax.set_xticks([0, 30, 60])
        ax.grid(axis='y', visible=False)
    axes[0].set_yticks(range(6), [f'm{6 - k}' for k in range(6)])
    axes[0].set_ylabel('Message (m6 = latest)')
    fig.supxlabel('Observation ID (visible 0-59)', fontsize=8.5, color=INK2, y=0.0)
    save(fig, out, 'fig4_observation_windows', written)
    return ('fig4_observation_windows', 'Controlled observation-lineage design generated from research.simulation.windows. Each bar is '
            'one message\'s observation window; the latest message (blue) is identical across reuse conditions, so the '
            'latest-message comparator is invariant. Exact replay repeats no-reuse messages; burst reissue repeats them at new '
            'publication times (not shown).')


def fig_real_contrasts(inputs, out, written):
    """Exposed retrospective real data (A01): R1-R4 with event and mission-cluster intervals."""
    d = read('real_2026-10-10/contrasts.csv', inputs)
    labels = {'R1': 'R1 history summary\nminus latest metadata', 'R2': 'R2 grouped\nminus history summary',
              'R3': 'R3 latest metadata\nminus latest risk', 'R4': 'R4 gradient boosting\nminus latest metadata'}
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3), sharey=True)
    fig.subplots_adjust(bottom=0.27)
    for ax, (split, title) in zip(axes, [('training_oof', 'Training cohort (out of fold)'), ('historical_test', 'Historical test split')]):
        g = d[d.split == split].set_index('id')
        for i, cid in enumerate(['R1', 'R2', 'R3', 'R4']):
            y = 3 - i
            if cid not in g.index:
                ax.text(0.02, y, 'not evaluated (no test predictions)', fontsize=7, color=MUTED, va='center',
                        transform=ax.get_yaxis_transform())
                continue
            r = g.loc[cid]
            ax.hlines(y + 0.12, r.mission_lower, r.mission_upper, color=MUTED, linewidth=1.2)
            ax.hlines(y - 0.12, r.event_lower, r.event_upper, color=BLUE, linewidth=1.5)
            ax.plot(r['mean'], y - 0.12, 'o', color=BLUE, markersize=5, markeredgecolor=SURFACE, markeredgewidth=0.8, zorder=3)
        ax.axvline(0, color=INK2, linewidth=0.8)
        ax.set_title(title, fontsize=9)
        ax.grid(axis='y', visible=False)
    axes[0].set_yticks(range(4), [labels[c] for c in ['R4', 'R3', 'R2', 'R1']], fontsize=7.5)
    from matplotlib.lines import Line2D
    fig.legend([Line2D([], [], color=BLUE, linewidth=1.5), Line2D([], [], color=MUTED, linewidth=1.2)],
               ['Event bootstrap-t 95%', 'Mission-cluster 95%'], loc='lower center', ncols=2, bbox_to_anchor=(0.55, 0.0))
    fig.supxlabel('Difference in mean clipped log loss (nats); positive favours the comparator', fontsize=8.5, color=INK2, y=0.07)
    save(fig, out, 'fig5_real_contrasts', written)
    return ('fig5_real_contrasts', 'Exposed retrospective real CDMs (A01; Kelvins), never pooled with simulation. Paired event-level '
            'contrasts with studentized-bootstrap (blue) and mission-cluster bootstrap-t (gray) 95% intervals. Training cohort: '
            '8,293 events / 66 positives, out of fold; historical test: 2,167 / 150, labels long public. Public CDMs carry no '
            'observation lineage, so these are absolute comparisons, not reuse contrasts. Source: real_2026-10-10/contrasts.csv.')


def fig_frontier(inputs, out, written):
    """Exposed retrospective real data (A01): review fraction versus missed positives (training OOF)."""
    f = read('real_2026-10-10/frontiers.csv', inputs)
    m = read('real_2026-10-10/metrics.csv', inputs)
    f = f[f.split == 'training_oof']
    fig, ax = plt.subplots(figsize=(5.4, 3.3))
    series = [('latest', MUTED, 'Context: latest risk and grouped'), ('grouped', MUTED, None),
              ('causal_gbm', AQUA, 'Gradient boosting'), ('latest_metadata', ORANGE, 'Latest metadata'),
              ('singleton', BLUE, 'History summary')]
    for arm, color, label in series:
        g = f[f.arm == arm].sort_values('review_fraction')
        ax.step(g.review_fraction, g.missed, where='post', color=color, linewidth=1.0 if color == MUTED else 1.5, label=label)
        point = m[(m.split == 'training_oof') & (m.arm == arm)].iloc[0]
        if color != MUTED:
            ax.plot(point.reviewed_95 / point.n, point.missed_95, 'o', color=color, markersize=5, markeredgecolor=SURFACE,
                    markeredgewidth=0.8, zorder=3)
    ax.set_xlim(0, 0.6)
    ax.set_ylim(0, 40)
    ax.set_xlabel('Fraction of events reviewed (enriched retrospective cohort)')
    ax.set_ylabel('Missed positives (of 66)')
    ax.set_title('Workload versus misses, training cohort (out of fold)')
    ax.legend(loc='upper right')
    save(fig, out, 'fig6_real_frontier', written)
    return ('fig6_real_frontier', 'Exposed retrospective real CDMs (A01), training cohort out of fold. Missed positives against the '
            'fraction reviewed across score thresholds; points mark the training-selected nominal 95%-recall operating point. '
            'Descriptive only: thresholds along the curve were not selected on training data, and review fractions are not '
            'operational workload. Source: real_2026-10-10/frontiers.csv and metrics.csv.')


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
    if args.out.exists() and any(args.out.iterdir()) and not args.force:
        raise FileExistsError(f'{args.out} is not empty; use --force to regenerate')
    args.out.mkdir(parents=True, exist_ok=True)
    style()
    inputs, written, captions = {}, [], []
    captions.append(fig_overlap_response(inputs, args.out, written))
    captions.append(fig_contrasts(inputs, args.out, written))
    captions.append(fig_persistence(inputs, args.out, written))
    captions.append(fig_windows(args.out, written))
    captions.append(fig_real_contrasts(inputs, args.out, written))
    captions.append(fig_frontier(inputs, args.out, written))
    written += tables(inputs, args.out)
    (args.out / 'captions.md').write_text('# Figure captions (generated)\n\n' + '\n\n'.join(f'**{stem}.** {text}' for stem, text in captions) + '\n',
                                          encoding='utf-8')
    (args.out / 'provenance.json').write_text(json.dumps({'generator': 'research/paper_figures.py', 'inputs_sha256': inputs,
                                                          'outputs': sorted(written + ['captions.md'])}, indent=2) + '\n', encoding='utf-8')
    print('WROTE', len(written), 'files to', args.out)


if __name__ == '__main__':
    main()
