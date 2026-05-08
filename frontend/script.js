const API_BASE = "/api";
let sessionId = null;
let isCorrect = false;
let sortMode = "similarity";

function getSimClass(similarity) {
    if (similarity === 0) return "sim-zero";
    if (similarity >= 50) return "sim-high";
    if (similarity >= 25) return "sim-mid";
    return "sim-low";
}

async function initGame() {
    try {
        const res = await fetch(`${API_BASE}/new-game`);
        const data = await res.json();
        sessionId = data.game_id;
        document.getElementById("attempts").textContent = "0";
        document.getElementById("correct-count").textContent = "0";
        document.getElementById("history").innerHTML = '<div class="history-placeholder">开始猜测吧！</div>';
        document.getElementById("guess-input").value = "";
        document.getElementById("guess-input").focus();
    } catch (err) {
        showToast("初始化游戏失败，请检查服务器连接", false);
    }
}

async function submitGuess() {
    const input = document.getElementById("guess-input");
    const word = input.value.trim();
    if (!word) return;
    if (isCorrect) return; // wait for new round transition

    const btn = document.getElementById("guess-btn");
    btn.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/guess?session_id=${sessionId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ word }),
        });
        const data = await res.json();

        if (data.error) {
            showToast(data.error, false);
            btn.disabled = false;
            return;
        }

        // Update attempts
        document.getElementById("attempts").textContent = data.attempts;
        document.getElementById("correct-count").textContent = data.correct_count;

        // Render history
        renderHistory(data.history);

        // Clear input
        input.value = "";

        if (data.is_correct) {
            showToast(`🎉 恭喜猜中！目标词是「${data.target_word}」`, true);
            // Backend auto-starts new round, just update UI
            document.getElementById("attempts").textContent = "0";
            document.getElementById("history").innerHTML = '<div class="history-placeholder">新的一轮，开始猜测吧！</div>';
            document.getElementById("correct-count").textContent = data.correct_count;
            btn.disabled = false;
            document.getElementById("guess-input").focus();
        } else {
            btn.disabled = false;
        }

        input.focus();
    } catch (err) {
        showToast("提交失败，请重试", false);
        btn.disabled = false;
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
    }
    // sortMode === "time": keep original order

    container.innerHTML = items
        .map(
            (h, i) => `
            <div class="history-item${h._idx === latestIdx ? ' latest' : ''}" style="animation-delay: ${i * 0.05}s">
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
    try {
        const res = await fetch(`${API_BASE}/reset-game?session_id=${sessionId}`, { method: "POST" });
        const data = await res.json();
        sessionId = data.game_id;
        document.getElementById("attempts").textContent = "0";
        document.getElementById("correct-count").textContent = "0";
        document.getElementById("history").innerHTML = '<div class="history-placeholder">开始猜测吧！</div>';
        document.getElementById("guess-input").value = "";
        isCorrect = false;
        document.getElementById("guess-btn").disabled = false;
        document.getElementById("guess-input").focus();
        showToast("游戏已重置", true);
    } catch (err) {
        showToast("重置失败", false);
    }
}

// Event bindings
document.addEventListener("DOMContentLoaded", () => {
    initGame();

    document.getElementById("guess-btn").addEventListener("click", submitGuess);
    document.getElementById("guess-input").addEventListener("keydown", (e) => {
        if (e.key === "Enter") submitGuess();
    });
    document.getElementById("reset-btn").addEventListener("click", resetGame);

    // Sort buttons
    document.querySelectorAll(".sort-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".sort-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            sortMode = btn.dataset.sort;
            fetch(`${API_BASE}/status?session_id=${sessionId}`)
                .then(r => r.json())
                .then(data => renderHistory(data.history));
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
