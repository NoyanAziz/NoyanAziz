# Profile stats setup

Copy `README.md`, `assets/`, `scripts/`, and `.github/workflows/profile-stats.yml` into the root of `NoyanAziz/NoyanAziz`.

The workflow runs daily at 04:23 UTC or on manual dispatch. Public statistics refresh automatically; private activity refreshes once its token is configured.

## Activity data access

This profile includes public and accessible private work as anonymous totals, as requested. The workflow defaults `INCLUDE_PRIVATE` to true. Configure the repository Actions secret `PROFILE_STATS_TOKEN` with a GitHub token that can read the relevant repositories and PR metadata. Access restrictions, including organization approval, determine coverage. Without that secret, the workflow preserves the existing activity snapshot and emits a notice rather than replacing private totals with an incomplete public-only snapshot.

Only line counts, PR counts, and weekly aggregates are included. Private repository names, PR titles, links, file paths, and source code are not saved to the generated assets. To switch back to public-only statistics, set the repository Actions variable `PROFILE_INCLUDE_PRIVATE` to `false`. The standalone script retains a public-only default unless `INCLUDE_PRIVATE=true` is explicitly provided.

The workflow token's `contents: write` permission is for committing generated assets; it doesn't grant access to private work elsewhere. A failed API request fails the refresh rather than overwriting activity with zeroes.

## Metric definitions

- **PR lines added/deleted:** full diffs of PRs I opened that merged in the current UTC year. This restores the original PR-volume definition. Includes collaborator changes, generated files and overlapping work across separate PRs. It is not attributed solely to my authored commits.
- **Commit lines added/deleted:** sums of additions/deletions for commits whose primary GitHub-linked author is this account and whose author timestamp is in the current UTC year. Includes commits on other people's PRs, whether merged or unmerged. Excludes merge commits (multiple parents). Deduplicates by commit SHA across search results, repositories and PRs. When a PR's original commits are scanned, its synthetic merge/squash result is excluded if it isn't one of those original commits. Generated/vendor files are included; this is change volume, not unique code or productivity. Co-author trailers alone do not qualify a commit.
- **Authored commits:** number of those unique eligible commits.
- **PRs contributed to:** distinct discovered PRs containing at least one eligible authored commit, regardless of who opened the PR or its state. The subset opened by others is shown separately. These PRs need not have been created this year.
- **PRs opened this year:** authored PRs created in the current UTC calendar year, regardless of their current state.
- **PRs merged this year:** authored PRs merged in the current UTC calendar year, including PRs opened in earlier years.
- **Weekly PRs:** authored PRs created each Monday–Sunday UTC week, over the last 12 weeks. The final week is partial.
- **Public work stats:** public owned repositories and primary languages of non-fork repositories, excluding the profile repository from original project counts.

PR change volume and commit change volume are separate metrics and must never be summed or substituted for each other.

## Commit discovery and coverage

The collector combines GitHub's authored-commit search with full commit pagination on recently updated PRs. It discovers repositories from indexed authored commits, this account's recent authored PRs, GitHub's contributed-repositories connection, and accessible private memberships active this year. PR scanning does not filter by PR author. This recovers work on colleagues' PRs, including original commits retained in squash-merged PR histories. Both PR and commit connections are fully paginated. Search windows are split when the 1,000-result limit is exceeded; incomplete responses fail the refresh.

This is an accessible-history snapshot, not a guarantee of every commit ever pushed. Unindexed commits on standalone branches without a discoverable PR, unlinked author email identities, deleted/inaccessible history, and public repositories not discovered through these sources may be absent. Distinct SHAs created by rebases or cherry-picks can represent overlapping work; there is no patch-level semantic deduplication.

`assets/activity.json` contains only the aggregates used in the SVG. The current snapshot's scope is written on the image.

Data fields: [GitHub GraphQL PR reference](https://docs.github.com/en/graphql/reference/pulls) and [GitHub commit API](https://docs.github.com/en/rest/commits/commits).
