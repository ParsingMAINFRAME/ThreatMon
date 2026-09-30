const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function freshnessModule() {
  const loadedModule = { exports: {} };
  const source = readFileSync(path.join(__dirname, '../src/lib/freshness.ts'), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  vm.runInNewContext(compiled, { exports: loadedModule.exports, module: loadedModule });
  return loadedModule.exports;
}

const NOW = Date.parse('2026-09-30T12:00:00Z');
const connector = (extra = {}) => ({
  name: 'usgs_earthquakes', state: 'ok', last_attempt_at: '2026-09-30T10:59:00Z',
  last_success_at: '2026-09-30T11:00:00Z', ...extra,
});

test('retrieval age uses an explicit greater-than-24-hour policy', () => {
  const { assessConnectorFreshness, STALE_AFTER_HOURS } = freshnessModule();
  assert.equal(STALE_AFTER_HOURS, 24);
  const boundary = connector({ last_success_at: '2026-09-29T12:00:00Z' });
  assert.equal(assessConnectorFreshness(boundary, NOW).ageState, 'within_threshold');
  assert.equal(assessConnectorFreshness(boundary, NOW + 1).ageState, 'stale');
});

test('failed latest fetch preserves the age and UTC timestamp of prior success', () => {
  const { assessConnectorFreshness } = freshnessModule();
  const result = assessConnectorFreshness(connector({ state: 'error', last_success_at: '2026-09-28T14:00:00+02:00' }), NOW);
  assert.equal(result.attemptState, 'error');
  assert.equal(result.ageState, 'stale');
  assert.equal(result.lastSuccessAt, '2026-09-28T12:00:00.000Z');
  assert.equal(result.ageLabel, '2d 0h ago');
});

test('never-run and first failed fetch cannot imply a successful retrieval', () => {
  const { assessConnectorFreshness } = freshnessModule();
  for (const state of ['never_run', 'error']) {
    const result = assessConnectorFreshness(connector({ state, last_success_at: null }), NOW);
    assert.equal(result.attemptState, state);
    assert.equal(result.ageState, 'never_fetched');
    assert.equal(result.lastSuccessAt, null);
    assert.equal(result.ageLabel, null);
  }
});

test('invalid, timezone-free, missing or future success times have unknown age', () => {
  const { assessConnectorFreshness } = freshnessModule();
  for (const last_success_at of [null, 'invalid', '2026-09-30T11:00:00', '2026-09-30T12:00:00.001Z', '2026-02-30T11:00:00Z', '2026-09-29T24:00:00Z']) {
    const result = assessConnectorFreshness(connector({ last_success_at }), NOW);
    assert.equal(result.ageState, 'unknown');
    assert.equal(result.ageLabel, null);
  }
});

test('age labels are deterministic at minute and hour boundaries', () => {
  const { assessConnectorFreshness } = freshnessModule();
  for (const [elapsed, label] of [[0, 'Less than 1m ago'], [59999, 'Less than 1m ago'], [60000, '1m ago'], [3599999, '59m ago'], [3600000, '1h 0m ago']]) {
    const result = assessConnectorFreshness(connector({ last_success_at: new Date(NOW - elapsed).toISOString() }), NOW);
    assert.equal(result.ageLabel, label);
  }
});

test('invalid assessment clock does not manufacture a recent fetch', () => {
  const { assessConnectorFreshness } = freshnessModule();
  assert.equal(assessConnectorFreshness(connector(), NaN).ageState, 'unknown');
});
