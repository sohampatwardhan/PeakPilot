# PeakPilot — Change Workflow Steering

How work moves from idea to `main`. Applies to humans and agents.

## New tasks and major changes

A major change is a new feature, a behavior change in the engine or dashboard, a new
dependency, or a change to these steering rules.

1. **GitHub issue.** Open an issue in `sohampatwardhan/PeakPilot` stating the problem,
   the proposed change, and acceptance criteria. Record the issue number.
2. **Kiro spec.** Write `.kiro/specs/<feature>/{requirements.md,design.md,tasks.md}` in the
   format of `.kiro/specs/peakpilot/`, and link the issue number at the top. Size it to
   the change: a one-page requirements file and a short task list are often enough.
3. **Branch.** Branch from `main` (not from another open feature branch), named
   `feat/<topic>`, `fix/<topic>`, or `docs/<topic>`. Use a git worktree under
   `.worktrees/<topic>` when another branch is checked out in the main checkout.
4. **Pull request.** Open a PR against `main`. The body includes `Closes #<issue>`, a short
   summary, and the test results. Keep the spec in the same PR as the code it describes.
5. **Merge.** Merge only when CI is green and the user has confirmed. Use a merge commit
   (`gh pr merge --merge`), matching earlier PRs. Confirm the issue closed automatically.

## Small changes

Bug fixes, typo fixes, and small doc or config tweaks skip the spec. They still get an
issue (or reference an existing one) and go through a branch and PR.

## Never

- Commit directly to `main`.
- Stack unrelated work on an open feature branch to save time.
- Merge with failing CI, or merge without the user's go-ahead.
