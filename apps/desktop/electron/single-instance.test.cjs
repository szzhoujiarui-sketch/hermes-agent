'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const ELECTRON_DIR = __dirname

function readMainCjs() {
  return fs.readFileSync(path.join(ELECTRON_DIR, 'main.cjs'), 'utf8').replace(/\r\n/g, '\n')
}

function segmentBetween(source, startMark, endMark) {
  const si = source.indexOf(startMark)
  assert.notEqual(si, -1, `missing: ${startMark}`)
  const ei = source.indexOf(endMark, si + startMark.length)
  assert.notEqual(ei, -1, `missing after ${startMark}: ${endMark}`)
  return source.slice(si + startMark.length, ei)
}

test('single-instance lock failure branch does not reach startup', () => {
  const source = readMainCjs()

  assert.match(source, /app\.requestSingleInstanceLock\(\)/, 'missing requestSingleInstanceLock()')

  const failBody = segmentBetween(source, 'if (!_gotSingleInstanceLock) {', '} else {')
  assert.match(failBody, /app\.quit\(\)/, 'lock failure branch must call app.quit()')
  assert.doesNotMatch(failBody, /createWindow\(/, 'lock failure branch must not call createWindow()')
  assert.doesNotMatch(failBody, /startHermes\(/, 'lock failure branch must not call startHermes()')
})

test('successful lock path registers second-instance, open-url, and whenReady startup', () => {
  const source = readMainCjs()

  const elseBody = segmentBetween(source, '} else {', 'function configureSpellChecker')

  assert.match(elseBody, /app\.on\('second-instance'/, 'missing second-instance handler')
  assert.match(elseBody, /_extractDeepLink\(argv\)/, 'missing deep-link extraction in second-instance')
  assert.match(elseBody, /handleDeepLink\(url\)/, 'missing handleDeepLink in second-instance')
  assert.match(elseBody, /mainWindow\.focus\(\)/, 'missing window focus in second-instance')

  assert.match(elseBody, /app\.on\('open-url'/, 'missing open-url handler')
  assert.match(elseBody, /event\.preventDefault\(\)/, 'missing preventDefault in open-url')
  assert.match(elseBody, /handleDeepLink\(url\)/, 'missing handleDeepLink in open-url')

  assert.match(elseBody, /app\.whenReady\(\)\.then\(/, 'missing whenReady startup')
  assert.match(elseBody, /createWindow\(\)/, 'missing createWindow() in startup')
})

test('before-quit and window-all-closed cleanup remain registered', () => {
  const source = readMainCjs()

  assert.match(source, /app\.on\('before-quit'/, 'missing before-quit handler')
  assert.match(source, /app\.on\('window-all-closed'/, 'missing window-all-closed handler')
})

test('configureSpellChecker is defined', () => {
  const source = readMainCjs()

  assert.match(source, /function configureSpellChecker\(\)/, 'missing configureSpellChecker definition')
})
