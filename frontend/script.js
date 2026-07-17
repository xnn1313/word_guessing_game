const API_BASE = "/api";
let sessionId = null;
let sortMode = "similarity";
let currentHistory = [];
let isSubmitting = false;
let currentUsername = null;
let currentMode = "classic";
let campaignCatalog = null;
let activeCampaignLevel = null;
let campaignLevelComplete = false;
let campaignNextLevel = null;
let battleState = null;
let battlePollTimer = null;
let battleSubmitting = false;

async function fetchJSON(url, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);
    const acceptedStatuses = Array.isArray(options.acceptedStatuses) ? options.acceptedStatuses : [];
    const fetchOptions = { ...options };
    delete fetchOptions.acceptedStatuses;

    try {
        const res = await fetch(url, { ...fetchOptions, signal: controller.signal });
        const data = await res.json().catch(() => ({}));
        if (!res.ok && !acceptedStatuses.includes(res.status)) {
            const error = new Error(data.error || `请求失败（HTTP ${res.status}）`);
            error.statusCode = res.status;
            error.data = data;
            throw error;
        }
        return data;
    } finally {
        clearTimeout(timeout);
    }
}

function showRoundResult(message, success = false) {
    const result = document.getElementById("round-result");
    result.textContent = message;
    result.className = "round-result show" + (success ? " success" : "");
}

function clearRoundResult() {
    const result = document.getElementById("round-result");
    result.textContent = "";
    result.className = "round-result";
}

function applyGameState(game) {
    sessionId = game.session_id;
    currentMode = game.mode || "classic";
    currentHistory = game.history || [];
    document.getElementById("attempts").textContent = game.attempts || 0;
    document.getElementById("correct-count").textContent = game.correct_count || 0;
    renderHistory(currentHistory);
    clearRoundResult();
}

function setActiveModeButton(mode) {
    document.querySelectorAll(".mode-btn").forEach((button) => {
        button.classList.toggle("active", button.dataset.mode === mode);
    });
}

function findCampaignLevel(levelId) {
    if (!campaignCatalog) return null;
    for (const category of campaignCatalog.categories) {
        const level = category.levels.find((item) => item.id === levelId);
        if (level) return level;
    }
    return null;
}

function renderCampaignCatalog() {
    if (!campaignCatalog) return;
    document.getElementById("campaign-total-stars").textContent = campaignCatalog.total_stars;
    document.getElementById("campaign-max-stars").textContent = campaignCatalog.max_stars;

    const container = document.getElementById("campaign-categories");
    container.innerHTML = campaignCatalog.categories.map((category, categoryIndex) => `
        <details class="category-card" ${categoryIndex === 0 ? "open" : ""}>
            <summary class="category-header">
                <span class="category-emoji">${category.emoji}</span>
                <div class="category-meta">
                    <strong>${escapeHTML(category.name)}</strong>
                    <span>${escapeHTML(category.description)} · 20 关</span>
                </div>
                <span class="category-stars">${category.stars}/${category.max_stars} ⭐</span>
            </summary>
            <div class="difficulty-legend">
                <span>难度递增</span><i class="difficulty-dot difficulty-1"></i><i class="difficulty-dot difficulty-2"></i><i class="difficulty-dot difficulty-3"></i><i class="difficulty-dot difficulty-4"></i><i class="difficulty-dot difficulty-5"></i>
            </div>
            <div class="level-grid">
                ${category.levels.map((level) => `
                    <button class="level-btn difficulty-border-${level.difficulty}" data-level-id="${level.id}" ${level.unlocked ? "" : "disabled"} title="${escapeHTML(level.name)} · 难度 ${level.difficulty}/5">
                        <span class="level-number">${level.order}</span>
                        <span class="level-difficulty difficulty-text-${level.difficulty}">${escapeHTML(level.difficulty_label)}</span>
                        ${level.unlocked
                            ? `<span class="level-stars">${level.stars ? "★".repeat(level.stars) + "☆".repeat(3 - level.stars) : "☆☆☆"}</span>`
                            : '<span class="level-lock">🔒</span>'}
                    </button>
                `).join("")}
            </div>
        </details>
    `).join("");

    container.querySelectorAll(".level-btn:not(:disabled)").forEach((button) => {
        button.addEventListener("click", () => startCampaignLevel(button.dataset.levelId));
    });
}

function showCampaignHome() {
    stopBattlePolling();
    document.getElementById("game-container").classList.remove("battle-layout");
    currentMode = "campaign";
    activeCampaignLevel = null;
    campaignLevelComplete = false;
    campaignNextLevel = null;
    setActiveModeButton("campaign");
    document.getElementById("campaign-panel").hidden = false;
    document.getElementById("battle-panel").hidden = true;
    document.getElementById("game-panel").hidden = true;
    renderCampaignCatalog();
}

function showClassicGame() {
    stopBattlePolling();
    document.getElementById("game-container").classList.remove("battle-layout");
    currentMode = "classic";
    activeCampaignLevel = null;
    campaignLevelComplete = false;
    campaignNextLevel = null;
    setActiveModeButton("classic");
    document.getElementById("campaign-panel").hidden = true;
    document.getElementById("battle-panel").hidden = true;
    document.getElementById("game-panel").hidden = false;
    document.getElementById("level-context").hidden = true;
    document.getElementById("secondary-stat-label").textContent = "已猜对";
    document.getElementById("secondary-stat-suffix").textContent = "个词语";
    document.getElementById("reveal-btn").textContent = "查看答案 / 跳过本轮";
    document.getElementById("reset-btn").textContent = "新游戏";
    document.getElementById("guess-input").disabled = false;
    document.getElementById("guess-btn").disabled = false;
}

function showCampaignGame(level, game) {
    stopBattlePolling();
    document.getElementById("game-container").classList.remove("battle-layout");
    currentMode = "campaign";
    activeCampaignLevel = level;
    campaignLevelComplete = !game.game_active;
    setActiveModeButton("campaign");
    document.getElementById("campaign-panel").hidden = true;
    document.getElementById("battle-panel").hidden = true;
    document.getElementById("game-panel").hidden = false;
    document.getElementById("level-context").hidden = false;
    document.getElementById("level-category").textContent = `${level.category_emoji} ${level.category_name} · 第 ${level.order} 关`;
    document.getElementById("level-name").textContent = level.name;
    document.getElementById("secondary-stat-label").textContent = "累计";
    document.getElementById("secondary-stat-suffix").textContent = "颗星";
    document.getElementById("correct-count").textContent = campaignCatalog ? campaignCatalog.total_stars : 0;
    document.getElementById("reveal-btn").textContent = campaignLevelComplete ? "返回选关" : "查看答案 / 重试本关";
    document.getElementById("reset-btn").textContent = campaignLevelComplete ? "继续闯关" : "重试本关";
    document.getElementById("guess-input").disabled = campaignLevelComplete;
    document.getElementById("guess-btn").disabled = campaignLevelComplete;
    if (campaignLevelComplete) {
        showRoundResult("本关已经完成，返回选关继续挑战。", true);
    }
}

async function loadCampaignCatalog(showHome = true) {
    campaignCatalog = await fetchJSON(`${API_BASE}/campaign`);
    renderCampaignCatalog();
    if (showHome) showCampaignHome();
    return campaignCatalog;
}

async function startCampaignLevel(levelId) {
    try {
        const data = await fetchJSON(`${API_BASE}/campaign/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ level_id: levelId }),
        });
        applyGameState(data.game);
        activeCampaignLevel = data.level;
        campaignLevelComplete = false;
        campaignNextLevel = null;
        showCampaignGame(data.level, data.game);
        document.getElementById("guess-input").value = "";
        document.getElementById("guess-input").focus();
    } catch (err) {
        showToast(err.message || "进入关卡失败，请重试", false);
    }
}

async function enterCampaignMode() {
    if (!currentUsername) {
        showToast("请先登录，闯关成绩才可以保存", false);
        openAuthModal();
        return;
    }
    try {
        await loadCampaignCatalog(true);
    } catch (err) {
        showToast(err.message || "加载关卡失败，请重试", false);
    }
}

async function enterClassicMode() {
    try {
        const data = await fetchJSON(`${API_BASE}/classic/start?session_id=${encodeURIComponent(sessionId || "")}`, { method: "POST" });
        applyGameState(data.game);
        showClassicGame();
        document.getElementById("guess-input").focus();
    } catch (err) {
        showToast(err.message || "切换经典模式失败", false);
    }
}

async function restoreGameSurface(game) {
    applyGameState(game);
    if (game.mode === "campaign" && game.campaign_level_id) {
        await loadCampaignCatalog(false);
        const level = findCampaignLevel(game.campaign_level_id);
        if (level) {
            showCampaignGame(level, game);
            return;
        }
    }
    showClassicGame();
}

function stopBattlePolling() {
    if (battlePollTimer) {
        clearInterval(battlePollTimer);
        battlePollTimer = null;
    }
}

function startBattlePolling() {
    stopBattlePolling();
    if (!battleState || (battleState.state === "finished" && !battleState.can_rematch)) return;
    battlePollTimer = setInterval(refreshBattleState, 1000);
}

function showBattleHome() {
    stopBattlePolling();
    currentMode = "battle";
    battleState = null;
    setActiveModeButton("battle");
    document.getElementById("game-container").classList.add("battle-layout");
    document.getElementById("campaign-panel").hidden = true;
    document.getElementById("game-panel").hidden = true;
    document.getElementById("battle-panel").hidden = false;
    document.getElementById("battle-home").hidden = false;
    document.getElementById("battle-room").hidden = true;
    document.getElementById("battle-join-code").value = "";
}

function renderBattleHistory(history) {
    const container = document.getElementById("battle-history");
    if (!history || history.length === 0) {
        container.innerHTML = '<div class="history-placeholder">还没有提交猜测。</div>';
        return;
    }
    container.innerHTML = [...history].reverse().map((item) => `
        <div class="battle-history-item">
            <span>${escapeHTML(item.word)}</span>
            <strong class="${getSimClass(item.similarity)}">${Number(item.similarity).toFixed(4)}%</strong>
        </div>
    `).join("");
}

function renderBattleState(state) {
    const enteringPlaying = state.state === "playing" && (!battleState || battleState.state !== "playing");
    battleState = state;
    currentMode = "battle";
    setActiveModeButton("battle");
    document.getElementById("game-container").classList.add("battle-layout");
    document.getElementById("campaign-panel").hidden = true;
    document.getElementById("game-panel").hidden = true;
    document.getElementById("battle-panel").hidden = false;
    document.getElementById("battle-home").hidden = true;
    document.getElementById("battle-room").hidden = false;
    document.getElementById("battle-room-code").textContent = state.code;

    const statusLabels = { waiting: "等待玩家", playing: "比赛中", finished: "已结束" };
    document.getElementById("battle-status-text").textContent = statusLabels[state.state] || state.state;

    const cards = state.players.map((player) => `
        <article class="battle-player-card${player.is_self ? " self" : ""}">
            <div class="battle-player-name">
                ${player.is_winner ? "🏆 " : ""}${escapeHTML(player.username)}
                <span class="battle-player-tags">${player.is_self ? "你" : "对手"}${player.is_host ? " · 房主" : ""}${player.rematch_ready ? " · 已确认再战" : ""}</span>
            </div>
            <div class="battle-player-score">
                <span>已猜 <strong>${player.attempts}</strong> 次</span>
                <span>最高 <strong>${Number(player.best_similarity).toFixed(2)}%</strong></span>
            </div>
        </article>
    `);
    while (cards.length < 2) {
        cards.push('<article class="battle-player-card empty">等待好友加入…</article>');
    }
    document.getElementById("battle-player-list").innerHTML = cards.join("");

    const waiting = state.state === "waiting";
    const playing = state.state === "playing";
    const finished = state.state === "finished";
    document.getElementById("battle-waiting-actions").hidden = !waiting;
    document.getElementById("battle-arena").hidden = waiting;
    document.getElementById("battle-live-grid").className = `battle-live-grid ${state.state}`;

    const startButton = document.getElementById("battle-start-btn");
    startButton.hidden = !state.is_host;
    startButton.disabled = !state.can_start;
    startButton.textContent = state.can_start ? "开始 90 秒比赛" : "等待另一名玩家";

    document.getElementById("battle-timer").textContent = state.remaining_seconds;
    document.getElementById("battle-timer-wrap").hidden = !playing;
    document.getElementById("battle-input-row").hidden = !playing;
    if (enteringPlaying) document.getElementById("battle-input").value = "";
    document.getElementById("battle-input").disabled = !playing;
    document.getElementById("battle-guess-btn").disabled = !playing || battleSubmitting;
    renderBattleHistory(state.my_history);

    const resultBox = document.getElementById("battle-result");
    resultBox.hidden = !finished;
    if (finished) {
        const outcome = state.winner_username
            ? `🏆 ${escapeHTML(state.winner_username)} 获胜`
            : "🤝 本局平局";
        const reason = state.finish_reason === "opponent_left" ? "对手离开房间" : "";
        resultBox.innerHTML = `${outcome}<br>答案：${escapeHTML(state.target_word || "-")}${reason ? `<br>${reason}` : ""}`;
    } else {
        resultBox.innerHTML = "";
    }

    const rematchButton = document.getElementById("battle-rematch-btn");
    rematchButton.hidden = !finished;
    rematchButton.disabled = !state.can_rematch || state.rematch_ready;
    if (!state.can_rematch) {
        rematchButton.textContent = "对手已离开，无法再战";
    } else if (state.rematch_ready) {
        rematchButton.textContent = "已确认，等待对手…";
    } else {
        rematchButton.textContent = "再来一局";
    }
    if (finished && !state.can_rematch) stopBattlePolling();

    if (playing) {
        document.getElementById("battle-input").focus();
    }
}

async function refreshBattleState() {
    if (currentMode !== "battle") return;
    try {
        const state = await fetchJSON(`${API_BASE}/battle/current`);
        renderBattleState(state);
    } catch (err) {
        showBattleHome();
    }
}

async function enterBattleMode() {
    if (!currentUsername) {
        showToast("请先登录后再进入双人竞速", false);
        openAuthModal();
        return;
    }

    currentMode = "battle";
    setActiveModeButton("battle");
    document.getElementById("game-container").classList.add("battle-layout");
    document.getElementById("campaign-panel").hidden = true;
    document.getElementById("game-panel").hidden = true;
    document.getElementById("battle-panel").hidden = false;
    try {
        const state = await fetchJSON(`${API_BASE}/battle/current`);
        renderBattleState(state);
        startBattlePolling();
    } catch (err) {
        showBattleHome();
    }
}

async function createBattleRoom() {
    try {
        const state = await fetchJSON(`${API_BASE}/battle/create`, { method: "POST" });
        renderBattleState(state);
        startBattlePolling();
    } catch (err) {
        showToast(err.message || "创建房间失败", false);
    }
}

async function joinBattleRoom() {
    const codeInput = document.getElementById("battle-join-code");
    const code = codeInput.value.trim().toUpperCase();
    if (code.length !== 6) {
        showToast("请输入六位房间码", false);
        return;
    }
    try {
        const state = await fetchJSON(`${API_BASE}/battle/join`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code }),
        });
        renderBattleState(state);
        startBattlePolling();
    } catch (err) {
        showToast(err.message || "加入房间失败", false);
    }
}

async function startBattleRoom() {
    if (!battleState) return;
    try {
        const state = await fetchJSON(`${API_BASE}/battle/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code: battleState.code }),
        });
        renderBattleState(state);
        startBattlePolling();
    } catch (err) {
        showToast(err.message || "开始比赛失败", false);
    }
}

async function submitBattleGuess() {
    if (!battleState || battleState.state !== "playing" || battleSubmitting) return;
    const input = document.getElementById("battle-input");
    const word = input.value.trim();
    if (!word) return;

    battleSubmitting = true;
    document.getElementById("battle-guess-btn").disabled = true;
    try {
        const state = await fetchJSON(`${API_BASE}/battle/guess`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ word }),
        });
        input.value = "";
        renderBattleState(state);
        if (state.guess_result && state.guess_result.is_correct) {
            showToast("🎉 你率先猜中了！", true);
        }
    } catch (err) {
        showToast(err.message || "提交猜测失败", false);
    } finally {
        battleSubmitting = false;
        document.getElementById("battle-guess-btn").disabled = !battleState || battleState.state !== "playing";
        if (!input.disabled) input.focus();
    }
}

async function leaveBattleRoom() {
    try {
        await fetchJSON(`${API_BASE}/battle/leave`, { method: "POST" });
        showBattleHome();
        showToast("已离开双人房间", true);
    } catch (err) {
        showToast(err.message || "离开房间失败", false);
    }
}

async function requestBattleRematch() {
    if (!battleState || battleState.state !== "finished") return;
    const button = document.getElementById("battle-rematch-btn");
    button.disabled = true;
    try {
        const state = await fetchJSON(`${API_BASE}/battle/rematch`, { method: "POST" });
        renderBattleState(state);
        startBattlePolling();
        if (state.state === "playing") {
            showToast("双方已确认，新一轮开始！", true);
        }
    } catch (err) {
        showToast(err.message || "发起再战失败", false);
        button.disabled = false;
    }
}

function updateAuthUI(username) {
    currentUsername = username || null;
    const authBtn = document.getElementById("auth-btn");
    const userMenu = document.getElementById("user-menu");
    const saveStatus = document.getElementById("save-status");

    if (currentUsername) {
        authBtn.hidden = true;
        userMenu.hidden = false;
        document.getElementById("username").textContent = currentUsername;
        saveStatus.className = "save-status";
        document.getElementById("save-status-text").textContent = `已登录 ${currentUsername}：进度已自动保存`;
    } else {
        authBtn.hidden = false;
        userMenu.hidden = true;
        document.getElementById("username").textContent = "";
        saveStatus.className = "save-status guest";
        document.getElementById("save-status-text").textContent = "试玩模式：进度仅保存在当前浏览器";
    }
    window.dispatchEvent(new CustomEvent("web-auth-changed", {
        detail: { username: currentUsername },
    }));
}

async function bootstrapGame() {
    try {
        const data = await fetchJSON(`${API_BASE}/auth/status`);
        if (data.authenticated) {
            updateAuthUI(data.username);
            await restoreGameSurface(data.game);
            document.getElementById("guess-input").focus();
            return;
        }
        updateAuthUI(null);
        await initGame();
    } catch (err) {
        updateAuthUI(null);
        showToast("读取登录状态失败，请刷新重试", false);
    }
}

function getSimClass(similarity) {
    if (similarity === 0) return "sim-zero";
    if (similarity >= 50) return "sim-high";
    if (similarity >= 25) return "sim-mid";
    return "sim-low";
}

async function initGame() {
    try {
        const data = await fetchJSON(`${API_BASE}/new-game`);
        sessionId = data.game_id;
        currentMode = "classic";
        currentHistory = [];
        document.getElementById("attempts").textContent = "0";
        document.getElementById("correct-count").textContent = "0";
        document.getElementById("history").innerHTML = '<div class="history-placeholder">开始猜测吧！</div>';
        document.getElementById("guess-input").value = "";
        clearRoundResult();
        showClassicGame();
        document.getElementById("guess-input").focus();
    } catch (err) {
        showToast("初始化游戏失败，请检查服务器连接", false);
    }
}

function openAuthModal() {
    document.getElementById("auth-error").textContent = "";
    document.getElementById("auth-modal-overlay").classList.add("show");
    document.getElementById("auth-username").focus();
}

function closeAuthModal() {
    document.getElementById("auth-modal-overlay").classList.remove("show");
    document.getElementById("auth-password").value = "";
    document.getElementById("auth-error").textContent = "";
}

async function authenticate(mode) {
    const username = document.getElementById("auth-username").value.trim();
    const password = document.getElementById("auth-password").value;
    const loginBtn = document.getElementById("login-btn");
    const registerBtn = document.getElementById("register-btn");
    const errorBox = document.getElementById("auth-error");

    errorBox.textContent = "";
    loginBtn.disabled = true;
    registerBtn.disabled = true;

    try {
        const data = await fetchJSON(`${API_BASE}/auth/${mode}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password, session_id: sessionId }),
        });
        updateAuthUI(data.username);
        await restoreGameSurface(data.game);
        closeAuthModal();
        showToast(mode === "register" ? "注册成功，已开启自动存档" : "登录成功，存档已恢复", true);
        document.getElementById("guess-input").focus();
    } catch (err) {
        errorBox.textContent = err.message || "操作失败，请重试";
    } finally {
        loginBtn.disabled = false;
        registerBtn.disabled = false;
    }
}

async function logoutAccount() {
    try {
        await fetchJSON(`${API_BASE}/auth/logout`, { method: "POST" });
        updateAuthUI(null);
        await initGame();
        showToast("已退出登录，当前为试玩模式", true);
    } catch (err) {
        showToast(err.message || "退出失败，请重试", false);
    }
}

async function submitGuess() {
    const input = document.getElementById("guess-input");
    const word = input.value.trim();
    if (!word) return;
    if (isSubmitting) return;

    const btn = document.getElementById("guess-btn");
    isSubmitting = true;
    btn.disabled = true;
    btn.textContent = "计算中…";

    try {
        const data = await fetchJSON(`${API_BASE}/guess?session_id=${encodeURIComponent(sessionId || "")}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ word }),
        });
        sessionId = data.session_id || sessionId;

        if (data.error) {
            showToast(data.error, false);
            return;
        }

        // Update attempts
        document.getElementById("attempts").textContent = data.attempts;
        if (currentMode === "classic") {
            document.getElementById("correct-count").textContent = data.correct_count;
        }

        // Render history
        currentHistory = data.history || [];
        renderHistory(currentHistory);

        // Clear input
        input.value = "";

        if (data.is_correct && data.campaign_result) {
            const result = data.campaign_result;
            campaignLevelComplete = true;
            campaignNextLevel = result.next_level;
            document.getElementById("correct-count").textContent = result.total_stars;
            document.getElementById("guess-input").disabled = true;
            document.getElementById("reveal-btn").textContent = "返回选关";
            document.getElementById("reset-btn").textContent = campaignNextLevel ? "下一关" : "返回选关";
            showToast(`闯关成功，获得 ${result.earned_stars} 星！`, true);
            showRoundResult(`🎉 答案：${data.target_word}　${"⭐".repeat(result.earned_stars)}（${data.attempts} 次猜中）`, true);
            await loadCampaignCatalog(false);
        } else if (data.is_correct) {
            showToast(`🎉 恭喜猜中！目标词是「${data.target_word}」`, true);
            showRoundResult(`🎉 上一轮答案：${data.target_word}（已开始新一轮）`, true);
            // Backend auto-starts new round, just update UI
            document.getElementById("attempts").textContent = "0";
            document.getElementById("history").innerHTML = '<div class="history-placeholder">新的一轮，开始猜测吧！</div>';
            currentHistory = [];
            document.getElementById("correct-count").textContent = data.correct_count;
        }
    } catch (err) {
        const message = err.name === "AbortError" ? "计算超时，请重试" : (err.message || "提交失败，请重试");
        showToast(message, false);
    } finally {
        isSubmitting = false;
        btn.disabled = currentMode === "campaign" && campaignLevelComplete;
        btn.textContent = "猜测";
        if (!input.disabled) input.focus();
    }
}

function renderHistory(history) {
    const container = document.getElementById("history");
    if (!history || history.length === 0) {
        container.innerHTML = '<div class="history-placeholder">开始猜测吧！</div>';
        return;
    }

    // Tag each item with its original chronological index
    let items = history.map((h, i) => ({ ...h, _idx: i }));
    const latestIdx = history.length - 1;

    if (sortMode === "similarity") {
        items.sort((a, b) => b.similarity - a.similarity);
    } else if (sortMode === "time") {
        items.reverse();
    }

    container.innerHTML = items
        .map(
            (h) => `
            <div class="history-item${h._idx === latestIdx ? ' latest' : ''}">
                <span class="history-word">${escapeHTML(h.word)}</span>
                <span class="history-similarity ${getSimClass(h.similarity)}">${h.similarity.toFixed(4)}%</span>
            </div>
        `
        )
        .join("");

    container.scrollTop = 0;
}

function escapeHTML(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function showToast(message, success) {
    const existing = document.querySelector(".toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.className = "toast" + (success ? " success" : "");
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
}

async function resetGame() {
    if (currentMode === "campaign") {
        if (campaignLevelComplete) {
            if (campaignNextLevel) {
                await startCampaignLevel(campaignNextLevel.id);
            } else {
                showCampaignHome();
            }
        } else if (activeCampaignLevel) {
            await startCampaignLevel(activeCampaignLevel.id);
            showToast("本关已重新开始", true);
        }
        return;
    }

    try {
        const data = await fetchJSON(`${API_BASE}/reset-game?session_id=${encodeURIComponent(sessionId || "")}`, { method: "POST" });
        sessionId = data.game_id;
        currentHistory = [];
        document.getElementById("attempts").textContent = "0";
        document.getElementById("correct-count").textContent = "0";
        document.getElementById("history").innerHTML = '<div class="history-placeholder">开始猜测吧！</div>';
        document.getElementById("guess-input").value = "";
        document.getElementById("guess-btn").disabled = false;
        clearRoundResult();
        document.getElementById("guess-input").focus();
        showToast("游戏已重置", true);
    } catch (err) {
        showToast("重置失败", false);
    }
}

async function revealAnswer() {
    if (currentMode === "campaign" && campaignLevelComplete) {
        showCampaignHome();
        return;
    }

    const btn = document.getElementById("reveal-btn");
    btn.disabled = true;

    try {
        const data = await fetchJSON(`${API_BASE}/give-up?session_id=${encodeURIComponent(sessionId || "")}`, { method: "POST" });
        sessionId = data.session_id || sessionId;
        currentHistory = [];
        campaignLevelComplete = false;
        campaignNextLevel = null;
        document.getElementById("attempts").textContent = "0";
        if (currentMode === "classic") {
            document.getElementById("correct-count").textContent = data.correct_count;
        }
        document.getElementById("history").innerHTML = '<div class="history-placeholder">新的一轮，开始猜测吧！</div>';
        if (currentMode === "campaign") {
            document.getElementById("guess-input").disabled = false;
            document.getElementById("guess-btn").disabled = false;
            document.getElementById("reveal-btn").textContent = "查看答案 / 重试本关";
            document.getElementById("reset-btn").textContent = "重试本关";
            showRoundResult(`本关答案：${data.target_word}（已重新开始本关）`);
        } else {
            showRoundResult(`上一轮答案：${data.target_word}（已开始新一轮）`);
        }
        document.getElementById("guess-input").focus();
    } catch (err) {
        showToast(err.message || "查看答案失败，请重试", false);
    } finally {
        btn.disabled = false;
    }
}

window.WebGameBridge = {
    apiBase: API_BASE,
    fetchJSON,
    showToast,
    getUsername: () => currentUsername,
    isLoggedIn: () => Boolean(currentUsername),
    stopWordBackgroundWork: stopBattlePolling,
    resumeWordSurface: () => {
        if (currentMode === "battle" && currentUsername) enterBattleMode();
    },
};

// Event bindings
document.addEventListener("DOMContentLoaded", () => {
    bootstrapGame();

    document.getElementById("guess-btn").addEventListener("click", submitGuess);
    document.getElementById("guess-input").addEventListener("keydown", (e) => {
        if (e.key === "Enter") submitGuess();
    });
    document.getElementById("reset-btn").addEventListener("click", resetGame);
    document.getElementById("reveal-btn").addEventListener("click", revealAnswer);
    document.getElementById("classic-mode-btn").addEventListener("click", enterClassicMode);
    document.getElementById("campaign-mode-btn").addEventListener("click", enterCampaignMode);
    document.getElementById("battle-mode-btn").addEventListener("click", enterBattleMode);
    document.getElementById("back-levels-btn").addEventListener("click", showCampaignHome);
    document.getElementById("create-battle-btn").addEventListener("click", createBattleRoom);
    document.getElementById("join-battle-btn").addEventListener("click", joinBattleRoom);
    document.getElementById("battle-start-btn").addEventListener("click", startBattleRoom);
    document.getElementById("battle-guess-btn").addEventListener("click", submitBattleGuess);
    document.getElementById("battle-rematch-btn").addEventListener("click", requestBattleRematch);
    document.getElementById("battle-leave-btn").addEventListener("click", leaveBattleRoom);
    document.getElementById("battle-join-code").addEventListener("input", (event) => {
        event.target.value = event.target.value.toUpperCase();
    });
    document.getElementById("battle-join-code").addEventListener("keydown", (event) => {
        if (event.key === "Enter") joinBattleRoom();
    });
    document.getElementById("battle-input").addEventListener("keydown", (event) => {
        if (event.key === "Enter") submitBattleGuess();
    });
    document.getElementById("auth-btn").addEventListener("click", openAuthModal);
    document.getElementById("logout-btn").addEventListener("click", logoutAccount);
    document.getElementById("close-auth-modal").addEventListener("click", closeAuthModal);
    document.getElementById("auth-form").addEventListener("submit", (event) => {
        event.preventDefault();
        authenticate("login");
    });
    document.getElementById("register-btn").addEventListener("click", () => authenticate("register"));
    document.getElementById("auth-modal-overlay").addEventListener("click", (event) => {
        if (event.target === event.currentTarget) closeAuthModal();
    });

    // Sort buttons
    document.querySelectorAll(".sort-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".sort-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            sortMode = btn.dataset.sort;
            renderHistory(currentHistory);
        });
    });

    // Modal
    document.getElementById("info-btn").addEventListener("click", () => {
        document.getElementById("modal-overlay").classList.add("show");
    });
    document.getElementById("close-modal").addEventListener("click", () => {
        document.getElementById("modal-overlay").classList.remove("show");
    });
    document.getElementById("modal-overlay").addEventListener("click", (e) => {
        if (e.target === e.currentTarget) {
            document.getElementById("modal-overlay").classList.remove("show");
        }
    });
});
