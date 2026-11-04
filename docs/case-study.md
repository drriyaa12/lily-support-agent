# Lily: case study

Lily is an AI support agent I built with Claude Code as a portfolio project. It
reads a customer ticket and does one of three things: sends a fix, asks the
customer for a missing detail, or hands the ticket to a person with a written
handoff. Everything it works with is fictional: the product (Quillstack), its
17 help articles and 36 tickets.

All the results below come from a version that analyses tickets with
hand-written rules, which use no AI model and give the same answer every time.
The version that uses Claude for the analysis is written and tested against a
stand-in for the API, but it has never made a real API call, so it is
unmeasured. The [demo](https://drriyaa12.github.io/lily-support-agent/) shows
how Lily decided each ticket, and the
[code](https://github.com/drriyaa12/lily-support-agent) is on GitHub.

## The problem

Most of the risk in a support agent sits in one choice: answer, ask, or
escalate. A wrong choice sends refund steps when no refund policy covers the
request, or asks a customer to repeat a fix that already failed. I wanted an
agent whose choice a support lead could check.

## How it works

Lily runs in two stages. First, an investigator searches the help articles,
reads the ticket thread for steps the customer already tried and details they
gave, and checks the status page for an open incident in the same product
area. Whether the analysis comes from the hand-written rules or from Claude,
the investigator drops any claim that fails its checks. For example, a quote
has to appear word for word in the article it cites, and a reported attempt
has to appear in the customer's own messages.

Then a decision policy applies ten rules in order, and the first rule that
applies decides. One hands the ticket to a person when the best-matching
article is marked "always escalate", as the security and privacy articles are.
The last sends the steps the customer hasn't tried yet. Each rule checked goes
into a trace, so any decision can be read line by line. Replies are built only
from fixed templates, the articles' own text and the status page's message.
That limits what Lily can say, but it can still apply an article that doesn't fit the ticket, as the
invoice example below shows. Escalations come with a handoff that lists the
issue, what was tried, the evidence checked and the open questions.

## How I evaluated it

I compared Lily with a simple baseline that uses the same search: when the
best-matching article clears the relevance threshold, the baseline sends every
step in it, and otherwise it escalates. Both ran on 26 development tickets and
on 10 held-out tickets that a separate AI agent wrote from the help articles
without seeing any code. Three more AI agents worked out the expected answers
for the held-out tickets on their own and agreed with all ten.

I scored two things: whether the decision (resolve, ask or escalate) was right,
and whether the response was correct too. A resolution counts only if it cites
an expected source, includes every step the customer hasn't tried and repeats
none they have. A question counts only if it asks for exactly the missing
details. An escalation counts if the decision is right. Every handoff Lily
wrote was also complete.

| | Lily (rules) | Baseline |
|---|---|---|
| Development tickets (26): right decision | 25 | 11 |
| Development tickets (26): right decision and correct response | 25 | 9 |
| Held-out tickets (10): right decision | 6 | 3 |
| Held-out tickets (10): right decision and correct response | 5 | 1 |

A score of 6 out of 10 does not mean six solved tickets. Only three of the
held-out tickets should have been resolved, and Lily's reply was correct for
two of them. On the third, its reply told the customer to replace a payment
card they had already replaced. The scoring compares replies with the expected answers, so
it can't tell whether a fix would have worked.

The development score is optimistic: the thresholds were tuned on those
tickets, and the same assistant wrote both the tickets and Lily. The held-out
score is a better guide, but a preliminary one. Ten AI-written tickets is a
small sample, their writer used the same labelling guide that Lily's rules
follow, and agreement between AI labellers doesn't replace an independent
check by people.

Lily got five held-out tickets wrong in all: four with the wrong decision and
one with a wrong reply. All five come from simple word counting and matching:
a vague ticket that was too long for the seven-word "too vague" limit, a
conflict between two help articles that the matching missed, two steps that
customers had already done but described in different words, and an invoice
request that matched the refund article because it shared the words
"invoice", "number" and "look". Lily asked that
customer for an invoice number, which the refund article requires, when the
ticket needed a person.

GitHub re-runs both evaluations on every push to `main` and every pull request,
and the check fails if their results files, transcripts or the demo page no
longer match what the code produces.

## What the reviews found

Claude Code also ran adversarial reviews of the code and the claims: reviewer
agents reported problems, and skeptic agents tried to disprove each one. They
found bugs the tests had missed. Lily read phrases like "I need to update" as
"I already updated", so it could skip a step and thank the customer for doing
it. A later review found that a fix from an earlier one had broken something
else: a sentence ending in a question mark no longer counted as a report of
what the customer had tried.

## How I worked with Claude Code

I set the brief: the requirements, the scope, the baseline comparison and the
kinds of tickets the evaluation had to cover (routine tickets, missing
information, conflicting guidance and failed fixes). Claude Code turned the
brief into a design for me to review, wrote the code, the fictional data and
labels, the tests and the docs, tuned the thresholds, ran the evaluations and
reviews, and made the fixes. I made the publishing decisions, including the license, the demo page
and the automatic checks, and did the final review of the published claims.
[A page in the repository](https://github.com/drriyaa12/lily-support-agent/blob/main/docs/claude-code-assistance.md)
lists what was and wasn't verified.

## What I'd do next

First, I would run the Claude version on both ticket sets and compare it with
the rules. Then I would add tickets written and labelled by people, and
tickets that try to steer the agent with hidden instructions. Longer term, the
investigator needs sources beyond the help articles and the status page, such
as account and billing lookups, before it could work on real tickets.
