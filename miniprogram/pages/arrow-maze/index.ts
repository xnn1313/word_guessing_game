import type {
  ArrowMazeBoardResponse,
  ArrowMazeSavedState,
  PuzzleCompletionResult,
  PuzzleDifficulty,
  PuzzleSubmitResponse,
} from "../../types/api";
import { isLoggedIn } from "../../utils/auth";
import {
  clearCloudPuzzleShadow,
  clearGuestPuzzleDefinition,
  clearGuestPuzzleState,
  loadGuestPuzzleDefinition,
  loadGuestPuzzleState,
  resolveCloudPuzzleState,
  saveGuestPuzzleState,
  saveGuestPuzzleDefinition,
  stageCloudPuzzleShadow,
} from "../../utils/puzzle-storage";
import { request, showRequestError } from "../../utils/request";

let clockTimer: any = null;
let saveTimer: any = null;

const ARROW_DELTAS: Record<string, { dr: number; dc: number }> = {
  "↑": { dr: -1, dc: 0 },
  "↗": { dr: -1, dc: 1 },
  "→": { dr: 0, dc: 1 },
  "↘": { dr: 1, dc: 1 },
  "↓": { dr: 1, dc: 0 },
  "↙": { dr: 1, dc: -1 },
  "←": { dr: 0, dc: -1 },
  "↖": { dr: -1, dc: -1 },
};

function stopClock(): void {
  if (clockTimer) clearInterval(clockTimer);
  clockTimer = null;
}

function formatTime(seconds: number): string {
  const safe = Math.max(0, Number(seconds) || 0);
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

Page({
  data: {
    loading: true,
    submitting: false,
    hinting: false,
    mode: "daily" as "daily" | "practice",
    difficulty: "easy" as PuzzleDifficulty,
    board: null as ArrowMazeBoardResponse | null,
    puzzleId: "",
    runId: "",
    cloudSavedState: null as ArrowMazeSavedState | null,
    path: [0] as number[],
    cells: [] as any[],
    currentIndex: 0,
    reachableIndexes: [] as number[],
    hintIndex: -1,
    hintActive: false,
    canUndo: false,
    steps: 0,
    elapsedSeconds: 0,
    elapsedText: "00:00",
    hintsUsed: 0,
    mistakes: 0,
    completed: false,
    result: null as PuzzleCompletionResult | null,
    instruction: "从起点出发，只能沿当前格箭头方向跳到任意一格。",
    modeOptions: [
      { value: "daily", label: "每日航线" },
      { value: "practice", label: "自由练习" },
    ],
    difficultyOptions: [
      { value: "easy", label: "直行" },
      { value: "medium", label: "斜向" },
      { value: "hard", label: "迷航" },
    ],
  },

  onLoad() {
    void this.loadBoard();
  },

  onShow() {
    if (this.data.board && !this.data.completed) this.startClock();
  },

  onHide() {
    stopClock();
    void this.flushSave(true);
  },

  onUnload() {
    stopClock();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    void this.flushSave(true);
  },

  startClock() {
    stopClock();
    clockTimer = setInterval(() => {
      if (this.data.loading || this.data.completed) return;
      const elapsedSeconds = this.data.elapsedSeconds + 1;
      this.setData({ elapsedSeconds, elapsedText: formatTime(elapsedSeconds) });
    }, 1000);
  },

  async loadBoard(fresh = false) {
    stopClock();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    this.setData({ loading: true, submitting: false, completed: false, result: null, hintIndex: -1 });
    try {
      const guestSlot = `${this.data.mode}:${this.data.difficulty}`;
      if (!isLoggedIn() && fresh) {
        const previous = loadGuestPuzzleDefinition<ArrowMazeBoardResponse>("arrow_maze", guestSlot);
        if (previous?.puzzle_id) clearGuestPuzzleState("arrow_maze", previous.puzzle_id);
        clearGuestPuzzleDefinition("arrow_maze", guestSlot);
      }
      let board = !isLoggedIn() && this.data.mode === "practice" && !fresh
        ? loadGuestPuzzleDefinition<ArrowMazeBoardResponse>("arrow_maze", guestSlot)
        : null;
      if (!board) {
        board = await request<ArrowMazeBoardResponse>(
          `/arrow-maze/board?mode=${this.data.mode}&difficulty=${this.data.difficulty}${fresh ? "&fresh=1" : ""}`,
        );
        if (!isLoggedIn() && this.data.mode === "practice") {
          saveGuestPuzzleDefinition("arrow_maze", guestSlot, board);
        }
      }
      const local = !isLoggedIn()
        ? loadGuestPuzzleState<ArrowMazeSavedState>("arrow_maze", board.puzzle_id)
        : null;
      const saved = isLoggedIn()
        ? resolveCloudPuzzleState("arrow_maze", board.puzzle_id, board.saved_state)
        : local;
      const path = Array.isArray(saved?.path) && saved!.path.length ? saved!.path : [board.start_index];
      const elapsedSeconds = Number(saved?.elapsed_seconds || 0);
      this.setData({
        board,
        puzzleId: board.puzzle_id,
        runId: board.run_id || "",
        cloudSavedState: board.saved_state,
        path,
        elapsedSeconds,
        elapsedText: formatTime(elapsedSeconds),
        hintsUsed: Number(saved?.hints_used || 0),
        mistakes: Number(saved?.mistakes || 0),
      });
      this.refreshBoard();
      this.persistGuestState();
      this.startClock();
    } catch (error) {
      showRequestError(error, "箭头迷宫加载失败");
    } finally {
      this.setData({ loading: false });
    }
  },

  reachableFrom(index: number): number[] {
    const board = this.data.board;
    if (!board || index === board.target_index) return [];
    const direction = ARROW_DELTAS[board.grid[index]];
    if (!direction) return [];
    const result: number[] = [];
    let row = Math.floor(index / board.columns) + direction.dr;
    let column = (index % board.columns) + direction.dc;
    while (row >= 0 && row < board.rows && column >= 0 && column < board.columns) {
      result.push(row * board.columns + column);
      row += direction.dr;
      column += direction.dc;
    }
    return result;
  },

  refreshBoard() {
    const board = this.data.board;
    if (!board) return;
    const currentIndex = this.data.path[this.data.path.length - 1];
    const reachableIndexes = this.reachableFrom(currentIndex);
    const visited = new Set(this.data.path);
    const reachable = new Set(reachableIndexes);
    const cells = board.grid.map((arrow, index) => ({
      index,
      arrow,
      current: index === currentIndex,
      visited: visited.has(index),
      reachable: reachable.has(index),
      start: index === board.start_index,
      target: index === board.target_index,
      hinted: index === this.data.hintIndex,
      stepNumber: this.data.path.indexOf(index) + 1,
    }));
    this.setData({
      currentIndex,
      reachableIndexes,
      cells,
      steps: this.data.path.length - 1,
      canUndo: this.data.path.length > 1,
      hintActive: this.data.hintIndex >= 0,
      instruction: currentIndex === board.target_index
        ? "出口已找到，正在记录本次路线。"
        : `沿 ${board.grid[currentIndex]} 方向选择亮起的格子`,
    });
  },

  tapCell(event: any) {
    const index = Number(event.currentTarget.dataset.index);
    const board = this.data.board;
    if (!board || this.data.completed || this.data.submitting || !Number.isInteger(index)) return;
    if (!this.data.reachableIndexes.includes(index)) {
      if (index !== this.data.currentIndex) {
        this.setData({ mistakes: this.data.mistakes + 1, instruction: "这格不在当前箭头方向上" });
        wx.vibrateShort({ type: "medium" });
        this.queueSave();
      }
      return;
    }
    this.setData({ path: [...this.data.path, index], hintIndex: -1, hintActive: false });
    this.refreshBoard();
    wx.vibrateShort({ type: "light" });
    this.queueSave();
    if (index === board.target_index) void this.submitPath();
  },

  undoStep() {
    if (this.data.path.length <= 1 || this.data.completed || this.data.submitting) return;
    this.setData({ path: this.data.path.slice(0, -1), hintIndex: -1, hintActive: false });
    this.refreshBoard();
    this.queueSave();
  },

  resetPath() {
    if (!this.data.board || this.data.completed || this.data.submitting) return;
    this.setData({ path: [this.data.board.start_index], hintIndex: -1, hintActive: false, mistakes: this.data.mistakes + 1 });
    this.refreshBoard();
    this.queueSave();
  },

  async showHint() {
    if (!this.data.board || this.data.hinting || this.data.completed) return;
    this.setData({ hinting: true });
    try {
      const response = await request<{ next_index: number; remaining_steps: number }>("/arrow-maze/hint", {
        method: "POST",
        data: {
          puzzle_id: this.data.puzzleId,
          difficulty: this.data.difficulty,
          path: this.data.path,
        },
      });
      this.setData({
        hintIndex: response.next_index,
        hintActive: true,
        hintsUsed: this.data.hintsUsed + 1,
        instruction: `罗盘提示：选择闪烁格，距出口约 ${response.remaining_steps} 步`,
      });
      this.refreshBoard();
      this.queueSave();
    } catch (error) {
      showRequestError(error, "暂时无法提供提示");
    } finally {
      this.setData({ hinting: false });
    }
  },

  persistGuestState() {
    if (isLoggedIn() || !this.data.puzzleId) return;
    saveGuestPuzzleState<ArrowMazeSavedState>("arrow_maze", this.data.puzzleId, {
      path: this.data.path,
      elapsed_seconds: this.data.elapsedSeconds,
      hints_used: this.data.hintsUsed,
      mistakes: this.data.mistakes,
    });
  },

  queueSave() {
    this.persistGuestState();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => void this.flushSave(true), 700);
  },

  async flushSave(silent = false) {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    this.persistGuestState();
    if (!isLoggedIn() || !this.data.runId || !this.data.puzzleId || this.data.completed) return;
    const state: ArrowMazeSavedState = {
      path: this.data.path,
      elapsed_seconds: this.data.elapsedSeconds,
      hints_used: this.data.hintsUsed,
      mistakes: this.data.mistakes,
    };
    stageCloudPuzzleShadow("arrow_maze", this.data.puzzleId, state, this.data.cloudSavedState);
    try {
      await request("/arrow-maze/save", {
        method: "POST",
        authenticated: true,
        data: {
          run_id: this.data.runId,
          puzzle_id: this.data.puzzleId,
          path: state.path,
          elapsed_seconds: state.elapsed_seconds,
          hints_used: state.hints_used,
          mistakes: state.mistakes,
        },
      });
      this.setData({ cloudSavedState: state });
      clearCloudPuzzleShadow("arrow_maze", this.data.puzzleId);
    } catch (error) {
      if (!silent) showRequestError(error, "迷宫进度保存失败");
    }
  },

  async submitPath() {
    if (!this.data.board || this.data.submitting || this.data.completed) return;
    this.setData({ submitting: true });
    try {
      const response = await request<PuzzleSubmitResponse>("/arrow-maze/submit", {
        method: "POST",
        data: {
          run_id: this.data.runId || undefined,
          puzzle_id: this.data.puzzleId,
          difficulty: this.data.difficulty,
          path: this.data.path,
          elapsed_seconds: this.data.elapsedSeconds,
          hints_used: this.data.hintsUsed,
          mistakes: this.data.mistakes,
        },
      });
      if (response.correct && response.result) {
        stopClock();
        clearGuestPuzzleState("arrow_maze", this.data.puzzleId);
        clearGuestPuzzleDefinition("arrow_maze", `${this.data.mode}:${this.data.difficulty}`);
        clearCloudPuzzleShadow("arrow_maze", this.data.puzzleId);
        this.setData({ completed: true, result: response.result, instruction: "出口已找到" });
      }
    } catch (error) {
      showRequestError(error, "路线结算失败");
    } finally {
      this.setData({ submitting: false });
    }
  },

  switchMode(event: any) {
    const mode = event.currentTarget.dataset.value as "daily" | "practice";
    if (!mode || mode === this.data.mode) return;
    void this.flushSave(true).finally(() => {
      this.setData({ mode });
      void this.loadBoard();
    });
  },

  switchDifficulty(event: any) {
    const difficulty = event.currentTarget.dataset.value as PuzzleDifficulty;
    if (!difficulty || difficulty === this.data.difficulty) return;
    void this.flushSave(true).finally(() => {
      this.setData({ difficulty });
      void this.loadBoard();
    });
  },

  newBoard() {
    void this.loadBoard(this.data.mode === "practice");
  },

  goHub() {
    wx.reLaunch({ url: "/pages/hub/index" });
  },
});

export {};
