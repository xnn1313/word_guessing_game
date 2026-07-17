(function () {
    "use strict";

    const bridge = window.WebGameBridge;
    if (!bridge) throw new Error("WebGameBridge 未初始化");

    const registry = new Map();
    const instances = new Map();
    let activeGame = "word";
    let switching = false;

    function formatTime(seconds) {
        const value = Math.max(0, Number(seconds) || 0);
        return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
    }

    function escapeHTML(value) {
        const element = document.createElement("div");
        element.textContent = String(value ?? "");
        return element.innerHTML;
    }

    function renderStars(stars) {
        const value = Math.max(0, Math.min(3, Number(stars) || 0));
        return "★".repeat(value) + "☆".repeat(3 - value);
    }

    function accountScope() {
        const username = String(bridge.getUsername() || "").trim();
        return username ? `user:${encodeURIComponent(username)}` : "guest";
    }

    function storageKey(kind, game, slot) {
        return `word_game_web_${kind}_v1:${accountScope()}:${game}:${slot}`;
    }

    function loadStored(kind, game, slot, fallback = null) {
        try {
            const raw = localStorage.getItem(storageKey(kind, game, slot));
            return raw ? JSON.parse(raw) : fallback;
        } catch (error) {
            return fallback;
        }
    }

    function saveStored(kind, game, slot, value) {
        try {
            localStorage.setItem(storageKey(kind, game, slot), JSON.stringify(value));
        } catch (error) {
            // Storage quotas or privacy mode should not make a game unplayable.
        }
    }

    function clearStored(kind, game, slot) {
        try {
            localStorage.removeItem(storageKey(kind, game, slot));
        } catch (error) {
            // Ignore unavailable browser storage.
        }
    }

    function createClock(onTick) {
        let timer = null;
        return {
            start() {
                this.stop();
                timer = window.setInterval(onTick, 1000);
            },
            stop() {
                if (timer) window.clearInterval(timer);
                timer = null;
            },
        };
    }

    function setBusy(button, busy, busyText = "处理中…") {
        if (!button) return;
        if (busy) {
            button.dataset.originalText = button.textContent;
            button.textContent = busyText;
            button.disabled = true;
        } else {
            button.textContent = button.dataset.originalText || button.textContent;
            button.disabled = false;
            delete button.dataset.originalText;
        }
    }

    async function switchGame(game) {
        if (switching || game === activeGame) return;
        switching = true;
        try {
            if (activeGame !== "word") {
                const previous = instances.get(activeGame);
                if (previous && typeof previous.beforeLeave === "function") {
                    const canLeave = await previous.beforeLeave();
                    if (canLeave === false) return;
                }
            }

            const shell = document.getElementById("game-container");
            const wordShell = document.getElementById("word-game-shell");
            const puzzleRoot = document.getElementById("puzzle-games-root");
            document.querySelectorAll(".game-switch-btn").forEach((button) => {
                button.classList.toggle("active", button.dataset.game === game);
                button.setAttribute("aria-current", button.dataset.game === game ? "page" : "false");
            });

            if (game === "word") {
                puzzleRoot.hidden = true;
                puzzleRoot.querySelectorAll(".puzzle-panel").forEach((panel) => { panel.hidden = true; });
                wordShell.hidden = false;
                shell.classList.remove("puzzle-layout");
                bridge.resumeWordSurface();
            } else {
                bridge.stopWordBackgroundWork();
                wordShell.hidden = true;
                puzzleRoot.hidden = false;
                shell.classList.remove("battle-layout");
                shell.classList.add("puzzle-layout");
                puzzleRoot.querySelectorAll(".puzzle-panel").forEach((panel) => {
                    panel.hidden = panel.dataset.game !== game;
                });
                const controller = instances.get(game);
                if (!controller) throw new Error(`游戏控制器未注册：${game}`);
                await controller.enter();
            }
            activeGame = game;
        } catch (error) {
            bridge.showToast(error.message || "游戏加载失败，请重试", false);
        } finally {
            switching = false;
        }
    }

    function register(game, factory) {
        if (registry.has(game)) throw new Error(`重复注册游戏：${game}`);
        registry.set(game, factory);
    }

    function boot() {
        const root = document.getElementById("puzzle-games-root");
        for (const [game, factory] of registry.entries()) {
            const panel = document.createElement("section");
            panel.className = "puzzle-panel";
            panel.dataset.game = game;
            panel.hidden = true;
            root.appendChild(panel);
            instances.set(game, factory(panel));
        }

        document.querySelectorAll(".game-switch-btn").forEach((button) => {
            button.addEventListener("click", () => switchGame(button.dataset.game));
        });

        window.addEventListener("web-auth-changed", async () => {
            for (const controller of instances.values()) {
                if (typeof controller.onAuthChange === "function") controller.onAuthChange();
            }
            if (activeGame !== "word") {
                const controller = instances.get(activeGame);
                if (controller) await controller.enter(true);
            }
        });

        window.addEventListener("beforeunload", () => {
            const controller = instances.get(activeGame);
            if (controller && typeof controller.persistLocalNow === "function") {
                controller.persistLocalNow();
            }
        });
    }

    window.WebPuzzleKit = {
        bridge,
        register,
        switchGame,
        formatTime,
        escapeHTML,
        renderStars,
        createClock,
        setBusy,
        loadStored,
        saveStored,
        clearStored,
        isLoggedIn: bridge.isLoggedIn,
    };

    document.addEventListener("DOMContentLoaded", boot);
})();
