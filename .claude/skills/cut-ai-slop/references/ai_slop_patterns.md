# AI-Slop Pattern Catalog

The shared source of truth for the `cut-ai-slop` skill and for Agent E (the AI-slop
audit) inside the `review-papers` pipeline. It lists the writing patterns that make
text read as machine-generated, the words to replace, and, most importantly for this
repo, the **research-paper carve-outs** that stop the catalog from firing on prose that
is correct in academic writing.

This catalog is **research-paper first**. Every entry carries a scope tag:

- `[paper]` — apply when editing or auditing a research paper.
- `[both]` — apply to papers and to general writing.
- `[general]` — general-writing only (blogs, social, marketing). These are listed in the
  "General-writing extensions" appendix and are NOT applied in `--paper` mode yet. They
  are the deferred, comprehensive-port half of the catalog.

## The golden rule for every rewrite

**You may subtract and sharpen. You may not add.** Cut filler, make an existing claim
concrete from material already in the text, surface a buried point. Never introduce a
number, name, date, citation, result, stance, or personality the source did not contain.
A fabricated specific is worse than the vague phrasing it replaced. For each edit, ask
whether the information came from the source. If a concrete detail is missing, flag the
gap, do not fill it.

This matters more in papers than anywhere else. A rewrite that invents a statistic, a
baseline, or a citation is a research-integrity failure, not a style improvement.

## Attribution

Adapted, in our own words, from two MIT-licensed skills:

- `avoid-ai-writing` by Conor Bronsdon (MIT, 2026) — the tiered word tables, most
  structural patterns, the severity tiers, and the "never inject" guardrails.
- `no-ai-slop` by Peter Yang (MIT, 2026) — the voice-preserving editing stance, colon
  reveals, faux-insight setups, and fake-profound kickers.

Both permit reuse with attribution. The research-paper carve-outs and scope tagging are
ours.

---

## 1. Editorial guardrails (never inject) `[both]`

These are constraints on the editor, not detections on the text. None may be **added** to
a text that did not already contain it. Each is a rewrite failure even when the result
reads clean.

- **No invented specifics.** No number, dataset, baseline, metric, name, date, citation,
  or mechanism the source never contained. This is the cardinal rule for papers.
- **No fabricated citations or references.** Never add a `\cite{}`, a bracketed number, or
  an author-year key. If a claim needs support the paper does not give, mark it as a gap.
- **No fake first person or stance.** If the source has no authorial voice or opinion, the
  rewrite adds none.
- **No manufactured stakes.** "now more than ever", "in an era where", "the stakes have
  never been higher".
- **No forced contrarianism.** Inventing a foil ("conventional wisdom is wrong") is
  inventing a claim.
- **No performed candor.** "let us be honest", "the truth is", "here is the thing".
- **No em-dash theatrics or staccato conversion.** Do not add dashes for drama, and do not
  chop ordinary sentences into fragments to fake rhythm.
- **Preserve verbatim:** all numbers, results, statistical values, dataset and model names,
  proper nouns, acronyms, technical terms, equations, `\cite{}` keys, labels, and URLs.

---

## 2. Word-level tells

### 2A. Replace on sight, even in papers `[both]`

These read as slop in any register, including academic prose. Match the word and its
inflections. Replacement in parentheses.

| Word / phrase | Replace with |
|---|---|
| delve / delve into | examine, study, look at |
| leverage (verb) | use, exploit, apply |
| underscore(s) / underscoring | show, highlight, indicate |
| showcase / showcasing | show, demonstrate, present |
| cutting-edge | latest, recent, current |
| state-of-the-art (as praise, not the noun "the state of the art") | strongest, best-performing (or name the benchmark) |
| deep dive / dive into | examine, analyze |
| unpack / unpacking | explain, break down |
| tapestry / realm / landscape (metaphor) | field, area, setting (or name it) |
| beacon / embark / embrace (metaphor) | (rewrite plainly) |
| testament to | shows, demonstrates, is evidence of |
| game-changer / game-changing | (state what specifically changed) |
| at its core | (cut, state the thing) |
| ever-evolving / rapidly evolving | changing, growing (or cut) |
| holistic | complete, whole (or describe what is included) |
| synergy / synergies | (describe the combined effect) |
| meticulous(ly) | careful(ly), precise(ly) |
| seamless(ly) | smooth(ly), without extra steps |
| learnings | findings, lessons |
| best practices | established methods (or name them) |
| plethora / myriad | many, numerous (or give a number) |

### 2B. Keep the technical sense, cut the puffery sense `[paper]`

These are the false-positive minefield. Each has a legitimate scientific meaning and a
puffery meaning. Cut only the puffery use. When in doubt in a paper, keep the word.

| Word | Legitimate (keep) | Puffery (cut or make concrete) |
|---|---|---|
| significant / significantly | statistical significance with a test or p-value | "a significant improvement" with no number or test → give the number |
| robust / robustness | robustness to noise, robust optimization, a robustness study | "a robust method / robust results" as a vague compliment |
| comprehensive | a genuinely exhaustive survey or evaluation | "comprehensive experiments" that are actually a few runs |
| novel / innovative | a first, clearly stated once with the delta named | "novel" repeated as a self-compliment across the paper |
| nuanced | a specific distinction you then name | "a nuanced understanding" with the nuance unnamed |
| crucial / pivotal / paramount / vital | rarely needed; prefer "important" or state why | importance puffery ("plays a crucial role") |
| effective / powerful | tied to a metric or comparison | "highly effective" with no evidence |

### 2C. Flag only in clusters or at density `[both]`

Individually fine. Two or more of the cluster words in one paragraph, or a density of the
praise words above roughly 3% of a section, signals filler.

- **Cluster words (≥2 per paragraph):** foster, facilitate, streamline, harness, elevate,
  empower, unleash, bolster, underpin, catalyze, cultivate, illuminate, encompass.
- **Density words (flag when saturated):** effective, remarkable, compelling, exceptional,
  sophisticated, unprecedented, powerful, instrumental.

### 2D. Do NOT flag in papers `[paper]`

Required or accepted academic phrasing. Leave it alone.

- Method framing: "we propose", "we present", "we introduce", "we study", "we show".
- Calibrated hedging where the evidence is genuinely limited: "our results suggest", "this
  indicates", "may", "could", "to the best of our knowledge". Hedging is scientific
  caution, not slop. Do not strip it and make a claim overconfident.
- Passive voice in Methods and Setup ("samples were randomly assigned", "the model was
  trained for 100 epochs"). Standard and often preferred there.
- Genuine parallel lists: numbered contributions, research questions, ablation rows,
  hyperparameter lists. Parallel structure is correct here, not a rule-of-three tell.
- Deliberate repetition of a defined technical term. Do not thesaurus a term for variety.
  If the paper defines "the retriever", keep calling it "the retriever".

---

## 3. Phrase and sentence patterns

Each entry: what it is, why it reads as slop, and a paper-flavored before → after. Apply
the golden rule, the "after" never adds a fact the "before" lacked.

### 3.1 Formulaic openers `[both]`
"In recent years, X has attracted increasing attention." "With the advent of deep
learning..." "In the rapidly evolving field of..." These delay the actual contribution.
Before: "In recent years, large language models have attracted increasing attention in the
NLP community." After: "Large language models now underpin most NLP systems, yet they still
fail at X." (Only if the paper supports the "fail at X" claim.)

### 3.2 Importance and significance inflation `[both]`
"plays a crucial role", "is of paramount importance", "marks a significant milestone",
"stands as a testament to". State the fact and let the reader judge weight.
Before: "Attention plays a pivotal role in modern architectures." After: "Most modern
architectures use attention."

### 3.3 Superficial -ing analysis `[both]`
Trailing participles that pretend to explain: "highlighting the importance of X",
"underscoring the need for Y", "demonstrating the potential of Z". They assert significance
without evidence. Cut the clause or replace it with the concrete consequence stated in the
paper.
Before: "Accuracy rose to 91%, demonstrating the effectiveness of our approach." After:
"Accuracy rose to 91%, a 6 point gain over the strongest baseline." (Only if 6 points and
the baseline are in the paper.)

### 3.4 Binary contrast `[both]`
"It is not X, it is Y." Also the split form across two sentences: "The problem is not the
model. It is the data." State Y directly.
Before: "This is not merely an engineering trick, it is a principled method." After: "This
method is principled: it minimizes [the stated objective]." (Keep the colon for a genuine
explanation; see 5.)

### 3.5 Filler openers `[both]`
"It is worth noting that", "It is important to note that", "Notably,", "Importantly,",
"Interestingly,". Just state the fact.

### 3.6 Transition-word stacking `[both]`
"Moreover", "Furthermore", "Additionally", "Consequently" opening consecutive sentences.
One or two across a section is fine. A stack is a tell. Restructure so the connection is
obvious, or use "and", "also", "so".

### 3.7 Copula avoidance `[paper]`
"serves as", "represents", "constitutes", "acts as" where "is" is clearer. Prefer "is" and
"has" unless the fancier verb adds real meaning.
Before: "The encoder serves as a feature extractor." After: "The encoder extracts
features."

### 3.8 Hollow intensifiers `[both]`
"truly", "highly", "remarkably", "genuinely", "extremely" attached to an abstract noun.
Cut, or replace with the number. "highly effective" → the metric.

### 3.9 Vague attribution without a citation `[paper]`
"studies show", "prior work has shown", "it is widely believed", "researchers agree" with
no reference. In a paper, cite the specific work or drop the claim. Never invent a
citation to satisfy this.

### 3.10 Overclaiming and promotional language `[both]`
"unprecedented", "remarkable", "compelling evidence" at density, or "we are the first to"
without a scoped literature check. Competent reviewers see through inflation and trust it
less. State the result and the standard of evidence plainly.

### 3.11 Synonym cycling `[paper]`
Rotating "method / approach / framework / technique / paradigm" for the same thing inside a
paragraph to avoid repetition. Pick the clearest term and repeat it.

### 3.12 Compulsive rule of three `[both]`
"efficient, scalable, and robust." Reflexive triads where the third item is padding. Vary
the grouping. Carve-out: genuine three-item content (three contributions, three datasets)
is fine, keep it.

### 3.13 Generic conclusions and summary-recap `[both]`
"In conclusion", "To summarize", "Overall," followed by a restatement of what the reader
just read. End on the last concrete point or the takeaway. A Conclusion section can exist,
but it should state the implication, not recap sentence by sentence.

### 3.14 Aphorism and slot-fill profundity `[both]`
"X is the cornerstone of Y", "X is the backbone of Z", "at the heart of X lies Y". The
formula manufactures depth. Replace with the concrete claim it gestures at.

### 3.15 Colon reveals and faux-insight setups `[both]` (from no-ai-slop)
A noun phrase, a colon, then a dramatic lowercase reveal: "The key insight: attention is
enough." Or "What most people miss:", "Here is the part that matters:". Rewrite as a plain
sentence. Keep colons for genuine lists and labels.

### 3.16 Fake-profound kicker `[both]` (from no-ai-slop)
A final "deep" one-liner that turns the point into an aphorism or mic-drop. Delete it and
end on the clearest concrete sentence already present.

### 3.17 False breadth `[general]`
"Whether you are a practitioner or a theorist..." Pick the audience or cut. Rare in paper
bodies, common in abstracts that try to claim universal relevance.

---

## 4. Structure and rhythm (writer-side tests) `[both]`

**Sentence length (best-effort target).** Prefer sentences under 20 words. Split long sentences
(20 or more words) wherever a natural boundary exists, a coordinating conjunction, a relative
clause, a list, or a cause-and-effect break, and the split reads better. Apply this as much as
possible, but it is a target, not a strict cap. Leave a long sentence intact when splitting
would create choppy fragments, force an awkward break, or blur a precise claim, and never
manufacture staccato (see the rhythm and manufactured-punchline notes below). Splitting only
restructures, it adds no content (grammatical glue such as a repeated subject is not new
content). Preserve every number, citation, and technical term when splitting.

Not word-level. Read the draft as a whole.

- **Paragraph-reshuffle test.** Can you swap two body paragraphs without breaking the
  argument? If order does not matter, you have a list of points, not an argument that
  builds. Add the through-line, or make the list explicit.
- **Treadmill / low information density.** For each paragraph, name the one fact, claim, or
  turn it adds. If there is none, cut it. AI prose restates the premise in fresh words. If
  you can cut 40 to 60% with no information lost, do.
- **Uniformity.** If most sentences are 15 to 25 words and every paragraph is the same
  size, the text reads metronomic. Vary deliberately. This is a real detector signal.
- **Do not over-polish.** Sanding every irregularity out pushes writing back toward the AI
  profile. For encyclopedic and technical text, plain and neutral is the correct human
  voice, do not inject personality. But do not manufacture uniformity either.

---

## 5. Formatting `[both]`

- **Em-dashes (—) and en-dashes (–) as connectors.** Remove. Use a comma with a
  conjunction, or split into two sentences. House style for this repo is zero. Catch the
  double-hyphen substitute (--) too.
- **Semicolons and colons joining clauses.** Split into sentences. A colon introducing a
  genuine list or a label is fine.
- **Bold sprinkled mid-sentence for emphasis.** Remove. If a point matters, restructure to
  lead with it.
- **List-label periods.** "**Setup.** We train..." reads as AI; a person writes
  "**Setup:** we train...". Change the period to a colon and lowercase the gloss, or fold
  the label into the sentence.
- **Excessive bullets.** Convert bullet-heavy prose into paragraphs. Keep lists for
  genuinely list-shaped content (contributions, hyperparameters, algorithm steps).

---

## 6. Research-paper carve-outs (the noise control) `[paper]`

Do not flag any of the following in a paper. This section exists to keep `--paper` mode
quiet and precise.

- Statistical "significant" tied to a test or p-value.
- Technical "robust" and "robustness" as properties or study names.
- "we propose / present / introduce / study / show".
- Calibrated hedging where evidence is limited ("our results suggest", "may", "could",
  "to the best of our knowledge").
- Passive voice in Methods, Setup, and data-collection descriptions.
- Genuine parallel lists: contributions, research questions, ablation rows, hyperparameters.
- Deliberate repetition of a defined technical term.
- Numeric precision and units.
- Standard field openers when they carry real content (naming the subfield and the
  specific open problem is fine, the empty "attracted increasing attention" wrapper is not).

**Self-reference escape hatch.** Never flag or rewrite: text inside quotation marks, direct
quotes, figure and table captions the author must keep verbatim, defined-term glossaries,
equations, code listings, or `\cite{}` keys. When a paper quotes an example of bad writing,
that is not the author's own prose.

---

## 7. Severity tiers (for triage) `[paper]`

When auditing a long paper, prioritize.

- **P0 — worst offenders.** Overclaiming and unsupported "first / significant" claims,
  invented-sounding certainty, importance inflation in the abstract and introduction,
  superficial -ing analysis attached to results.
- **P1 — clear AI smell.** Section-2A word hits, formulaic openers, filler openers,
  transition stacking, binary contrasts, colon reveals, em-dashes.
- **P2 — polish.** Copula avoidance, hollow intensifiers, rule-of-three padding, generic
  conclusions, list-label periods, uniform rhythm.

A quick pass fixes P0 and P1. A full audit covers all three.

---

## Appendix. General-writing extensions (deferred, not applied in `--paper` mode) `[general]`

Kept here as the roadmap for the comprehensive general-writing port. Do not apply these to
papers. Add them to the active catalog when general-writing support is turned on.

- Chatbot artifacts ("I hope this helps!", "Great question!", "Certainly!").
- "Let's" transition openers ("Let's dive in", "Let's explore").
- Hashtag stuffing, emoji in headers, curly-quote paste signals.
- Tourism-brochure and promotional prose ("nestled in", "a vibrant hub").
- LinkedIn and review openers ("I recently had the pleasure of").
- Generic future-narrative closers ("may become one of the most important narratives").
- Wall-of-text replies, recap-flattery openers, sycophantic tone (conversational registers).
- Crypto and web3 boilerplate ("decentralized compute", "tokenized incentive structures").
- Speculative scenario openers ("Imagine a world where"), false ranges, notability
  name-dropping, hashtag and emoji formatting slop.
