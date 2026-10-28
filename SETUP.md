# Profile stats setup

Copy `README.md`, `assets/`, `scripts/`, and `.github/workflows/profile-stats.yml` into the root of `NoyanAziz/NoyanAziz`.

The workflow runs daily at 04:23 UTC or on manual dispatch. Public statistics refresh automatically; private activity refreshes once its token is configured.

## Activity data access

This profile includes public and accessible private work as anonymous totals, as requested. The workflow defaults `INCLUDE_PRIVATE` to true. Configure the repository Actions secret `PROFILE_STATS_TOKEN` with a GitHub token that can read the relevant repositories and PR metadata. Access restrictions, including organization approval, determine coverage. Without that secret, the workflow preserves the existing activity snapshot and emits a notice rather than replacing private totals with an incomplete public-only snapshot.

Only line counts, PR counts, and weekly aggregates are included. Private repository names, PR titles, links, file paths, and source code are not saved to the generated assets. To switch back to public-only statistics, set the repository Actions variable `PROFILE_INCLUDE_PRIVATE` to `false`. The standalone script retains a public-only default unless `INCLUDE_PRIVATE=true` is explicitly provided.

The workflow token's `contents: write` permission is for committing generated assets; it doesn't grant access to private work elsewhere. A failed API request fails the refresh rather than overwriting activity with zeroes.

## Metric definitions

- **Lines added/deleted this year:** sums of `additions`/`deletions` from authored PRs whose `mergedAt` falls in the current UTC calendar year. Includes generated files, vendor files, and overlapping changes in separate PRs. Excludes direct commits without a PR and unmerged PRs. This is merged-PR diff volume, not unique source lines or productivity.
- **PRs opened this year:** authored PRs created in the current UTC calendar year, regardless of their current state.
- **PRs merged this year:** authored PRs merged in the current UTC calendar year, including PRs opened in earlier years.
- **Weekly PRs:** authored PRs created each Monday–Sunday UTC week, over the last 12 weeks. The final week is partial.
- **Public work stats:** public owned repositories and primary languages of non-fork repositories, excluding the profile repository from original project counts.

`assets/activity.json` contains only the aggregates used in the SVG. The current snapshot's scope is written on the image.

Data fields: [GitHub GraphQL PR reference](https://docs.github.com/en/graphql/reference/pulls).
