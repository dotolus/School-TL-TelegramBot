# DevOps Guidelines

This document tracks DevOps, CI/CD, and release-process requirements for this project — branch policy, pipelines, deployments, infrastructure, environments, secrets. See CLAUDE.md for the rule that keeps this file current.

## Branch protection

- `main` is protected: no direct pushes. Changes land via pull request.
- Once a GitHub remote exists, configure a branch protection rule on `main` requiring PR review and passing status checks before merge.
- **Blocked:** the repo (`dotolus/SchoolAtmosphere`) is private, and GitHub's branch protection API requires GitHub Pro or the repo being public on a private repo under the free plan. `main` is currently **not** protected on GitHub. To unblock: upgrade to GitHub Pro, or make the repo public, then re-apply the rule (no PR reviews required, admin may bypass — per the earlier decision for solo work; no required status checks until CI exists).

## CI / Testing

- After each push of a branch to GitHub, run all available automated tests.
- **Status: not yet implemented.** The project has no code/language chosen yet (see CLAUDE.md), so there is no test suite and no CI workflow. Once tests exist:
  - Add a GitHub Actions workflow that runs the full test suite on every push.
  - Add that workflow as a required status check on the `main` branch protection rule above.

## Open items

- [ ] Create the GitHub remote and push
- [ ] Add CI workflow once a test suite exists
- [ ] Enable the `main` branch protection rule (requires the GitHub remote to exist)
