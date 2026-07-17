import type { PuzzleGameKey } from "../types/api";

const STATE_PREFIX = "puzzle_guest_state_v1";
const DEFINITION_PREFIX = "puzzle_guest_definition_v1";
const IDIOM_PROGRESS_KEY = "puzzle_guest_idiom_progress_v1";

interface StoredState<T> {
  version: 1;
  updated_at: number;
  state: T;
}

export interface GuestIdiomResult {
  stars: number;
  best_score: number;
  completed_at: number;
}

export type GuestIdiomProgress = Record<string, GuestIdiomResult>;

function stateKey(gameKey: PuzzleGameKey, puzzleId: string): string {
  return `${STATE_PREFIX}:${gameKey}:${puzzleId}`;
}

function definitionKey(gameKey: PuzzleGameKey, slot: string): string {
  return `${DEFINITION_PREFIX}:${gameKey}:${slot}`;
}

export function loadGuestPuzzleState<T>(gameKey: PuzzleGameKey, puzzleId: string): T | null {
  if (!puzzleId) return null;
  const stored = wx.getStorageSync(stateKey(gameKey, puzzleId)) as StoredState<T> | null;
  if (!stored || stored.version !== 1 || !stored.state) return null;
  return stored.state;
}

export function saveGuestPuzzleState<T>(gameKey: PuzzleGameKey, puzzleId: string, state: T): void {
  if (!puzzleId) return;
  const payload: StoredState<T> = { version: 1, updated_at: Date.now(), state };
  wx.setStorageSync(stateKey(gameKey, puzzleId), payload);
}

export function clearGuestPuzzleState(gameKey: PuzzleGameKey, puzzleId: string): void {
  if (puzzleId) wx.removeStorageSync(stateKey(gameKey, puzzleId));
}

export function loadGuestPuzzleDefinition<T>(gameKey: PuzzleGameKey, slot: string): T | null {
  const stored = wx.getStorageSync(definitionKey(gameKey, slot)) as StoredState<T> | null;
  if (!stored || stored.version !== 1 || !stored.state) return null;
  return stored.state;
}

export function saveGuestPuzzleDefinition<T>(gameKey: PuzzleGameKey, slot: string, value: T): void {
  const payload: StoredState<T> = { version: 1, updated_at: Date.now(), state: value };
  wx.setStorageSync(definitionKey(gameKey, slot), payload);
}

export function clearGuestPuzzleDefinition(gameKey: PuzzleGameKey, slot: string): void {
  wx.removeStorageSync(definitionKey(gameKey, slot));
}

export function getGuestIdiomProgress(): GuestIdiomProgress {
  const value = wx.getStorageSync(IDIOM_PROGRESS_KEY);
  return value && typeof value === "object" ? value : {};
}

export function saveGuestIdiomResult(levelId: string, stars: number, score: number): GuestIdiomProgress {
  const progress = getGuestIdiomProgress();
  const previous = progress[levelId];
  progress[levelId] = {
    stars: Math.max(Number(previous?.stars || 0), Number(stars || 0)),
    best_score: Math.max(Number(previous?.best_score || 0), Number(score || 0)),
    completed_at: Date.now(),
  };
  wx.setStorageSync(IDIOM_PROGRESS_KEY, progress);
  return progress;
}
