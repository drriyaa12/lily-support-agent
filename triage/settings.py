"""Every tunable number in one place, with how it was chosen.

These were set by looking at retrieval scores on the 26 development cases in
eval/cases.json (see README, "Limitations"): they are tuned, not validated.
"""

# Articles retrieved per ticket and shown to the analyzer.
TOP_K = 5

# Minimum BM25 score for the offline analyzer to treat an article as relevant.
# On the dev cases, the lowest correct top match scored 8.5 and the highest
# top match on a ticket with no KB coverage scored 6.0.
RELEVANCE_THRESHOLD = 7.5

# At most this many relevant articles are kept (conflicts are checked between them).
MAX_RELEVANT = 3

# When an FAQ-style article (no steps) outranks a step-by-step article in the
# same product area by less than this ratio, the step-by-step one is preferred.
SIMILAR_SCORE_RATIO = 0.8

# A ticket with at most this many content words and no relevant article is
# treated as too vague to triage ("Nothing works, please fix").
LOW_INFO_MAX_TOKENS = 7
