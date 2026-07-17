import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const storage = new Map();
let currentUsername = "alice";
globalThis.wx = {
  getStorageSync(key) { return storage.get(key); },
  setStorageSync(key, value) { storage.set(key, structuredClone(value)); },
  removeStorageSync(key) { storage.delete(key); },
};

const sourcePath = path.resolve(import.meta.dirname, "../utils/puzzle-storage.ts");
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
  fileName: sourcePath,
}).outputText;
const module = { exports: {} };
new Function("exports", "module", "require", compiled)(
  module.exports,
  module,
  (specifier) => specifier === "./auth" ? { getUsername: () => currentUsername } : {},
);
const {
  confirmCloudPuzzleShadow,
  failCloudPuzzleShadowRequest,
  markCloudPuzzleShadowInFlight,
  resolveCloudPuzzleState,
  stageCloudPuzzleShadow,
} = module.exports;

const baseline = { grid: "100", notes: { "2": [1, 2] } };
const offlineEdit = { grid: "120", notes: {} };
stageCloudPuzzleShadow("sudoku", "recovery", offlineEdit, baseline);
assert.deepEqual(
  resolveCloudPuzzleState("sudoku", "recovery", { notes: { "2": [1, 2] }, grid: "100" }),
  offlineEdit,
  "pending local edits should recover when the server still matches their baseline",
);

const remoteEdit = { grid: "103", notes: {} };
assert.deepEqual(
  resolveCloudPuzzleState("sudoku", "recovery", remoteEdit),
  remoteEdit,
  "a newer server state must win over a stale local shadow",
);

currentUsername = "alice";
const aliceEdit = { grid: "111", notes: {} };
const aliceToken = stageCloudPuzzleShadow("sudoku", "shared-puzzle", aliceEdit, baseline);
currentUsername = "bob";
assert.deepEqual(
  resolveCloudPuzzleState("sudoku", "shared-puzzle", baseline),
  baseline,
  "another account must not see the previous account's shadow",
);
const bobEdit = { grid: "122", notes: {} };
stageCloudPuzzleShadow("sudoku", "shared-puzzle", bobEdit, baseline);
markCloudPuzzleShadowInFlight(aliceToken);
assert.equal(confirmCloudPuzzleShadow(aliceToken), true);
assert.deepEqual(
  resolveCloudPuzzleState("sudoku", "shared-puzzle", baseline),
  bobEdit,
  "an old account request callback must not confirm or replace the current account's shadow",
);
currentUsername = "alice";
assert.deepEqual(
  resolveCloudPuzzleState("sudoku", "shared-puzzle", aliceEdit),
  aliceEdit,
  "each account should retain its own pending shadow",
);

currentUsername = "alice";
const firstEdit = { grid: "130", notes: {} };
const newestEdit = { grid: "134", notes: {} };
const firstToken = stageCloudPuzzleShadow("sudoku", "in-flight", firstEdit, baseline);
markCloudPuzzleShadowInFlight(firstToken);
const newestToken = stageCloudPuzzleShadow("sudoku", "in-flight", newestEdit, baseline);
assert.equal(
  confirmCloudPuzzleShadow(firstToken),
  false,
  "an older request must not mark a newer snapshot as fully synced",
);
assert.deepEqual(
  resolveCloudPuzzleState("sudoku", "in-flight", firstEdit),
  newestEdit,
  "after an older request succeeds, a crash must still recover the newer staged snapshot",
);
markCloudPuzzleShadowInFlight(newestToken);
assert.equal(confirmCloudPuzzleShadow(newestToken), true);
assert.deepEqual(resolveCloudPuzzleState("sudoku", "in-flight", newestEdit), newestEdit);

const interruptedRequest = { grid: "140", notes: {} };
const interruptedNewest = { grid: "145", notes: {} };
const interruptedToken = stageCloudPuzzleShadow("sudoku", "crash-window", interruptedRequest, baseline);
markCloudPuzzleShadowInFlight(interruptedToken);
stageCloudPuzzleShadow("sudoku", "crash-window", interruptedNewest, baseline);
assert.deepEqual(
  resolveCloudPuzzleState("sudoku", "crash-window", interruptedRequest),
  interruptedNewest,
  "if the app dies before the old request callback, its possible server result must still recover the newest snapshot",
);

const failedRequest = { grid: "150", notes: {} };
const failedToken = stageCloudPuzzleShadow("sudoku", "known-failure", failedRequest, baseline);
markCloudPuzzleShadowInFlight(failedToken);
failCloudPuzzleShadowRequest(failedToken);
assert.deepEqual(
  resolveCloudPuzzleState("sudoku", "known-failure", baseline),
  failedRequest,
  "a known failed request should keep the local edit pending against the confirmed baseline",
);

const legacyKey = "puzzle_cloud_shadow_v1:sudoku:legacy";
storage.set(legacyKey, { version: 1, pending: true, state: aliceEdit });
currentUsername = "";
assert.equal(stageCloudPuzzleShadow("sudoku", "legacy", offlineEdit, baseline), null);
assert.equal(storage.has(legacyKey), false, "unowned legacy shadows should be removed, not migrated");
assert.deepEqual(
  resolveCloudPuzzleState("sudoku", "legacy", baseline),
  baseline,
  "an empty username must not read or create an unscoped shadow",
);

for (const page of ["sudoku", "idiom", "memory"]) {
  const pageSource = fs.readFileSync(path.resolve(import.meta.dirname, `../pages/${page}/index.ts`), "utf8");
  const queueSave = pageSource.slice(pageSource.indexOf("  queueSave()"), pageSource.indexOf("  async flushSave()"));
  assert.ok(
    queueSave.indexOf("createSaveTask") >= 0 &&
      queueSave.indexOf("createSaveTask") < queueSave.indexOf("setTimeout"),
    `${page} must stage its snapshot synchronously before the debounce timer/enqueue`,
  );
}

console.log("Puzzle storage shadow: 11 scenarios passed");
