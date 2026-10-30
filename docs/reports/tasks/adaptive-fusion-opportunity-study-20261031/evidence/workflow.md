# Workflow provenance

Started: 2026-10-31, Asia/Saigon.
Authorization: user's research request on conditions/datasets favoring QPAF/QARF, followed by “Deep search đi”.
Workspace: C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project.
Branch at start: feature/lab-f3-objective, clean working tree; no branch switch planned for documentation research.
Task bundle: docs/reports/tasks/adaptive-fusion-opportunity-study-20261031.

## Skills read and selected

Superpowers package: C:/Users/lanph/.codex/plugins/cache/openai-curated-remote/superpowers/7.0.1/skills/
- using-superpowers/SKILL.md: initial workflow selection; codex-tools reference previously read in this conversation.
- brainstorming/SKILL.md: clarify and explore the research intent; user explicitly requested recon.
  This is research and design discussion, not approval to build a new experiment.
- writing-plans/SKILL.md: proportional, checkable research plan with canonical owner paths.
- dispatching-parallel-agents/SKILL.md: independent primary-literature and benchmark investigations.
- verification-before-completion/SKILL.md: read and applied to source/local-evidence integrity, report links/layout,
  source-edit isolation and handoff hashes. Research artifacts are checked directly; no production test suite rerun.

## Scope

No new training, paid compute, sealed labels, corpus/model downloads, or production edits.
Existing F3 results remain unchanged. Primary-source findings are separate from hypotheses and toy examples.
Current paper/protocol scope is preserved; any additional dataset is a proposed extension.

## Initial local observations

F1 documentation says 12/13 gate inputs derive from the three channel scores, plus query length.
F4 proposes query embeddings to expose question semantics; neither idea is a measured result in the F3 run.
## Actual research and verification

- Twenty-one primary-source cards recorded in sources.json and sources.md; two focused agent reports integrated.
- Executor directly opened core papers/cards, including UniDoc Table7, ViDoRe V3, MMDocIR release/body,
  mFAR, DAT, GQR, MIDR, DocRetriever and the two recent methodological preprints.
- Publisher DRAG direct fetch returned HTTP429. Indexed official publisher text supports the mechanism;
  numerical ablation claims are deliberately excluded.
- Read-only recomputation of existing M4.4 validation oracle CSV: W66 global0.871743, query0.911900,
  page0.940125; 20/171 queries have strictly higher page-oracle nDCG than query oracle.
- Existing oracle implementation uses two coordinate sweeps. It is label-using and not certified globally optimal;
  it is not compared numerically to the separate 970-query F3 CV result as if the populations were identical.
- Original toy checked numerically and analytically; nonlinear max-score also solves it, so it does not prove QPAF novelty.
- Finance metadata records materialization and a sealed-external role; this does not establish whether later tuning happened.
  Prior exposure needs auditing before labeling it fresh external validation.
- Dataset/protocol review of the completed report found no material correction; see domain-review.md.
- No new experiment, dataset/model payload download, cloud compute, sealed-label inspection, or source-code change.
- Recommendations are proposals, not approved implementation or new claims that QPAF has won.
- Native branch remains feature/lab-f3-objective. Initial source commit82958a6; current F3 result bundle remains unchanged.
- Final validation checks exact bundle layout, local links, JSON/source provenance, old F3 hashes, source-edit isolation,
  mathematical toy and the research hash manifest.
- Generated research JSON is standardized to LF before hashing; the validator writes LF explicitly so Windows newline
  conversion does not fail the staged whitespace check. Prior F3 evidence is not rewritten.
