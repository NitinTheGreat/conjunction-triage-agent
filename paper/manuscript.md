# Paper: Observation reuse and history-based forecasting of conjunction risk

The paper's source is [`main.tex`](main.tex): one self-contained LaTeX file with an
inline bibliography, written for Overleaf. This file replaces the earlier Markdown
draft, which is in the git history (commit `78760c0`).

## Using it in Overleaf

1. Create a blank project and paste `main.tex` as it is.
2. Upload the six figures from [`figures/`](figures/), either to the project root or
   into a folder named `figures/`; both layouts compile. The PDF versions are
   preferred and the PNG versions also work:
   - `observation_windows`
   - `overlap_response`
   - `frozen_contrasts`
   - `development_banks`
   - `real_contrasts`
   - `real_frontier`
3. Compile with pdfLaTeX (the default).

The figures are not kept in git. Regenerate them with:

```powershell
.\.venv\Scripts\python.exe -m research.paper_figures --force
```

## Keeping the numbers honest

Every estimate in `main.tex` is preceded by a comment such as
`% claims: V01=0.063 V02=0.053`. The comment names rows of the
[claim register](../docs/research/claims/claim_evidence.csv). The three tables
between `BEGIN GENERATED` and `END GENERATED` are written from the committed result
bundles. Run the checker before every submission or upload:

```powershell
.\.venv\Scripts\python.exe -m research.paper_tex          # check
.\.venv\Scripts\python.exe -m research.paper_tex --write  # regenerate the tables, then check
```

The check confirms four things:
- every claimed value rounds correctly from its register row and appears in the text;
- the generated tables match the bundles;
- every citation has an entry and every entry is cited, and the entries match
  [`references.bib`](references.bib);
- every figure and cross-reference exists.

## Background documents

- [Claim audit](../docs/research/execution/w03_claim_audit.md): the weak claims of
  the earlier draft and how each was supported, corrected or softened.
- [Related-work update](../docs/research/2026-10-10/related_work_update.md):
  literature for the measurement framing, publication status of arXiv-only
  citations, and the novelty re-check.
- [Style notes](../docs/research/writing/radzik_style_notes.md): the writing voice
  used.

## Still open

- Independent reproduction (A03) has not been done. The paper states this as a
  limitation.
- Authors, affiliations, acknowledgements and any AI-assistance disclosure must be
  completed for the chosen venue.
