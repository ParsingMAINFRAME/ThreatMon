const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const loadedModule = { exports: {} };
const source = readFileSync(path.join(__dirname, '../src/lib/register-state.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
vm.runInNewContext(compiled, { exports: loadedModule.exports, module: loadedModule, URLSearchParams });
const { parseRegisterState, registerHref, evidenceHref, recordOrdinals, selectRegisterRecord, registerPage, PAGE_SIZE } = loadedModule.exports;
const parse = (query = '') => parseRegisterState(new URLSearchParams(query));
const plain = (value) => JSON.parse(JSON.stringify(value));

test('round-trips every investigation field through the register and dossier URLs', () => {
  const state = parse('category=natural_hazard&status=developing&severity=35&q=M%205%20%26%20coast&geography=Jap%C3%B3n&origin=live&sort=updated&page=3&selected=event%2Fa');
  const dossier = evidenceHref('event/a', state);
  assert.ok(dossier.startsWith('/threats/event%2Fa?'));
  const restored = parse(dossier.split('?')[1]);
  assert.deepEqual(plain(restored), plain(state));
  assert.equal(registerHref(restored, true), registerHref(state) + '#event-register');
});

test('invalid URL filters and pagination fall back safely', () => {
  const state = parse('category=invalid&status=invalid&origin=invalid&sort=__proto__&severity=NaN&page=-4');
  assert.deepEqual(plain(state), plain(parse()));
  for (const page of ['1.5', 'Infinity', '1e8', '9007199254740992']) assert.equal(parse('page=' + page).page, 1);
  assert.equal(parse('severity=999').minSeverity, 100);
  assert.equal(parse('severity=-1').minSeverity, 0);
});

test('return URLs retain only known state and cannot become external destinations', () => {
  const state = parse('returnTo=https://example.com&next=//example.com&q=a%26b%23c&selected=__proto__');
  const href = registerHref(state, true);
  assert.ok(href.startsWith('/signals?'));
  assert.ok(!href.includes('example.com'));
  assert.equal(parse(href.split('?')[1].split('#')[0]).query, 'a&b#c');
});

test('map and register share ordinals even when unlocated records intervene', () => {
  const records = [{ id: 'global' }, { id: 'earthquake', map_location: {} }, { id: 'cyber' }, { id: 'other-point', map_location: {} }];
  const ordinals = recordOrdinals(records);
  assert.equal(ordinals.get('earthquake'), 2);
  assert.equal(ordinals.get('other-point'), 4);
  assert.equal(recordOrdinals(records.slice(1)).get('earthquake'), 1);
});

test('selecting a map record reveals its correct register page at page boundaries', () => {
  const records = Array.from({ length: 60 }, (_, i) => ({ id: 'record-' + i }));
  const original = parse('q=record&sort=title&page=3');
  for (const index of [0, PAGE_SIZE - 1, PAGE_SIZE, 59]) {
    const selected = selectRegisterRecord(original, records[index].id, records);
    assert.equal(selected.selectedId, records[index].id);
    assert.equal(selected.page, Math.floor(index / PAGE_SIZE) + 1);
    assert.equal(selected.query, original.query);
    assert.equal(selected.sort, original.sort);
  }
  assert.equal(selectRegisterRecord(original, 'missing', records), original);
});

test('a shorter refreshed dataset clamps the visible page without dropping filters', () => {
  assert.equal(registerPage(99, 27), 2);
  assert.equal(registerPage(5, 0), 1);
  assert.equal(registerPage(1, 27), 1);
});
