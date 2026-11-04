# First held-out run (kept as a record)

This folder is the first and only run of the 10 held-out cases on the code as it
stood when they were written: commit `90af606`, before the pre-publish review
fixes. It is kept unchanged so the before and after numbers can be compared.

- Command: `python3 -m triage eval --cases eval/heldout_cases.json --out results/heldout-first-run`
  (the package was later renamed from `triage` to `lily`).
- Its `summary.md` says the cases are "development cases the thresholds were tuned
  on". That sentence is wrong for this run, because these are the held-out cases.
  The report generator fixed the wording later (review finding: split-aware
  caveat).
- Before the run, three independent auditors re-derived all 10 labels without
  seeing the code or any results, and agreed with every one.
- The later fixes came from code reviewers who were told not to open the
  held-out cases. No change was designed around a held-out ticket.
