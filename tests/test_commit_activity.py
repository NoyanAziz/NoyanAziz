import datetime as dt
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('commits', Path(__file__).resolve().parents[1]/'scripts/commit_activity.py')
commits = importlib.util.module_from_spec(spec)
spec.loader.exec_module(commits)


def commit(oid, author='NoyanAziz', date='2026-01-05T00:00:00Z', private=True, parents=1):
    return dict(oid=oid, authoredDate=date, additions=10, deletions=3,
                author={'user': {'login': author}}, parents={'totalCount': parents},
                repository={'isPrivate': private})


class CommitActivityTests(unittest.TestCase):
    now = dt.datetime(2026, 1, 6, 12, tzinfo=dt.timezone.utc)

    def test_counts_our_commit_on_someone_elses_pr_only(self):
        rows = [commit('ours'), commit('theirs', author='teammate')]
        result = commits.summarize(rows, [('pr-1', 'teammate', {'ours', 'theirs'})], set(), 'NoyanAziz', self.now, True)
        self.assertEqual(result, dict(commits_authored=1, lines_added=10, lines_deleted=3,
                                     prs_contributed=1, others_prs_contributed=1))

    def test_deduplicates_commits_across_prs_and_search(self):
        result = commits.summarize([commit('same')]*3,
            [('pr-1', 'NoyanAziz', {'same'}), ('pr-1', 'NoyanAziz', {'same'}),
             ('pr-2', 'teammate', {'same'})], set(), 'NoyanAziz', self.now, True)
        self.assertEqual((result['commits_authored'], result['lines_added'], result['prs_contributed']), (1, 10, 2))

    def test_ignores_merges_squash_results_old_future_and_other_authors(self):
        rows = [commit('good'), commit('merge', parents=2), commit('squash'),
                commit('old', date='2025-12-31T23:59:59Z'),
                commit('future', date='2026-01-07T00:00:00Z'), commit('other', author='other')]
        result = commits.summarize(rows, [], {'squash'}, 'NoyanAziz', self.now, True)
        self.assertEqual((result['commits_authored'], result['lines_added']), (1, 10))

    def test_public_filter_also_filters_pr_contribution_counts(self):
        rows = [commit('private'), commit('public', private=False)]
        result = commits.summarize(rows, [('private-pr', 'other', {'private'})], set(), 'NoyanAziz', self.now, False)
        self.assertEqual((result['commits_authored'], result['others_prs_contributed']), (1, 0))

    def test_missing_author_identity_is_not_attributed(self):
        row = commit('unlinked');row['author']['user'] = None
        self.assertEqual(commits.summarize([row], [], set(), 'NoyanAziz', self.now, True)['commits_authored'], 0)

    def test_search_splits_result_windows_instead_of_truncating(self):
        class API:
            def request(self, path):
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(path).query)['q'][0]
                if '2026-01-01..2026-01-02' in q:
                    return {'total_count': 1001, 'items': [], 'incomplete_results': False}
                return {'total_count': 1, 'items': [q], 'incomplete_results': False}
        results = list(commits.search_authored_commits(API(), 'NoyanAziz', dt.date(2026,1,1), dt.date(2026,1,2)))
        self.assertEqual(len(results), 2)

    def test_incomplete_search_fails_instead_of_publishing_partial_stats(self):
        class API:
            def request(self, path):
                return {'total_count': 1, 'items': [], 'incomplete_results': True}
        with self.assertRaises(RuntimeError):
            list(commits.search_authored_commits(API(), 'NoyanAziz', self.now.date(), self.now.date()))

    def test_finds_our_commit_after_first_page_of_colleagues_pr(self):
        class API:
            calls = 0
            def graphql(self, query, **variables):
                self.calls += 1
                if 'node(id:' in query:
                    return {'node': {'commits': {'nodes': [{'commit': commit('ours')}],
                            'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}
                return {'repository': {'pullRequests': {
                    'pageInfo': {'hasNextPage': False, 'endCursor': None},
                    'nodes': [{'id': 'colleague-pr', 'updatedAt': '2026-01-05T00:00:00Z',
                               'author': {'login': 'teammate'}, 'mergeCommit': None,
                               'commits': {'nodes': [{'commit': commit(str(i), author='teammate')} for i in range(100)],
                                           'pageInfo': {'hasNextPage': True, 'endCursor': 'next'}}}]}}}
        api = API()
        pr, rows = list(commits.repository_prs(api, 'example/work', '2026-01-01'))[0]
        result = commits.summarize(rows, [(pr['id'], pr['author']['login'], {r['oid'] for r in rows})],
                                   set(), 'NoyanAziz', self.now, True)
        self.assertEqual(api.calls, 2)
        self.assertEqual((result['commits_authored'], result['others_prs_contributed']), (1, 1))


if __name__ == '__main__':
    unittest.main()
