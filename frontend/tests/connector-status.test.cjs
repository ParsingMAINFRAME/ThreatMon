const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function apiFor(fetch) {
  const loadedModule = { exports: {} };
  const source = readFileSync(path.join(__dirname, '../src/lib/api.ts'), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  vm.runInNewContext(compiled, {
    exports: loadedModule.exports, module: loadedModule, AbortSignal,
    process: { env: { API_BASE_URL: 'http://test-api' } }, fetch,
  });
  return loadedModule.exports;
}

const payload = () => ({
  live_ingestion_enabled: true, automatic_refresh_enabled: false, note: 'Manual snapshots.',
  connectors: [{ name: 'usgs_earthquakes', feed_url: 'https://earthquake.usgs.gov/feed', description: 'Earthquakes',
    state: 'never_run', last_attempt_at: null, last_success_at: null, item_count: 0, error: null }],
});
const response = (data) => ({ ok: true, status: 200, json: async () => data });

test('loads connector status with no-store semantics from the read-only endpoint', async () => {
  const api = apiFor(async (url, options) => {
    assert.equal(url, 'http://test-api/ingest/connectors');
    assert.equal(options.cache, 'no-store');
    return response(payload());
  });
  const result = await api.getConnectorStatus();
  assert.equal(result.connectors[0].state, 'never_run');
  assert.equal(result.automatic_refresh_enabled, false);
});

test('HTTP, transport, JSON and invalid-contract failures become unavailable status', async () => {
  const failures = [
    async () => ({ ok: false, status: 503 }),
    async () => { throw new Error('network unavailable'); },
    async () => ({ ok: true, json: async () => { throw new Error('invalid JSON'); } }),
    async () => response({ connectors: [] }),
    async () => response({ ...payload(), connectors: [{ ...payload().connectors[0], state: 'unexpected' }] }),
    async () => response({ ...payload(), connectors: [{ ...payload().connectors[0], last_success_at: 123 }] }),
  ];
  for (const fetch of failures) assert.equal(await apiFor(fetch).getConnectorStatus(), null);
});

test('connector-status failure leaves a successful register load available', async () => {
  const api = apiFor(async (url) => url.endsWith('/ingest/connectors')
    ? { ok: false, status: 503 }
    : response({ items: [{ id: 'retained-record' }], total: 1, data_mode: 'live', snapshot_id: 'stable' }));
  const [records, status] = await Promise.all([api.getThreats(), api.getConnectorStatus()]);
  assert.equal(records.items[0].id, 'retained-record');
  assert.equal(status, null);
});
