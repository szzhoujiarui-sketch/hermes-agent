// Terminal theming, matched to VS Code / Cursor's integrated terminal:
//   1. ANSI palette is VS Code's exact light/dark table (below), keyed off the
//      *painted* mode (renderedMode, the luminance-derived class applyTheme
//      toggles) — not the user's light/dark setting, so skins that invert read
//      right.
//   2. The terminal background is painted with the live skin surface
//      (--ui-editor-surface-background) at runtime via withSurface(), so the
//      pane blends into the app instead of showing a flat #1e1e1e/#fff slab.
//   3. minimumContrastRatio (set on the Terminal) clamps foregrounds against
//      that surface, killing the over-saturated "cotton candy" look while
//      keeping colors crisp. Contrast needs an opaque bg, hence (2) over real
//      transparency.
import type { ITheme, Terminal } from '@xterm/xterm'
import type { CSSProperties } from 'react'

// VS Code's default integrated-terminal palette (terminalColorRegistry.ts) — a
// fixed table per theme type, not luminance-derived. Light/dark diverge on
// purpose so each stays legible (e.g. mustard yellow on white).
const DARK_THEME: ITheme = {
  background: '#1e1e1e',
  foreground: '#cccccc',
  cursor: '#cccccc',
  cursorAccent: '#1e1e1e',
  selectionBackground: '#264f7866',
  black: '#000000',
  red: '#cd3131',
  green: '#0dbc79',
  yellow: '#e5e510',
  blue: '#2472c8',
  magenta: '#bc3fbc',
  cyan: '#11a8cd',
  white: '#e5e5e5',
  brightBlack: '#666666',
  brightRed: '#f14c4c',
  brightGreen: '#23d18b',
  brightYellow: '#f5f543',
  brightBlue: '#3b8eea',
  brightMagenta: '#d670d6',
  brightCyan: '#29b8db',
  brightWhite: '#e5e5e5'
}

const LIGHT_THEME: ITheme = {
  background: '#ffffff',
  foreground: '#333333',
  cursor: '#333333',
  cursorAccent: '#ffffff',
  selectionBackground: '#add6ff80',
  black: '#000000',
  red: '#cd3131',
  green: '#00bc00',
  yellow: '#949800',
  blue: '#0451a5',
  magenta: '#bc05bc',
  cyan: '#0598bc',
  white: '#555555',
  brightBlack: '#666666',
  brightRed: '#cd3131',
  brightGreen: '#14ce14',
  brightYellow: '#b5ba00',
  brightBlue: '#0451a5',
  brightMagenta: '#bc05bc',
  brightCyan: '#0598bc',
  brightWhite: '#a5a5a5'
}

// Palette by painted mode. `background` is only a fallback — withSurface swaps
// in the live skin surface at runtime; minimumContrastRatio keeps colors crisp.
export const terminalTheme = (mode: 'light' | 'dark'): ITheme => (mode === 'dark' ? DARK_THEME : LIGHT_THEME)

// Resolve --ui-editor-surface-background (a color-mix on the skin seed) to a
// concrete rgb for the WebGL renderer + contrast clamp. Custom props don't
// resolve via getComputedStyle, so probe a real background-color. Read AFTER
// applyTheme repaints (mount / rAF post-change) or it lags a frame behind.
export function resolveSurfaceColor(fallback: string): string {
  if (typeof document === 'undefined' || !document.body) {
    return fallback
  }

  const probe = document.createElement('span')
  probe.style.cssText =
    'position:absolute;visibility:hidden;pointer-events:none;background-color:var(--ui-editor-surface-background)'
  document.body.appendChild(probe)
  const resolved = getComputedStyle(probe).backgroundColor
  probe.remove()

  return resolved && resolved !== 'rgba(0, 0, 0, 0)' ? resolved : fallback
}

export const isMacPlatform = () => navigator.platform.toLowerCase().includes('mac')

export const addSelectionShortcutLabel = () => (isMacPlatform() ? '⌘L' : 'Ctrl+L')

export function isAddSelectionShortcut(event: KeyboardEvent) {
  const mod = isMacPlatform() ? event.metaKey : event.ctrlKey

  return mod && !event.shiftKey && event.key.toLowerCase() === 'l'
}

export function terminalSelectionLabel(term: Terminal, shellName: string, text: string) {
  const pos = term.getSelectionPosition()

  if (pos) {
    return pos.start.y === pos.end.y ? `${shellName}:${pos.start.y}` : `${shellName}:${pos.start.y}-${pos.end.y}`
  }

  const lines = Math.max(1, text.trim().split(/\r?\n/).length)

  return `${shellName}:${lines} line${lines === 1 ? '' : 's'}`
}

export function terminalSelectionAnchor(host: HTMLDivElement): CSSProperties | null {
  const rect = Array.from(host.querySelectorAll<HTMLElement>('.xterm-selection div'))
    .map(node => node.getBoundingClientRect())
    .filter(r => r.width > 0 && r.height > 0)
    .at(-1)

  if (!rect) {
    return null
  }

  const hostRect = host.getBoundingClientRect()
  const buttonWidth = 128
  const left = Math.min(Math.max(rect.left - hostRect.left, 8), Math.max(8, host.clientWidth - buttonWidth - 8))
  const top = Math.min(Math.max(rect.bottom - hostRect.top + 4, 8), Math.max(8, host.clientHeight - 34))

  return { left, top }
}
