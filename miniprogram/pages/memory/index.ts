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
import { request, showRequestError } from "../../utils/request";

let clockTimer: any = null;
let saveTimer: any = null;
let resolveTimer: any = null;

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
    theme: "fruit" as "classic" | "fruit" | "animal",
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
      { value: "practice", label: "自由练习" },
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
    this.flushSave();
  },

  onUnload() {
    stopAllTimers();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    this.flushSave();
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
      const guestSlot = `${this.data.mode}:${this.data.difficulty}:${this.data.theme}`;
      const canResumeLocally = !isLoggedIn() && this.data.mode === "practice" && !forceNew;
      let board = canResumeLocally
        ? loadGuestPuzzleDefinition<MemoryBoardResponse>("memory", guestSlot)
        : null;
      if (!board) {
        board = await request<MemoryBoardResponse>(
          `/memory/board?mode=${this.data.mode}&difficulty=${this.data.difficulty}&theme=${this.data.theme}`,
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

  switchMode(event: any) {
    const mode = event.currentTarget.dataset.value as "daily" | "practice";
    if (mode === this.data.mode) return;
    this.flushSave();
    this.setData({ mode }, () => this.loadBoard());
  },

  switchDifficulty(event: any) {
    const difficulty = event.currentTarget.dataset.value as PuzzleDifficulty;
    if (difficulty === this.data.difficulty) return;
    this.flushSave();
    this.setData({ difficulty }, () => this.loadBoard());
  },

  switchTheme(event: any) {
    const theme = event.currentTarget.dataset.value as "classic" | "fruit" | "animal";
    if (theme === this.data.theme) return;
    this.flushSave();
    this.setData({ theme }, () => this.loadBoard());
  },

  flipCard(event: any) {
    if (!this.data.board || this.data.resolving || this.data.completed) return;
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

  flushSave() {
    if (!this.data.board || this.data.completed) return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    this.saveProgress(true);
  },

  async saveProgress(silent = false) {
    if (!this.data.board || this.data.completed) return;
    const state: MemorySavedState = {
      matched_positions: this.data.matchedPositions,
      moves: this.data.moves,
      elapsed_seconds: this.data.elapsedSeconds,
    };
    if (!isLoggedIn()) {
      saveGuestPuzzleState("memory", this.data.boardId, state);
      return;
    }
    if (!this.data.runId) return;
    try {
      await request("/memory/save", {
        method: "POST",
        authenticated: true,
        data: {
          run_id: this.data.runId,
          board_id: this.data.boardId,
          matched_positions: state.matched_positions,
          moves: state.moves,
          elapsed_seconds: state.elapsed_seconds,
        },
      });
    } catch (error) {
      if (!silent) showRequestError(error, "翻牌进度保存失败");
    }
  },

  async submitCompletion() {
    if (!this.data.board || this.data.submitting || this.data.completed) return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    this.setData({ submitting: true });
    try {
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
            `${this.data.mode}:${this.data.difficulty}:${this.data.theme}`,
          );
        }
      }
      this.setData({ completed: true, result: response.result || null });
      wx.vibrateShort({ type: "medium" });
    } catch (error) {
      showRequestError(error, "保存翻牌成绩失败");
    } finally {
      this.setData({ submitting: false });
    }
  },

  playAgain() {
    if (this.data.mode === "daily") {
      this.setData({ mode: "practice" }, () => this.loadBoard(true));
    } else {
      this.loadBoard(true);
    }
  },
});

export {};
