(function () {
    "use strict";

    const kit = window.WebPuzzleKit;
    if (!kit) throw new Error("WebPuzzleKit 未初始化");

    const DIFFICULTY_LABELS = { easy: "简单", medium: "中等", hard: "困难" };

    function entryCoordinates(entry) {
        const coordinates = [];
        for (let offset = 0; offset < Number(entry.length || 0); offset += 1) {
            coordinates.push(`${entry.start.row + (entry.direction === "down" ? offset : 0)},${entry.start.column + (entry.direction === "across" ? offset : 0)}`);
        }
        return coordinates;
    }

    function controller(panel) {
        const state = {
            view: "catalog",
            catalog: null,
            loading: false,
            dailyDifficulty: "medium",
            puzzle: null,
            grid: [],
            selectedIndex: -1,
            activeEntryId: "",
            elapsed: 0,
            hints: 0,
            mistakes: 0,
            invalid: [],
            completed: false,
            result: null,
            busy: false,
            saveTimer: null,
            pendingSave: null,
            saveLoop: null,
            loadVersion: 0,
            authResumePath: "",
        };

        const clock = kit.createClock(() => {
            if (!state.puzzle || state.completed || state.view !== "game" || panel.hidden) return;
            state.elapsed += 1;
            const timer = panel.querySelector("[data-idiom-stat=time]");
            if (timer) timer.textContent = kit.formatTime(state.elapsed);
            if (state.elapsed % 15 === 0) scheduleSave(true);
        });

        function guestProgress() {
            return kit.loadStored("progress", "idiom", "catalog", {});
        }

        function statePayload() {
            return {
                grid: [...state.grid],
                elapsed_seconds: state.elapsed,
                hints_used: state.hints,
                mistakes: state.mistakes,
            };
        }

        function persistLocalNow() {
            if (!state.puzzle || state.completed || state.view !== "game") return;
            kit.saveStored("state", "idiom", state.puzzle.puzzle_id, statePayload());
        }

        function makeSaveTask(silent) {
            if (!state.puzzle || state.completed || state.view !== "game") return null;
            persistLocalNow();
            return {
                silent,
                loggedIn: kit.isLoggedIn(),
                account: String(kit.bridge.getUsername() || ""),
                puzzleId: state.puzzle.puzzle_id,
                runId: state.puzzle.run_id || "",
                payload: statePayload(),
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
                                throw new Error("登录账号已变更，已停止旧账号的成语云存档");
                            }
                            await kit.bridge.fetchJSON(`${kit.bridge.apiBase}/idiom/save`, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({
                                    run_id: current.runId,
                                    puzzle_id: current.puzzleId,
                                    grid: current.payload.grid,
                                    elapsed_seconds: current.payload.elapsed_seconds,
                                    mistakes: current.payload.mistakes,
                                }),
                            });
                            const localShadow = kit.loadStored("state", "idiom", current.puzzleId, null);
                            if (JSON.stringify(localShadow) === JSON.stringify(current.payload)) {
                                kit.clearStored("state", "idiom", current.puzzleId);
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

        async function flushSave() {
            window.clearTimeout(state.saveTimer);
            state.saveTimer = null;
            try {
                await queueSave(false);
                if (state.saveLoop) await state.saveLoop;
                return true;
            } catch (error) {
                kit.bridge.showToast(error.message || "成语云存档失败，本地备份已保留", false);
                return false;
            }
        }

        function normalizedCatalog(raw) {
            const progress = kit.isLoggedIn() ? {} : guestProgress();
            let guestStars = 0;
            const categories = (raw.categories || []).map((category) => {
                const levels = (category.levels || []).map((level, index) => {
                    const local = progress[level.id];
                    const stars = kit.isLoggedIn() ? Number(level.stars || 0) : Number(local?.stars || 0);
                    if (!kit.isLoggedIn()) guestStars += stars;
                    return {
                        ...level,
                        stars,
                        best_score: kit.isLoggedIn() ? level.best_score : local?.best_score || null,
                        unlocked: kit.isLoggedIn() ? Boolean(level.unlocked) : index === 0 || Boolean(progress[category.levels[index - 1]?.id]),
                    };
                });
                return {
                    ...category,
                    levels,
                    completed_levels: levels.filter((level) => level.stars > 0).length,
                };
            });
            return {
                ...raw,
                categories,
                total_stars: kit.isLoggedIn() ? Number(raw.total_stars || 0) : guestStars,
            };
        }

        function renderCatalog() {
            const catalog = state.catalog;
            panel.innerHTML = `
                <div class="puzzle-heading">
                    <div class="puzzle-title">
                        <h2>成语填字</h2>
                        <p>顺着横竖释义补全交叉成语。关卡按主题逐步解锁，也可以每天挑战一张新题。</p>
                    </div>
                    <span class="puzzle-heading-meta">${(catalog.categories || []).length} 个分类 · ${(catalog.categories || []).reduce((sum, item) => sum + item.total_levels, 0)} 关</span>
                </div>
                <div class="puzzle-toolbar">
                    <div class="puzzle-toolbar-group">
                        <strong>每日挑战</strong>
                        <div class="puzzle-segment" aria-label="每日成语难度">
                            ${Object.entries(DIFFICULTY_LABELS).map(([value, label]) => `<button type="button" data-idiom-daily="${value}" class="${state.dailyDifficulty === value ? "active" : ""}">${label}</button>`).join("")}
                        </div>
                    </div>
                    <button type="button" class="puzzle-button" data-idiom-action="daily">开始今日题</button>
                </div>
                <div class="idiom-catalog-summary">
                    <span>收集星星</span><strong>${catalog.total_stars}/${catalog.max_stars} ★</strong>
                </div>
                <div class="idiom-category-list">
                    ${(catalog.categories || []).map((category, categoryIndex) => `
                        <details class="idiom-category" ${categoryIndex === 0 ? "open" : ""}>
                            <summary>
                                <span class="idiom-category-mark">${kit.escapeHTML((category.name || "成").slice(0, 1))}</span>
                                <span class="idiom-category-copy"><strong>${kit.escapeHTML(category.name)}</strong><span>${kit.escapeHTML(category.description)}</span></span>
                                <span class="idiom-category-score">${category.completed_levels}/${category.total_levels} 关</span>
                            </summary>
                            <div class="idiom-level-grid">
                                ${(category.levels || []).map((level) => `
                                    <button type="button" class="idiom-level-button ${level.stars ? "completed" : ""}"
                                        data-idiom-level="${kit.escapeHTML(level.id)}" ${level.unlocked ? "" : "disabled"}
                                        title="${kit.escapeHTML(level.title)} · ${DIFFICULTY_LABELS[level.difficulty] || level.difficulty}">
                                        <strong>${level.order}</strong>${level.unlocked ? (level.stars ? kit.renderStars(level.stars) : "☆☆☆") : "锁定"}
                                    </button>`).join("")}
                            </div>
                        </details>`).join("")}
                </div>`;
        }

        async function loadCatalog() {
            const version = ++state.loadVersion;
            state.loading = true;
            panel.innerHTML = '<div class="puzzle-loading">正在整理成语卷轴…</div>';
            try {
                const raw = await kit.bridge.fetchJSON(`${kit.bridge.apiBase}/idiom/catalog`);
                if (version !== state.loadVersion) return;
                state.catalog = normalizedCatalog(raw);
                state.view = "catalog";
                state.puzzle = null;
                renderCatalog();
            } catch (error) {
                if (version !== state.loadVersion) return;
                panel.innerHTML = `<div class="puzzle-empty"><div>关卡暂时加载失败<br><button class="puzzle-button secondary" type="button" data-idiom-action="retry-catalog">重试</button></div></div>`;
                kit.bridge.showToast(error.message || "成语关卡加载失败", false);
            } finally {
                if (version === state.loadVersion) state.loading = false;
            }
        }

        function activeCoordinates() {
            const entry = state.puzzle?.entries.find((item) => item.id === state.activeEntryId);
            return new Set(entry ? entryCoordinates(entry) : []);
        }

        function renderGame() {
            const puzzle = state.puzzle;
            if (!puzzle) return;
            const active = activeCoordinates();
            const invalid = new Set(state.invalid);
            panel.innerHTML = `
                <div class="idiom-back-row"><button type="button" class="puzzle-button secondary" data-idiom-action="back">← 返回选关</button></div>
                <div class="puzzle-heading">
                    <div class="puzzle-title"><h2>${kit.escapeHTML(puzzle.title)}</h2><p>${puzzle.mode === "daily" ? `${puzzle.puzzle_date || "今日"}每日挑战` : "填满所有交叉格后提交答案"} · ${DIFFICULTY_LABELS[puzzle.difficulty] || puzzle.difficulty}</p></div>
                    <span class="puzzle-heading-meta">${puzzle.mode === "daily" ? "每日挑战" : "分类闯关"}</span>
                </div>
                <div class="idiom-workspace">
                    <div class="idiom-board-wrap">
                        <div class="idiom-board-web" role="grid" aria-label="成语填字棋盘">
                            ${puzzle.cells.map((cell, index) => {
                                const key = `${cell.row},${cell.column}`;
                                const classes = ["idiom-cell-web"];
                                if (cell.type === "fixed") classes.push("fixed");
                                if (active.has(key)) classes.push("active-entry");
                                if (index === state.selectedIndex) classes.push("selected");
                                if (invalid.has(index)) classes.push("invalid");
                                return `<button type="button" role="gridcell" class="${classes.join(" ")}"
                                    style="grid-row:${cell.row + 1};grid-column:${cell.column + 1}"
                                    data-idiom-cell="${index}" ${state.completed ? "disabled" : ""}
                                    aria-label="第${cell.row + 1}行第${cell.column + 1}列${cell.type === "fixed" ? "固定字" : "填字"}">${kit.escapeHTML(state.grid[index] || cell.value || "")}</button>`;
                            }).join("")}
                        </div>
                    </div>
                    <aside class="idiom-side">
                        <div class="puzzle-status">
                            <div class="puzzle-status-item">用时 <strong data-idiom-stat="time">${kit.formatTime(state.elapsed)}</strong></div>
                            <div class="puzzle-status-item">提示 <strong>${state.hints}/${Number(puzzle.limits?.max_hints || 3)}</strong></div>
                            <div class="puzzle-status-item">失误 <strong>${state.mistakes}</strong></div>
                        </div>
                        <div class="idiom-clues">
                            ${puzzle.entries.map((entry, index) => `<button type="button" class="idiom-clue ${entry.id === state.activeEntryId ? "active" : ""}" data-idiom-entry="${kit.escapeHTML(entry.id)}">
                                <strong>${index + 1} · ${entry.direction === "across" ? "横向" : "纵向"} · ${entry.length} 字</strong>
                                <span>${kit.escapeHTML(entry.clue)}</span><small>${kit.escapeHTML(entry.pinyin_hint || "")}</small>
                            </button>`).join("")}
                        </div>
                        <div class="character-bank-web" aria-label="备选汉字">
                            ${puzzle.character_bank.map((character) => `<button type="button" data-idiom-character="${kit.escapeHTML(character)}" ${state.completed ? "disabled" : ""}>${kit.escapeHTML(character)}</button>`).join("")}
                        </div>
                        <div class="puzzle-actions">
                            <button type="button" class="puzzle-button secondary" data-idiom-action="erase" ${state.completed ? "disabled" : ""}>擦除</button>
                            <button type="button" class="puzzle-button secondary" data-idiom-action="hint" ${(state.completed || state.hints >= Number(puzzle.limits?.max_hints || 3)) ? "disabled" : ""}>提示一格</button>
                            <button type="button" class="puzzle-button" data-idiom-action="submit" ${state.completed ? "disabled" : ""}>提交答案</button>
                        </div>
                    </aside>
                </div>
                ${state.completed && state.result ? `<div class="puzzle-result">
                    <h3>成语全部填对</h3><div class="puzzle-result-stars">${kit.renderStars(state.result.stars)}</div>
                    <p>得分 ${Number(state.result.score || 0)} · 用时 ${kit.formatTime(state.result.elapsed_seconds)} · 提示 ${Number(state.result.hints_used || 0)} 次</p>
                    <div class="puzzle-result-actions">
                        ${puzzle.mode === "level" && state.result.next_level_id ? '<button type="button" class="puzzle-button" data-idiom-action="next">下一关</button>' : ""}
                        <button type="button" class="puzzle-button secondary" data-idiom-action="back">返回关卡</button>
                    </div>
                </div>` : ""}`;
        }

        async function loadPuzzle(path) {
            if (state.loading) return;
            state.loading = true;
            const version = ++state.loadVersion;
            clock.stop();
            window.clearTimeout(state.saveTimer);
            panel.innerHTML = '<div class="puzzle-loading">正在展开题目…</div>';
            try {
                const puzzle = await kit.bridge.fetchJSON(`${kit.bridge.apiBase}${path}`);
                if (version !== state.loadVersion) return;
                const localShadow = kit.loadStored("state", "idiom", puzzle.puzzle_id, null);
                const saved = kit.isLoggedIn() ? (localShadow || puzzle.saved_state) : localShadow;
                const initial = puzzle.cells.map((cell) => cell.value || "");
                state.puzzle = puzzle;
                state.grid = Array.isArray(saved?.grid) && saved.grid.length === puzzle.cells.length ? [...saved.grid] : initial;
                state.selectedIndex = puzzle.cells.findIndex((cell) => cell.type === "input");
                state.activeEntryId = puzzle.entries[0]?.id || "";
                state.elapsed = Number(saved?.elapsed_seconds || 0);
                state.hints = Number(saved?.hints_used || 0);
                state.mistakes = Number(saved?.mistakes || 0);
                state.invalid = [];
                state.completed = false;
                state.result = null;
                state.view = "game";
                renderGame();
                clock.start();
            } catch (error) {
                panel.innerHTML = `<div class="puzzle-empty"><div>题目暂时加载失败<br><button class="puzzle-button secondary" type="button" data-idiom-action="back">返回关卡</button></div></div>`;
                kit.bridge.showToast(error.message || "成语题目加载失败", false);
            } finally {
                state.loading = false;
            }
        }

        function selectCell(index) {
            const cell = state.puzzle?.cells[index];
            if (!cell || state.completed) return;
            const coordinate = `${cell.row},${cell.column}`;
            const entry = state.puzzle.entries.find((item) => entryCoordinates(item).includes(coordinate));
            if (entry) state.activeEntryId = entry.id;
            if (cell.type === "input") state.selectedIndex = index;
            else if (entry) {
                const coordinates = entryCoordinates(entry);
                const next = state.puzzle.cells.findIndex((item) => item.type === "input" && coordinates.includes(`${item.row},${item.column}`));
                if (next >= 0) state.selectedIndex = next;
            }
            renderGame();
        }

        function selectEntry(id) {
            const entry = state.puzzle?.entries.find((item) => item.id === id);
            if (!entry) return;
            state.activeEntryId = id;
            const coordinates = entryCoordinates(entry);
            const empty = state.puzzle.cells.findIndex((cell, index) => cell.type === "input" && !state.grid[index] && coordinates.includes(`${cell.row},${cell.column}`));
            const first = state.puzzle.cells.findIndex((cell) => cell.type === "input" && coordinates.includes(`${cell.row},${cell.column}`));
            state.selectedIndex = empty >= 0 ? empty : first;
            renderGame();
        }

        function inputCharacter(value) {
            const index = state.selectedIndex;
            if (state.busy || state.completed || !state.puzzle || index < 0 || state.puzzle.cells[index]?.type !== "input") return;
            state.grid[index] = value;
            state.invalid = state.invalid.filter((item) => item !== index);
            const entry = state.puzzle.entries.find((item) => item.id === state.activeEntryId);
            if (entry) {
                const coordinates = entryCoordinates(entry);
                const candidates = state.puzzle.cells.map((cell, cellIndex) => ({ cell, cellIndex }))
                    .filter(({ cell }) => cell.type === "input" && coordinates.includes(`${cell.row},${cell.column}`));
                const current = candidates.findIndex((item) => item.cellIndex === index);
                const next = candidates.slice(current + 1).find((item) => !state.grid[item.cellIndex]);
                if (next) state.selectedIndex = next.cellIndex;
            }
            renderGame();
            scheduleSave(true);
        }

        function erase() {
            const index = state.selectedIndex;
            if (!state.puzzle || index < 0 || state.puzzle.cells[index]?.type !== "input" || state.busy || state.completed) return;
            state.grid[index] = "";
            state.invalid = state.invalid.filter((item) => item !== index);
            renderGame();
            scheduleSave(true);
        }

        async function requestHint() {
            if (!state.puzzle || state.busy || state.completed || state.hints >= Number(state.puzzle.limits?.max_hints || 3)) return;
            state.busy = true;
            try {
                if (!(await flushSave())) return;
                const response = await kit.bridge.fetchJSON(`${kit.bridge.apiBase}/idiom/hint`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        run_id: state.puzzle.run_id || undefined,
                        puzzle_id: state.puzzle.puzzle_id,
                        grid: state.grid,
                        entry_id: state.activeEntryId,
                    }),
                });
                const index = state.puzzle.cells.findIndex((cell) => cell.row === response.row && cell.column === response.column);
                if (index >= 0) {
                    state.grid[index] = String(response.value || "");
                    state.selectedIndex = index;
                    state.invalid = state.invalid.filter((item) => item !== index);
                }
                state.hints = Number(response.hints_used || state.hints + 1);
                renderGame();
                scheduleSave(true);
            } catch (error) {
                kit.bridge.showToast(error.message || "提示获取失败", false);
            } finally {
                state.busy = false;
            }
        }

        function saveGuestResult(result) {
            if (kit.isLoggedIn() || state.puzzle?.mode !== "level") return;
            const progress = guestProgress();
            const previous = progress[state.puzzle.puzzle_id] || {};
            progress[state.puzzle.puzzle_id] = {
                stars: Math.max(Number(previous.stars || 0), Number(result.stars || 0)),
                best_score: Math.max(Number(previous.best_score || 0), Number(result.score || 0)),
            };
            kit.saveStored("progress", "idiom", "catalog", progress);
        }

        async function submit() {
            if (!state.puzzle || state.busy || state.completed) return;
            state.busy = true;
            try {
                if (!(await flushSave())) return;
                const response = await kit.bridge.fetchJSON(`${kit.bridge.apiBase}/idiom/submit`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    acceptedStatuses: [422],
                    body: JSON.stringify({
                        run_id: state.puzzle.run_id || undefined,
                        puzzle_id: state.puzzle.puzzle_id,
                        grid: state.grid,
                        elapsed_seconds: state.elapsed,
                        mistakes: state.mistakes,
                        hints_used: state.hints,
                    }),
                });
                if (!response.correct) {
                    state.invalid = Array.isArray(response.invalid_cells) ? response.invalid_cells : [];
                    state.mistakes += 1;
                    renderGame();
                    scheduleSave(true);
                    kit.bridge.showToast("还有文字不正确，标红处再检查一下", false);
                    return;
                }
                clock.stop();
                state.completed = true;
                state.result = response.result;
                state.invalid = [];
                kit.clearStored("state", "idiom", state.puzzle.puzzle_id);
                saveGuestResult(response.result || {});
                renderGame();
                kit.bridge.showToast("填字完成！", true);
            } catch (error) {
                kit.bridge.showToast(error.message || "答案提交失败", false);
            } finally {
                state.busy = false;
            }
        }

        async function backToCatalog() {
            if (state.busy) return;
            clock.stop();
            if (!(await flushSave())) {
                if (!state.completed) clock.start();
                return;
            }
            await loadCatalog();
        }

        panel.addEventListener("click", (event) => {
            const dailyDifficulty = event.target.closest("[data-idiom-daily]")?.dataset.idiomDaily;
            const level = event.target.closest("[data-idiom-level]")?.dataset.idiomLevel;
            const cell = event.target.closest("[data-idiom-cell]")?.dataset.idiomCell;
            const entry = event.target.closest("[data-idiom-entry]")?.dataset.idiomEntry;
            const character = event.target.closest("[data-idiom-character]")?.dataset.idiomCharacter;
            const action = event.target.closest("[data-idiom-action]")?.dataset.idiomAction;
            if (dailyDifficulty) {
                state.dailyDifficulty = dailyDifficulty;
                renderCatalog();
            } else if (level) void loadPuzzle(`/idiom/puzzle?mode=level&level_id=${encodeURIComponent(level)}`);
            else if (cell !== undefined) selectCell(Number(cell));
            else if (entry) selectEntry(entry);
            else if (character) inputCharacter(character);
            else if (action === "daily") void loadPuzzle(`/idiom/puzzle?mode=daily&difficulty=${state.dailyDifficulty}`);
            else if (action === "erase") erase();
            else if (action === "hint") void requestHint();
            else if (action === "submit") void submit();
            else if (action === "back") void backToCatalog();
            else if (action === "retry-catalog") void loadCatalog();
            else if (action === "next" && state.result?.next_level_id) {
                void loadPuzzle(`/idiom/puzzle?mode=level&level_id=${encodeURIComponent(state.result.next_level_id)}`);
            }
        });

        return {
            async enter(force = false) {
                if (force) {
                    const resumePath = state.authResumePath;
                    state.authResumePath = "";
                    state.catalog = null;
                    state.puzzle = null;
                    state.view = "catalog";
                    if (resumePath) {
                        await loadPuzzle(resumePath);
                        return;
                    }
                }
                if (state.view === "game" && state.puzzle) {
                    renderGame();
                    if (!state.completed) clock.start();
                } else if (!state.catalog) await loadCatalog();
                else renderCatalog();
            },
            async beforeLeave() {
                clock.stop();
                const saved = await flushSave();
                if (!saved && !state.completed) clock.start();
                return saved;
            },
            onAuthChange() {
                clock.stop();
                state.loadVersion += 1;
                state.loading = false;
                window.clearTimeout(state.saveTimer);
                state.pendingSave = null;
                state.authResumePath = state.view === "game" && state.puzzle
                    ? (state.puzzle.mode === "daily"
                        ? `/idiom/puzzle?mode=daily&difficulty=${encodeURIComponent(state.puzzle.difficulty)}`
                        : `/idiom/puzzle?mode=level&level_id=${encodeURIComponent(state.puzzle.puzzle_id)}`)
                    : "";
                state.catalog = null;
                state.puzzle = null;
                state.view = "catalog";
            },
            persistLocalNow,
        };
    }

    kit.register("idiom", controller);
})();
