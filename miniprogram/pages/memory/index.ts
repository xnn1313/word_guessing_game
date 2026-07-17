import type {
  MemoryBoardResponse,
  MemorySavedState,
  PuzzleCompletionResult,
  PuzzleDifficulty,
  PuzzleSubmitResponse,
} from "../../types/api";
import { isLoggedIn } from "../../utils/auth";
import {
  clearGuestPuzzleDefinition,
  clearGuestPuzzleState,
  loadGuestPuzzleDefinition,
  loadGuestPuzzleState,
  saveGuestPuzzleDefinition,
  saveGuestPuzzleState,
} from "../../utils/puzzle-storage";
import { LatestTaskQueue } from "../../utils/latest-task-queue";
import { request, showRequestError } from "../../utils/request";

let clockTimer: any = null;
let saveTimer: any = null;
let resolveTimer: any = null;

type MemoryTheme = "classic" | "fruit" | "animal";

const MEMORY_LEVEL_KEY = "memory_level_progress_v1";
const MEMORY_LEVEL_COUNT = 18;
const MEMORY_LEVEL_THEMES: MemoryTheme[] = ["classic", "fruit", "animal"];

function levelConfig(level: number): { difficulty: PuzzleDifficulty; theme: MemoryTheme } {
  const safeLevel = Math.min(MEMORY_LEVEL_COUNT, Math.max(1, Number(level) || 1));
  const difficulty: PuzzleDifficulty = safeLevel <= 6 ? "easy" : safeLevel <= 12 ? "medium" : "hard";
  return { difficulty, theme: MEMORY_LEVEL_THEMES[(safeLevel - 1) % MEMORY_LEVEL_THEMES.length] };
}

function loadLevelProgress(): Record<string, number> {
  try {
    return wx.getStorageSync(MEMORY_LEVEL_KEY) || {};
  } catch (error) {
    return {};
  }
}

function buildLevelOptions(selectedLevel: number) {
  const progress = loadLevelProgress();
  return Array.from({ length: MEMORY_LEVEL_COUNT }, (_, index) => {
    const level = index + 1;
    const stars = Number(progress[String(level)] || 0);
    const unlocked = level === 1 || Number(progress[String(level - 1)] || 0) > 0;
    const config = levelConfig(level);
    return {
      level,
      stars,
      unlocked,
      selected: level === selectedLevel,
      detail: stars ? "★".repeat(stars) : config.difficulty === "easy" ? "入门" : config.difficulty === "medium" ? "进阶" : "挑战",
    };
  });
}

interface MemorySaveTask {
  loggedIn: boolean;
  silent: boolean;
  boardId: string;
  runId: string;
  state: MemorySavedState;
}

const memorySaveQueue = new LatestTaskQueue<MemorySaveTask>(
  async (task) => {
    if (!task.loggedIn) {
      saveGuestPuzzleState("memory", task.boardId, task.state);
      return;
    }
    if (!task.runId) return;
    await request("/memory/save", {
      method: "POST",
      authenticated: true,
      data: {
        run_id: task.runId,
        board_id: task.boardId,
        matched_positions: task.state.matched_positions,
        moves: task.state.moves,
        elapsed_seconds: task.state.elapsed_seconds,
      },
    });
  },
  (error, task) => {
    if (!task.silent) showRequestError(error, "翻牌进度保存失败");
  },
);

function stopClock(): void {
  if (clockTimer) clearInterval(clockTimer);
  clockTimer = null;
}

function stopAllTimers(): void {
  stopClock();
  if (resolveTimer) clearTimeout(resolveTimer);
  resolveTimer = null;
}

function formatTime(seconds: number): string {
  const safe = Math.max(0, Number(seconds) || 0);
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

Page({
  data: {
    loading: true,
    mode: "daily" as "daily" | "practice",
    difficulty: "easy" as PuzzleDifficulty,
    theme: "fruit" as MemoryTheme,
    selectedLevel: 1,
    levelCount: MEMORY_LEVEL_COUNT,
    levelOptions: buildLevelOptions(1),
    board: null as MemoryBoardResponse | null,
    boardId: "",
    runId: "",
    cards: [] as any[],
    matchedPositions: [] as number[],
    flippedPositions: [] as number[],
    firstPosition: -1,
    resolving: false,
    moves: 0,
    elapsedSeconds: 0,
    elapsedText: "00:00",
    completed: false,
    submitting: false,
    result: null as PuzzleCompletionResult | null,
    modeOptions: [
      { value: "daily", label: "每日牌局" },
      { value: "practice", label: "关卡模式" },
    ],
    difficultyOptions: [
      { value: "easy", label: "简单 4×4" },
      { value: "medium", label: "中等 4×5" },
      { value: "hard", label: "困难 5×6" },
    ],
    themeOptions: [
      { value: "classic", label: "符号" },
      { value: "fruit", label: "水果" },
      { value: "animal", label: "动物" },
    ],
  },

  onLoad() {
    this.loadBoard();
  },

  onShow() {
    if (this.data.board && !this.data.completed) this.startClock();
  },

  onHide() {
    // 配对动画需要继续收尾，否则切回页面后会一直停在 resolving 状态。
    stopClock();
    void this.flushSave();
  },

  onUnload() {
    stopAllTimers();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    void this.flushSave();
  },

  startClock() {
    stopClock();
    clockTimer = setInterval(() => {
      if (this.data.completed || this.data.loading) return;
      const elapsedSeconds = this.data.elapsedSeconds + 1;
      this.setData({ elapsedSeconds, elapsedText: formatTime(elapsedSeconds) });
      if (elapsedSeconds % 15 === 0) this.queueSave();
    }, 1000);
  },

  async loadBoard(forceNew = false) {
    stopAllTimers();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    this.setData({ loading: true, completed: false, result: null, resolving: false });
    try {
      const guestSlot = `${this.data.mode}:${this.data.difficulty}:${this.data.theme}:${this.data.selectedLevel}`;
      const canResumeLocally = !isLoggedIn() && this.data.mode === "practice" && !forceNew;
      let board = canResumeLocally
        ? loadGuestPuzzleDefinition<MemoryBoardResponse>("memory", guestSlot)
        : null;
      if (!board) {
        board = await request<MemoryBoardResponse>(
          `/memory/board?mode=${this.data.mode}&difficulty=${this.data.difficulty}&theme=${this.data.theme}${forceNew ? "&fresh=1" : ""}`,
        );
        if (!isLoggedIn() && this.data.mode === "practice") {
          saveGuestPuzzleDefinition("memory", guestSlot, board);
        }
      }
      const local = !isLoggedIn()
        ? loadGuestPuzzleState<MemorySavedState>("memory", board.board_id)
        : null;
      const saved = board.saved_state || local;
      this.setData({
        board,
        boardId: board.board_id,
        runId: board.run_id || "",
        matchedPositions: [...(saved?.matched_positions || [])],
        flippedPositions: [],
        firstPosition: -1,
        moves: Number(saved?.moves || 0),
        elapsedSeconds: Number(saved?.elapsed_seconds || 0),
        elapsedText: formatTime(Number(saved?.elapsed_seconds || 0)),
      });
      this.refreshCards();
      this.startClock();
    } catch (error) {
      showRequestError(error, "翻牌游戏加载失败");
    } finally {
      this.setData({ loading: false });
    }
  },

  refreshCards() {
    if (!this.data.board) return;
    const matched = new Set(this.data.matchedPositions);
    const flipped = new Set(this.data.flippedPositions);
    this.setData({
      cards: this.data.board.cards.map((card) => ({
        ...card,
        matched: matched.has(card.position),
        flipped: matched.has(card.position) || flipped.has(card.position),
      })),
    });
  },

  async switchMode(event: any) {
    if (this.data.loading || this.data.submitting || this.data.resolving) return;
    const mode = event.currentTarget.dataset.value as "daily" | "practice";
    if (mode === this.data.mode) return;
    await this.flushSave();
    const config = mode === "practice" ? levelConfig(this.data.selectedLevel) : null;
    this.setData(
      config ? { mode, difficulty: config.difficulty, theme: config.theme } : { mode },
      () => this.loadBoard(),
    );
  },

  async switchLevel(event: any) {
    if (this.data.loading || this.data.submitting || this.data.resolving) return;
    const level = Number(event.currentTarget.dataset.level);
    const option = this.data.levelOptions.find((item: any) => item.level === level);
    if (!option?.unlocked) {
      wx.showToast({ title: "先完成上一关", icon: "none" });
      return;
    }
    if (level === this.data.selectedLevel && this.data.mode === "practice") return;
    await this.flushSave();
    const config = levelConfig(level);
    this.setData({
      mode: "practice",
      selectedLevel: level,
      difficulty: config.difficulty,
      theme: config.theme,
      levelOptions: buildLevelOptions(level),
    }, () => this.loadBoard(true));
  },

  async switchDifficulty(event: any) {
    if (this.data.loading || this.data.submitting || this.data.resolving) return;
    const difficulty = event.currentTarget.dataset.value as PuzzleDifficulty;
    if (difficulty === this.data.difficulty) return;
    await this.flushSave();
    this.setData({ difficulty }, () => this.loadBoard());
  },

  async switchTheme(event: any) {
    if (this.data.loading || this.data.submitting || this.data.resolving) return;
    const theme = event.currentTarget.dataset.value as "classic" | "fruit" | "animal";
    if (theme === this.data.theme) return;
    await this.flushSave();
    this.setData({ theme }, () => this.loadBoard());
  },

  flipCard(event: any) {
    if (!this.data.board || this.data.resolving || this.data.completed || this.data.submitting) return;
    const position = Number(event.currentTarget.dataset.position);
    const card = this.data.board.cards.find((item) => item.position === position);
    if (!card || this.data.matchedPositions.includes(position) || this.data.flippedPositions.includes(position)) return;

    if (this.data.firstPosition < 0) {
      this.setData({ firstPosition: position, flippedPositions: [position] });
      this.refreshCards();
      return;
    }

    const firstPosition = this.data.firstPosition;
    const first = this.data.board.cards.find((item) => item.position === firstPosition);
    if (!first) return;
    const moves = this.data.moves + 1;
    this.setData({ flippedPositions: [firstPosition, position], resolving: true, moves });
    this.refreshCards();
    resolveTimer = setTimeout(() => {
      const matchedPositions = [...this.data.matchedPositions];
      if (first.face_key === card.face_key) {
        matchedPositions.push(firstPosition, position);
        matchedPositions.sort((a, b) => a - b);
        wx.vibrateShort({ type: "light" });
      }
      this.setData({
        matchedPositions,
        flippedPositions: [],
        firstPosition: -1,
        resolving: false,
      });
      this.refreshCards();
      this.queueSave();
      if (matchedPositions.length === this.data.board?.cards.length) this.submitCompletion();
    }, 650);
  },

  queueSave() {
    if (!this.data.board || this.data.completed) return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => this.saveProgress(true), 500);
  },

  async flushSave() {
    if (!this.data.board || this.data.completed) return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    const task = this.createSaveTask(true);
    if (task) await memorySaveQueue.flush(task);
  },

  createSaveTask(silent = false): MemorySaveTask | null {
    if (!this.data.board || this.data.completed) return null;
    const state: MemorySavedState = {
      matched_positions: [...this.data.matchedPositions],
      moves: this.data.moves,
      elapsed_seconds: this.data.elapsedSeconds,
    };
    return {
      loggedIn: isLoggedIn(),
      silent,
      boardId: this.data.boardId,
      runId: this.data.runId,
      state,
    };
  },

  saveProgress(silent = false) {
    const task = this.createSaveTask(silent);
    if (task) memorySaveQueue.enqueue(task);
  },

  async submitCompletion() {
    if (!this.data.board || this.data.submitting || this.data.completed) return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    this.setData({ submitting: true });
    try {
      await this.flushSave();
      const response = await request<PuzzleSubmitResponse>("/memory/submit", {
        method: "POST",
        acceptedStatusCodes: [422],
        data: {
          run_id: this.data.runId || undefined,
          board_id: this.data.boardId,
          matched_positions: this.data.matchedPositions,
          moves: this.data.moves,
          elapsed_seconds: this.data.elapsedSeconds,
        },
      });
      if (!response.correct) {
        wx.showToast({ title: "还有牌没有匹配", icon: "none" });
        return;
      }
      stopAllTimers();
      if (!isLoggedIn()) {
        clearGuestPuzzleState("memory", this.data.boardId);
        if (this.data.mode === "practice") {
          clearGuestPuzzleDefinition(
            "memory",
            `${this.data.mode}:${this.data.difficulty}:${this.data.theme}:${this.data.selectedLevel}`,
          );
        }
      }
      if (this.data.mode === "practice") {
        const progress = loadLevelProgress();
        const currentStars = Number(progress[String(this.data.selectedLevel)] || 0);
        progress[String(this.data.selectedLevel)] = Math.max(currentStars, Number(response.result?.stars || 1));
        wx.setStorageSync(MEMORY_LEVEL_KEY, progress);
      }
      this.setData({ completed: true, result: response.result || null });
      this.setData({ levelOptions: buildLevelOptions(this.data.selectedLevel) });
      wx.vibrateShort({ type: "medium" });
    } catch (error) {
      showRequestError(error, "保存翻牌成绩失败");
    } finally {
      this.setData({ submitting: false });
    }
  },

  playAgain() {
    if (this.data.loading || this.data.submitting) return;
    if (this.data.mode === "daily") {
      const config = levelConfig(this.data.selectedLevel);
      this.setData({ mode: "practice", difficulty: config.difficulty, theme: config.theme }, () => this.loadBoard(true));
    } else {
      this.loadBoard(true);
    }
  },

  nextLevel() {
    if (this.data.loading || this.data.submitting) return;
    const next = Math.min(MEMORY_LEVEL_COUNT, this.data.selectedLevel + 1);
    if (next === this.data.selectedLevel) {
      this.playAgain();
      return;
    }
    const config = levelConfig(next);
    this.setData({
      mode: "practice",
      selectedLevel: next,
      difficulty: config.difficulty,
      theme: config.theme,
      levelOptions: buildLevelOptions(next),
    }, () => this.loadBoard(true));
  },
});

export {};
