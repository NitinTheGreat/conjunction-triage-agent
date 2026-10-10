# Writing style notes: Tomasz Radzik (King's College London)

Notes from three papers supplied by the user on 10 October 2026, used as the model
for the paper's voice:
1. C. Cooper, T. Radzik and T. Shiraga, *Discrete incremental voting on expanders*,
   Discrete Mathematics 349(1), 2026 (DIV).
2. R. Elsässer and T. Radzik, *Recent results in population protocols for exact
   majority and leader election*, Distributed Computing Column, Bulletin of the EATCS
   (survey).
3. C. Cooper, N. Kang and T. Radzik, *A simple model of influence*, WAW 2023, LNCS
   (influence).

The aim is to borrow the voice, not to copy wording or slips such as "Using a edge
exposure martingale" or a stray comma before a verb.

## 1. Titles

Titles are short noun phrases that name the object and the setting, with no colon,
question or slogan:
- *A simple model of influence*;
- *Discrete incremental voting on expanders*;
- *Recent results in population protocols for exact majority and leader election*.

## 2. Abstracts

The abstract is a compressed version of the paper, results included:
1. **Define the object** in one long sentence. "Pull voting is a random process in
   which vertices of a connected graph have initial opinions chosen from a set of k
   distinct opinions, and at each step a random vertex alters its opinion to that of
   a randomly chosen neighbour until the system reaches a state where each vertex
   holds the same opinion."
2. **Contrast with the usual view**, often using *whereas*. "In general the opinions
   ... are regarded as incommensurate, whereas we consider a type of pull voting,
   which we call discrete incremental voting, suitable for ..."
3. **Give the simplest concrete case.** "In the simplest case, the vertex increases
   its opinion by +1 if ..."
4. **Set the formal scene.** "Let G = (V, E) be a connected non-bipartite n-vertex
   graph, and let λ be ..."
5. **State the result with its conditions and numbers.** "We show that provided λk =
   o(1) and k = o(n/log n) the following holds with high probability." In the
   influence paper: "a single stubborn vertex reduces the number of influencers by a
   factor of √(1 − c)".
6. **Finish with "In particular"** or with a last, smaller result: "Finally we analyse
   ..., and remark that ...".

## 3. Voice and tense

- First person plural throughout, in the present tense for the paper's own work: "We
  show", "We prove", "We give", "We make an equivalent analysis", "We remark that".
- The past tense is used for earlier work: "was first analysed in [13] using ad-hoc
  methods for ...".
- The purpose is stated plainly: "The purpose of this paper is to prove Theorem 1,
  which shows that ..."; "In this paper we make an analysis of ...".
- Modesty is built into the words: "a simple model", "in a simplistic way", "perhaps
  surprising", "it seems", "suggest", "indicates".
- A few informal, human sentences appear among the formal ones: "However, people being
  what they are, it seems possible that ..."; "It turns out to be quite a lot of work."
  At most one or two per paper.
- Praise for others is specific and generous: "A breakthrough in this field was
  achieved by ...", "These two building blocks are combined in a fascinating way."
  It is never self-praise.

## 4. Sentences

- Medium-length declarative sentences. Most paragraphs open with one longer defining
  sentence and continue with shorter ones.
- Conditions are attached with *provided*, *whereas*, *if ... then*, *in which case*,
  *so that*.
- Appositives and parenthetical glosses name things in plain words: "an active
  vertex, the influencer, at the head of the group"; "vertices (people)"; "stubborn
  vertices (dictators)"; "(intransigent, autocratic, dictatorial)".
- Sentence openers that connect the argument: *Thus*, *Hence*, *In particular*, *In
  contrast*, *Note that*, *We note that*, *Recall that*, *Clearly*, *Essentially*,
  *Intuitively*, *Interestingly*, *Henceforth*, *For convenience*, *In what follows*,
  *Finally*.
- Abbreviations are introduced once in parentheses and then used freely: "with high
  probability (w.h.p.)", "u.a.r.", "DIV". A definition can sit in a footnote.

## 5. Paragraph architecture

Sections are made of **labelled paragraphs** with a run-in heading, bold in the journal
paper and italic in LNCS. Examples:
- "Background on distributed pull voting."
- "Discrete incremental voting: An introduction."
- "Features of discrete incremental voting."
- "Discrete incremental voting: Previous work."
- "Results."
- "Graphs with small second eigenvalue."
- "Proof outline."
- "Notation."
- "Joining Protocol."
- "Summary of results."
- "Looking backwards: A Polya urn process."

The reader always knows what each paragraph is for.

## 6. Examples before abstraction

A concrete, everyday picture comes first, then a small worked example narrated step by
step, then the formal definition:
- "As a simple example, suppose the entries reflect the views of the vertices about
  some issue, and range from 1 ('disagree strongly') to k ('agree strongly'). It seems
  unrealistic that a vertex would completely change its opinion ...";
- "Returning to our original example ... suppose we start with each vertex having one
  of the opinions in {1, 2, 5}. Then a possible evolution of the system ... is {1,2,5}
  → {1,2,4} → ...".

The example is then used to point out a property: "Intermediate values may disappear
and then appear again."

## 7. Positioning

- Previous work is short and factual: what was done, under which restrictions, and what
  remained open. "Unlike ordinary pull voting, no general method is known to predict
  the outcome of incremental voting."
- Citation habits: "see [17]", "see e.g. [11]", "has been extensively studied see e.g.
  [8], [10], [11] and references therein".
- Bibliographies are numeric and ordered alphabetically by first author.

## 8. Results and figures

- Results are stated as numbered statements with their conditions, then restated in
  plain words and illustrated: "To illustrate the applicability of Theorem 2, we next
  give three examples ...".
- A **Summary of results** in the introduction lists, with dashes, which theorem or
  section gives what, and says how simulations support it.
- What is proved is kept apart from what is suggested: "Simulation results (see
  Figure 1) suggest that E a(t) should continue to track b_t of (3) throughout." Also:
  "Due to space limitations the proof is only given in outline."
- Figures are described in the text, curve by curve, with their settings: "The plots
  are based on G(n, p), for n = 1000 and p ⩾ 0.1. The upper curve in the right hand
  figure is ... The middle curve is ... The lower curve is ..."
- Captions are long and self-contained: what was simulated, the parameters, and what
  each colour or curve shows.

## 9. Endings

The survey ends with "Further results and open problems": "There are open questions
left regarding ... A natural open question is how close can we get ... An interesting
open question is whether ... Finally, it is still open whether ..." Remarks close
sections rather than a long summary: "We remark that if the network is sparse ..., and
there are only a few stubborn vertices, these will have little effect."

## 10. Articles and small words

- **"The"** marks a model, process or object already introduced or unique in context:
  "the model", "the process", "the edge model", "the final opinion", "the influencer".
- **"A" / "an"** marks a first mention or a generic member: "a random vertex", "an
  active neighbour", "a stage of the proof".
- **No article** with named variables and labelled items ("vertex v directs an edge to
  u", "Theorem 1 gives", "Section 3.1", "Lemma 5(iii)"), and with process names used as
  mass nouns ("pull voting", "discrete incremental voting").
- **"The" again** when a variant is contrasted: "the vertex process" against "the edge
  process".

## 11. Spelling and typography

- British spelling: *neighbour*, *colour*, *behaviour*, *analyse/analysed*. Oxford
  *-ize* is common: *characterize*, *randomized*, *synchronized*.
- Plain numbers in text: "n = 1000", "20 replications".
- Light mathematics in running text; displayed equations are numbered.
- En-dash ranges.

## 12. Avoid (not in his voice)

- Hype words: *novel*, *groundbreaking*, *state-of-the-art*, *paradigm*, *leverage*.
- "In recent years" openers.
- Rhetorical questions.
- Contribution lists with bold verbs.
- Stacks of hedges.
- Citations without a sentence on what the cited work did.

## Applying this to an empirical paper

- **Title and abstract:** a plain title. The abstract follows section 2 above, with
  the actual estimates and intervals.
- **Introduction:**
  - run-in paragraphs: background on conjunction messages; observation reuse with a
    worked example (six messages, sixty observations, fifteen distinct ones at 90%
    overlap); previous work; summary of results;
  - organisation of the paper.
- **Results:** labelled findings rather than theorems. Each states its condition (the
  configuration, the arms, the contrast), then the number and its interval, then a
  plain restatement.
- **Figures:** described curve by curve in the text, with long captions.
- **Proved versus suggested:** confirmatory, development and exposed real-data
  evidence are named every time, mirroring his separation of proof from simulation.
- **Ending:** close with further questions, posed the way he states open problems.
