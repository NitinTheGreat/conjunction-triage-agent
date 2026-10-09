# V01: closest-work compatibility and comparator decision

Checked 9 October 2026. **V01 complete as a compatibility review, not as a reproduction.** V02 implementation and scientific evaluation remain open. This is a bounded search of primary papers and author code, not an exhaustive literature review.

The paper route remains a controlled robustness/measurement study. Select comparators by compatible inputs, target and information boundary; published scores from different tasks do not form a leaderboard. No reserved scenarios were generated or read.

## What changed since the earlier review

The final 48-page Sanchez ASR paper, the 13-page AMOS fusion paper and the seven-page Pinto sequence paper were downloaded successfully and relevant methods inspected. Kessler predictor code was also inspected. These upgrade the earlier access limitations. The October 2026 revision of Overlapping Covariance Intersection adds relevant prior art with public code. Ouari remains subscription-preview only; TimeQuery's full method remains unavailable in this review.

The [source access record](closest_work_sources.json) gives URLs, versions, downloaded-file hashes and code revisions. Downloaded PDFs and third-party code remain under ignored `processed/research/literature_v01_20261009/`; they are not vendored into this repository.

## Compatibility matrix

Statuses describe **our proposed treatment**, not an experiment already performed. The [CSV](closest_work_comparison.csv) is the structured version. “Adaptation” means changed target or protocol; “approximation” means important mathematical inputs or details differ.

| Work / access | Original task and inputs | Horizon / split / calibration / metric | Our treatment and constraint |
|---|---|---|---|
| Kelvins / existing audit | Final reported log-risk from visible CDMs | Two-day cutoff; released cohorts; official high-risk MSE/F2 ratio | B1 reconstruction already complete. Keep the separate class-probability task explicit. |
| Sanchez ASR 2024 / full final paper | Belief/plausibility classification from encounter-plane means and covariance components | Evolving sequences; operator-comparison experiments; evidence confidence is not final-class calibration | **Approximate weighting comparator planned** for current allowlist; full DSt reproduction deferred. No theorem transferred to grouped scores. |
| Sanchez CEC 2024 / previously inspected manuscript | Supervised six-class robust labels | Encounter-group separation; different target from final-risk binary class | **Discussion-only for numerical comparison** until target adaptation is justified; no copied accuracy headline. |
| Pinto 2020 / full paper + Kessler code | Next-message numerical fields and recursive CDM trajectories | Event split; next-step MSE; Monte Carlo dropout | **Sequence-family adaptation planned** with training-only scaling and final-class endpoint. Not reproduction of its reported MSE. |
| Ouari 2026 / publisher preview | Kelvins probabilistic/ensemble and sequence models | Exact cutoff, partitions and calibration implementation unverified | **Discussion-only**. Implementing a generic ensemble would not reproduce this work. |
| TimeQuery 2026 / prior indexed publisher abstract | Full-horizon sequence/uncertainty forecasts | Complete split, censoring and conformal unit unverified | **Discussion-only**; no inherited coverage guarantee. |
| TCN-Transformer 2026 / author record | Next-message collision-probability prediction on TUBITAK UZAY CDMs | Different horizon/data; full replication protocol not inspected | **Discussion-only**; no transferable score. |
| Agrawal/Ansari AMOS 2025 / full paper | Aligned multi-source Gaussian state/covariance fusion, then Pc | Common frame/time; additive precision; case illustrations | **Adapted simulation diagnostic planned**. Independence-based product is a failure control, not protection against overlap. |
| Denoeux cautious fusion / earlier full-method review | Dependent evidence expressed as belief functions | Different representation/guarantees from calibrated class scores | **Discussion-only** for current method. Revisit only if a justified mass-function construction is introduced. |
| Pedroso/Batista/Heemels OCI 2026 / v2 + code record | State estimation with partial structural covariance knowledge | Bounds on error covariance; semidefinite optimization | **Simulation-only future adaptation**, conditional on valid inputs; not a direct final-risk classifier. Basic CI is the smaller first comparator. |

## Method notes that affect implementation

### Covariance-linked weighting

The final ASR paper, section 3.1 and equations (9)-(10), fits a sequence-specific exponential trend to normalized combined-covariance determinants and weights samples inversely to that fitted trend. It then constructs weighted empirical distributions, DKW-based bounds and belief/plausibility structures. Those outputs are not calibrated probabilities of our binary final label. [Final paper](https://strathprints.strath.ac.uk/90580/13/Sanchez-etal-ASR-2024-Treatment-of-epistemic-uncertainty-in-conjunction-analysis.pdf)

Our inference: a diagonal-volume proxy on the current sigma allowlist is an **approximation**, not the published combined encounter-plane determinant. A faithful implementation needs consistent geometry and full covariance transformation. The extracted time-normalization expression also needs visual/equation verification before claiming exact reproduction. Fit any weighting law only to the visible prefix; specify degenerate-length, nonpositive-determinant and optimization-failure handling in advance. Do not substitute a guessed effective sample count into an iid coverage theorem.

### Accessible sequence family

Pinto et al., section 3, use two 256-dimensional LSTM layers, dropout 0.2, next-CDM MSE, Adam, and recursive prediction. Kessler exposes a corresponding `LSTMPredictor`; the inspected revision is `cc9404a73d6e9719b1c1be317ab2271e9dedea45`. [Paper](https://ai4earthscience.github.io/neurips-2020-workshop/papers/ai4earth_neurips_2020_41.pdf), [predictor code](https://github.com/kesslerlib/kessler/blob/cc9404a73d6e9719b1c1be317ab2271e9dedea45/kessler/nn.py)

In that code, normalization statistics are computed before its internal training/validation split. A direct call is therefore insufficient for our fold contract unless the caller supplies appropriate training-only statistics/data. This observation does not establish leakage in the paper's reported experiment. Our adaptation must create event folds first, fit normalization on training events, mask padding, and choose the final-class readout/calibration within training data. Declare any smaller capacity or different training budget. Do not describe a small replacement as reproduction or as a proven state-of-the-art comparator. The repository advertises GPL-3.0; no source was copied into our implementation.

### State fusion is a distinct diagnostic

AMOS section 4.3 uses a product of Gaussian estimates under a conditional-independence approximation. Its conclusion explicitly leaves unknown correlations for future conservative fusion. Thus, reference to overlap in its introduction is not evidence that its evaluated fusion solves overlap. [Official AMOS paper](https://amostech.com/TechnicalPapers/2025/Poster/Agrawal.pdf)

Our simulation can compare that product with covariance intersection and a union-of-unique-observations oracle. Report state error/covariance behavior separately from final-class forecast loss. A posterior covariance bound is not automatically a conservative upper collision probability: integrating a small disk is not monotone in covariance for all mean/radius regimes. Do not place raw fused Pc and calibrated class `q` in one proper-score table without a declared mapping.

OCI v2, dated 1 October 2026, handles structural information about covariance bounds with an efficient semidefinite formulation. Its public MATLAB implementation is at revision `c33865114d94b73a0bb93546964dde2b0a5b6f2e`. [Paper v2](https://arxiv.org/html/2603.16768v2), [author repository](https://github.com/decenter2021/OCI)

Our inference: OCI is relevant prior art, but public CDM age bins do not supply its required matrices/bounds. Start with basic CI on well-specified synthetic state estimates; treat common-bias inputs that omit bias covariance as misspecified. A more elaborate OCI comparison requires an explicit input mapping and solver verification, not just the method name.

### Remaining access limits

Ouari's publisher confirms ensemble/sequence modeling and calibration but does not expose the needed full experimental protocol. [Publisher preview](https://link.springer.com/article/10.1007/s10489-026-07494-6) TimeQuery's full method was not retrieved; retain the earlier abstract-level status. [Publisher record](https://www.sciencedirect.com/science/article/abs/pii/S0094576526005357) The TCN-Transformer author record concerns a different next-update task. [Author record](https://arxiv.org/abs/2609.13191)

These limitations restrict novelty and “best existing method” claims. They do not prevent a bounded benchmark with clearly labeled adaptations. No paid access, author contact or external submission was performed.

## V02 implementation order and acceptance gates

1. **Repair the generator before adding model complexity.** Add irregular cadence with short clusters and gaps; check that time grouping and six-hour thinning actually produce different retained messages/groups. Preserve overlap windows, common labels and matched latest-message inputs. Save construction diagnostics before any performance comparison.
2. **Match information access.** Include latest-risk and latest-metadata arms in simulation; distinguish observable metadata from oracle observation IDs. Preserve exact replay canonicalization for every arm.
3. **Separate training shift from new information.** Compare a deliberately shifted training regime with a matched regime that includes cumulative-observation histories. Keep all variants of each latent scenario in the same fold. Weight scenarios equally even if training uses multiple variants.
4. **Add smaller justified comparators first.** Implement a clearly named covariance-proxy weighting adaptation; add state-fusion/unique-observation-oracle diagnostics separately. Verify their numerical behavior before integration. Then implement the sequence-family adaptation with an explicit compute budget and fold-contained early stopping.
5. **Choose precision and freeze only after development.** Use scenario-level paired variation and training-seed variation. Select one primary comparator/condition/estimand for V03, not whichever pilot interval is most favorable. Keep absolute loss, the new-information control and bias sensitivity mandatory.

V02 is **not complete**. Subsequent [development records](v02_development.md) now document the cadence/control repair, training-regime comparison and expanded-grid/subset campaign. The [covariance-proxy comparator and direct-weighting ablation](covariance_proxy_plan.md) are now complete on exposed simulation banks. The next step is [state-fusion/oracle diagnostics](state_fusion_plan.md); sequence, provenance-component and precision work remain open. These updates do not turn the literature review into a numerical reproduction. The original pilot, including failed controls and negative comparisons, remains unchanged.
