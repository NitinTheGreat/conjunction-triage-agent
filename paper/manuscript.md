# Paper: Observation Reuse and History-Based Forecasting of Conjunction Risk

The paper's source is [`main.tex`](main.tex): one self-contained LaTeX file in IEEE
two-column conference format (`\documentclass[conference]{IEEEtran}`), with an inline
bibliography in IEEE style. It compiles to 9 pages. The single-column version it
replaced is in the git history (commit `91a94fb`), and the earlier Markdown draft is at
commit `78760c0`.

## Using it in Overleaf

1. Create a blank project and paste `main.tex` as it is. Overleaf already provides the
   IEEEtran class.
2. Upload the six figures from [`figures/`](figures/), either to the project root or
   into a folder named `figures/`; both layouts compile. The PDF versions are
   preferred, and the PNG versions (300 dpi) also work:
   - `observation_windows` (spans both columns)
   - `overlap_response`
   - `frozen_contrasts`
   - `development_banks`
   - `real_contrasts`
   - `real_frontier`
3. Compile with pdfLaTeX (the default).

The figures are drawn at their printed size: 3.49 in wide for one column and 7.14 in
for both, so their text prints at 7-8 pt. They are not kept in git. Regenerate them
with:

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

The check confirms five things:
- every claimed value rounds correctly from its register row and appears in the text;
- the generated tables match the bundles;
- every citation has an entry and every entry is cited, and the entries match
  [`references.bib`](references.bib);
- the references are in order of first citation, as IEEE numbering requires;
- every figure and cross-reference exists.

## Before submission

- Data and Code Availability says "URL to be added". Add the repository link once the
  repository is public and holds the commits the paper reports.
- The Acknowledgment states the use of AI assistants, as IEEE requires. Confirm it
  against the tools actually used, and add the authors' statement of review and
  responsibility and any other acknowledgments.
- Check the venue's page limit (the paper has 9 pages) and paper size. The class
  defaults to US letter; add the `a4paper` option if the venue asks for A4.
- Independent reproduction (A03) has not been done; the paper states this as a
  limitation.

## Background documents

- [Claim audit](../docs/research/execution/w03_claim_audit.md): the weak claims of
  the earlier draft and how each was supported, corrected or softened.
- [Related-work update](../docs/research/2026-10-10/related_work_update.md):
  literature for the measurement framing, publication status of arXiv-only
  citations, and the novelty re-check.
- [Style notes](../docs/research/writing/radzik_style_notes.md): the writing voice
  used.
