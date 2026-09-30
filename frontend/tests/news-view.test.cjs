const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const loadedModule = { exports: {} };
const source = readFileSync(path.join(__dirname, '../src/lib/news-view.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
vm.runInNewContext(compiled, { exports: loadedModule.exports, module: loadedModule, URL, URLSearchParams, Intl });
const { deduplicateNewsArticles, buildNewsEvents, clusterNewsEvents, parseNewsState, newsHref, selectNewsEvents, newsCoverage, formatNewsTime } = loadedModule.exports;
const plain = value => JSON.parse(JSON.stringify(value));
const AS_OF = '2026-09-30T12:00:00Z';
const article = (id, overrides = {}) => ({ id, canonical_url: null, headline: `Synthetic story ${id}`, publisher: 'Demo Publisher', published_at: '2026-09-30T11:30:00Z', retrieved_at: AS_OF, summary: 'Synthetic scenario.', is_demo: true, syndication_key: null, duplicate_urls: [], ...overrides });
const event = (id, articles, overrides = {}) => ({ id, title: `DEMO event ${id}`, summary: 'Synthetic event, not a real report.', category: 'demonstration', status: 'unconfirmed', severity: 'unknown', severity_basis: 'No severity assessed.', grouping_basis: 'Explicit fixture association.', location: { lat: 35, lon: 51, label: 'Illustrative demo area', precision: 'illustrative', confidence: 'low', basis: 'Synthetic location.' }, scope: 'located', is_demo: true, articles, ...overrides });

test('counts 35 unique stories and five stories separately without changing assessed severity', () => {
  const events = buildNewsEvents([
    event('many', Array.from({ length: 35 }, (_, i) => article(`a${i}`, { publisher: `Demo ${i % 4}` })), { severity: 'high' }),
    event('few', Array.from({ length: 5 }, (_, i) => article(`b${i}`)), { severity: 'low' }),
  ], AS_OF, '24h');
  assert.equal(events[0].story_count, 35);
  assert.equal(events[0].publisher_count, 4);
  assert.equal(events[1].story_count, 5);
  assert.equal(events[1].severity, 'low');
  assert.equal(buildNewsEvents([event('unknown', events[0].articles)], AS_OF, '24h')[0].severity, 'unknown');
});

test('uses the supplied clock and inclusive cutoff; excludes future, invalid and empty events', () => {
  const inputs = [event('timed', [
    article('cutoff', { published_at: '2026-09-29T12:00:00Z' }),
    article('old', { published_at: '2026-09-29T11:59:59Z' }),
    article('future', { published_at: '2026-09-30T12:00:01Z' }),
    article('invalid', { published_at: 'not a date' }),
    article('local', { published_at: '2026-09-30T11:30:00' }),
  ]), event('empty', [])];
  assert.deepEqual(plain(buildNewsEvents(inputs, AS_OF, '24h').map(e => e.articles.map(a => a.id))), [['cutoff']]);
  assert.equal(buildNewsEvents(inputs, AS_OF, '1h').length, 0);
  assert.equal(buildNewsEvents(inputs, AS_OF, 'all')[0].story_count, 2);
  assert.equal(buildNewsEvents(inputs, 'invalid', 'all').length, 0);
});

test('deduplicates URL aliases and syndication transitively while null URLs remain distinct', () => {
  const articles = [
    article('first', { canonical_url: 'https://example.org/a', syndication_key: 'wire-1' }),
    article('second', { canonical_url: 'https://example.org/b' }),
    article('bridge', { canonical_url: 'https://example.org/b#copy', syndication_key: 'wire-1' }),
    article('alias', { canonical_url: 'https://example.org/alias' }),
    article('original', { canonical_url: 'https://example.org/original', duplicate_urls: ['https://example.org/alias'] }),
    article('demo-1'), article('demo-2'),
  ];
  assert.equal(deduplicateNewsArticles(articles).length, 4);
});

test('time windows recalculate retained publisher breadth and preserve unlocated/global stories', () => {
  const inputs = [
    event('global', [article('fresh', { publisher: ' Demo A ' }), article('fresh-two', { publisher: 'demo a' }), article('old', { publisher: 'Demo B', published_at: '2026-09-28T12:00:00Z' })], { scope: 'global', location: null }),
    event('unlocated', [article('nasa')], { scope: 'unlocated', location: null, severity: 'unknown', is_demo: false }),
  ];
  const day = buildNewsEvents(inputs, AS_OF, '24h');
  assert.equal(day[0].publisher_count, 1);
  assert.equal(buildNewsEvents(inputs, AS_OF, '7d')[0].publisher_count, 2);
  assert.equal(selectNewsEvents(day, { scope: 'unlocated', query: '' })[0].id, 'unlocated');
  assert.equal(clusterNewsEvents(day, 1).length, 0);
  assert.equal(newsCoverage(day).story_count, 3);
});

test('nearby map groups keep incidents distinct and expand at maximum zoom', () => {
  const events = buildNewsEvents([
    event('one', [article('a'), article('b')]),
    event('two', [article('c')], { location: { lat: 35.5, lon: 52, label: 'Nearby demo', precision: 'illustrative', confidence: 'low', basis: 'Demo' } }),
    event('far', [article('d')], { location: { lat: -30, lon: -70, label: 'Distant demo', precision: 'illustrative', confidence: 'low', basis: 'Demo' } }),
  ], AS_OF, '24h');
  const groups = clusterNewsEvents(events, 1);
  const cluster = groups.find(g => g.kind === 'cluster');
  assert.equal(groups.length, 2);
  assert.equal(cluster.events.length, 2);
  assert.equal(cluster.story_count, 3);
  assert.deepEqual(plain(cluster.events.map(e => e.id)), ['one', 'two']);
  assert.equal(clusterNewsEvents(events, 3).length, 3);
});

test('map grouping recognizes proximity across the dateline and never plots malformed points', () => {
  const events = buildNewsEvents([
    event('east', [article('east')], { location: { lat: 10, lon: 179, label: 'East', precision: 'illustrative', confidence: 'low', basis: 'Demo' } }),
    event('west', [article('west')], { location: { lat: 10, lon: -179, label: 'West', precision: 'illustrative', confidence: 'low', basis: 'Demo' } }),
    event('bad', [article('bad')], { location: { lat: 95, lon: 20, label: 'Invalid', precision: 'illustrative', confidence: 'low', basis: 'Demo' } }),
  ], AS_OF, '24h');
  const groups = clusterNewsEvents(events, 1);
  assert.equal(groups.length, 1);
  assert.ok(Math.abs(groups[0].lon) > 170);
  assert.equal(groups[0].story_count, 2);
});

test('coverage totals do not double count a story referenced by multiple events', () => {
  const views = buildNewsEvents([event('one', [article('shared')]), event('two', [article('shared'), article('other')])], AS_OF, '24h');
  assert.deepEqual(plain(newsCoverage(views)), { event_count: 2, story_count: 2, publisher_count: 1 });
});

test('URL state round-trips edition, window, scope, selection and text safely', () => {
  const state = parseNewsState(new URLSearchParams('window=7d&scope=global&selected=event%2F1&q=Demo%20%26%20space'));
  const href = newsHref(state, 'snapshot');
  assert.ok(href.startsWith('/?edition=snapshot&'));
  assert.deepEqual(plain(parseNewsState(new URLSearchParams(href.split('?')[1]))), plain(state));
  assert.equal(parseNewsState(new URLSearchParams('window=forever&scope=planet')).window, '24h');
  assert.equal(parseNewsState(new URLSearchParams('scope=planet')).scope, 'all');
  assert.ok(!newsHref({ ...state, selectedId: 'https://evil.invalid/' }, 'demo').startsWith('https:'));
});

test('formatted evidence times are UTC and invalid timestamps stay explicitly unavailable', () => {
  assert.match(formatNewsTime(AS_OF), /UTC$/);
  assert.equal(formatNewsTime('not a date'), 'Not recorded');
  assert.equal(formatNewsTime(null), 'Not recorded');
});
