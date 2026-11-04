"""Every tunable number in one place, with how it was chosen.

These were set by looking at retrieval scores on the 26 development cases in
eval/cases.json (see README, "Limitations"): they are tuned, not validated.
"""

# Articles retrieved per ticket and shown to the analyzer.
TOP_K = 5

# Minimum BM25 score for the offline analyzer to treat an article as relevant.
# From the dev cases: correct top matches start at 8.5 (C10); the second
# article of C14's conflict scores 8.0, so the cut-off must sit below that;
# C24 (no KB coverage) tops out at 6.0. No threshold can fix C25 (no coverage,
# but a wrong keyword match at 14.5): that is a limit of keyword search.
RELEVANCE_THRESHOLD = 7.5

# At most this many relevant articles are kept (conflicts are checked between them).
MAX_RELEVANT = 3

# When an FAQ-style article (no steps) outranks a step-by-step article in the
# same product area by less than this ratio, the step-by-step one is preferred.
SIMILAR_SCORE_RATIO = 0.8

# A ticket with at most this many content words and no relevant article is
# treated as too vague to triage ("Nothing works, please fix").
LOW_INFO_MAX_TOKENS = 7
