import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const storage = new Map();
globalThis.wx = {
  getStorageSync(key) { return storage.get(key); },
  setStorageSync(key, value) { storage.set(key, structuredClone(value)); },
};

const sourcePath = path.resolve(import.meta.dirname, "../utils/level-progress.ts");
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  fileName: sourcePath,
}).outputText;
const module = { exports: {} };
new Function("exports", "module", "require", compiled)(module.exports, module, () => ({}));

const { completeGuestLevel, mergeGuestLevelProgress } = module.exports;
const catalog = {
  game_key: "sokoban",
  total_stars: 0,
  max_stars: 9,
  difficulties: [{
    key: "easy",
    completed_levels: 0,
    total_levels: 3,
    levels: [1, 2, 3].map((order) => ({
      order,
      puzzle_id: `sokoban-level-easy-0${order}`,
      unlocked: order === 1,
      stars: 0,
      best_score: null,
    })),
  }],
};

completeGuestLevel("sokoban", "easy", 1, 2);
let merged = mergeGuestLevelProgress(catalog, "sokoban");
assert.equal(merged.total_stars, 2);
assert.equal(merged.difficulties[0].levels[0].stars, 2);
assert.equal(merged.difficulties[0].levels[1].unlocked, true);
assert.equal(merged.difficulties[0].levels[2].unlocked, false);

completeGuestLevel("sokoban", "easy", 1, 1);
completeGuestLevel("sokoban", "easy", 2, 3);
merged = mergeGuestLevelProgress(catalog, "sokoban");
assert.equal(merged.total_stars, 5, "replaying a level must keep the best stars");
assert.equal(merged.difficulties[0].levels[2].unlocked, true);

console.log("Guest level progress: 7 scenarios passed");
