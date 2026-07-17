import type { PuzzleGameKey } from "../types/api";
import { getUsername } from "./auth";

const STATE_PREFIX = "puzzle_guest_state_v1";
const DEFINITION_PREFIX = "puzzle_guest_definition_v1";
const CLOUD_SHADOW_PREFIX = "puzzle_cloud_shadow_v1";
const IDIOM_PROGRESS_KEY = "puzzle_guest_idiom_progress_v1";

interface StoredState<T> {
  version: 1;
  updated_at: number;
  state: T;
}

interface CloudPuzzleShadow<T> {
  version: 2;
  updated_at: number;
  pending: boolean;
  snapshot_token: string;
  confirmed_state: T | null;
  in_flight_states: T[];
  state: T;
}

export interface CloudPuzzleShadowToken<T> {
  storageKey: string;
  snapshotToken: string;
  confirmedState: T | null;
  state: T;
  username: string;
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

let cloudShadowSequence = 0;

function legacyCloudShadowKey(gameKey: PuzzleGameKey, puzzleId: string): string {
  return `${CLOUD_SHADOW_PREFIX}:${gameKey}:${puzzleId}`;
}

function cloudShadowKey(gameKey: PuzzleGameKey, puzzleId: string): { key: string; username: string } | null {
  // Unscoped v1 shadows may belong to any previously logged-in account. They
  // are never migrated because ownership cannot be proven.
  wx.removeStorageSync(legacyCloudShadowKey(gameKey, puzzleId));
  const username = String(getUsername() || "").trim();
  if (!username) return null;
  return {
    key: `${CLOUD_SHADOW_PREFIX}:${encodeURIComponent(username)}:${gameKey}:${puzzleId}`,
    username,
  };
}

function createSnapshotToken(): string {
  cloudShadowSequence += 1;
  return `${Date.now()}-${cloudShadowSequence}`;
}

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === "object") {
    return Object.keys(value as Record<string, unknown>)
      .sort()
      .reduce<Record<string, unknown>>((result, key) => {
        result[key] = stableValue((value as Record<string, unknown>)[key]);
        return result;
      }, {});
  }
  return value;
}

function sameState<T>(left: T | null, right: T | null): boolean {
  return JSON.stringify(stableValue(left)) === JSON.stringify(stableValue(right));
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

/**
 * Writes the newest logged-in snapshot before the network request starts.
 * confirmedState must be the last state known to have come from the server.
 */
export function stageCloudPuzzleShadow<T>(
  gameKey: PuzzleGameKey,
  puzzleId: string,
  state: T,
  confirmedState: T | null,
): CloudPuzzleShadowToken<T> | null {
  if (!puzzleId) return null;
  const scoped = cloudShadowKey(gameKey, puzzleId);
  if (!scoped) return null;
  const existing = wx.getStorageSync(scoped.key) as CloudPuzzleShadow<T> | null;
  const baseline = existing?.version === 2 ? existing.confirmed_state : confirmedState;
  const snapshotToken = createSnapshotToken();
  const payload: CloudPuzzleShadow<T> = {
    version: 2,
    updated_at: Date.now(),
    pending: true,
    snapshot_token: snapshotToken,
    confirmed_state: baseline,
    in_flight_states: existing?.version === 2 ? existing.in_flight_states || [] : [],
    state,
  };
  wx.setStorageSync(scoped.key, payload);
  return {
    storageKey: scoped.key,
    snapshotToken,
    confirmedState: baseline,
    state,
    username: scoped.username,
  };
}

/** Records a request that may still reach the server if the app is killed. */
export function markCloudPuzzleShadowInFlight<T>(
  token: CloudPuzzleShadowToken<T> | null,
): void {
  if (!token) return;
  const existing = wx.getStorageSync(token.storageKey) as CloudPuzzleShadow<T> | null;
  if (!existing || existing.version !== 2) return;
  const inFlight = existing.in_flight_states || [];
  if (inFlight.some((state) => sameState(state, token.state))) return;
  wx.setStorageSync(token.storageKey, {
    ...existing,
    updated_at: Date.now(),
    in_flight_states: [...inFlight, token.state],
  } as CloudPuzzleShadow<T>);
}

/** Removes a request from the crash-recovery candidates after a known failure. */
export function failCloudPuzzleShadowRequest<T>(
  token: CloudPuzzleShadowToken<T> | null,
): void {
  if (!token) return;
  const existing = wx.getStorageSync(token.storageKey) as CloudPuzzleShadow<T> | null;
  if (!existing || existing.version !== 2) return;
  wx.setStorageSync(token.storageKey, {
    ...existing,
    updated_at: Date.now(),
    in_flight_states: (existing.in_flight_states || []).filter(
      (state) => !sameState(state, token.state),
    ),
  } as CloudPuzzleShadow<T>);
}

/**
 * Advances the confirmed cloud baseline without replacing a newer pending
 * snapshot. This makes an older in-flight request safe to finish after a newer
 * local snapshot has already been staged.
 */
export function confirmCloudPuzzleShadow<T>(
  token: CloudPuzzleShadowToken<T> | null,
): boolean {
  if (!token) return false;
  const existing = wx.getStorageSync(token.storageKey) as CloudPuzzleShadow<T> | null;
  if (!existing || existing.version !== 2) return false;

  const canAdvanceBaseline =
    sameState(existing.confirmed_state, token.confirmedState) ||
    (existing.in_flight_states || []).some((state) => sameState(state, token.state));
  if (!canAdvanceBaseline) return false;

  if (existing.snapshot_token === token.snapshotToken) {
    wx.setStorageSync(token.storageKey, {
      ...existing,
      updated_at: Date.now(),
      pending: false,
      confirmed_state: token.state,
      in_flight_states: [],
    } as CloudPuzzleShadow<T>);
    return true;
  }

  if (existing.pending && sameState(existing.confirmed_state, token.confirmedState)) {
    wx.setStorageSync(token.storageKey, {
      ...existing,
      updated_at: Date.now(),
      confirmed_state: token.state,
      in_flight_states: [],
    } as CloudPuzzleShadow<T>);
  }
  return false;
}

/**
 * Recovers a failed local save only while the cloud still matches the baseline
 * that the edit started from. A server change wins and discards the stale local
 * shadow, preventing an older device snapshot from overwriting newer progress.
 */
export function resolveCloudPuzzleState<T>(
  gameKey: PuzzleGameKey,
  puzzleId: string,
  serverState: T | null,
): T | null {
  if (!puzzleId) return serverState;
  const scoped = cloudShadowKey(gameKey, puzzleId);
  if (!scoped) return serverState;
  const shadow = wx.getStorageSync(scoped.key) as CloudPuzzleShadow<T> | null;
  if (!shadow || shadow.version !== 2) {
    if (shadow) wx.removeStorageSync(scoped.key);
    return serverState;
  }
  const matchesPendingBaseline =
    sameState(serverState, shadow.confirmed_state) ||
    (shadow.in_flight_states || []).some((state) => sameState(serverState, state));
  if (shadow.pending && matchesPendingBaseline) {
    wx.setStorageSync(scoped.key, {
      ...shadow,
      updated_at: Date.now(),
      confirmed_state: serverState,
      in_flight_states: [],
    } as CloudPuzzleShadow<T>);
    return shadow.state;
  }
  if (!shadow.pending && sameState(serverState, shadow.confirmed_state)) return serverState;
  wx.removeStorageSync(scoped.key);
  return serverState;
}

export function clearCloudPuzzleShadow(gameKey: PuzzleGameKey, puzzleId: string): void {
  if (!puzzleId) return;
  const scoped = cloudShadowKey(gameKey, puzzleId);
  if (scoped) wx.removeStorageSync(scoped.key);
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
