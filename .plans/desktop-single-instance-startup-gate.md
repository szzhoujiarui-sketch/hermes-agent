# Desktop Single-Instance Startup Gate Fix Plan

## Target Issue

- Issue: `#53539`
- Area: Desktop Electron lifecycle on Windows
- Symptom cluster:
  - Multiple command windows flash during Desktop startup.
  - Logs show repeated `HERMES_DASHBOARD_READY port=...` lines for different ports.
  - Renderer reports WebSocket disconnects such as `client_disconnect(code=1006,reason=)`.
  - Task Manager shows multiple `Hermes.exe` / backend child processes.

## Diagnosis

The strongest root-cause candidate is the Electron single-instance failure path in `apps/desktop/electron/main.cjs`.

Current flow:

1. Electron calls `app.requestSingleInstanceLock()`.
2. If the process fails to acquire the lock, it calls `app.quit()`.
3. The module still registers `app.whenReady().then(...)` unconditionally.
4. If the losing process reaches `whenReady`, it calls `createWindow()`.
5. `createWindow()` starts the renderer.
6. The renderer load path calls `startHermes()` from `did-finish-load`.
7. That second Electron main process has its own `connectionPromise`, `backendStartFailure`, and `hermesProcess` globals, so it can spawn an independent backend.

Relevant anchors:

- `apps/desktop/electron/main.cjs:7376` acquires the single-instance lock.
- `apps/desktop/electron/main.cjs:7378` calls `app.quit()` after lock failure.
- `apps/desktop/electron/main.cjs:7397` registers `app.whenReady().then(...)` unconditionally.
- `apps/desktop/electron/main.cjs:7409` calls `createWindow()`.
- `apps/desktop/electron/main.cjs:5909` calls `startHermes()` after renderer load.
- `apps/desktop/electron/main.cjs:5351` reuses `connectionPromise`, but only inside one Electron process.

## Excluded Adjacent Causes

These paths can explain reconnect attempts or startup delays, but they do not fully explain multiple Desktop processes each announcing different backend ports.

- Renderer reconnect loop:
  - `apps/desktop/src/app/gateway/hooks/use-gateway-boot.ts:147` calls `desktop.getConnection(...)` during reconnect.
  - `apps/desktop/src/app/gateway/hooks/use-gateway-request.ts:67` calls `desktop.getConnection(...)` after request transport failures.
  - These reuse the same Electron main process and hit the same `connectionPromise` for the primary backend.

- Backend port announcement timeout:
  - `apps/desktop/electron/backend-ready.cjs` already uses a 90 second default and a 45 second floor.
  - This fixes cold-start timeout loops inside one main process.

- Windows console flashes from child processes:
  - `apps/desktop/electron/main.cjs` wraps backend spawns in `hiddenWindowsChildOptions(...)`.
  - `apps/desktop/electron/windows-child-process.test.cjs` locks the hidden-child-process invariant.
  - Remaining flashes are more likely caused by extra Electron/backend processes starting.

- `HERMES_DESKTOP_IGNORE_EXISTING`:
  - This only controls backend resolution in `resolveHermesBackend(...)`.
  - It forces Desktop to skip an existing `hermes` CLI on PATH during backend selection.
  - It is not a multi-GUI-instance opt-in.

## Fix Strategy

Make the single-instance lock failure a real startup gate.

Desired invariant:

> A process that fails `requestSingleInstanceLock()` must not register the normal Desktop startup path and must not reach `createWindow()` or `startHermes()`.

Minimal implementation shape:

1. Keep `const _gotSingleInstanceLock = app.requestSingleInstanceLock()` near the deep-link setup.
2. If `_gotSingleInstanceLock` is false, call `app.quit()` and skip all normal startup registration.
3. If `_gotSingleInstanceLock` is true, register `second-instance`, `open-url`, `app.whenReady().then(...)`, and the existing `activate` handler.

Concrete patch direction:

```javascript
const _gotSingleInstanceLock = app.requestSingleInstanceLock()

if (!_gotSingleInstanceLock) {
  app.quit()
} else {
  app.on('second-instance', (_event, argv) => {
    const url = _extractDeepLink(argv)
    if (url) handleDeepLink(url)
    else if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })

  app.on('open-url', (event, url) => {
    event.preventDefault()
    handleDeepLink(url)
  })

  app.whenReady().then(() => {
    // Existing startup body unchanged.
  })
}
```

Alternative patch shape:

```javascript
const _gotSingleInstanceLock = app.requestSingleInstanceLock()
if (!_gotSingleInstanceLock) {
  app.quit()
} else {
  registerSingleInstanceLifecycle()
}
```

Where `registerSingleInstanceLifecycle()` contains the current `second-instance`, `open-url`, and `whenReady` registration. This is clearer but creates one new helper.

Preferred approach:

- Use the minimal wrapping approach if the diff stays readable.
- Use `registerSingleInstanceLifecycle()` if review clarity is better than a large nested block.

## Behavior Preservation

Preserve these existing behaviors:

- Existing app receives Win/Linux deep links via `second-instance`.
- Existing app focuses/restores when a second launch has no deep link.
- macOS continues to receive deep links via `open-url` in the primary instance.
- Cold-start deep links are still read from `process.argv` after `createWindow()`.
- `registerDeepLinkProtocol()` still runs after `app.whenReady()` in the primary instance.
- `window-all-closed` and `before-quit` cleanup remain unchanged.

Expected behavior after fix:

- Secondary Win/Linux Electron process exits without creating a BrowserWindow.
- Secondary process does not spawn a backend.
- Only the primary process can print `HERMES_DASHBOARD_READY port=...` for the primary backend.
- Existing renderer reconnect logic remains unchanged.

## Test Plan

Add a focused Electron main startup invariant test.

Recommended file:

- `apps/desktop/electron/single-instance.test.cjs`

Wire it into:

- `apps/desktop/package.json` script `test:desktop:platforms`

Test style:

- Use `node:test` and static source inspection, consistent with existing Desktop platform tests.
- Read `electron/main.cjs` and assert structural ordering / containment.

Test cases:

1. `single-instance loser does not register normal startup`
   - Assert `requestSingleInstanceLock()` exists.
   - Assert the lock failure branch calls `app.quit()`.
   - Assert `app.whenReady().then` is inside the successful lock path, or inside a helper only called from the successful lock path.

2. `single-instance winner still handles second launch`
   - Assert `app.on('second-instance'` exists.
   - Assert it routes `_extractDeepLink(argv)` to `handleDeepLink(url)`.
   - Assert it focuses `mainWindow` when no URL exists.

3. `primary startup still creates the window`
   - Assert the primary startup body still calls `registerDeepLinkProtocol()` and `createWindow()`.

Static assertion options:

- If using a helper:
  - assert `function registerSingleInstanceLifecycle()` exists;
  - assert the helper contains `app.whenReady().then` and `createWindow()`;
  - assert the lock success branch calls `registerSingleInstanceLifecycle()`;
  - assert the lock failure branch does not call the helper.

- If using direct wrapping:
  - assert the source segment after `else {` contains `app.whenReady().then`;
  - assert the failure branch segment before `else` contains `app.quit()` and no `createWindow` / `startHermes`.

Suggested validation command:

```bash
# Run the focused Electron platform tests.
cd apps/desktop
node --test electron/single-instance.test.cjs electron/windows-child-process.test.cjs electron/backend-ready.test.cjs
```

Optional broader validation:

```bash
# Run all Desktop platform tests.
cd apps/desktop
npm run test:desktop:platforms
```

## PR Plan

Create a standalone PR from current upstream main.

Branch name:

```bash
260627-fix-desktop-single-instance-startup-gate
```

Commit title:

```text
fix(desktop): gate startup on single-instance lock
```

PR scope:

- `apps/desktop/electron/main.cjs`
- `apps/desktop/electron/single-instance.test.cjs`
- `apps/desktop/package.json`

Keep out of scope:

- Gateway duplicate reply suppression from PR `#53516`.
- Changes to renderer reconnect/backoff behavior.
- Changes to backend ready timeout values.
- Changes to Windows child process hiding.
- Large lifecycle refactors.

## PR Description Draft

```markdown
## Summary

- Gate Desktop startup behind the successful Electron single-instance lock.
- Prevent a losing Win/Linux second-instance process from reaching `createWindow()` and spawning its own dashboard backend.
- Add an Electron startup invariant test for the single-instance path.

## Why

Issue #53539 reports repeated command windows, multiple `HERMES_DASHBOARD_READY port=...` announcements, WebSocket 1006 disconnects, and multiple Hermes processes on Windows.

The existing losing-lock path calls `app.quit()`, but the normal `app.whenReady().then(...)` startup callback is still registered unconditionally. If the losing process reaches `whenReady`, it can create a window; the renderer load path then calls `startHermes()`. Because `connectionPromise` and `backendStartFailure` are process-local, a second Electron main process can spawn a second local backend.

## Testing

- `node --test electron/single-instance.test.cjs electron/windows-child-process.test.cjs electron/backend-ready.test.cjs`
```

## Review Notes

Likely reviewer questions and answers:

- Why not change renderer reconnect?
  - Renderer reconnect only re-enters `getConnection()` within the same Electron main process. It does not explain multiple independent `Hermes.exe` processes or multiple READY ports by itself.

- Why not adjust backend ready timeout?
  - That was already addressed by the 90 second cold-start-tolerant timeout. The current bug signature points to more than one process starting, not only one slow child.

- Why not change `windowsHide`?
  - Backend and background child spawns already go through `hiddenWindowsChildOptions(...)`, with static coverage in `windows-child-process.test.cjs`. Preventing the losing Electron process from spawning a backend reduces the extra console windows at the source.

- Does this break deep links?
  - Win/Linux deep links still go to the existing app via `second-instance` in the winning process. macOS `open-url` remains registered by the winning process. Cold-start argv handling remains inside the primary startup path.

## Rollback Plan

If regressions appear, revert the single-instance startup gate commit. The change is limited to Electron lifecycle registration and its test.

## Acceptance Criteria

- Launching a second Desktop instance routes to/focuses the existing app.
- The losing process exits without creating a BrowserWindow.
- The losing process does not call `startHermes()`.
- A repeated launch does not produce extra `HERMES_DASHBOARD_READY port=...` announcements from new backend children.
- Existing deep link routing remains functional.
