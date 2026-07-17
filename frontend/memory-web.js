(function () {
    "use strict";

    const kit = window.WebPuzzleKit;
    if (!kit) throw new Error("WebPuzzleKit 未初始化");

    const { bridge } = kit;
    const THEMES = [
        ["classic", "符号"], ["fruit", "水果"], ["animal", "动物"],
        ["transport", "交通"], ["food", "美食"], ["weather", "天气"],
        ["sport", "运动"], ["ocean", "海洋"], ["space", "太空"],
        ["place", "建筑"], ["music", "音乐"], ["culture", "国风"],
    ];
    const THEME_LABELS = Object.fromEntries(THEMES);
    const DIFFICULTY_LABELS = { easy: "简单 4×4", medium: "中等 4×5", hard: "困难 5×6" };
    const LEGACY_THEMES = ["classic", "fruit", "animal"];
    const EXPANDED_THEMES = THEMES.slice(3).map(([value]) => value);
    const LEVEL_COUNT = 18 + EXPANDED_THEMES.length * 3;

    function levelConfig(level) {
        const safe = Math.max(1, Math.min(LEVEL_COUNT, Number(level) || 1));
        if (safe <= 18) {
            return {
                difficulty: safe <= 6 ? "easy" : safe <= 12 ? "medium" : "hard",
                theme: LEGACY_THEMES[(safe - 1) % LEGACY_THEMES.length],
            };
        }
        const index = safe - 19;
        return {
            difficulty: index < EXPANDED_THEMES.length
                ? "easy"
                : index < EXPANDED_THEMES.length * 2 ? "medium" : "hard",
            theme: EXPANDED_THEMES[index % EXPANDED_THEMES.length],
        };
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

    kit.register("memory", (panel) => {
        let loaded = false;
        let loading = false;
        let loadVersion = 0;
        let saveTimer = null;
        let resolveTimer = null;
        let mode = "daily";
        let difficulty = "easy";
        let theme = "fruit";
        let selectedLevel = 1;
        let board = null;
        let matchedPositions = [];
        let flippedPositions = [];
        let moves = 0;
        let elapsedSeconds = 0;
        let resolving = false;
        let completed = false;
        let result = null;
        let submitting = false;
        let submitPromise = null;

        const clock = kit.createClock(() => {
            if (!loaded || loading || completed) return;
            elapsedSeconds += 1;
            updateStatus();
            if (elapsedSeconds % 15 === 0) scheduleSave();
        });

        panel.innerHTML = `
            <div class="puzzle-heading">
                <div class="puzzle-title">
                    <h2>记忆翻牌</h2>
                    <p>翻开两张相同牌面完成配对。45 个递进关卡覆盖 12 类主题，步数越少得分越高。</p>
                </div>
                <span class="puzzle-heading-meta" data-role="memory-meta">每日牌局</span>
            </div>
            <div class="puzzle-toolbar">
                <div class="puzzle-toolbar-group">
                    <div class="puzzle-segment" aria-label="翻牌模式">
                        <button type="button" data-action="mode" data-value="daily">每日牌局</button>
                        <button type="button" data-action="mode" data-value="practice">关卡模式</button>
                    </div>
                    <button type="button" class="puzzle-chip" data-action="difficulty" data-value="easy">简单</button>
                    <button type="button" class="puzzle-chip" data-action="difficulty" data-value="medium">中等</button>
                    <button type="button" class="puzzle-chip" data-action="difficulty" data-value="hard">困难</button>
                </div>
                <button type="button" class="puzzle-button secondary" data-action="restart" data-role="restart-button">开始练习</button>
            </div>
            <div data-role="memory-content"><div class="puzzle-loading">正在洗牌…</div></div>
        `;

        const content = panel.querySelector("[data-role='memory-content']");

        function loadProgress() {
            const value = kit.loadStored("progress", "memory", "levels", {});
            return value && typeof value === "object" ? value : {};
        }

        function saveLevelResult(stars) {
            if (mode !== "practice") return;
            const progress = loadProgress();
            const key = String(selectedLevel);
            progress[key] = Math.max(Number(progress[key] || 0), Number(stars || 1));
            kit.saveStored("progress", "memory", "levels", progress);
        }

        function levelOptions() {
            const progress = loadProgress();
            return Array.from({ length: LEVEL_COUNT }, (_, index) => {
                const level = index + 1;
                const stars = Number(progress[String(level)] || 0);
                return {
                    level,
                    stars,
                    unlocked: level === 1 || Number(progress[String(level - 1)] || 0) > 0,
                    config: levelConfig(level),
                };
            });
        }

        function stateSnapshot() {
            return {
                matched_positions: [...matchedPositions].sort((left, right) => left - right),
                moves,
                elapsed_seconds: elapsedSeconds,
            };
        }

        function sameState(left, right) {
            if (!left || !right) return false;
            return JSON.stringify(left) === JSON.stringify(right);
        }

        function persistLocalNow() {
            if (!board || completed) return;
            kit.saveStored("state", "memory", board.board_id, stateSnapshot());
        }

        function createCloudTask() {
            if (!board || completed || !kit.isLoggedIn()) return null;
            persistLocalNow();
            return {
                account: String(bridge.getUsername() || ""),
                runId: board.run_id || "",
                boardId: board.board_id,
                state: stateSnapshot(),
            };
        }

        const saver = createLatestSaver(async (task) => {
            if (!kit.isLoggedIn() || String(bridge.getUsername() || "") !== task.account) {
                throw new Error("登录账号已变更，已停止旧账号的翻牌云存档");
            }
            if (!task.runId) throw new Error("翻牌云存档缺少运行标识");
            await bridge.fetchJSON(`${bridge.apiBase}/memory/save`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    run_id: task.runId,
                    board_id: task.boardId,
                    matched_positions: task.state.matched_positions,
                    moves: task.state.moves,
                    elapsed_seconds: task.state.elapsed_seconds,
                }),
            });
            const localShadow = kit.loadStored("state", "memory", task.boardId, null);
            if (sameState(localShadow, task.state)) {
                kit.clearStored("state", "memory", task.boardId);
            }
        });

        function scheduleSave() {
            if (!board || completed) return;
            persistLocalNow();
            window.clearTimeout(saveTimer);
            const task = createCloudTask();
            if (task) saveTimer = window.setTimeout(() => saver.enqueue(task), 500);
        }

        async function flushSave() {
            if (!board || completed) return;
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
                button.hidden = mode !== "daily";
            });
            const meta = panel.querySelector("[data-role='memory-meta']");
            if (meta) {
                meta.textContent = mode === "daily"
                    ? `${THEME_LABELS[theme]} · ${DIFFICULTY_LABELS[difficulty].split(" ")[0]}`
                    : `第 ${selectedLevel}/${LEVEL_COUNT} 关`;
            }
            const restart = panel.querySelector("[data-role='restart-button']");
            if (restart) restart.textContent = mode === "daily" ? "开始练习" : "换一局";
        }

        function updateStatus() {
            const elapsed = panel.querySelector("[data-role='memory-elapsed']");
            const moveNode = panel.querySelector("[data-role='memory-moves']");
            const pairNode = panel.querySelector("[data-role='memory-pairs']");
            if (elapsed) elapsed.textContent = kit.formatTime(elapsedSeconds);
            if (moveNode) moveNode.textContent = String(moves);
            if (pairNode) pairNode.textContent = board ? `${matchedPositions.length / 2}/${board.cards.length / 2}` : "0/0";
        }

        function renderSelectionRail() {
            if (mode === "practice") {
                return `
                    <div class="memory-levels-web" aria-label="翻牌关卡">
                        ${levelOptions().map((item) => {
                            const classes = ["memory-level-button"];
                            if (item.level === selectedLevel) classes.push("active");
                            if (item.stars) classes.push("completed");
                            const detail = item.stars ? kit.renderStars(item.stars) : THEME_LABELS[item.config.theme];
                            return `<button type="button" class="${classes.join(" ")}" data-action="level" data-level="${item.level}" ${item.unlocked ? "" : "disabled"}><strong>${item.level}</strong>${detail}</button>`;
                        }).join("")}
                    </div>`;
            }
            return `
                <div class="memory-themes-web" aria-label="牌面主题">
                    ${THEMES.map(([value, label]) => `<button type="button" class="memory-level-button${theme === value ? " active" : ""}" data-action="theme" data-value="${value}"><strong>${label}</strong>${value === theme ? "已选择" : "主题"}</button>`).join("")}
                </div>`;
        }

        function renderBoard() {
            const host = panel.querySelector("[data-role='memory-board']");
            if (!host || !board) return;
            const matched = new Set(matchedPositions);
            const flipped = new Set(flippedPositions);
            host.style.setProperty("--memory-columns", String(board.columns));
            host.innerHTML = board.cards.map((card) => {
                const isMatched = matched.has(card.position);
                const isFlipped = isMatched || flipped.has(card.position);
                const classes = ["memory-card-web"];
                if (isFlipped) classes.push("flipped");
                if (isMatched) classes.push("matched");
                const label = isMatched ? `已匹配，${card.display}` : isFlipped ? `已翻开，${card.display}` : "未翻开";
                return `
                    <button type="button" class="${classes.join(" ")}" data-action="flip" data-position="${card.position}"
                        aria-label="第 ${card.position + 1} 张牌，${kit.escapeHTML(label)}" ${isMatched || completed ? "disabled" : ""}>
                        <span>${isFlipped ? kit.escapeHTML(card.display) : "?"}</span>
                    </button>`;
            }).join("");
        }

        function renderGame() {
            if (!board) return;
            content.innerHTML = `
                ${renderSelectionRail()}
                <div class="memory-workspace">
                    <div class="memory-board-web" data-role="memory-board" aria-label="记忆翻牌牌面"></div>
                    <aside class="memory-side">
                        <div class="puzzle-status">
                            <div class="puzzle-status-item"><span>用时</span><strong data-role="memory-elapsed">${kit.formatTime(elapsedSeconds)}</strong></div>
                            <div class="puzzle-status-item"><span>步数</span><strong data-role="memory-moves">${moves}</strong></div>
                            <div class="puzzle-status-item"><span>配对</span><strong data-role="memory-pairs">${matchedPositions.length / 2}/${board.cards.length / 2}</strong></div>
                        </div>
                        <p class="memory-note">每翻开两张牌计一步。已配对牌面会保留，登录后进度同步到云端，游客进度保存在当前浏览器。</p>
                        <button type="button" class="puzzle-button secondary" data-action="restart">重新洗牌</button>
                    </aside>
                </div>
                <div data-role="memory-result"></div>
            `;
            renderBoard();
            renderResult();
            updateStatus();
        }

        function renderResult() {
            const host = panel.querySelector("[data-role='memory-result']");
            if (!host) return;
            if (!completed || !result) {
                host.innerHTML = "";
                return;
            }
            const nextLabel = mode === "daily" ? "练习一局" : selectedLevel < LEVEL_COUNT ? "下一关" : "再来一局";
            host.innerHTML = `
                <div class="puzzle-result" aria-live="polite">
                    <h3>全部配对完成</h3>
                    <div class="puzzle-result-stars">${kit.renderStars(result.stars)}</div>
                    <p>得分 ${Number(result.score || 0)} · ${Number(result.moves || moves)} 步 · 用时 ${kit.formatTime(result.elapsed_seconds)}${result.is_new_best ? " · 新纪录" : ""}</p>
                    <div class="puzzle-result-actions"><button type="button" class="puzzle-button" data-action="next">${nextLabel}</button></div>
                </div>`;
        }

        function chooseSavedState(payload) {
            const local = kit.loadStored("state", "memory", payload.board_id, null);
            if (kit.isLoggedIn()) return local || payload.saved_state || null;
            return local;
        }

        async function loadBoard(forceNew = false) {
            const version = ++loadVersion;
            loading = true;
            loaded = false;
            completed = false;
            result = null;
            submitting = false;
            submitPromise = null;
            resolving = false;
            flippedPositions = [];
            clock.stop();
            window.clearTimeout(saveTimer);
            window.clearTimeout(resolveTimer);
            saveTimer = null;
            resolveTimer = null;
            setToolbarState();
            content.innerHTML = `<div class="puzzle-loading">正在准备${THEME_LABELS[theme]}牌面…</div>`;
            try {
                const definitionSlot = `${mode}:${difficulty}:${theme}:${selectedLevel}`;
                let payload = null;
                if (!kit.isLoggedIn() && mode === "practice" && !forceNew) {
                    payload = kit.loadStored("definition", "memory", definitionSlot, null);
                }
                if (!payload) {
                    const query = new URLSearchParams({ mode, difficulty, theme });
                    if (forceNew) query.set("fresh", "1");
                    payload = await bridge.fetchJSON(`${bridge.apiBase}/memory/board?${query.toString()}`);
                    if (!kit.isLoggedIn() && mode === "practice") {
                        kit.saveStored("definition", "memory", definitionSlot, payload);
                    }
                }
                if (version !== loadVersion) return;
                const saved = chooseSavedState(payload);
                const available = new Set(payload.cards.map((card) => Number(card.position)));
                const savedMatched = Array.isArray(saved && saved.matched_positions)
                    ? saved.matched_positions.map(Number).filter((position) => available.has(position))
                    : [];
                board = payload;
                matchedPositions = [...new Set(savedMatched)].sort((left, right) => left - right);
                moves = Math.max(matchedPositions.length / 2, Number(saved && saved.moves) || 0);
                elapsedSeconds = Math.max(0, Number(saved && saved.elapsed_seconds) || 0);
                loaded = true;
                renderGame();
                setToolbarState();
                clock.start();
                if (matchedPositions.length === board.cards.length) void submitCompletion();
            } catch (error) {
                if (version !== loadVersion) return;
                board = null;
                content.innerHTML = `
                    <div class="puzzle-empty">
                        <div><p>${kit.escapeHTML(error.message || "翻牌加载失败")}</p><div class="puzzle-actions"><button type="button" class="puzzle-button" data-action="retry">重试</button></div></div>
                    </div>`;
                bridge.showToast(error.message || "翻牌游戏加载失败", false);
            } finally {
                if (version === loadVersion) loading = false;
            }
        }

        function finishPair(autoSubmit = true) {
            if (!resolving || !board || flippedPositions.length !== 2) return false;
            window.clearTimeout(resolveTimer);
            resolveTimer = null;
            const [firstPosition, secondPosition] = flippedPositions;
            const first = board.cards.find((card) => Number(card.position) === firstPosition);
            const second = board.cards.find((card) => Number(card.position) === secondPosition);
            if (first && second && first.face_key === second.face_key) {
                matchedPositions = [...new Set([...matchedPositions, firstPosition, secondPosition])]
                    .sort((left, right) => left - right);
            }
            flippedPositions = [];
            resolving = false;
            renderBoard();
            updateStatus();
            scheduleSave();
            const allMatched = matchedPositions.length === board.cards.length;
            if (allMatched && autoSubmit) void submitCompletion();
            return allMatched;
        }

        function flipCard(position) {
            if (!board || completed || submitting || resolving) return;
            if (matchedPositions.includes(position) || flippedPositions.includes(position)) return;
            const card = board.cards.find((item) => Number(item.position) === position);
            if (!card) return;
            if (flippedPositions.length === 0) {
                flippedPositions = [position];
                renderBoard();
                return;
            }
            flippedPositions = [flippedPositions[0], position];
            moves += 1;
            resolving = true;
            renderBoard();
            updateStatus();
            resolveTimer = window.setTimeout(() => finishPair(true), 650);
        }

        function submitCompletion() {
            if (!board || completed) return Promise.resolve();
            if (submitPromise) return submitPromise;
            submitting = true;
            submitPromise = (async () => {
                try {
                    await flushSave();
                    const response = await bridge.fetchJSON(`${bridge.apiBase}/memory/submit`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        acceptedStatuses: [422],
                        body: JSON.stringify({
                            run_id: board.run_id || undefined,
                            board_id: board.board_id,
                            matched_positions: matchedPositions,
                            moves,
                            elapsed_seconds: elapsedSeconds,
                        }),
                    });
                    if (!response.correct) {
                        bridge.showToast(`还有 ${Number(response.unmatched_count || 0)} 张牌未匹配`, false);
                        return;
                    }
                    completed = true;
                    result = response.result || {};
                    clock.stop();
                    window.clearTimeout(saveTimer);
                    kit.clearStored("state", "memory", board.board_id);
                    if (mode === "practice") {
                        kit.clearStored("definition", "memory", `${mode}:${difficulty}:${theme}:${selectedLevel}`);
                        saveLevelResult(result.stars);
                    }
                    renderGame();
                    setToolbarState();
                    bridge.showToast("全部配对完成，成绩已记录", true);
                } catch (error) {
                    bridge.showToast(error.message || "保存翻牌成绩失败", false);
                } finally {
                    submitting = false;
                    submitPromise = null;
                }
            })();
            return submitPromise;
        }

        async function prepareChange() {
            if (loading || submitting) return false;
            const completedPair = finishPair(false);
            if (completedPair) await submitCompletion();
            if (completed) return true;
            try {
                await flushSave();
                return true;
            } catch (error) {
                bridge.showToast(error.message || "翻牌进度未同步，已取消切换", false);
                return false;
            }
        }

        async function switchMode(nextMode) {
            if (nextMode === mode || !(await prepareChange())) return;
            mode = nextMode;
            if (mode === "practice") {
                const config = levelConfig(selectedLevel);
                difficulty = config.difficulty;
                theme = config.theme;
            }
            await loadBoard();
        }

        async function switchDifficulty(nextDifficulty) {
            if (mode !== "daily" || nextDifficulty === difficulty || !(await prepareChange())) return;
            difficulty = nextDifficulty;
            await loadBoard();
        }

        async function switchTheme(nextTheme) {
            if (mode !== "daily" || nextTheme === theme || !(await prepareChange())) return;
            theme = nextTheme;
            await loadBoard();
        }

        async function switchLevel(level) {
            if (loading || submitting) return;
            const option = levelOptions().find((item) => item.level === level);
            if (!option || !option.unlocked) {
                bridge.showToast("先完成上一关，才能解锁本关", false);
                return;
            }
            if (mode === "practice" && selectedLevel === level) return;
            if (!(await prepareChange())) return;
            selectedLevel = level;
            mode = "practice";
            difficulty = option.config.difficulty;
            theme = option.config.theme;
            await loadBoard();
        }

        async function restartRound() {
            if (loading || submitting || !(await prepareChange())) return;
            if (mode === "daily") {
                mode = "practice";
                const config = levelConfig(selectedLevel);
                difficulty = config.difficulty;
                theme = config.theme;
            }
            await loadBoard(true);
        }

        async function nextRound() {
            if (loading || submitting) return;
            if (mode === "daily") {
                mode = "practice";
                const config = levelConfig(selectedLevel);
                difficulty = config.difficulty;
                theme = config.theme;
                await loadBoard(true);
                return;
            }
            if (selectedLevel < LEVEL_COUNT) {
                selectedLevel += 1;
                const config = levelConfig(selectedLevel);
                difficulty = config.difficulty;
                theme = config.theme;
            }
            await loadBoard(true);
        }

        panel.addEventListener("click", (event) => {
            const button = event.target.closest("[data-action]");
            if (!button || !panel.contains(button)) return;
            const action = button.dataset.action;
            if (action === "flip") flipCard(Number(button.dataset.position));
            else if (action === "mode") switchMode(button.dataset.value);
            else if (action === "difficulty") switchDifficulty(button.dataset.value);
            else if (action === "theme") switchTheme(button.dataset.value);
            else if (action === "level") switchLevel(Number(button.dataset.level));
            else if (action === "restart") restartRound();
            else if (action === "next") nextRound();
            else if (action === "retry") loadBoard();
        });

        return {
            async enter(force = false) {
                if (force || !loaded) await loadBoard();
                else if (!completed) clock.start();
            },
            async beforeLeave() {
                clock.stop();
                const completedPair = finishPair(false);
                if (completedPair) await submitCompletion();
                if (submitPromise) await submitPromise;
                try {
                    await flushSave();
                    return true;
                } catch (error) {
                    bridge.showToast(error.message || "翻牌进度保存失败，已取消切换", false);
                    if (!completed) clock.start();
                    return false;
                }
            },
            onAuthChange() {
                loadVersion += 1;
                loaded = false;
                loading = false;
                board = null;
                completed = false;
                result = null;
                clock.stop();
                window.clearTimeout(saveTimer);
                window.clearTimeout(resolveTimer);
                saveTimer = null;
                resolveTimer = null;
                resolving = false;
                flippedPositions = [];
            },
            persistLocalNow() {
                if (resolving) finishPair(false);
                persistLocalNow();
            },
        };
    });
})();
