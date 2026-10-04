import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { homedir, tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

function comment(id: string, text: string, reactions: number, replies = '') {
  return `<article role="article" aria-label="Comment by Pat Example"><a role="link" href="https://www.facebook.com/pat"><strong>Pat Example</strong></a><div dir="auto">${text}</div><a href="?comment_id=${id}">Reply</a><span aria-label="${reactions} reactions">${reactions}</span>${replies}</article>`;
}
function post(id: string, date: string, text: string, comments = '') {
  return `<article role="article"><a role="link" href="https://www.facebook.com/alex"><strong>Alex Example</strong></a><a href="/groups/fixture/posts/${id}" aria-label="${date}">${date}</a><div data-ad-preview="message">${text}</div><span aria-label="12 reactions">12 reactions</span><span aria-label="3 comments">3 comments</span>${comments}</article>`;
}
const first = post('101', 'October 3, 2026 at 11:00 PM', 'Looking for a café, tired of queues?<br>Help me find a better option.', comment('201', 'Use the riverside café, near the park.', 7) + comment('202', 'Another option has "fast" service.\nTry it!', 2));
const second = post('102', 'October 2, 2026 at 2:30 PM', 'Community picnic this weekend, bring food.');
const old = Array.from({ length: 5 }, (_, i) => post(`${900 + i}`, 'January 1, 2024', 'An old archived discussion outside the requested range.')).join('');
const head = '<!doctype html><html><head><title>Fixture Neighbors | Facebook</title></head><body><div role="navigation">Account</div>';
const feed = (articles: string) => `${head}<main role="feed">${articles}</main></body></html>`;
const tile = (id: string, title: string) => `<a href="/marketplace/item/${id}/?ref=search"><div>$100</div><div>${title}</div><div>Wilmington, NC</div></a>`;

export async function workspace() {
  const dir = await mkdtemp(join(tmpdir(), 'forage-e2e-'));
  const session = join(dir, '.config', 'forage', 'session');
  await mkdir(session, { recursive: true, mode: 0o700 });
  const sessionFile = join(session, 'storage_state.json');
  await writeFile(sessionFile, JSON.stringify({ cookies: [{ name: 'c_user', value: 'synthetic-user', domain: '.facebook.com', path: '/', expires: -1, httpOnly: false, secure: true, sameSite: 'Lax' }], origins: [] }), { mode: 0o600 });
  const requests: { path: string; query: URLSearchParams; cookie: string }[] = [];
  const state = { mode: 'feed' };
  const server = createServer((req, res) => {
    const url = new URL(req.url!, 'http://localhost');
    requests.push({ path: url.pathname, query: url.searchParams, cookie: String(req.headers['x-fixture-cookie'] ?? '') });
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    if (state.mode === 'login-authenticated' && url.pathname === '/login') return res.end(`${head}<script>document.cookie="c_user=synthetic-login-user; Path=/; Secure; SameSite=Lax";localStorage.setItem('fixture-login-marker','created-through-browser');</script><div aria-label="Your profile">Fixture user</div></body></html>`);
    if (state.mode === 'login-denied' || (state.mode === 'login-authenticated' && url.pathname === '/' && !String(req.headers['x-fixture-cookie'] ?? '').includes('c_user=synthetic-login-user'))) return res.end(`${head}<input name="email"><input name="pass"><button name="login">Log in</button></body></html>`);
    if (state.mode === 'transport') { res.setHeader('X-Fixture-Abort', '1'); return res.end(); }
    if (state.mode === 'expired') return res.end(`${head}<input name="email"><input name="pass"><button name="login">Log in</button><main role="feed"></main></body></html>`);
    if (url.pathname.startsWith('/marketplace/item/')) {
      const id = url.pathname.split('/')[3];
      const location = id === '301' ? { latitude: 40, longitude: -74 } : id === '302' ? { latitude: 34.22, longitude: -77.92 } : null;
      return res.end(`${head}<script type="application/json">${JSON.stringify({ id, location })}</script></body></html>`);
    }
    if (url.pathname.startsWith('/marketplace/')) {
      if (state.mode === 'empty') return res.end(`${head}<p>No results found</p></body></html>`);
      if (state.mode === 'missing-layout') return res.end(`${head}<p>Changed marketplace layout</p></body></html>`);
      if (state.mode === 'market-pagination') return res.end(`${head}<script type="application/json">{"buyLocation":{"latitude":34.21,"longitude":-77.92}}</script>${tile('301', 'Distant graphics card')}<div style="height:4000px"></div><script>let fetched=false;window.addEventListener('scroll',async()=>{if(!fetched&&window.scrollY>1500){fetched=true;document.body.insertAdjacentHTML('beforeend',await(await fetch('/fixture-marketplace-next')).text());}});</script></body></html>`);
      const center = state.mode === 'missing-center' ? '' : '<script type="application/json">{"buyLocation":{"latitude":34.21,"longitude":-77.92}}</script>';
      return res.end(`${head}${center}${tile('301', 'Distant graphics card')}${tile('302', 'Local graphics card')}${tile('302', 'Duplicate card')}${tile('303', 'Unverifiable card')}</body></html>`);
    }
    if (url.pathname === '/fixture-marketplace-next') return res.end(tile('302', 'Local graphics card'));
    if (url.pathname === '/fixture-next') return res.end(first + second + old);
    if (url.pathname.includes('/posts/')) return res.end(`${head}${comment('211', 'Top parent comment.', 9, comment('212', 'Nested reply, with café advice.', 4))}${comment('213', 'Lower ranked comment.', 1)}</body></html>`);
    if (state.mode === 'denied') return res.end(`${head}<p>This group isn't available</p></body></html>`);
    if (state.mode === 'missing-layout') return res.end(`${head}<p>Changed group layout</p></body></html>`);
    if (state.mode === 'empty') return res.end(`${head}<p>No posts yet</p></body></html>`);
    if (state.mode === 'parse-failure') return res.end(feed('<article role="article"><div>People you may know: suggested profiles that are not posts.</div></article>'));
    if (state.mode === 'permalink') return res.end(feed(post('103', 'October 3, 2026', 'A question that needs comments from the dedicated post page.')));
    if (state.mode === 'expansion') return res.end(feed(post('104', 'October 3, 2026', 'Short content… <button onclick="this.parentElement.textContent=\'Expanded full content with a useful answer.\'">See more</button>')));
    if (state.mode === 'pagination') return res.end(`${head}<main role="feed">${first}<div style="height:4000px"></div><div id="end">Next page</div></main><script>let fetched=false; window.addEventListener('scroll',async()=>{if(!fetched&&window.scrollY>1500){fetched=true; const html=await(await fetch('/fixture-next')).text(); document.querySelector('#end').remove();document.querySelector('[role=feed]').insertAdjacentHTML('beforeend',html);}});</script></body></html>`);
    if (state.mode === 'unknown-time') return res.end(feed(post('105', 'unknown clock', 'This post has no readable time and must stay visible.') + old));
    return res.end(feed(first + second + old));
  });
  await new Promise<void>((done) => server.listen(0, '127.0.0.1', done));
  const origin = `http://127.0.0.1:${(server.address() as any).port}`;
  const browserPath = process.env.PLAYWRIGHT_BROWSERS_PATH ?? join(homedir(), process.platform === 'darwin' ? 'Library/Caches/ms-playwright' : '.cache/ms-playwright');
  const env = { PATH: process.env.PATH, DISPLAY: process.env.DISPLAY, XAUTHORITY: process.env.XAUTHORITY, HOME: dir, XDG_CONFIG_HOME: join(dir, '.config'), PLAYWRIGHT_BROWSERS_PATH: browserPath, PYTHONPATH: resolve('tests/e2e/bootstrap'), FORAGE_E2E_ORIGIN: origin, NO_COLOR: '1', TERM: 'dumb', DO_NOT_TRACK: '1', PYTHONUNBUFFERED: '1' };
  async function run(args: string[], stdin = '') {
    return new Promise<{ code: number | null; stdout: string; stderr: string }>((done, reject) => {
      const child = spawn(resolve('.venv/bin/forage'), ['--no-color', ...args], { env, stdio: 'pipe' });
      const stdout: Buffer[] = [], stderr: Buffer[] = [];
      const timer = setTimeout(() => { child.kill('SIGKILL'); reject(new Error(`Forage exceeds 60 seconds: ${args.join(' ')}`)); }, 60_000);
      child.stdout.on('data', (b) => stdout.push(b)); child.stderr.on('data', (b) => stderr.push(b));
      child.on('error', (e) => { clearTimeout(timer); reject(e); });
      child.on('close', (code) => { clearTimeout(timer); done({ code, stdout: Buffer.concat(stdout).toString(), stderr: Buffer.concat(stderr).toString() }); });
      child.stdin.end(stdin);
    });
  }
  return { dir, session, sessionFile, state, requests, run, async close() { server.closeAllConnections(); await new Promise<void>((done) => server.close(() => done())); await rm(dir, { recursive: true, force: true }); } };
}
export const scrape = ['scrape', 'fixture', '--since', '2026-10-01', '--until', '2026-10-03', '--delay', '0', '--no-input'];
