# Changelog

## 2026.10.18

Official optimizer image, build of 2026-10-18:

- Internal solver cleanup and updated dependencies (Python 3.14 base image); results are identical to the previous build on our test plans.
- The optional plain-language plan explanations were reworked; they stay off unless configured and evcc custom does not use them.
- Nothing to do for you.

## 2026.10.16

Official optimizer image, build of 2026-10-16:

- Faster solving: a hybrid solver combines CBC and HiGHS, and the allowed cost
  gap now scales with the size of the request (two cents by default).
- Requests with contradictory battery limits are answered with a clear error
  naming the field; an empty horizon is rejected instead of failing inside the
  model.
- Requests the solver cannot answer are logged for analysis.
- New optional endpoints for plain-language plan explanations; they are off
  unless configured and evcc custom does not use them.
- Nothing to do for you.

## 2026.10.4

Official optimizer image, build of 2026-10-04 (newest published). The previous
pin was a pre-release line of the same work; everything is now in the official
release:

- A vehicle already charging when the plan starts (`c_active`, sent by evcc
  0.316) is no longer treated as a new charging session.
- Fewer charging interruptions are preferred.
- A schedule that breaks the model is refused, whatever the solver reports.
- The cost bound is relaxed when the solver cannot hold it, and the cost stage
  no longer starves the tie break.
- Time per solve stage is capped and tuned (cost stage, continuity 2.5 s,
  split path with its own clock).
- Bad requests are logged with their cause; malformed json no longer fails.
- Nothing to do for you.

## 2026.9.14

- First version: official optimizer image, build of 2026-09-14, for evcc
  custom 0.316.0-lm1.
