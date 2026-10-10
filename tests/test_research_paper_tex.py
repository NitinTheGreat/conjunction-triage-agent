import pandas as pd

import research.paper_tex as pt


def register(**values):
    return pd.DataFrame([{'id': key, 'expected': value} for key, value in values.items()], columns=['id', 'expected'])


def test_the_paper_passes_every_check():
    tex = pt.PAPER.read_text(encoding='utf-8')
    assert pt.check(tex, pd.read_csv(pt.REGISTER), bib=pt.BIB.read_text(encoding='utf-8')) == []
    assert pt.write_tables(tex) == tex


def test_claims_must_round_from_the_register_and_appear_in_the_text(tmp_path):
    (tmp_path / 'fig.pdf').write_bytes(b'%PDF')
    base = '% claims: A=0.063 B=8.7% C=four D=7,700\nThe loss is 0.063 and 8.7\\% missed; all four, 7,700 pairs.\n'
    good = register(A=0.0628, B=0.0874, C=4.0, D=7700.0)
    assert pt.check(base, good, tmp_path) == []
    assert any('does not round' in p for p in pt.check(base, register(A=0.0640, B=0.0874, C=4.0, D=7700.0), tmp_path))
    assert any('not in the text' in p for p in pt.check(base.replace('0.063 and', 'and'), good, tmp_path))
    assert any('not in the claim register' in p for p in pt.check(base, register(A=0.0628, B=0.0874, C=4.0), tmp_path))


def test_citations_figures_and_references_are_checked(tmp_path):
    tex = ('See~\\cite{a} and Figure~\\ref{fig:x}.\n\\includegraphics{missing}\n'
           '\\begin{thebibliography}{9}\\bibitem{a} A.\\bibitem{b} B.\\end{thebibliography}\n')
    problems = pt.check(tex, register(), tmp_path)
    assert 'bibliography entry b is never cited' in problems
    assert any('missing.pdf' in p for p in problems)
    assert 'reference fig:x has no label' in problems
