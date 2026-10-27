const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');

const html = fs.readFileSync('static/index.html', 'utf8');
const sendCode = html.slice(html.indexOf('async function send()'), html.indexOf('// Shared pieces'));

async function run(parts, { abort = false, failThrows = false } = {}) {
  let reads = 0, cancelled = false, finished = 0, failed = 0, buttons = 0;
  const events = [];
  const reader = {
    async read() {
      if (abort) { const error = new Error('aborted'); error.name = 'AbortError'; throw error; }
      assert.ok(reads < parts.length, 'must finish on done without waiting for connection closure');
      return parts[reads++];
    },
    async cancel() { cancelled = true; },
  };
  const ui = {
    event(event) { events.push(event); },
    finish() { finished++; },
    fail() { failed++; if (failThrows) throw new Error('render failed'); },
  };
  const context = vm.createContext({
    input: { value: 'What is MACEA?' }, attached: null, history: [], entries: [], controller: null,
    autosize() {}, clearAttachment() {}, addUser() {}, scrollDown() {}, refreshStatus() {},
    updateButton() { buttons++; }, chatUI() { return ui; },
    FormData, AbortController, TextDecoder,
    fetch: async () => ({ ok: true, body: { getReader: () => reader } }),
  });
  vm.runInContext(sendCode, context);
  try { await context.send(); } catch (error) { if (!failThrows) throw error; }
  assert.equal(context.controller, null, 'composer must leave loading state');
  assert.equal(buttons, 2);
  return { reads, cancelled, finished, failed, events };
}
const part = text => ({ value: new TextEncoder().encode(text), done: false });

test('completion event finishes immediately, even with an open connection', async () => {
  const result = await run([part('{"type":"token","text":"Answer"}\n{"type":"done"}\n')]);
  assert.equal(result.finished, 1);
  assert.equal(result.cancelled, true);
  assert.equal(result.events.length, 1);
});

test('handles split JSON events and a final line without newline', async () => {
  const result = await run([part('{"type":"tok'), part('en","text":"Answer"}\n'),
    { value: new TextEncoder().encode('{"type":"done"}'), done: true }]);
  assert.equal(result.finished, 1);
  assert.equal(result.events[0].text, 'Answer');
});

test('errors and aborts reset composer, even if error rendering fails', async () => {
  assert.equal((await run([part('{"type":"error","message":"failed"}\n')])).failed, 1);
  assert.equal((await run([], { abort: true })).failed, 1);
  assert.equal((await run([], { abort: true, failThrows: true })).failed, 1);
});

test('hidden loading indicators override activity display styles', () => {
  assert.match(html, /\[hidden\]\s*\{\s*display:\s*none\s*!important;/);
});

test('uncertain findings display Needs review with rationale and reviewer controls', () => {
  const start = html.indexOf('function renderResult(');
  const code = html.slice(start, html.indexOf('// What the AI remembers', start));
  const context = vm.createContext({ esc: text => String(text), fmtTime: String, ICON_DOWNLOAD: '' });
  vm.runInContext(code, context);
  const result = context.renderResult({result:'NEEDS_REVIEW', message:'Small text is unreadable.', reasons:[]}, 1);
  assert.match(result, /Needs review/);
  assert.match(result, /Small text is unreadable/);
  assert.match(result, /Human review required/);
  assert.doesNotMatch(result, /class="verdict good"/);
});
