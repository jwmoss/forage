import { test, expect } from 'e2e';
import { readFile, writeFile, chmod, rm, access, symlink, stat } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { join, resolve } from 'node:path';
import { workspace, scrape } from './support';

const execute = promisify(execFile);
let w: Awaited<ReturnType<typeof workspace>>;
test.beforeEach(async () => { w = await workspace(); });
test.afterEach(async () => { await w?.close(); });

async function success(args: string[], stdin = '') {
  const result = await w.run(args, stdin);
  expect(result.code, result.stderr).toBe(0);
  expect(result.stderr).not.toContain('Traceback');
  return result;
}
async function json(args: string[], stdin = '') { return JSON.parse((await success(args, stdin)).stdout); }
async function failure(args: string[], code: number, message: string, stdin = '') {
  const result = await w.run(args, stdin);
  expect(result.code, `${result.stdout}\n${result.stderr}`).toBe(code);
  expect(result.stdout).toBe('');
  expect(result.stderr).toContain(message);
  expect(result.stderr).not.toContain('Traceback');
}
async function absent(path: string) { expect(await access(path).then(() => false, () => true)).toBe(true); }
async function artifact(kind: string, path: string) {
  return JSON.parse((await execute(resolve('.venv/bin/python'), [resolve('tests/e2e/artifact.py'), kind, path], { timeout: 5000 })).stdout);
}
function savedResult() {
  return {
    group: { id: 'saved-group', name: 'Saved Neighbors', url: 'https://www.facebook.com/groups/saved-group' },
    scraped_at: '2026-10-04T12:00:00', date_range: { since: '2026-10-01', until: '2026-10-03' },
    posts: [{ id: 'saved-post', author: { name: 'Alex Example' }, content: 'Looking for a café, tired of queues?\nI need advice.', timestamp: '2026-10-03T23:00:00', reactions: { total: 12 }, comments_count: 2, comments: [
      { id: 'saved-comment', author: { name: 'Pat Example' }, content: 'Go to "River Café", near the park.\nIt is quick.', reactions: { total: 7 }, replies: [{ id: 'saved-reply', author: { name: 'Sam Example' }, content: 'I agree, thanks!', reactions: { total: 2 } }] },
      { id: 'saved-low', author: { name: 'Lee Example' }, content: 'A lower ranked option.', reactions: { total: 1 } },
    ] }, { id: 'saved-neutral', author: { name: 'Casey Example' }, content: 'Picnic at the park this weekend.' }],
  };
}
async function source() { const path = join(w.dir, 'source.json'); await writeFile(path, JSON.stringify(savedResult())); return path; }

// These flows use separate installed CLI processes. Browser routes replace the
// Facebook HTTP boundary only; all parsing, filtering, and exports remain real.
test('saved JSON export needs no session and preserves nested data in stdout and files', async () => {
  await rm(w.session, { recursive: true });
  const input = await source();
  const got = await json(['export', input]);
  expect(got.group.name).toBe('Saved Neighbors');
  expect(got.posts[0].comments[0].replies[0].id).toBe('saved-reply');
  const output = join(w.dir, 'copy.json');
  expect((await success(['-q', 'export', input, '-o', output])).stdout).toBe('');
  expect(JSON.parse(await readFile(output, 'utf8'))).toEqual(got);
  expect(w.requests).toHaveLength(0);
});

test('saved CSV export creates readable posts and nested comment rows with correct quoting', async () => {
  const input = await source(), output = join(w.dir, 'posts.csv');
  await success(['export', input, '-f', 'csv', '-o', output]);
  const posts = await artifact('csv', output), comments = await artifact('csv', join(w.dir, 'posts.comments.csv'));
  expect(posts.map((p: any) => p.post_id)).toEqual(['saved-post', 'saved-neutral']);
  expect(posts[0].content).toBe('Looking for a café, tired of queues?\nI need advice.');
  expect(comments.map((c: any) => c.comment_id)).toEqual(['saved-comment', 'saved-reply', 'saved-low']);
  expect(comments[0].content).toBe('Go to "River Café", near the park.\nIt is quick.');
  expect(comments[1].parent_comment_id).toBe('saved-comment');
  expect(comments[1].post_id).toBe('saved-post');
  expect(w.requests).toHaveLength(0);
});

test('saved SQLite export persists relationships and updates records without duplicates', async () => {
  const input = await source(), output = join(w.dir, 'posts.db');
  await success(['export', input, '-f', 'sqlite', '-o', output]);
  const updated = savedResult(); updated.posts[0].content = 'Updated café advice.';
  await writeFile(input, JSON.stringify(updated));
  await success(['export', input, '-f', 'sqlite', '-o', output]);
  const db = await artifact('sqlite', output);
  expect(db.groups).toHaveLength(1); expect(db.posts).toHaveLength(2); expect(db.comments).toHaveLength(3);
  expect(db.posts.find((p: any) => p.id === 'saved-post').content).toBe('Updated café advice.');
  expect(db.comments.find((c: any) => c.id === 'saved-reply').parent_comment_id).toBe('saved-comment');
  expect(db.comments.every((c: any) => c.post_id === 'saved-post')).toBe(true);
});

test('saved LLM export filters pain signals, sorts top comments, and keeps file and stdout output equal', async () => {
  const input = await source(), output = join(w.dir, 'compact.json');
  const args = ['export', input, '-f', 'llm', '--top-comments', '1', '--min-pain-score', '2'];
  const got = await json(args);
  expect(got.posts.map((p: any) => p.id)).toEqual(['saved-post']);
  expect(got.posts[0].top_comments).toEqual([{ content: 'Go to "River Café", near the park.\nIt is quick.', reactions: 7 }]);
  expect(got.metadata.stats.post_count).toBe(1);
  expect(got.metadata.stats.total_reactions).toBe(12);
  await success([...args, '-o', output]);
  expect(JSON.parse(await readFile(output, 'utf8'))).toEqual(got);
});

test('malformed saved input and invalid options return clear errors before browser or filesystem work', async () => {
  const invalid = join(w.dir, 'bad.json');
  for (const body of ['{broken', '{}', '{"query":"marketplace result"}']) {
    await writeFile(invalid, body);
    await failure(['export', invalid], 1, 'Input is not a group scrape JSON result');
  }
  const cases = [
    ['scrape', 'fixture', '--limit', '-1'], ['scrape', 'fixture', '--delay', '-1'], ['scrape', 'fixture', '--days', '-1'],
    ['scrape', 'fixture', '--since', 'bad'], ['scrape', 'fixture', '--since', '2026-10-04', '--until', '2026-10-01'],
    ['scrape', 'fixture', '-f', 'csv'], ['scrape', 'fixture', '-f', 'sqlite'], ['scrape', 'fixture', '-f', 'invalid'],
    ['scrape', 'fixture', '--browser', 'invalid'], ['marketplace', 'card', '--radius', '3'], ['marketplace', 'card', '--limit', '0'],
    ['marketplace', 'card', '--max-candidates', '0'], ['export', invalid, '-f', 'sqlite'], ['export', invalid, '--top-comments', '-1'],
    ['login', '--browser', 'invalid'], ['export', join(w.dir, 'absent.json')], ['unknown'],
  ];
  for (const args of cases) await failure(args, 2, 'Error:');
  await failure(['scrape', '-', '--no-input'], 2, 'Empty input', ' \n\n');
  expect(w.requests).toHaveLength(0);
});

test('non-UTF8 saved input returns a handled error without traceback', async () => {
  const invalid = join(w.dir, 'encoding.json'); await writeFile(invalid, Buffer.from([0xff, 0xfe]));
  const output = join(w.dir, 'existing.json'); await writeFile(output, 'keep existing data');
  await failure(['export', invalid, '-o', output], 1, 'Input is not a group scrape JSON result');
  expect(await readFile(output, 'utf8')).toBe('keep existing data');
});

test('login creates a private browser session and fresh CLI processes consume it', async () => {
  await rm(w.session, { recursive: true });
  await absent(w.sessionFile);
  w.state.mode = 'login-authenticated';
  const result = await success(['login'], '\n');
  expect(result.stdout).toBe('');
  expect(result.stderr).toContain('Session saved successfully');
  expect(result.stderr).not.toContain('synthetic-login-user');
  const bytes = await readFile(w.sessionFile, 'utf8');
  const state = JSON.parse(bytes);
  expect(state.cookies).toEqual([{ name: 'c_user', value: 'synthetic-login-user', domain: 'www.facebook.com', path: '/', expires: -1, httpOnly: false, secure: true, sameSite: 'Lax' }]);
  expect(state.origins).toEqual([{ origin: 'https://www.facebook.com', localStorage: [{ name: 'fixture-login-marker', value: 'created-through-browser' }] }]);
  expect((await stat(w.sessionFile)).mode & 0o777).toBe(0o600);
  expect((await stat(w.session)).mode & 0o777).toBe(0o700);
  expect(w.requests.map(r => r.path)).toContain('/login');
  expect(w.requests.find(r => r.path === '/')?.cookie).toContain('c_user=synthetic-login-user');
  const count = w.requests.length;
  const doctor = await json(['doctor']);
  expect(doctor.session_path).toBe(w.sessionFile);
  expect(doctor.session_exists).toBe(true);
  expect(doctor.session_permissions_private).toBe(true);
  expect(doctor.session_validity).toBe('not_checked');
  expect(w.requests.length).toBe(count);
  const scraped = await json([...scrape, '--limit', '1', '--skip-comments']);
  expect(scraped.posts[0].id).toBe('101');
  expect(w.requests.find(r => r.path === '/groups/fixture')?.cookie).toContain('c_user=synthetic-login-user');
  expect(await readFile(w.sessionFile, 'utf8')).toBe(bytes);
  const selected = join(w.dir, 'selected-session');
  await success(['login', '--session-dir', selected], '\n');
  expect(JSON.parse(await readFile(join(selected, 'storage_state.json'), 'utf8')).cookies[0].value).toBe('synthetic-login-user');
  expect((await stat(join(selected, 'storage_state.json'))).mode & 0o777).toBe(0o600);
  expect((await stat(selected)).mode & 0o777).toBe(0o700);
  expect(await readFile(w.sessionFile, 'utf8')).toBe(bytes);
  expect((await json(['doctor', '--session-dir', selected])).session_path).toBe(join(selected, 'storage_state.json'));
});

test('failed login creates no session and cannot overwrite an existing saved session', async () => {
  const original = await readFile(w.sessionFile, 'utf8');
  const newSession = join(w.dir, 'new-session');
  w.state.mode = 'login-denied';
  await failure(['login', '--session-dir', newSession], 3, 'Login not detected', '\n');
  await absent(join(newSession, 'storage_state.json'));
  expect(w.requests.map(r => r.path)).toContain('/login');
  expect(w.requests.find(r => r.path === '/')?.cookie).toBe('');
  await failure(['login'], 3, 'Login not detected', '\n');
  expect(await readFile(w.sessionFile, 'utf8')).toBe(original);
  const doctor = await json(['doctor']);
  expect(doctor.session_exists).toBe(true);
  expect(doctor.session_permissions_private).toBe(true);
});

test('doctor distinguishes absent and insecure session files without network access', async () => {
  expect((await success(['--version'])).stdout).toContain('2.1.0');
  const healthy = await json(['doctor']);
  expect(healthy.session_path).toBe(w.sessionFile); expect(healthy.session_exists).toBe(true);
  expect(healthy.browser_installed).toBe(true); expect(healthy.session_permissions_private).toBe(true);
  expect(healthy.session_validity).toBe('not_checked');
  await chmod(w.sessionFile, 0o644);
  const insecure = await w.run(['doctor']); expect(insecure.code).toBe(1); expect(JSON.parse(insecure.stdout).session_permissions_private).toBe(false);
  await rm(w.sessionFile);
  const missing = await w.run(['doctor']); expect(missing.code).toBe(1); expect(JSON.parse(missing.stdout).session_exists).toBe(false);
  await failure(['scrape', 'fixture', '--no-input'], 3, "forage login");
  await failure(['marketplace', 'card'], 3, "forage login");
  const link = join(w.dir, 'session-link'); await symlink(w.session, link);
  await failure(['login', '--session-dir', link], 1, 'symbolic links');
  expect(w.requests).toHaveLength(0);
});

test('group scrape parses a real feed, filters dates, keeps comments, and reports a partial date boundary', async () => {
  const got = await json(scrape);
  expect(got.group).toEqual({ id: 'fixture', name: 'Fixture Neighbors', url: 'https://www.facebook.com/groups/fixture' });
  expect(got.posts.map((p: any) => p.id)).toEqual(['101', '102']);
  expect(got.posts[0].content).toBe('Looking for a café, tired of queues?\nHelp me find a better option.');
  expect(got.posts[0].timestamp).toBe('2026-10-03T23:00:00');
  expect(got.posts[0].comments.map((c: any) => c.id)).toEqual(['201', '202']);
  expect(got.posts[0].reactions.total).toBe(12);
  expect(got.diagnostics.stop_reason).toBe('date_boundary'); expect(got.diagnostics.rejected_count).toBe(5);
  expect(got.diagnostics.partial).toBe(true);
  expect(w.requests[0].query.get('sorting_setting')).toBe('CHRONOLOGICAL');
  expect(w.requests.every((r) => r.cookie.includes('c_user=synthetic-user'))).toBe(true);
});

test('scrape accepts stdin group URLs, respects limits, and saves skip/filter options in real output', async () => {
  const output = join(w.dir, 'scrape.json');
  const args = [...scrape]; args[1] = '-';
  await success(['-q', ...args, '--limit', '1', '--skip-comments', '--skip-reactions', '-o', output], '\nhttps://www.facebook.com/groups/fixture?ref=share\nignored-second-line\n');
  const got = JSON.parse(await readFile(output, 'utf8'));
  expect(got.posts.map((p: any) => p.id)).toEqual(['101']); expect(got.posts[0].comments).toEqual([]);
  expect(got.posts[0].reactions.total).toBe(0); expect(got.diagnostics.stop_reason).toBe('limit');
  const filtered = await json([...scrape, '--limit', '1', '--min-reactions', '3', '--top-comments', '1']);
  expect(filtered.posts[0].comments.map((c: any) => c.id)).toEqual(['201']);
});

test('scrape follows lazy feed pages, removes duplicate identities, and expands full content', async () => {
  w.state.mode = 'pagination';
  const got = await json([...scrape, '--skip-comments']);
  expect(got.posts.map((p: any) => p.id)).toEqual(['101', '102']);
  expect(w.requests.some((r) => r.path === '/fixture-next')).toBe(true);
  expect(got.diagnostics.candidates_seen).toBe(7);
  w.state.mode = 'expansion';
  const expanded = await json([...scrape, '--limit', '1', '--skip-comments']);
  expect(expanded.posts[0].content).toBe('Expanded full content with a useful answer.');
  expect(expanded.posts[0].content_truncated).toBe(false);
});

test('scrape retrieves dedicated permalink comments with nested replies and exports live LLM data', async () => {
  w.state.mode = 'permalink';
  const got = await json([...scrape, '--limit', '1']);
  expect(got.posts[0].comments.map((c: any) => c.id)).toEqual(['211', '213']);
  expect(got.posts[0].comments[0].replies[0].id).toBe('212');
  expect(w.requests.some((r) => r.path === '/groups/fixture/posts/103')).toBe(true);
  w.state.mode = 'feed';
  const compact = await json([...scrape, '--limit', '1', '-f', 'llm', '--min-pain-score', '2', '--top-comments', '1']);
  expect(compact.posts.map((p: any) => p.id)).toEqual(['101']);
  expect(compact.posts[0].top_comments[0].reactions).toBe(7);
});

test('scrape retains unknown timestamps and distinguishes verified empty data from auth and layout errors', async () => {
  w.state.mode = 'unknown-time';
  const got = await json([...scrape, '--skip-comments']);
  expect(got.posts[0].id).toBe('105'); expect(got.posts[0].timestamp).toBe(null); expect(got.diagnostics.unknown_timestamps).toBe(1);
  w.state.mode = 'empty';
  const empty = await json([...scrape, '--skip-comments']);
  expect(empty.posts).toEqual([]); expect(empty.diagnostics.stop_reason).toBe('empty'); expect(empty.diagnostics.partial).toBe(false);
  w.state.mode = 'expired'; await failure([...scrape, '--limit', '1'], 3, 'refresh your session');
  w.state.mode = 'missing-layout'; await failure([...scrape, '--limit', '1'], 1, 'feed is missing');
});

test('corrupt session data fails without a browser request or output artifact', async () => {
  await writeFile(w.sessionFile, '{broken');
  const output = join(w.dir, 'failed.json');
  await failure([...scrape, '-o', output], 1, 'Error:');
  await failure(['marketplace', 'card', '-o', output], 1, 'Error:');
  await absent(output); expect(w.requests).toHaveLength(0);
});

test('Marketplace verifies listing locations, counts accepted limits, and bounds rejected candidates', async () => {
  const args = ['marketplace', 'graphics & card', '--city', 'wilmington', '--radius', '40'];
  const got = await json([...args, '--limit', '1']);
  expect(got.listings.map((l: any) => l.id)).toEqual(['302']);
  expect(got.listings[0].title).toBe('Local graphics card'); expect(got.listings[0].price).toBe('$100');
  expect(got.diagnostics.candidates_seen).toBe(2); expect(got.diagnostics.rejected_count).toBe(1); expect(got.diagnostics.stop_reason).toBe('limit');
  expect(w.requests[0].query.get('query')).toBe('graphics & card');
  expect(w.requests[0].query.get('sortBy')).toBe('creation_time_descend'); expect(w.requests[0].query.get('category')).toBe('electronics');
  const output = join(w.dir, 'marketplace.json');
  await success(['-q', ...args, '--limit', '3', '--max-candidates', '3', '-o', output]);
  const bounded = JSON.parse(await readFile(output, 'utf8'));
  expect(bounded.listings.map((l: any) => l.id)).toEqual(['302']);
  expect(bounded.diagnostics.rejected_count).toBe(2); expect(bounded.diagnostics.stop_reason).toBe('candidate_limit');
});

test('Marketplace output filesystem errors return handled diagnostics without a traceback', async () => {
  const output = join(w.dir, 'missing', 'result.json');
  await failure(['marketplace', 'card', '--limit', '1', '-o', output], 1, 'Error:');
  await absent(output);
  const existing = join(w.dir, 'existing.json'); await writeFile(existing, 'keep existing data'); await chmod(existing, 0o400);
  await failure(['marketplace', 'card', '--limit', '1', '-o', existing], 1, 'Error:');
  expect(await readFile(existing, 'utf8')).toBe('keep existing data');
});

test('Marketplace rejects expired sessions and missing location data and recognizes verified empty results', async () => {
  w.state.mode = 'expired'; await failure(['marketplace', 'card', '--limit', '1'], 3, 'refresh your session');
  w.state.mode = 'missing-center'; await failure(['marketplace', 'card', '--limit', '1'], 1, 'search location');
  w.state.mode = 'missing-layout'; await failure(['marketplace', 'card', '--limit', '1'], 1, 'results are missing');
  w.state.mode = 'empty'; const got = await json(['marketplace', 'card', '--limit', '1']);
  expect(got.listings).toEqual([]); expect(got.diagnostics.stop_reason).toBe('empty'); expect(got.diagnostics.partial).toBe(false);
});

test('scrape export errors preserve stderr diagnostics and produce no misleading JSON output', async () => {
  await failure([...scrape, '--limit', '1', '--skip-comments', '-o', join(w.dir, 'missing', 'file.json')], 1, 'Error:');
  const input = await source();
  for (const format of ['json', 'csv', 'sqlite', 'llm']) await failure(['export', input, '-f', format, '-o', join(w.dir, 'missing', `file.${format}`)], 1, 'Error:');
});

test('navigation failure retries real browser requests and returns a non-success exit', async () => {
  w.state.mode = 'transport';
  await failure(['marketplace', 'card', '--limit', '1'], 1, 'ERR_CONNECTION_REFUSED');
  expect(w.requests).toHaveLength(4);
});

test('live scrape CSV and SQLite artifacts contain parsed feed data', async () => {
  for (const format of ['csv', 'sqlite']) {
    const output = join(w.dir, `live.${format === 'csv' ? 'csv' : 'db'}`);
    await success([...scrape, '--limit', '1', '--skip-comments', '-f', format, '-o', output]);
    const data = await artifact(format, output);
    if (format === 'csv') {
      expect(data[0].post_id).toBe('101'); expect(data[0].author_name).toBe('Alex Example');
      expect(await artifact('csv', join(w.dir, 'live.comments.csv'))).toEqual([]);
    } else {
      expect(data.posts[0].id).toBe('101'); expect(data.groups[0].name).toBe('Fixture Neighbors');
      expect(data.comments).toEqual([]);
    }
  }
});

test('denied groups and unparseable feed articles fail instead of returning an empty success', async () => {
  w.state.mode = 'denied'; await failure([...scrape, '--skip-comments'], 4, 'Group not found or access denied');
  w.state.mode = 'parse-failure'; await failure([...scrape, '--skip-comments'], 1, 'no posts parse');
});

test('Marketplace follows lazy result pages before applying the accepted-listing limit', async () => {
  w.state.mode = 'market-pagination';
  const got = await json(['marketplace', 'card', '--limit', '1']);
  expect(got.listings.map((l: any) => l.id)).toEqual(['302']);
  expect(got.diagnostics.candidates_seen).toBe(2); expect(got.diagnostics.rejected_count).toBe(1);
  expect(w.requests.some((r) => r.path === '/fixture-marketplace-next')).toBe(true);
});
