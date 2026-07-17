(function () {
    "use strict";

    const kit = window.WebPuzzleKit;
    if (!kit) throw new Error("WebPuzzleKit 未初始化");

    const { bridge } = kit;
    const DIFFICULTY_LABELS = { easy: "简单", medium: "中等", hard: "困难" };

    function copyNotes(notes) {
        const result = {};
        if (!notes || typeof notes !== "object") return result;
        Object.entries(notes).forEach(([index, values]) => {
            if (!Array.isArray(values)) return;
            result[String(index)] = [...new Set(values.map(Number).filter((value) => value >= 1 && value <= 9))]
                .sort((left, right) => left - right);
        });
        return result;
    }

    function createLatestSaver(worker) {
        let pending = null;
        let active = null;

        function pump() {
            if (active) return active;
            active = (async () => {
                let latestError = null;
                while (pending) {
                    const task = pending;
                    pending = null;
                    try {
                        await worker(task);
                        latestError = null;
                    } catch (error) {
                        latestError = error;
                    }
                }
                if (latestError) throw latestError;
            })().finally(() => {
                active = null;
                if (pending) pump().catch(() => {});
            });
            return active;
        }

        return {
            enqueue(task) {
                pending = task;
                pump().catch(() => {});
            },
            async flush(task) {
                if (task) pending = task;
                while (pending || active) await pump();
            },
        };
    }

    kit.register("sudoku", (panel) => {
        let loaded = false;
        let loading = false;
        let loadVersion = 0;
        let saveTimer = null;
        let selectedIndex = -1;
        let mode = "daily";
        let difficulty = "medium";
        let puzzle = null;
        let grid = [];
        let notes = {};
        let elapsedSeconds = 0;
        let hintsUsed = 0;
        let mistakes = 0;
        let maxHints = 3;
        let noteMode = false;
        let invalidCells = new Set();
        let completed = false;
        let result = null;
        let submitting = false;
        let hinting = false;

        const clock = kit.createClock(() => {
            if (!loaded || loading || completed) return;
            elapsedSeconds += 1;
            updateStatus();
            if (elapsedSeconds % 15 === 0) scheduleSave();
        });

        panel.innerHTML = `
            <div class="puzzle-heading">
                <div class="puzzle-title">
                    <h2>数独挑战</h2>
                    <p>填满九宫格，让每行、每列和每个 3×3 宫都包含 1–9。支持候选数、提示与自动存档。</p>
                </div>
                <span class="puzzle-heading-meta" data-role="date-label">每日题</span>
            </div>
            <div class="puzzle-toolbar">
                <div class="puzzle-toolbar-group">
                    <div class="puzzle-segment" aria-label="数独模式">
                        <button type="button" data-action="mode" data-value="daily">每日挑战</button>
                        <button type="button" data-action="mode" data-value="practice">自由练习</button>
                    </div>
                    <button type="button" class="puzzle-chip" data-action="difficulty" data-value="easy">简单</button>
                    <button type="button" class="puzzle-chip" data-action="difficulty" data-value="medium">中等</button>
                    <button type="button" class="puzzle-chip" data-action="difficulty" data-value="hard">困难</button>
                </div>
                <button type="button" class="puzzle-button secondary" data-action="clear">清空填写</button>
            </div>
            <div data-role="sudoku-content"><div class="puzzle-loading">正在准备数独…</div></div>
        `;

        const content = panel.querySelector("[data-role='sudoku-content']");

        function stateSnapshot() {
            return {
                grid: grid.join(""),
                notes: copyNotes(notes),
                elapsed_seconds: elapsedSeconds,
                hints_used: hintsUsed,
                mistakes,
            };
        }

        function sameState(left, right) {
            if (!left || !right) return false;
            return JSON.stringify(left) === JSON.stringify(right);
        }

        function persistLocalNow() {
            if (!puzzle || completed) return;
            kit.saveStored("state", "sudoku", puzzle.puzzle_id, stateSnapshot());
        }

        function createCloudTask() {
            if (!puzzle || completed || !kit.isLoggedIn()) return null;
            persistLocalNow();
            return {
                account: String(bridge.getUsername() || ""),
                runId: puzzle.run_id || "",
                puzzleId: puzzle.puzzle_id,
                state: stateSnapshot(),
            };
        }

        const saver = createLatestSaver(async (task) => {
            if (!kit.isLoggedIn() || String(bridge.getUsername() || "") !== task.account) {
                throw new Error("登录账号已变更，已停止旧账号的数独云存档");
            }
            if (!task.runId) throw new Error("数独云存档缺少运行标识");
            await bridge.fetchJSON(`${bridge.apiBase}/sudoku/save`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    run_id: task.runId,
                    puzzle_id: task.puzzleId,
                    grid: task.state.grid,
                    notes: task.state.notes,
                    elapsed_seconds: task.state.elapsed_seconds,
                    mistakes: task.state.mistakes,
                }),
            });
            const localShadow = kit.loadStored("state", "sudoku", task.puzzleId, null);
            if (sameState(localShadow, task.state)) {
                kit.clearStored("state", "sudoku", task.puzzleId);
            }
        });

        function scheduleSave() {
            if (!puzzle || completed) return;
            persistLocalNow();
            window.clearTimeout(saveTimer);
            const task = createCloudTask();
            if (task) saveTimer = window.setTimeout(() => saver.enqueue(task), 500);
        }

        async function flushSave() {
            if (!puzzle || completed) return;
            window.clearTimeout(saveTimer);
            saveTimer = null;
            persistLocalNow();
            const task = createCloudTask();
            if (task) await saver.flush(task);
        }

        function setToolbarState() {
            panel.querySelectorAll("[data-action='mode']").forEach((button) => {
                button.classList.toggle("active", button.dataset.value === mode);
            });
            panel.querySelectorAll("[data-action='difficulty']").forEach((button) => {
                button.classList.toggle("active", button.dataset.value === difficulty);
            });
            const dateLabel = panel.querySelector("[data-role='date-label']");
            if (dateLabel) {
                dateLabel.textContent = mode === "daily"
                    ? (puzzle && puzzle.puzzle_date ? `${puzzle.puzzle_date} 每日题` : "每日题")
                    : `${DIFFICULTY_LABELS[difficulty]}练习`;
            }
        }

        function updateStatus() {
            const elapsed = panel.querySelector("[data-role='elapsed']");
            const hints = panel.querySelector("[data-role='hints']");
            const mistakeNode = panel.querySelector("[data-role='mistakes']");
            if (elapsed) elapsed.textContent = kit.formatTime(elapsedSeconds);
            if (hints) hints.textContent = `${hintsUsed}/${maxHints}`;
            if (mistakeNode) mistakeNode.textContent = String(mistakes);
            const hintButton = panel.querySelector("[data-action='hint']");
            if (hintButton) hintButton.disabled = completed || hinting || submitting || hintsUsed >= maxHints;
        }

        function renderBoard() {
            const board = panel.querySelector("[data-role='board']");
            if (!board || !puzzle) return;
            const selectedValue = selectedIndex >= 0 ? grid[selectedIndex] : "0";
            board.innerHTML = grid.map((value, index) => {
                const row = Math.floor(index / 9);
                const column = index % 9;
                const given = puzzle.givens[index] !== "0";
                const classes = ["sudoku-cell"];
                if (given) classes.push("given");
                if (column === 2 || column === 5) classes.push("box-right");
                if (row === 2 || row === 5) classes.push("box-bottom");
                if (index === selectedIndex) classes.push("selected");
                if (invalidCells.has(index)) classes.push("invalid");
                if (selectedValue !== "0" && value === selectedValue && index !== selectedIndex) classes.push("same-value");
                const noteText = value === "0" ? (notes[String(index)] || []).join("") : "";
                const display = value === "0" ? "" : value;
                return `
                    <button type="button" class="${classes.join(" ")}" data-action="select" data-index="${index}"
                        aria-label="第 ${row + 1} 行第 ${column + 1} 列${display ? `，数字 ${display}` : "，空格"}">
                        ${display || (noteText ? `<span class="sudoku-note-text">${noteText}</span>` : "")}
                    </button>
                `;
            }).join("");
        }

        function renderGame() {
            if (!puzzle) return;
            content.innerHTML = `
                <div class="sudoku-workspace">
                    <div class="sudoku-board" data-role="board" role="grid" aria-label="数独棋盘"></div>
                    <aside class="sudoku-side">
                        <div class="puzzle-status">
                            <div class="puzzle-status-item"><span>用时</span><strong data-role="elapsed">${kit.formatTime(elapsedSeconds)}</strong></div>
                            <div class="puzzle-status-item"><span>提示</span><strong data-role="hints">${hintsUsed}/${maxHints}</strong></div>
                            <div class="puzzle-status-item"><span>错误</span><strong data-role="mistakes">${mistakes}</strong></div>
                        </div>
                        <div class="digit-pad" aria-label="数字键盘">
                            ${Array.from({ length: 9 }, (_, index) => `<button type="button" class="digit-button" data-action="digit" data-value="${index + 1}">${index + 1}</button>`).join("")}
                        </div>
                        <div class="sudoku-tools">
                            <button type="button" class="puzzle-button secondary${noteMode ? " active" : ""}" data-action="note">${noteMode ? "候选数：开" : "候选数"}</button>
                            <button type="button" class="puzzle-button secondary" data-action="erase">擦除</button>
                            <button type="button" class="puzzle-button secondary" data-action="hint" ${hintsUsed >= maxHints ? "disabled" : ""}>提示</button>
                            <button type="button" class="puzzle-button" data-action="submit">检查答案</button>
                        </div>
                        <p class="memory-note">点击格子后输入数字。开启候选数可记录多个备选；键盘可使用 1–9、Delete 和方向键。</p>
                    </aside>
                </div>
                <div data-role="result"></div>
            `;
            renderBoard();
            renderResult();
            updateStatus();
        }

        function renderResult() {
            const host = panel.querySelector("[data-role='result']");
            if (!host) return;
            if (!completed || !result) {
                host.innerHTML = "";
                return;
            }
            host.innerHTML = `
                <div class="puzzle-result" aria-live="polite">
                    <h3>数独完成</h3>
                    <div class="puzzle-result-stars">${kit.renderStars(result.stars)}</div>
                    <p>得分 ${Number(result.score || 0)} · 用时 ${kit.formatTime(result.elapsed_seconds)} · ${Number(result.hints_used || 0)} 次提示${result.is_new_best ? " · 新纪录" : ""}</p>
                    <div class="puzzle-result-actions">
                        <button type="button" class="puzzle-button" data-action="next">${mode === "daily" ? "练习一局" : "下一题"}</button>
                    </div>
                </div>
            `;
        }

        function chooseSavedState(payload) {
            const local = kit.loadStored("state", "sudoku", payload.puzzle_id, null);
            if (kit.isLoggedIn()) return local || payload.saved_state || null;
            return local;
        }

        async function loadPuzzle(forceNew = false) {
            const version = ++loadVersion;
            loading = true;
            loaded = false;
            completed = false;
            result = null;
            clock.stop();
            window.clearTimeout(saveTimer);
            saveTimer = null;
            setToolbarState();
            content.innerHTML = `<div class="puzzle-loading">正在准备${DIFFICULTY_LABELS[difficulty]}数独…</div>`;
            try {
                const definitionSlot = `${mode}:${difficulty}`;
                let payload = null;
                if (!kit.isLoggedIn() && mode === "practice" && !forceNew) {
                    payload = kit.loadStored("definition", "sudoku", definitionSlot, null);
                }
                if (!payload) {
                    payload = await bridge.fetchJSON(`${bridge.apiBase}/sudoku/puzzle?mode=${encodeURIComponent(mode)}&difficulty=${encodeURIComponent(difficulty)}`);
                    if (!kit.isLoggedIn() && mode === "practice") {
                        kit.saveStored("definition", "sudoku", definitionSlot, payload);
                    }
                }
                if (version !== loadVersion) return;
                const saved = chooseSavedState(payload);
                const savedGrid = saved && typeof saved.grid === "string" && saved.grid.length === 81
                    ? saved.grid
                    : payload.givens;
                puzzle = payload;
                grid = savedGrid.split("");
                notes = copyNotes(saved && saved.notes);
                elapsedSeconds = Math.max(0, Number(saved && saved.elapsed_seconds) || 0);
                hintsUsed = Math.max(0, Number(saved && saved.hints_used) || 0);
                mistakes = Math.max(0, Number(saved && saved.mistakes) || 0);
                maxHints = Math.max(0, Number(payload.limits && payload.limits.max_hints) || 3);
                selectedIndex = -1;
                invalidCells = new Set();
                noteMode = false;
                loaded = true;
                renderGame();
                setToolbarState();
                clock.start();
            } catch (error) {
                if (version !== loadVersion) return;
                puzzle = null;
                content.innerHTML = `
                    <div class="puzzle-empty">
                        <div><p>${kit.escapeHTML(error.message || "数独加载失败")}</p><div class="puzzle-actions"><button type="button" class="puzzle-button" data-action="retry">重试</button></div></div>
                    </div>`;
                bridge.showToast(error.message || "数独题目加载失败", false);
            } finally {
                if (version === loadVersion) loading = false;
            }
        }

        function selectCell(index) {
            if (!loaded || index < 0 || index >= 81) return;
            selectedIndex = index;
            renderBoard();
        }

        function inputDigit(value) {
            if (!puzzle || completed || submitting || hinting || selectedIndex < 0) return;
            if (puzzle.givens[selectedIndex] !== "0") return;
            const key = String(selectedIndex);
            if (noteMode && value > 0 && grid[selectedIndex] === "0") {
                const values = [...(notes[key] || [])];
                const existing = values.indexOf(value);
                if (existing >= 0) values.splice(existing, 1);
                else values.push(value);
                values.sort((left, right) => left - right);
                if (values.length) notes[key] = values;
                else delete notes[key];
            } else {
                grid[selectedIndex] = value > 0 ? String(value) : "0";
                delete notes[key];
            }
            invalidCells.delete(selectedIndex);
            renderBoard();
            scheduleSave();
        }

        function clearInputs() {
            if (!loaded || loading || !puzzle || completed || submitting || hinting) return;
            grid = puzzle.givens.split("");
            notes = {};
            invalidCells = new Set();
            selectedIndex = -1;
            renderBoard();
            scheduleSave();
            bridge.showToast("已清空本题填写", true);
        }

        async function requestHint(button) {
            if (!puzzle || hinting || submitting || completed || hintsUsed >= maxHints) return;
            hinting = true;
            kit.setBusy(button, true, "提示中…");
            updateStatus();
            try {
                await flushSave();
                const response = await bridge.fetchJSON(`${bridge.apiBase}/sudoku/hint`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        run_id: puzzle.run_id || undefined,
                        puzzle_id: puzzle.puzzle_id,
                        grid: grid.join(""),
                    }),
                });
                const index = Number(response.index);
                if (!Number.isInteger(index) || index < 0 || index >= 81) throw new Error("提示数据无效");
                grid[index] = String(response.value);
                delete notes[String(index)];
                invalidCells.delete(index);
                selectedIndex = index;
                hintsUsed = Number(response.hints_used || hintsUsed + 1);
                renderBoard();
                updateStatus();
                scheduleSave();
            } catch (error) {
                bridge.showToast(error.message || "获取提示失败", false);
            } finally {
                hinting = false;
                kit.setBusy(button, false);
                updateStatus();
            }
        }

        async function submitPuzzle(button) {
            if (!puzzle || submitting || completed || hinting) return;
            submitting = true;
            kit.setBusy(button, true, "检查中…");
            try {
                await flushSave();
                const response = await bridge.fetchJSON(`${bridge.apiBase}/sudoku/submit`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    acceptedStatuses: [422],
                    body: JSON.stringify({
                        run_id: puzzle.run_id || undefined,
                        puzzle_id: puzzle.puzzle_id,
                        grid: grid.join(""),
                        elapsed_seconds: elapsedSeconds,
                        mistakes,
                        hints_used: hintsUsed,
                    }),
                });
                if (!response.correct) {
                    invalidCells = new Set(Array.isArray(response.invalid_cells) ? response.invalid_cells.map(Number) : []);
                    mistakes += 1;
                    renderBoard();
                    updateStatus();
                    scheduleSave();
                    bridge.showToast("还有格子不正确，已为你标出", false);
                    return;
                }
                completed = true;
                result = response.result || {};
                invalidCells = new Set();
                clock.stop();
                window.clearTimeout(saveTimer);
                kit.clearStored("state", "sudoku", puzzle.puzzle_id);
                if (mode === "practice") kit.clearStored("definition", "sudoku", `${mode}:${difficulty}`);
                renderBoard();
                renderResult();
                bridge.showToast("数独完成，成绩已记录", true);
            } catch (error) {
                bridge.showToast(error.message || "提交数独失败", false);
            } finally {
                submitting = false;
                kit.setBusy(button, false);
            }
        }

        async function changeSetting(nextMode, nextDifficulty) {
            if (loading || submitting || hinting) return;
            try {
                await flushSave();
            } catch (error) {
                bridge.showToast(error.message || "数独进度未同步，已取消切换", false);
                return;
            }
            mode = nextMode;
            difficulty = nextDifficulty;
            await loadPuzzle();
        }

        async function nextPuzzle() {
            if (loading || submitting) return;
            if (mode === "daily") mode = "practice";
            await loadPuzzle(true);
        }

        panel.addEventListener("click", (event) => {
            const button = event.target.closest("[data-action]");
            if (!button || !panel.contains(button)) return;
            const action = button.dataset.action;
            if (action === "select") selectCell(Number(button.dataset.index));
            else if (action === "digit") inputDigit(Number(button.dataset.value));
            else if (action === "erase") inputDigit(0);
            else if (action === "note") {
                if (completed || submitting || hinting) return;
                noteMode = !noteMode;
                renderGame();
            } else if (action === "clear") clearInputs();
            else if (action === "hint") requestHint(button);
            else if (action === "submit") submitPuzzle(button);
            else if (action === "mode" && button.dataset.value !== mode) changeSetting(button.dataset.value, difficulty);
            else if (action === "difficulty" && button.dataset.value !== difficulty) changeSetting(mode, button.dataset.value);
            else if (action === "next") nextPuzzle();
            else if (action === "retry") loadPuzzle();
        });

        window.addEventListener("keydown", (event) => {
            if (panel.hidden || !loaded || completed || submitting || hinting) return;
            if (/^[1-9]$/.test(event.key)) {
                event.preventDefault();
                inputDigit(Number(event.key));
                return;
            }
            if (event.key === "Backspace" || event.key === "Delete" || event.key === "0") {
                event.preventDefault();
                inputDigit(0);
                return;
            }
            if (event.key.toLowerCase() === "n") {
                event.preventDefault();
                noteMode = !noteMode;
                renderGame();
                return;
            }
            const steps = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -9, ArrowDown: 9 };
            if (Object.prototype.hasOwnProperty.call(steps, event.key)) {
                event.preventDefault();
                const next = selectedIndex < 0 ? 0 : Math.max(0, Math.min(80, selectedIndex + steps[event.key]));
                selectCell(next);
            }
        });

        return {
            async enter(force = false) {
                if (force || !loaded) await loadPuzzle();
                else if (!completed) clock.start();
            },
            async beforeLeave() {
                clock.stop();
                try {
                    await flushSave();
                    return true;
                } catch (error) {
                    bridge.showToast(error.message || "数独进度保存失败，已取消切换", false);
                    if (!completed) clock.start();
                    return false;
                }
            },
            onAuthChange() {
                loadVersion += 1;
                loaded = false;
                loading = false;
                puzzle = null;
                completed = false;
                result = null;
                clock.stop();
                window.clearTimeout(saveTimer);
                saveTimer = null;
            },
            persistLocalNow,
        };
    });
})();
