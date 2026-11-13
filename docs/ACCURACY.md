# Accuracy Lab: measured results

Run it yourself: `make benchmark` (or `python -m claimpassport.accuracy --errors --save`). The page `#/accuracy` shows the latest saved run.

**Set:** 174 labelled sentences, 18 claim types, one demo brand (Lumio) with 10 approved facts. Labels were written by the team that built the checker. Claim rules C-1 to C-6 are scored; a sentence is "exact" when the reported rule set equals the labelled set.

| Mode | Exact match | Precision | Recall | F1 | False alarms | Missed problems |
|---|---|---|---|---|---|---|
| Rules only (Round 2) | 116/174 (67%) | 0.94 | 0.57 | 0.71 | 0/40 | 52/134 |
| Hybrid (meaning layer) | 153/174 (88%) | 0.96 | 0.84 | 0.90 | 0/40 | 16/134 |
| Hybrid + cited AI judge | not measured (no AI key available when this was written) | | | | | |

Measured with: concept lexicon only; the optional embedding model was **not installed**, so the embedding path has not been measured.

## Honest reading
- The gain comes mostly from implied claims (absolute, certification, comparison, quantity, superlative), which rules-only misses almost entirely.
- Hybrid is **worse** on two types: `number_unsourced` (83% to 75%) and some paraphrased-number sentences are still wrong. 21 sentences remain wrong; the page lists them.
- The set is small, single-brand, English, and written by the checker's authors, so the numbers describe this set, not real-world accuracy. Hard paraphrases are in the set on purpose.
- The AI judge only runs with an API key, and its answer counts only if it cites a real fact id and quotes words that appear in that fact.
