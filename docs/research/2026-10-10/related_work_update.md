# Related-work update for the measurement framing

**Date:** 10 October 2026. **Purpose:** redo related work for the paper's current
framing, a controlled measurement of how observation reuse affects history-based
forecasting from conjunction data messages (CDMs), with a frozen confirmatory test.
Earlier searches (6 September novelty report; 6 October deep review) were made for a
history-aware *method* and an LLM triage agent, so they covered method comparisons
rather than the measurement and evaluation literature.

## Scope note on the request

The request also named an "audit of specified versus enacted behaviour", "ML system
testing and test oracles", "evaluation of agent guardrails", the citations FIRCE,
CALIBURN, LanG and GroundEval, and "an ablation of epistemic guardrails in an LLM
security agent". None of these appear anywhere in this repository, its history, or its
ignored files (checked 10 October 2026). They appear to belong to a different project.
The equivalent steps were carried out for this paper:
- its new framing's literature;
- the status of its own arXiv-only citations;
- a novelty re-check for its own claim.

## Literatures added for the new framing

| Area | Why a reviewer expects it | Sources added (verified 10 Oct 2026) |
|---|---|---|
| Dependent observations treated as independent | The central issue in plain statistical terms | Hurlbert (1984), *Ecol. Monogr.* 54(2):187-211, pseudoreplication; Kish (1965), *Survey Sampling*, design effect |
| Correlated estimates in fusion and tracking | Known double counting when estimates share information | Bar-Shalom and Campo (1986), *IEEE TAES* AES-22(6):803-805; Julier and Uhlmann (1997), *Proc. ACC* 2369-2373; Pedroso et al. (2026), arXiv 2603.16768; Denœux (2008, 2024) |
| Evaluation of learned models | Overlapping training sets, training-run variance, holdout reuse, leakage | Dietterich (1998), *Neural Comput.* 10(7):1895-1923; Nadeau and Bengio (2003), *Mach. Learn.* 52:239-281; Bouthillier et al. (2021), *MLSys* 3; D'Amour et al. (2022), *JMLR* 23(226); Dwork et al. (2015), *Science* 349:636-638; Kaufman et al. (2012), *ACM TKDD* 6(4):15 |
| Forecasting from CDM sequences | Direct application context | Uriot et al. (2022), *Astrodynamics* 6(2):121-140; Pinto et al. (2020), NeurIPS AI4Earth workshop; Catulo et al. (2023), arXiv 2311.10633; Tok et al. (2026), arXiv 2609.13191; Zerrouki et al. (2026); Ouari et al. (2026); Sánchez et al. (2024, two papers); Olson et al. (2026) |
| CDM content and collision probability | Where reuse comes from; what the label means | CCSDS 508.0-B-1 (2013); NASA CA handbook (NASA/SP-20205011318, Rev. 2 vol. 1, 2026); Akella and Alfriend (2000), *JGCD* 23(5):769-772; Alfano (2005), *J. Astronaut. Sci.* 53(2):193-205; Balch, Martin and Ferson (2019), *Proc. R. Soc. A* 475:20180565 |
| Statistical methods used | Interval and testing choices | Efron and Tibshirani (1993); Holm (1979), *Scand. J. Stat.* 6:65-70; Cameron, Gelbach and Miller (2008), *REStat* 90(3):414-427; Platt (1999); Saerens et al. (2002), *Neural Comput.* 14(1):21-41 |

## Publication status of arXiv-only and workshop citations

| Citation | Status on 10 Oct 2026 | How cited |
|---|---|---|
| Pedroso, Batista and Heemels, *Overlapping Covariance Intersection* | arXiv only (v2, 1 Oct 2026); IEEE template, no venue found | arXiv preprint |
| Tok et al., hybrid TCN-Transformer for next-CDM probability | arXiv only (Sept 2026) | arXiv preprint |
| Catulo, Soares and Guimarães, HMMs on Kelvins sequences | arXiv only (Nov 2023); derived from an IST master's thesis | arXiv preprint |
| Pinto et al., Bayesian deep learning for conjunction management | NeurIPS 2020 workshop (AI for Earth Sciences) poster; arXiv 2012.12450; no later journal version found | Workshop paper |
| Uriot et al., Kelvins challenge | Published: *Astrodynamics* 6(2):121-140, 2022 | Journal article |

## Novelty re-check

Searches on 10 October 2026 covered:
- observation reuse, overlapping orbit determination and double counting in CDM-based ML;
- forecasting from CDM histories against the latest-message baseline;
- recent arXiv and conference work in 2026.

No study was found that measures the effect of observation reuse on forecasts from CDM
histories, or that compares history summaries with a latest-message forecaster under
known lineage.

Two items are closest:
- **Catulo et al. (2023)** reports that naive latest-value forecasts are strong on
  Kelvins and attributes this to Markov-like behaviour. This is consistent with our
  real-data result but does not involve lineage.
- **Tok et al. (2026)** forecasts the next CDM's probability without addressing reuse.

The paper states the novelty boundary explicitly: double counting itself is known in
fusion and statistics; the contribution is a controlled, frozen measurement in the CDM
forecasting setting.

## Sources consulted

arXiv records 2603.16768, 2609.13191, 2311.10633, 2012.12450 and 2008.03069; Springer
DOI 10.1007/s42064-021-0101-5; NeurIPS 2020 virtual site; MLSys 2021 proceedings; JMLR
v23/20-1335; NTRS 20260000453; CCSDS 508.0-B-1; JSTOR 1942661; ACM DOI
10.1145/2382577.2382579; Science DOI 10.1126/science.aaa9375. Bibliographic details for
Holm (1979), Efron and Tibshirani (1993), Platt (1999), Saerens et al. (2002), Kish (1965),
Dietterich (1998) and Cameron et al. (2008) are standard and were not re-fetched.
