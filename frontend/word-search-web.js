(function () {
    "use strict";

    const kit = window.WebPuzzleKit;
    if (!kit) throw new Error("WebPuzzleKit 未初始化");

    const DIFFICULTY_LABELS = { easy: "简单", medium: "中等", hard: "困难" };

    function controller(panel) {
        panel.innerHTML = `
            <div class="puzzle-heading">
                <div class="puzzle-title">
                    <h2>字阵寻踪</h2>
                    <p>根据释义，在字阵中沿横、竖或斜线找出隐藏的四字词语。词语可能反向出现，路径也可以彼此交叉。</p>
                </div>
                <span class="puzzle-heading-meta" id="ws-board-meta">每日一阵</span>
            </div>
            <div class="puzzle-toolbar">
                <div class="puzzle-toolbar-group">
                    <div class="puzzle-segment" aria-label="字阵模式">
                        <button type="button" class="active" data-ws-mode="daily">每日</button>
                        <button type="button" data-ws-mode="practice">练习</button>
                    </div>
                    <div class="puzzle-segment" aria-label="字阵难度">
                        <button type="button" data-ws-difficulty="easy">简单</button>
                        <button type="button" class="active" data-ws-difficulty="medium">中等</button>
                        <button type="button" data-ws-difficulty="hard">困难</button>
                    </div>
                </div>
                <button type="button" class="puzzle-button secondary" data-ws-action="new">换一阵</button>
            </div>
            <div class="puzzle-toolbar" id="ws-theme-toolbar">
                <div class="puzzle-toolbar-group" id="ws-theme-chips" aria-label="字阵主题"></div>
            </div>
            <div id="ws-content"><div class="puzzle-loading">正在铺开字阵…</div></div>
        `;

        const state = {
            loaded: false,
            loading: false,
            mode: "daily",
            difficulty: "medium",
            theme: "classic",
            themes: [],
            board: null,
            foundIds: [],
            foundPaths: [],
            elapsed: 0,
            mistakes: 0,
            completed: false,
            result: null,
            selecting: [],
            pointerStart: null,
            pointerMoved: false,
            clickAnchor: null,
            submitting: false,
            saveTimer: null,
            pendingSave: null,
            saveLoop: null,
            loadVersion: 0,
        };

        const clock = kit.createClock(() => {
            if (!state.board || state.completed || panel.hidden) return;
            state.elapsed += 1;
            const value = panel.querySelector("[data-ws-stat=time]");
            if (value) value.textContent = kit.formatTime(state.elapsed);
            if (state.elapsed % 15 === 0) scheduleSave(true);
        });

        function settingsSlot() {
            return `${state.mode}:${state.difficulty}:${state.theme}`;
        }

        function boardState() {
            return {
                board_id: state.board?.board_id || "",
                found_entry_ids: [...state.foundIds],
                found_paths: state.foundPaths.map((path) => path.map((cell) => ({ ...cell }))),
                elapsed_seconds: state.elapsed,
                mistakes: state.mistakes,
            };
        }

        function persistLocalNow() {
            if (!state.board || state.completed) return;
            kit.saveStored("state", "word-search", state.board.board_id, boardState());
            kit.saveStored("slot", "word-search", settingsSlot(), { board_id: state.board.board_id });
        }

        function makeSaveTask(silent) {
            if (!state.board || state.completed) return null;
            persistLocalNow();
            return {
                silent,
                boardId: state.board.board_id,
                runId: state.board.run_id || "",
                payload: boardState(),
                loggedIn: kit.isLoggedIn(),
                account: String(kit.bridge.getUsername() || ""),
            };
        }

        function queueSave(silent = true) {
            const task = makeSaveTask(silent);
            if (!task || !task.loggedIn || !task.runId) return Promise.resolve();
            state.pendingSave = task;
            if (!state.saveLoop) {
                state.saveLoop = (async () => {
                    while (state.pendingSave) {
                        const current = state.pendingSave;
                        state.pendingSave = null;
                        try {
                            if (!kit.isLoggedIn() || String(kit.bridge.getUsername() || "") !== current.account) {
                                throw new Error("登录账号已变更，已停止旧账号的字阵云存档");
                            }
                            await kit.bridge.fetchJSON(`${kit.bridge.apiBase}/word-search/save`, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({
                                    board_id: current.payload.board_id,
                                    run_id: current.runId,
                                    found_paths: current.payload.found_paths,
                                    elapsed_seconds: current.payload.elapsed_seconds,
                                    mistakes: current.payload.mistakes,
                                }),
                            });
                            const localShadow = kit.loadStored("state", "word-search", current.boardId, null);
                            if (JSON.stringify(localShadow) === JSON.stringify(current.payload)) {
                                kit.clearStored("state", "word-search", current.boardId);
                            }
                        } catch (error) {
                            if (!current.silent) throw error;
                        }
                    }
                })().finally(() => { state.saveLoop = null; });
            }
            return state.saveLoop;
        }

        function scheduleSave(silent = true) {
            window.clearTimeout(state.saveTimer);
            state.saveTimer = window.setTimeout(() => { void queueSave(silent); }, 500);
        }

        function renderThemeChips() {
            const holder = panel.querySelector("#ws-theme-chips");
            holder.innerHTML = state.themes.map((theme) => `
                <button type="button" class="puzzle-chip ${theme.key === state.theme ? "active" : ""}"
                    data-ws-theme="${kit.escapeHTML(theme.key)}" title="${kit.escapeHTML(theme.description)}">
                    ${kit.escapeHTML(theme.title)}
                </button>
            `).join("");
        }

        function coordinateKey(cell) {
            return `${cell.row},${cell.column}`;
        }

        function foundCellKeys() {
            const keys = new Set();
            state.foundPaths.forEach((path) => path.forEach((cell) => keys.add(coordinateKey(cell))));
            return keys;
        }

        function render() {
            if (!state.board) return;
            const board = state.board;
            const newButton = panel.querySelector("[data-ws-action='new']");
            if (newButton) newButton.textContent = state.mode === "daily" ? "进入练习" : "换一阵";
            const foundCells = foundCellKeys();
            const selected = new Set(state.selecting.map(coordinateKey));
            panel.querySelector("#ws-board-meta").textContent = board.mode === "daily"
                ? `${board.puzzle_date || "今日"} · ${board.theme_title}`
                : `${board.theme_title} · 自由练习`;
            panel.querySelector("#ws-content").innerHTML = `
                <div class="word-search-workspace">
                    <div>
                        <div class="word-search-board" style="--search-size:${board.columns}" role="grid" aria-label="${board.rows}乘${board.columns}字阵">
                            ${board.grid.map((row, rowIndex) => row.map((character, columnIndex) => {
                                const key = `${rowIndex},${columnIndex}`;
                                const classes = ["word-search-cell"];
                                if (foundCells.has(key)) classes.push("found");
                                if (selected.has(key)) classes.push("selecting");
                                return `<button type="button" class="${classes.join(" ")}" role="gridcell"
                                    data-ws-row="${rowIndex}" data-ws-column="${columnIndex}"
                                    aria-label="第${rowIndex + 1}行第${columnIndex + 1}列，${kit.escapeHTML(character)}">${kit.escapeHTML(character)}</button>`;
                            }).join("")).join("")}
                        </div>
                        <div class="word-search-selection" id="ws-selection">${state.selecting.length
                            ? state.selecting.map((cell) => board.grid[cell.row][cell.column]).join("")
                            : "按住拖动，或依次点击起点和终点"}</div>
                    </div>
                    <aside class="word-search-side">
                        <div class="puzzle-status">
                            <div class="puzzle-status-item">找到 <strong data-ws-stat="found">${state.foundIds.length}/${board.word_count}</strong></div>
                            <div class="puzzle-status-item">用时 <strong data-ws-stat="time">${kit.formatTime(state.elapsed)}</strong></div>
                            <div class="puzzle-status-item">失误 <strong data-ws-stat="mistakes">${state.mistakes}</strong></div>
                        </div>
                        <div class="word-search-targets">
                            ${board.entries.map((entry, index) => {
                                const found = state.foundIds.includes(entry.id);
                                return `<div class="word-search-target ${found ? "found" : ""}">
                                    <div><strong>${kit.escapeHTML(entry.clue)}</strong><span>目标 ${index + 1} · ${entry.length} 个字</span></div>
                                    <em>${found ? "已找到 ✓" : "待寻找"}</em>
                                </div>`;
                            }).join("")}
                        </div>
                        <div class="puzzle-actions">
                            <button type="button" class="puzzle-button secondary" data-ws-action="clear-selection">清除选区</button>
                        </div>
                    </aside>
                </div>
                ${state.completed && state.result ? `
                    <div class="puzzle-result">
                        <h3>字阵全部找齐</h3>
                        <div class="puzzle-result-stars">${kit.renderStars(state.result.stars)}</div>
                        <p>得分 ${Number(state.result.score || 0)} · 用时 ${kit.formatTime(state.result.elapsed_seconds)} · 失误 ${Number(state.result.mistakes || 0)}</p>
                        <div class="puzzle-result-actions">
                            <button type="button" class="puzzle-button" data-ws-action="again">再来一阵</button>
                            <button type="button" class="puzzle-button secondary" data-ws-action="change-theme">换个主题</button>
                        </div>
                    </div>` : ""}
            `;
        }

        function pathBetween(start, end) {
            const rowDistance = end.row - start.row;
            const columnDistance = end.column - start.column;
            if (rowDistance !== 0 && columnDistance !== 0 && Math.abs(rowDistance) !== Math.abs(columnDistance)) {
                return [start];
            }
            const length = Math.max(Math.abs(rowDistance), Math.abs(columnDistance)) + 1;
            const rowStep = Math.sign(rowDistance);
            const columnStep = Math.sign(columnDistance);
            return Array.from({ length }, (_, index) => ({
                row: start.row + rowStep * index,
                column: start.column + columnStep * index,
            }));
        }

        function cellFromTarget(target) {
            const cell = target?.closest?.(".word-search-cell");
            if (!cell || !panel.contains(cell)) return null;
            return { row: Number(cell.dataset.wsRow), column: Number(cell.dataset.wsColumn) };
        }

        function preview(path) {
            state.selecting = path;
            const selected = new Set(path.map(coordinateKey));
            panel.querySelectorAll(".word-search-cell").forEach((cell) => {
                selected.has(`${cell.dataset.wsRow},${cell.dataset.wsColumn}`)
                    ? cell.classList.add("selecting")
                    : cell.classList.remove("selecting");
            });
            const label = panel.querySelector("#ws-selection");
            if (label) label.textContent = path.length
                ? path.map((item) => state.board.grid[item.row][item.column]).join("")
                : "按住拖动，或依次点击起点和终点";
        }

        async function submitPath(path) {
            if (state.submitting || state.completed || path.length < 2) return;
            state.submitting = true;
            const boardId = state.board.board_id;
            try {
                const response = await kit.bridge.fetchJSON(`${kit.bridge.apiBase}/word-search/submit`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    acceptedStatuses: [422],
                    body: JSON.stringify({
                        board_id: boardId,
                        run_id: state.board.run_id || undefined,
                        found_paths: state.foundPaths,
                        path,
                        elapsed_seconds: state.elapsed,
                        mistakes: state.mistakes,
                    }),
                });
                if (state.board?.board_id !== boardId) return;
                if (!response.correct) {
                    state.mistakes = Number(response.mistakes ?? state.mistakes + 1);
                    const cells = [...panel.querySelectorAll(".word-search-cell.selecting")];
                    cells.forEach((cell) => cell.classList.add("invalid"));
                    window.setTimeout(() => cells.forEach((cell) => cell.classList.remove("invalid")), 300);
                    kit.bridge.showToast("这条路径不在目标词语中，再找找看", false);
                    renderStatusOnly();
                    scheduleSave(true);
                    return;
                }
                state.foundIds = Array.isArray(response.found_entry_ids)
                    ? response.found_entry_ids
                    : [...state.foundIds];
                if (!state.foundPaths.some((item) => item.map(coordinateKey).join("|") === path.map(coordinateKey).join("|")
                    || item.map(coordinateKey).reverse().join("|") === path.map(coordinateKey).join("|"))) {
                    state.foundPaths.push(path.map((cell) => ({ ...cell })));
                }
                if (response.status === "completed") {
                    state.completed = true;
                    state.result = response.result;
                    state.foundIds = state.board.entries.map((entry) => entry.id);
                    clock.stop();
                    kit.clearStored("state", "word-search", boardId);
                    kit.clearStored("slot", "word-search", settingsSlot());
                    kit.bridge.showToast("全部找到！", true);
                } else {
                    persistLocalNow();
                    scheduleSave(true);
                    kit.bridge.showToast(`找到一个，还剩 ${Number(response.remaining_count || 0)} 个`, true);
                }
                state.selecting = [];
                render();
            } catch (error) {
                kit.bridge.showToast(error.message || "路径提交失败", false);
            } finally {
                state.submitting = false;
                state.clickAnchor = null;
                preview([]);
            }
        }

        function renderStatusOnly() {
            const found = panel.querySelector("[data-ws-stat=found]");
            const mistakes = panel.querySelector("[data-ws-stat=mistakes]");
            if (found) found.textContent = `${state.foundIds.length}/${state.board.word_count}`;
            if (mistakes) mistakes.textContent = state.mistakes;
        }

        async function loadBoard(fresh = false) {
            if (state.loading) return;
            state.loading = true;
            const version = ++state.loadVersion;
            clock.stop();
            window.clearTimeout(state.saveTimer);
            panel.querySelector("#ws-content").innerHTML = '<div class="puzzle-loading">正在铺开字阵…</div>';
            try {
                if (!state.themes.length) {
                    const catalog = await kit.bridge.fetchJSON(`${kit.bridge.apiBase}/word-search/themes`);
                    state.themes = Array.isArray(catalog.themes) ? catalog.themes : [];
                    if (!state.themes.some((item) => item.key === state.theme) && state.themes[0]) {
                        state.theme = state.themes[0].key;
                    }
                    renderThemeChips();
                }
                let requestedId = "";
                if (!fresh && !kit.isLoggedIn()) {
                    requestedId = kit.loadStored("slot", "word-search", settingsSlot(), {})?.board_id || "";
                }
                const query = new URLSearchParams({
                    mode: state.mode,
                    difficulty: state.difficulty,
                    theme: state.theme,
                });
                if (requestedId) query.set("board_id", requestedId);
                if (fresh && state.mode === "practice") query.set("fresh", "1");
                const board = await kit.bridge.fetchJSON(`${kit.bridge.apiBase}/word-search/board?${query}`);
                if (version !== state.loadVersion) return;
                state.board = board;
                const localShadow = kit.loadStored("state", "word-search", board.board_id, null);
                const stored = kit.isLoggedIn() ? (localShadow || board.saved_state) : localShadow;
                state.foundIds = Array.isArray(stored?.found_entry_ids) ? [...stored.found_entry_ids] : [];
                state.foundPaths = Array.isArray(stored?.found_paths)
                    ? stored.found_paths.map((path) => path.map((cell) => ({ row: Number(cell.row), column: Number(cell.column) })))
                    : [];
                state.elapsed = Number(stored?.elapsed_seconds || 0);
                state.mistakes = Number(stored?.mistakes || 0);
                state.completed = false;
                state.result = null;
                state.selecting = [];
                state.clickAnchor = null;
                kit.saveStored("slot", "word-search", settingsSlot(), { board_id: board.board_id });
                render();
                clock.start();
                state.loaded = true;
            } catch (error) {
                if (version !== state.loadVersion) return;
                panel.querySelector("#ws-content").innerHTML = `
                    <div class="puzzle-empty"><div>字阵暂时没有铺好<br><button type="button" class="puzzle-button secondary" data-ws-action="retry">重新加载</button></div></div>`;
                kit.bridge.showToast(error.message || "字阵加载失败", false);
            } finally {
                if (version === state.loadVersion) state.loading = false;
            }
        }

        async function changeSetting(kind, value) {
            if (state[kind] === value || state.loading) return;
            if (!(await flushSave())) return;
            state[kind] = value;
            panel.querySelectorAll(`[data-ws-${kind}]`).forEach((button) => {
                button.classList.toggle("active", button.dataset[`ws${kind[0].toUpperCase()}${kind.slice(1)}`] === value);
            });
            if (kind === "theme") renderThemeChips();
            await loadBoard(false);
        }

        async function flushSave() {
            window.clearTimeout(state.saveTimer);
            state.saveTimer = null;
            try {
                await queueSave(false);
                if (state.saveLoop) await state.saveLoop;
                return true;
            } catch (error) {
                kit.bridge.showToast(error.message || "字阵云存档失败，本地备份已保留", false);
                return false;
            }
        }

        panel.addEventListener("click", (event) => {
            const mode = event.target.closest("[data-ws-mode]")?.dataset.wsMode;
            const difficulty = event.target.closest("[data-ws-difficulty]")?.dataset.wsDifficulty;
            const theme = event.target.closest("[data-ws-theme]")?.dataset.wsTheme;
            const action = event.target.closest("[data-ws-action]")?.dataset.wsAction;
            if (mode) void changeSetting("mode", mode);
            else if (difficulty) void changeSetting("difficulty", difficulty);
            else if (theme) void changeSetting("theme", theme);
            else if (action === "new" || action === "again") void (async () => {
                if (!(await flushSave())) return;
                if (state.mode === "daily") {
                    state.mode = "practice";
                    panel.querySelectorAll("[data-ws-mode]").forEach((button) => {
                        button.classList.toggle("active", button.dataset.wsMode === state.mode);
                    });
                }
                await loadBoard(true);
            })();
            else if (action === "retry") void loadBoard(false);
            else if (action === "clear-selection") {
                state.clickAnchor = null;
                preview([]);
            } else if (action === "change-theme") {
                panel.querySelector("#ws-theme-toolbar")?.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        });

        panel.addEventListener("pointerdown", (event) => {
            const cell = cellFromTarget(event.target);
            if (!cell || state.submitting || state.completed) return;
            event.preventDefault();
            state.pointerStart = cell;
            state.pointerMoved = false;
            preview([cell]);
            event.target.setPointerCapture?.(event.pointerId);
        });

        panel.addEventListener("pointermove", (event) => {
            if (!state.pointerStart) return;
            const target = document.elementFromPoint(event.clientX, event.clientY);
            const cell = cellFromTarget(target);
            if (!cell) return;
            if (cell.row !== state.pointerStart.row || cell.column !== state.pointerStart.column) state.pointerMoved = true;
            preview(pathBetween(state.pointerStart, cell));
        });

        panel.addEventListener("pointerup", (event) => {
            if (!state.pointerStart) return;
            const start = state.pointerStart;
            const path = [...state.selecting];
            state.pointerStart = null;
            if (state.pointerMoved && path.length > 1) {
                state.clickAnchor = null;
                void submitPath(path);
                return;
            }
            const cell = cellFromTarget(event.target) || start;
            if (!state.clickAnchor) {
                state.clickAnchor = cell;
                preview([cell]);
            } else {
                const clickedPath = pathBetween(state.clickAnchor, cell);
                state.clickAnchor = null;
                if (clickedPath.length > 1) void submitPath(clickedPath);
                else preview([]);
            }
        });

        panel.addEventListener("pointercancel", () => {
            state.pointerStart = null;
            state.pointerMoved = false;
        });

        return {
            async enter(force = false) {
                if (force) {
                    state.loaded = false;
                    state.board = null;
                }
                if (!state.loaded) await loadBoard(false);
                else if (!state.completed) clock.start();
            },
            async beforeLeave() {
                clock.stop();
                return flushSave();
            },
            onAuthChange() {
                clock.stop();
                state.loadVersion += 1;
                state.loading = false;
                window.clearTimeout(state.saveTimer);
                state.loaded = false;
                state.board = null;
                state.pendingSave = null;
            },
            persistLocalNow,
        };
    }

    kit.register("word-search", controller);
})();
