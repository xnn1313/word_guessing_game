import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const sourcePath = path.resolve(import.meta.dirname, "../utils/latest-task-queue.ts");
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
  fileName: sourcePath,
}).outputText;
const module = { exports: {} };
new Function("exports", "module", compiled)(module.exports, module);
const { LatestTaskQueue } = module.exports;

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

{
  const expected = new Error("cloud unavailable");
  const reported = [];
  const queue = new LatestTaskQueue(async () => { throw expected; }, (error) => reported.push(error));
  await assert.rejects(queue.flush("snapshot"), (error) => error === expected);
  assert.deepEqual(reported, [expected], "worker errors should still reach onError");
}

{
  const firstStarted = deferred();
  const releaseFirst = deferred();
  const received = [];
  let active = 0;
  let maxActive = 0;
  const queue = new LatestTaskQueue(async (task) => {
    active += 1;
    maxActive = Math.max(maxActive, active);
    received.push(task);
    if (task === 1) {
      firstStarted.resolve();
      await releaseFirst.promise;
    }
    active -= 1;
  });
  queue.enqueue(1);
  await firstStarted.promise;
  queue.enqueue(2);
  queue.enqueue(3);
  const flushed = queue.flush();
  releaseFirst.resolve();
  await flushed;
  assert.deepEqual(received, [1, 3], "only the latest not-started snapshot should run");
  assert.equal(maxActive, 1, "workers must run serially");
}

{
  const failed = new Error("old snapshot failed");
  const firstStarted = deferred();
  const releaseFirst = deferred();
  const queue = new LatestTaskQueue(async (task) => {
    if (task === "old") {
      firstStarted.resolve();
      await releaseFirst.promise;
      throw failed;
    }
  });
  queue.enqueue("old");
  await firstStarted.promise;
  const flushed = queue.flush("latest");
  releaseFirst.resolve();
  await flushed;
}

console.log("LatestTaskQueue: 3 scenarios passed");
