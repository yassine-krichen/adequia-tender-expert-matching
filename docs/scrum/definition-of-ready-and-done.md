# Definition of Ready & Definition of Done

Shared by all 4 sprint plans — referenced, not repeated.

## Definition of Ready (DoR)

A story can enter a sprint only if:

- [ ] Acceptance criteria are written and understood
- [ ] The story is sized (points assigned, using the `1 2 3 5 8` scale from `docs/10-scrum-github-workflow.md`) — if it feels bigger than an 8, it's an epic or needs splitting first
- [ ] Dependencies are identified — flagged `blocked` or `needs-company-input` if it waits on something outside the sprint
- [ ] There's no open question that would block starting work today
- [ ] If it touches the pipeline: the eval metric it will be checked against is known in advance, not decided after the fact
- [ ] If it's user-facing: the tooltip/explanation requirement from `docs/05-frontend-dashboard.md`'s UX principles is noted, not silently deferred

## Definition of Done (DoD)

Reused verbatim from `docs/10-scrum-github-workflow.md`. An issue isn't Done until:

- [ ] Code is merged to `main` (or the relevant feature branch is merged)
- [ ] Lint/type checks pass in CI
- [ ] If it touches the pipeline: relevant eval metric checked, not just "it ran"
- [ ] If it's user-facing: has a tooltip/explanation per the UX principles in `docs/05-frontend-dashboard.md`, not just a raw number on screen
- [ ] Noted in the sprint log
