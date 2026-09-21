# Rebuttal writing guidelines

Use this both to draft a new author response from scratch and to revise an
existing draft for AI-sloppy language. Rule 0 is the workflow for starting
from nothing. Rules 1 onward are the content and structure standard that a
fresh draft should meet on the first pass, and that a revision pass checks
an existing draft against.

## 0. Starting from scratch: drafting a new response

When there is no existing draft to revise, work in this order.

1. Read the full review and list every weakness and every comment as its
   own labeled item (W1, W2, ..., C1, C2, ...), including any separate
   Ethical Concerns section. Don't skip or merge items, each one gets its
   own answer in the final response.
2. For each item, classify it as either a writing or clarification concern,
   or an experiment or evaluation concern. This decides which template in
   rule 11 to use.
3. Ground every factual claim in the actual paper. Pull the relevant
   abstract, introduction, method, and results text directly from the
   paper's source or PDF before writing about it. Never invent a number,
   a citation, a dataset detail, or a paper claim. If a number is needed
   and it does not already exist in the paper, run the analysis or
   experiment to produce it rather than estimating it.
4. Draft each item directly against the structure in rule 11 and the
   phrase templates there, applying rules 1 through 10 and rules 12 and 13
   as you write. Writing it clean the first time means no separate
   AI-slop revision pass is needed afterward.
5. Assemble the full set of items into one response per reviewer, and
   produce both the full version and the 2000-character version (rule 14).

## 1. Cut throat-clearing meta-commentary, but keep one opening thank-you line

A single brief line thanking the reviewer for their comments is expected
convention for a rebuttal and should stay. This rule is strict about
narrating what caused the reviewer's confusion or restating the reviewer's
point before answering it, that kind of throat-clearing carries no content
and should be cut in every version, full or trimmed.

Extra acknowledgment or agreement filler beyond the one-line thank-you is
different. It reads fine in the full version and can stay there. It is only
a candidate for cutting when trimming down to the 2000-character version
(rule 14), where every sentence has to earn its place.

- Keep in every version: "Thank you for the detailed feedback."
- Fine in the full version, cut only when trimming to 2000 characters:
  "This is a very useful suggestion and we agree with it."
- Bad in every version: "The paper never states its aim, which we see caused
  much of W1 and W3."

## 2. Cut self-justifying asides about your own reasoning

Don't explain why you picked one option over a worse alternative you aren't
taking. State the decision, not the internal deliberation behind it.

- Bad: "We would rather run this well than attach a rushed baseline, so we
  are planning it as the next stage of this work."
- Good: "We are planning this as the next stage of this work."

This is a specific case of rule 1: it reads as reasoning-out-loud rather than
as an answer to the reviewer.

## 3. Write full sentences, not dense fragments

Academic rebuttal prose should read as complete sentences with a subject and
a verb, not colon-separated phrase chains or clipped fragments. Bullets are
fine occasionally, but the default is full sentences, not short noun phrases.

- Bad: "Doing this properly is a substantially broader study than we can
  complete this cycle: the tool interface, step and cost budgets, and above
  all a protocol that keeps the contrast interpretable."
- Good: "Doing this properly requires a substantially broader study than we
  can complete this cycle. It requires designing the tool interface, setting
  step and cost budgets, and building a protocol that keeps the contrast
  interpretable."

## 4. One idea per sentence

If two claims are logically separate, don't fuse them with a colon or
semicolon. Start a new sentence instead.

- Bad: "We use ball-by-ball data: Text-to-SQL converts the NL question to SQL."
- Good: "We use ball-by-ball data. Text-to-SQL converts the natural-language
  question into a SQL query."

## 5. Avoid "so" and "hence" as default connectors

These are a strong AI tell for chaining two only-loosely-related clauses into
one sentence. Split into two sentences, or use "because" to state the actual
causal link explicitly.

## 6. Don't over-negate

"Not a separate axis," "not the thing studied," "not just X" reads as
hedging filler. State positively what something is, rather than primarily
listing what it isn't.

## 7. Minimize numbers per sentence

Cap at one, at most two, numbers per sentence. Only include a number if the
argument in that sentence actually needs it there. If the number already
lives in the paper's own tables, don't requote it in the rebuttal unless it
is the crux of that specific reply. When in doubt, cut the number and flag it
to the author rather than silently dropping something load-bearing. New
experimental results run specifically for the rebuttal are the exception:
present the table or numbers in full, since they are the evidence.

## 8. No em-dashes, en-dashes, colons, or semicolons as clause glue

Use commas, periods, or restructure the sentence.

## 9. Avoid the wider AI-tell word list

Never use: delve, straightforward, it's worth noting, importantly, in the
realm of, leverage, robust, nuanced, certainly, of course, absolutely,
comprehensive, facilitate, utilize, ensure, moreover, furthermore, in
conclusion, to summarize, notably, it is important to note, plays a crucial
role, serves as a foundation.

## 10. Write every revision commitment in future tense

The revised or camera-ready version has not been submitted yet. Describe
every planned change as something that will happen, not something that has
happened.

- Good: "We will clarify this in the camera-ready version."
- Good: "We will revise the affected paragraph to state this explicitly."

Useful phrases: "We agree," "We will clarify," "We re-ran the experiment,"
"We ran a new experiment," "We will make this clearer in the camera-ready
version," "We will revise the [X] paragraph."

## 11. Answer each point with a fixed structure

For a clarification or writing-related comment, answer in this order.

1. What the concern is, stated briefly, not restated at length.
2. What is true or what we will do about it.
3. Commit to adding the clarification to the camera-ready version.

Template: "We agree with your point. We will clarify this in the
camera-ready version." Then state the specific change that will be made.

For an experiment or evaluation-related comment, answer in this order.

1. What concern the reviewer raised.
2. What experiment was run (or re-run), with the bare minimum method detail.
3. The main result, presented as the finding itself, not just a table dump.
4. What that result implies for the reviewer's concern.

Template: "We ran [experiment] on [dataset/setting]." Present the result,
table, or numbers, then close with two or three sentences on what the result
shows.

If an experiment can plausibly be run within a day or two, run it and report
the actual result rather than promising it. This carries far more weight
with a reviewer than a commitment. Only fall back to "we will include this
in the camera-ready version" when the experiment cannot be completed in the
rebuttal window.

Always present the new result, conclusion, or correction first, and only
then state the commitment to update the paper. Don't lead with the
commitment and follow with the evidence.

Stay to the point and keep the response focused on the specific comment
being answered. Don't repeatedly address the reviewer or restate their
question throughout the response. State what was done and what the result
or finding was, once, and move on.

## 12. Do not argue with the reviewer

Accept the reviewer's point respectfully, even when partially disagreeing.
The rebuttal is not a venue for contesting the reviewer's judgment. Where a
correction is genuinely due, state it plainly and move to the fix, not to a
defense of the original text.

## 13. Each reviewer's response is self-contained

Do not reference "our response to Reviewer X," a shared global response, or
lean on context the reviewer would need to read elsewhere. Each reviewer only
reads their own thread. If two reviewers raise the same point, answer it in
full in both responses rather than pointing from one to the other. This is
not duplication to avoid, it is required so each reviewer gets a complete
answer without cross-referencing anything else. Keep references to the main
paper text itself to a minimum too. The reviewer is deciding based on the
rebuttal response, not by cross-checking it against the manuscript.

## 14. Always produce two versions, full and 2000-character

For every reviewer's response, generate both of the following by default,
without waiting to be asked.

1. A full version with no character limit. This is the more readable
   version, since it does not need to compress the evidence or the framing,
   and it is the version to write first.
2. A version trimmed to 2000 characters total for that reviewer's entire
   response, covering every weakness and comment together, not per item and
   not per platform field.

Present both to the author and let them choose which to submit, rather than
picking one on their behalf. Do not default to only producing the trimmed
version, and do not default to only producing the full version.

When trimming the full version down to the 2000-character version:

1. First remove throat-clearing and self-justifying asides (rules 1–2).
2. Then collapse repeated framing, e.g. a parenthetical label like
   "(cricket)" that repeats information already stated a sentence earlier,
   or the same word or phrase repeated across nearby sentences.
3. Then cut filler adjectives ("real," "additionally," "very") that add no
   information.
4. Only then consider cutting substantive content, and flag any cut number
   or finding to the author rather than dropping it silently. Prefer
   trimming a new experiment's result to its headline number over cutting
   it entirely, rather than dropping it outright.

## 15. Grammar and polish come last

Apply the above structural passes first. Run a final grammar/clarity pass
only once the content and structure are right.
