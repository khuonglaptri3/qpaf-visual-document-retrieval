# Reconstructing review packages

Review findings and implementation reports are delivered in `sdd/`. Full generated diff packages remain local scratch to avoid embedding earlier diffs recursively. These commands reproduce their source ranges from the shared commit ancestry included in every owner branch.

```bash
git diff -U10 e5060b4 c56acf2
git diff -U10 c56acf2 e108880
git diff -U10 e108880 d8df055
git diff -U10 d8df055 710c7e4
```

The third and fourth commands reproduce Task 2 fix rounds one and two respectively. Later review reports name their exact base and head. Use `git log --oneline BASE..HEAD` and `git diff --stat BASE HEAD` alongside a diff to reconstruct the package metadata. SHA values in older reports describe the exact historical commit named by that report, rather than the latest file after subsequent fixes.

During delivery, the controller replaced hyperlinks to ignored diff scratch with this reconstruction page. Findings, verdicts and source ranges were preserved.
