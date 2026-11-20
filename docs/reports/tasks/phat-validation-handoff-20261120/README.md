# Validation handoff for Thanh and Khương

## Receive and check the private package

Phát's verified local package is `%USERPROFILE%/qpaf-cache/jev-phat/phat-validation-scoring-inputs.zip`. The branch carries the package digest and each input digest in [the receipt](evidence/validation-handoff.json). The archive contains validation inputs for scoring. Development judgments and evaluation reports stay with the evaluator. Transfer the archive through the team's private storage.

In PowerShell, set `$zip` to the received archive and `$work` to a fresh private directory. From the branch root:

~~~powershell
$receipt = Get-Content docs/reports/tasks/phat-validation-handoff-20261120/evidence/validation-handoff.json -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $zip).Hash -ne $receipt.archive_sha256) { throw 'Archive hash mismatch' }
Expand-Archive -LiteralPath $zip -DestinationPath $work
foreach ($entry in $receipt.entries.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $work $entry.Name)).Hash -ne $entry.Value.sha256) { throw "Input hash mismatch: $($entry.Name)" }
}
python scripts/run_jev.py doctor --pairs "$work/inputs/pairs.json"
python scripts/run_jev.py doctor --pairs "$work/vimdoc/inputs/pairs.json"
~~~

ViDoSeek has 171 queries, 3,420 ordered pairs and 3 blank OCR pages. ViMDoc has 400 queries, 8,000 ordered pairs, 124 blank OCR pages and an embedded page-to-document map. Preserve the pair file bytes. On ViMDoc use native development document judgments with `--qrels-format vimdoc-dev`.

## Frozen scoring

Use separate Volumes and package environments. The [shared runbook](../jev-runnable-team-kit-20261120/README.md) covers account setup, input transfer, execution and retrieval. Preview commands below ran on CPU. The receipt records their resolved arguments and environment requirements. Use distinct remote output paths for each dataset and run.

~~~powershell
python scripts/modal_jev_rerank.py --volume jev-thanh --gpu A100-80GB score --backend bge --pairs inputs/pairs.json --out runs/validation-01/bge.json --chunks runs/validation-01/bge-chunks --device cuda --precision fp16 --input-cap 1024 --batch-size 4
python scripts/modal_jev_rerank.py --volume jev-khuong --gpu A100-80GB score --backend kev --pairs inputs/pairs.json --out runs/validation-01/kev.json --chunks runs/validation-01/kev-chunks --device cuda --precision fp32 --input-cap 1024 --batch-size 1
~~~

For Thanh, the historical BGE cache covers 2,877 ViDoSeek pairs. The archive contains the other 543 pairs across 160 queries. Filling only those pairs requires the historical scorer and matching model, instruction, precision, cap and package policy. Its Torch 2.11 / Transformers 4.53.3 runtime differs from the Jev baseline runtime. The full-pool BGE preview above is the reproducible route for the Jev environment. For a matching historical-format supplement, run the following against Phát's private source files:

~~~powershell
python scripts/jev_phat_bge_handoff.py merge --full "$work/inputs/pairs.json" --static "$lab/vidoseek_pairs.json" --static-scores "$lab/vidoseek_scores.json" --extra "$work/inputs/bge_missing_pairs.json" --extra-scores "$returned" --out "$freshOutput"
~~~

Here `$lab` is the private historical lab-rerank directory. Use `missing --help` to recreate the subset. The merge checks pair hashes, frozen text, exact coverage, finite values, and declared historical runtime policy. Preserve scorer code and environment receipts for independent review.

## Return and integrate

Each owner returns the full scores JSON with the pairs digest, chunk logs, model/code revisions and settings. On local receipt, run the following on the same branch, with a fresh output directory. For ViDoSeek, `$qrels` is the M2.8 EXPANSION bundle's qrels_development.json. For ViMDoc use the document-format option above. Use the archived Qwen evaluation with the same dataset and partition as the left side.

~~~powershell
python scripts/run_jev.py doctor --pairs "$pairs" --scores "$returned"
python scripts/run_jev.py evaluate --pairs "$pairs" --scores "$returned" --qrels "$qrels" --k 10 --out "$run/returned-eval.json"
$l = Get-Content -Raw $qwenEval | ConvertFrom-Json
$r = Get-Content -Raw "$run/returned-eval.json" | ConvertFrom-Json
if ($l.pairs_sha256 -ne $r.pairs_sha256 -or $l.qrels_sha256 -ne $r.qrels_sha256) { throw 'Evaluation inputs differ' }
python scripts/run_jev.py compare --left "$qwenEval" --right "$run/returned-eval.json" --seed 20260820 --resamples 10000 --out "$run/paired.json" --csv "$run/paired.csv"
~~~

For each actual job record provider app/run ID, Volume, input/output digests, GPU SKU and count, wall time, scored tokens, resumed chunks, billed duration, currency and charge from the provider receipt. The CLI reports token count, chunk scoring time and peak CUDA allocation. Chunk time excludes setup and is insufficient to derive the invoice. Agree a job budget before submission. No new GPU jobs or Volumes were created for these local handoffs.

## Train readiness and interpretation

The train export used the historical 799 ViDoSeek training queries and 15,980 top-20 pairs. All 799 supplied page judgments are positive. Exactly 795 fell in the pool. The judged-only JSONL has 795 positives and zero negatives. Local and Modal dry plans for matched one-step base and Kev initialization are available. Khương and the team need a negative-label policy or explicitly judged negatives before using these inputs to compare trained rerankers. Unjudged pages were skipped.

The canonical ViDoSeek reference-page parser recovers the source document stem (src/qpaf/m13/vidoseek.py). Across train and validation there are 282 and 130 reference documents respectively, with 124 in common; 162/171 validation queries reference a training document. The original query-based cohort is preserved. Resampling validation queries by reference document gives a sensitivity interval for the observed ViDoSeek Qwen gain of [0.0096, 0.0793]. This does not turn the historical partition into document-disjoint evaluation.

## Local evidence index

Under `%USERPROFILE%/qpaf-cache/jev-phat/`:

| Directory | Verified output |
| --- | --- |
| vidoseek-validation-51c5b83 and vimdoc-validation-v1 | Each has pairs, gate/Qwen score files, splits, inventory, rebuild script, doctor and hash receipts. |
| qwen-vs-gate-gcwsd66a and vimdoc-validation-eval | Gate and Qwen evaluations and paired intervals. ViDoSeek also has the regression audit. |
| train-handoff-v1 | Train-only export and sidecar, matched dry plans, group map and document bootstrap sensitivity. |
| scoring-handoff | Verified historical BGE request slice and four Modal preview JSON files. |

Historical ViDoSeek gate/Qwen nDCG@10: 0.8683 / 0.9122 (difference +0.0439, query bootstrap interval [0.0121, 0.0768]). ViMDoc document nDCG@10: 0.9606 / 0.9552 (difference −0.0053, interval [−0.0182, 0.0069]). Both use matched frozen validation pools. Fresh Kev and full matched BGE results, measured GPU costs and team delivery acknowledgment remain pending.
