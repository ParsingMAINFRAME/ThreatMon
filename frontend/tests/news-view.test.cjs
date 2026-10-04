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
const { deduplicateNewsArticles, buildNewsEvents, clusterNewsEvents, parseNewsState, newsHref, selectNewsEvents, newsCoverage, formatNewsTime, newsPublisherId, newsSources, coverageIntensity, COVERAGE_INTENSITY_BANDS } = loadedModule.exports;
const plain = value => JSON.parse(JSON.stringify(value));
const AS_OF = '2026-09-30T12:00:00Z';
const article = (id, overrides = {}) => ({ id, canonical_url: null, headline: `Synthetic story ${id}`, publisher: 'Demo Publisher', published_at: '2026-09-30T11:30:00Z', retrieved_at: AS_OF, summary: 'Synthetic scenario.', is_demo: true, syndication_key: null, duplicate_urls: [], ...overrides });
const event = (id, articles, overrides = {}) => ({ id, title: `DEMO event ${id}`, summary: 'Synthetic event, not a real report.', category: 'demonstration', status: 'unconfirmed', severity: 'unknown', severity_basis: 'No severity assessed.', grouping_basis: 'Explicit fixture association.', location: { lat: 35, lon: 51, label: 'Illustrative demo area', precision: 'illustrative', confidence: 'low', basis: 'Synthetic location.' }, scope: 'located', is_demo: true, articles, ...overrides });

test('coverage intensity uses explicit inclusive article-count boundaries', () => {
  for (const [count, expected] of [[1, 'green'], [5, 'green'], [10, 'green'], [11, 'amber'], [30, 'amber'], [31, 'red'], [35, 'red'], [1000, 'red']]) {
    assert.equal(coverageIntensity(count), expected, `Collected article count ${count}`);
  }
  for (const invalid of [0, -1, 1.5, NaN, Infinity]) assert.equal(coverageIntensity(invalid), 'none');
  assert.deepEqual(plain(COVERAGE_INTENSITY_BANDS.map(band => ({ intensity: band.intensity, label: band.label }))), [
    { intensity: 'green', label: '1–10 collected articles' },
    { intensity: 'amber', label: '11–30 collected articles' },
    { intensity: 'red', label: '31+ collected articles' },
  ]);
});

test('coverage intensity follows filtered unique articles independently of severity and official reports', () => {
  const articles = Array.from({ length: 35 }, (_, index) => article(`volume-${index}`, { publisher_id: index < 5 ? 'selected' : 'other', is_demo: false }));
  const input = event('volume', [...articles, article('official', { record_kind: 'official_report', publisher_id: 'gdacs', is_demo: false })], { severity: 'low' });
  const all = buildNewsEvents([input], AS_OF, '24h')[0];
  const selected = buildNewsEvents([input], AS_OF, '24h', 'selected')[0];
  const official = buildNewsEvents([input], AS_OF, '24h', 'gdacs')[0];
  assert.equal(coverageIntensity(all.story_count), 'red');
  assert.equal(coverageIntensity(selected.story_count), 'green');
  assert.equal(coverageIntensity(official.story_count), 'none');
  assert.equal(all.severity, 'low');
  assert.equal(selected.severity, 'low');
});

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

test('events at the same headline place stay grouped at maximum zoom so every one is reachable', () => {
  const moscow = { lat: 55.76, lon: 37.62, label: 'Moscow, Russia (place named in headline)', precision: 'approximate_area', confidence: 'low', basis: 'Headline mention.' };
  const events = buildNewsEvents([
    event('attack', [article('a'), article('b')], { location: moscow }),
    event('blast', [article('c')], { location: moscow }),
    event('kyiv', [article('d')], { location: { ...moscow, lat: 50.45, lon: 30.52, label: 'Kyiv, Ukraine (place named in headline)' } }),
  ], AS_OF, '24h');
  const groups = clusterNewsEvents(events, 3);
  assert.equal(groups.length, 2);
  const stacked = groups.find(group => group.kind === 'cluster');
  assert.deepEqual(plain(stacked.events.map(e => e.id)), ['attack', 'blast']);
  assert.equal(stacked.story_count, 3);
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

test('mobile grouping accounts for rendered control width while preserving distant demo hotspots', () => {
  const views = buildNewsEvents([
    event('iran', Array.from({ length: 35 }, (_, i) => article(`iran-${i}`)), { location: { lat: 35.7, lon: 51.4 } }),
    event('chile', Array.from({ length: 5 }, (_, i) => article(`chile-${i}`)), { location: { lat: -30, lon: -70 } }),
    event('nearby-a', [article('a')], { location: { lat: 40, lon: -123 } }),
    event('nearby-b', [article('b')], { location: { lat: 40, lon: -98 } }),
  ], AS_OF, '24h');
  const wide = clusterNewsEvents(views, 1, 1000);
  const narrow = clusterNewsEvents(views, 1, 343);
  assert.equal(wide.length, 4);
  assert.equal(narrow.length, 3);
  assert.equal(narrow.find(group => group.id === 'iran').story_count, 35);
  assert.equal(narrow.find(group => group.id === 'chile').story_count, 5);
  assert.equal(narrow.find(group => group.kind === 'cluster').events.length, 2);
  assert.equal(clusterNewsEvents(views, 3, 343).length, 4);
});

test('coverage totals do not double count a story referenced by multiple events', () => {
  const views = buildNewsEvents([event('one', [article('shared')]), event('two', [article('shared'), article('other')])], AS_OF, '24h');
  assert.deepEqual(plain(newsCoverage(views)), { event_count: 2, story_count: 2, official_report_count: 0, publisher_count: 1, news_publisher_count: 1, official_source_count: 0 });
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

test('official reports never inflate article counts or news publisher breadth', () => {
  const views = buildNewsEvents([event('mixed', [
    article('news-a', { publisher_id: 'globalvoices', publisher: 'Global Voices', is_demo: false }),
    article('news-b', { publisher_id: 'globalvoices', publisher: 'Global Voices Online', is_demo: false }),
    article('bulletin', { record_kind: 'official_report', publisher_id: 'gdacs', publisher: 'GDACS', is_demo: false }),
  ], { is_demo: false, severity: 'unknown', source_alert_level: 'Red' })], AS_OF, '24h');
  assert.equal(views[0].story_count, 2);
  assert.equal(views[0].official_report_count, 1);
  assert.equal(views[0].publisher_count, 2);
  assert.equal(views[0].news_publisher_count, 1);
  assert.equal(views[0].official_source_count, 1);
  assert.equal(views[0].severity, 'unknown');
  assert.equal(newsCoverage(views).official_report_count, 1);
});

test('retained publisher selection filters records before counts, timestamps and empty-event removal', () => {
  const inputs = [event('mixed', [
    article('news', { publisher_id: 'globalvoices', is_demo: false, published_at: '2026-09-30T11:00:00Z' }),
    article('report', { publisher_id: 'gdacs', record_kind: 'official_report', is_demo: false, published_at: '2026-09-30T11:45:00Z' }),
  ]), event('nasa-only', [article('nasa', { publisher_id: 'nasa', is_demo: false })])];
  const views = buildNewsEvents(inputs, AS_OF, '24h', 'globalvoices');
  assert.equal(views.length, 1);
  assert.deepEqual(plain(views[0].articles.map(item => item.id)), ['news']);
  assert.equal(views[0].story_count, 1);
  assert.equal(views[0].official_report_count, 0);
  assert.equal(views[0].freshest_published_at, '2026-09-30T11:00:00Z');
  assert.equal(buildNewsEvents(inputs, AS_OF, 'all', 'missing').length, 0);
});

test('spatial groups retain separate article and official-report totals', () => {
  const views = buildNewsEvents([
    event('news', [article('a')]),
    event('report', [article('b', { record_kind: 'official_report', source_window_start: '2026-09-01T00:00:00Z', source_window_end: '2026-09-02T00:00:00Z' })]),
  ], AS_OF, '24h');
  const group = clusterNewsEvents(views, 1)[0];
  assert.equal(group.events.length, 2);
  assert.equal(group.story_count, 1);
  assert.equal(group.official_report_count, 1);
  assert.equal(views[1].official_report_count, 1, 'source coverage windows do not replace RSS publication dates');
});

test('publisher selection round-trips without becoming a URL destination', () => {
  const state = parseNewsState(new URLSearchParams('publisher=globalvoices&window=7d&scope=unlocated&selected=story'));
  assert.equal(state.publisherId, 'globalvoices');
  const href = newsHref(state, 'snapshot');
  assert.deepEqual(plain(parseNewsState(new URLSearchParams(href.split('?')[1]))), plain(state));
  assert.equal(parseNewsState(new URLSearchParams()).publisherId, null);
  assert.ok(newsHref({ ...state, publisherId: 'https://example.invalid/' }, 'snapshot').startsWith('/?edition=snapshot'));
});

test('legacy demo publisher labels remain distinct and real stable publisher IDs take precedence', () => {
  assert.equal(newsPublisherId(article('nasa', { is_demo: false, publisher: ' NASA ' })), 'nasa');
  assert.equal(newsPublisherId(article('stable', { is_demo: false, publisher: 'A changed display name', publisher_id: 'globalvoices' })), 'globalvoices');
  const views = buildNewsEvents([event('demo', [article('a', { publisher: 'DEMO A', publisher_id: 'demo' }), article('b', { publisher: 'DEMO B', publisher_id: 'demo' })])], AS_OF, '24h');
  assert.equal(views[0].publisher_count, 2);
});

test('per-source health stays independent of aggregate snapshot success', () => {
  const sources = [
    { source_id: 'globalvoices', publisher_id: 'globalvoices', name: 'Global Voices', state: 'ok', last_success_at: AS_OF },
    { source_id: 'gdacs', publisher_id: 'gdacs', name: 'GDACS', state: 'error', last_success_at: '2026-09-28T12:00:00Z' },
  ];
  assert.deepEqual(plain(newsSources({ edition: 'snapshot', fetched_at: AS_OF, fetch_state: 'partial', sources })), sources);
  assert.deepEqual(plain(newsSources({ edition: 'demo', sources: [] })), []);
  const legacy = newsSources({ edition: 'snapshot', events: [], fetched_at: AS_OF, last_attempt_at: AS_OF, fetch_state: 'ok', error: null, source_note: 'Legacy NASA cache' });
  assert.equal(legacy[0].source_id, 'nasa');
  assert.equal(legacy[0].last_success_at, AS_OF);
});

test('unknown publication uses first collection for the window without manufacturing a publication time', () => {
  const views = buildNewsEvents([event('discovered', [
    article('discovered-now', { published_at: null, first_seen_at: '2026-09-30T11:40:00Z', is_demo: false, publisher_id: 'example.org', publisher: 'example.org', source_id: 'gdelt' }),
    article('discovered-old', { published_at: null, first_seen_at: '2026-09-28T12:00:00Z' }),
    article('time-unknown', { published_at: null, first_seen_at: null }),
    article('future-discovery', { published_at: null, first_seen_at: '2026-09-30T13:00:00Z' }),
  ], { scope: 'unlocated', location: null, grouping_status: 'candidate', place_hints: ['Unverified city mention'] })], AS_OF, '1h');
  assert.equal(views[0].story_count, 1);
  assert.equal(views[0].freshest_published_at, null);
  assert.equal(views[0].freshest_collected_at, '2026-09-30T11:40:00Z');
  assert.equal(views[0].articles[0].published_at, null);
  assert.equal(clusterNewsEvents(views, 1).length, 0);
});

test('known publication takes precedence over recent first collection', () => {
  const views = buildNewsEvents([event('old-publication', [article('old', { published_at: '2026-09-28T12:00:00Z', first_seen_at: AS_OF })])], AS_OF, '24h');
  assert.equal(views.length, 0);
});

test('discovery providers do not become publishers or duplicate collected articles', () => {
  const observations = [{ provider_id: 'gdelt', provider_url: 'https://api.gdeltproject.org/', provider_timestamp: AS_OF, retrieved_at: AS_OF, language: 'English', source_country: 'Example' }];
  const views = buildNewsEvents([event('candidate', [
    article('a', { canonical_url: 'https://publisher.example/article', publisher_id: 'publisher.example', publisher: 'publisher.example', observations, is_demo: false }),
    article('duplicate', { canonical_url: 'https://publisher.example/article', publisher_id: 'publisher.example', publisher: 'Publisher Example', observations: [...observations, { ...observations[0], provider_timestamp: '2026-09-30T11:00:00Z' }], is_demo: false }),
  ], { grouping_status: 'candidate' })], AS_OF, '24h');
  assert.equal(views[0].story_count, 1);
  assert.equal(views[0].news_publisher_count, 1);
  assert.equal(views[0].grouping_status, 'candidate');
});

test('bulletin channel URLs retain filters and edition on the secondary route', () => {
  const state = parseNewsState(new URLSearchParams('publisher=gdacs&window=7d&scope=located&selected=report'));
  const href = newsHref(state, 'snapshot', 'signals');
  assert.ok(href.startsWith('/signals?view=bulletins&edition=snapshot'));
  assert.deepEqual(plain(parseNewsState(new URLSearchParams(href.split('?')[1]))), plain(state));
  assert.ok(newsHref(state, 'snapshot', 'news').startsWith('/?edition=snapshot'));
});
