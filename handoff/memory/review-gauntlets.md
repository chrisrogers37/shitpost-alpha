---
name: review-gauntlets
description: Chris's standing ask (10-02) for simplify/review/verify gauntlets on every PR; who runs them, where findings go, sandbox setup for running them
metadata:
  type: project
  modified: 2026-10-02T19:53:58.685Z
---

Chris 2026-10-02 13:29 UTC: "For all chunks of work, can you orchestrate simplify, review, and verify completion gauntlets against each, and have the implementer fold in feedback and findings?" Standing ask for every PR.

- Runner: thread "Review gauntlets" (thread cmsg_01Ru8H43VFwFbPoWty16Gd6hDMWtqXa7ofRr7WhgV1zgrp, session_013E4KMGG5c9USVygEcNJkqa). Builders send it a note when their PR's CI is green; it runs three fresh subagents (simplify = built-in simplify lens, report-only on a scratch checkout; review = built-in code-review high + clauDNA review-work dimensions; verify = clauDNA verify-completion vs the brief, lint/mypy/pytest on sandbox Postgres, CLI behaviour checks).
- Output: /mnt/project-files/reviews/pr-<number>-round-<n>.md (file:line, problem, fix, which pass). Sent to the builder by send_message; builder folds in, pushes, says so; runner re-verifies whole PR + reviews new commits; repeats until clean; tells builder "passed"; builder posts in its thread, coordinator tells Chris.
- Runner never pushes to a builder's branch, never merges, never comments on GitHub (account posts as Chris). A declined finding with an accepted reason is closed. Clean-slate rule: no finding asks for compatibility with old code.
- Stacked PRs (#259 on #258): review only the PR's own commits until the base merges.
- Sandbox: clauDNA readable by anonymous git clone (https://github.com/Claudfather/claudna -> /home/user/claudfather/claudna), skills verify-completion, review-work (pr.md, review-dimensions.md, severity-categories.md). One venv per PR head (`python -m venv /home/user/engine-venv-<pr>; pip install -e "<worktree>/engine[dev]"`), git worktrees in the scratchpad. Postgres: `service postgresql start`, role shitpost (superuser) and DEV_DATABASE_URL; engine tests make throwaway DBs, safe to run in parallel.

State 2026-10-02 ~21:00 UTC (files /mnt/project-files/reviews/pr-<n>-round-<k>.md):
- #258 PR 1: PASSED at 201e01e (round 4 + 9 nits; F6 code and F9 declined, accepted). PR 2/3 need merge-only checks once they bring in 201e01e.
- #259 PR 2: PASSED at edbbc13 (round 5), still passes at 0235161 (merge of PR 1 201e01e + test_live flake fix); only a re-merge check if PR 1 pushes again.
- #260 PR 3: PASSED at b1c18e5 (round 4), still passes at a2493db (merges of PR 1 201e01e and PR 2 0235161); only a re-merge check if PR 1 pushes again. Builder session_018SyJAjgwB3XPJPjSHcuKjy.
- #261 PR 4 (stacked on #260; builder session_01JBFZ9aCZzXyN2bHi1j66ZX; B2 thread session_01CKsfdxBWbhTzpVq6SuL2dv also commits): round 2 sent at 4554d3d; round 3 SENT 00:20 at 178bbab: one should-fix left (S1 golden request-body test per provider), nits optional; Q2 (re-vote stored answers with 178bbab code, confirm row A) sent to B2 (fixes 57257a8 + B2 freeze cdd6411/eb48824/a784773; two-model "both agree" picker = option A, check approval). S3 reason words declined to PR 6; planner items for PR 5/6/7 sent to coordinator 23:05 and 23:30. Model at /home/user/engine-models; venv /home/user/engine-venv-261.
- #262 site D0 (stacked on #258 at 201e01e; builder session_01RZbykYzTehMFWUPpX7udYu): round 1 sent 23:35 at 7970317; builder folded all in at aac1f51 (incl. check_role startup guard, HealthProbe); ROUND 2 running 00:00 (probes need `-p tests.conftest -p tests.web.conftest`). Venv /home/user/engine-venv-262.
- #263 PR 5 Part A (stacked on #261 at 178bbab; builder session_018aHus6fRKr8MXrhfZGQf9u; branch claude/engine-pr5-9qgvyy): round 1 started 23:50 at b267c39 (own diff 178bbab..b267c39). Venv /home/user/engine-venv-261 (no new deps). Part B (real run) not in scope yet.
- Container restarted ~23:28 (killed a running agent; Postgres needed a start): re-launch lost agents with their transcript prompt.
- Lessons: REAL keys are in the sandbox env (ENGINE_OPENAI/ANTHROPIC/XAI_KEY, ALPACA_*, AWS_*): every agent prompt must forbid printing env values (no env/printenv; test with ${VAR+x}) and strip all of them (a PR 4 round-2 agent printed the AI keys 10-02 ~23:00; coordinator told, rotation suggested). key leaks via h11 "Illegal header value" text (strip/validate keys, scrub error text); combine review+verify into one agent once a delta is small; a leftover superuser role `engine` sits on the sandbox Postgres (drop was denied; harmless); sandbox Postgres can stop mid-session (`service postgresql start`); `rm -rf` in Bash is denied, use new dir names.

Coordinator session moved to session_01SfupL5JcEyRaeQCTedFkS3 (10-02 ~23:30; get_channel_session_id gives cse_ form).

Related: [[plan-stage]], [[engine-pr2-build]]
