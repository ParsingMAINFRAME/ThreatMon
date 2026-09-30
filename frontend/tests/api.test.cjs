const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

// Exercise the actual server fetch module with controlled HTTP responses.
function apiFor(pages) {
  const requests = [];
  const loadedModule = { exports: {} };
  const source = readFileSync(path.join(__dirname, '../src/lib/api.ts'), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  vm.runInNewContext(compiled, {
    exports: loadedModule.exports, module: loadedModule, AbortSignal, process: { env: { API_BASE_URL: 'http://test-api' } },
    fetch: async (url) => {
      requests.push(url);
      const page = pages.shift();
      if (!page) throw new Error('Unexpected request');
      return { ok: !page.status, status: page.status ?? 200, json: async () => page };
    },
  });
  return { ...loadedModule.exports, requests };
}
const record = (id) => ({ id });
const page = (ids, extra = {}) => ({ items: ids.map(record), total: 4, data_mode: 'live', snapshot_id: 'stable', ...extra });

test('collects a stable dataset across pages and requests the next offset', async () => {
  const api = apiFor([page(['a', 'b']), page(['c', 'd'])]);
  const result = await api.getThreats();
  assert.equal(result.items.map((item) => item.id).join(','), 'a,b,c,d');
  assert.equal(api.requests[1], 'http://test-api/threats?limit=100&offset=2');
});
test('rejects a repeated record at a shifted page boundary', async () => {
  const api = apiFor([page(['a', 'b']), page(['b', 'c'])]);
  await assert.rejects(api.getThreats(), /Records changed during loading/);
});
for (const [name, change] of Object.entries({ revision: { snapshot_id: 'revised' }, count: { total: 5 }, origin: { data_mode: 'mixed' } })) {
  test(`rejects a changed ${name} between pages`, async () => {
    const api = apiFor([page(['a', 'b']), page(['c', 'd'], change)]);
    await assert.rejects(api.getThreats(), /Records changed during loading/);
  });
}
test('rejects an empty continuation instead of looping', async () => {
  await assert.rejects(apiFor([page(['a', 'b']), page([])]).getThreats(), /Records changed/);
});
test('rejects duplicate IDs and excess records on the first page', async () => {
  await assert.rejects(apiFor([page(['a', 'a'])]).getThreats(), /Records changed/);
  await assert.rejects(apiFor([page(['a', 'b'], { total: 1 })]).getThreats(), /Records changed/);
});
test('returns an empty snapshot with no continuation request', async () => {
  const api = apiFor([page([], { total: 0, data_mode: 'empty' })]);
  assert.equal((await api.getThreats()).items.length, 0);
  assert.equal(api.requests.length, 1);
});
test('preserves HTTP failures and encodes detail record identifiers', async () => {
  const api = apiFor([{ status: 404 }]);
  await assert.rejects(api.getThreat('record/with space'), /HTTP 404/);
  assert.equal(api.requests[0], 'http://test-api/threats/record%2Fwith%20space');
});

test('news editions use an explicit endpoint and do not silently substitute demo data', async () => {
  const api = apiFor([{ edition: 'snapshot', events: [] }, { status: 503 }]);
  const data = await api.getNews();
  assert.equal(data.edition, 'snapshot');
  assert.equal(api.requests[0], 'http://test-api/news?edition=snapshot&channel=news');
  await assert.rejects(api.getNews('demo'), /HTTP 503/);
});

test('secondary bulletins use an explicit channel and never replace the primary news request', async () => {
  const api = apiFor([{ channel: 'news', events: [] }, { channel: 'signals', events: [] }]);
  assert.equal((await api.getNews()).channel, 'news');
  assert.equal((await api.getNews('snapshot', 'signals')).channel, 'signals');
  assert.deepEqual(api.requests, ['http://test-api/news?edition=snapshot&channel=news', 'http://test-api/news?edition=snapshot&channel=signals']);
});
