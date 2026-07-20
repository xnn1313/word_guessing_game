import type {
  PuzzleCompletionResult,
  PuzzleDifficulty,
  PuzzleSubmitResponse,
  SokobanBoardResponse,
  SokobanSavedState,
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
let walls = new Set<number>();
let targets = new Set<number>();
let initialBoxes = new Set<number>();
let initialPlayer = -1;
let touchStart: { x: number; y: number } | null = null;

const DIRECTIONS: Record<string, { dr: number; dc: number }> = {
  U: { dr: -1, dc: 0 },
  R: { dr: 0, dc: 1 },
  D: { dr: 1, dc: 0 },
  L: { dr: 0, dc: -1 },
};

function stopClock(): void {
  if (clockTimer) clearInterval(clockTimer);
  clockTimer = null;
}

function formatTime(seconds: number): string {
  const safe = Math.max(0, Number(seconds) || 0);
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

function parseBoard(board: SokobanBoardResponse): void {
  walls = new Set<number>();
  targets = new Set<number>();
  initialBoxes = new Set<number>();
  initialPlayer = -1;
  board.board.forEach((row, rowIndex) => {
    row.split("").forEach((value, columnIndex) => {
      const index = rowIndex * board.columns + columnIndex;
      if (value === "#") walls.add(index);
      if (value === "." || value === "*" || value === "+") targets.add(index);
      if (value === "$" || value === "*") initialBoxes.add(index);
      if (value === "@" || value === "+") initialPlayer = index;
    });
  });
}

function replay(board: SokobanBoardResponse, history: string) {
  let player = initialPlayer;
  const boxes = new Set(initialBoxes);
  let pushes = 0;
  for (const code of history) {
    const direction = DIRECTIONS[code];
    if (!direction) continue;
    const row = Math.floor(player / board.columns);
    const column = player % board.columns;
    const target = (row + direction.dr) * board.columns + column + direction.dc;
    if (boxes.has(target)) {
      const beyond = target + direction.dr * board.columns + direction.dc;
      boxes.delete(target);
      boxes.add(beyond);
      pushes += 1;
    }
    player = target;
  }
  return { player, boxes, moves: history.length, pushes };
}

Page({
  data: {
    loading: true,
    submitting: false,
    mode: "daily" as "daily" | "practice",
    difficulty: "easy" as PuzzleDifficulty,
    board: null as SokobanBoardResponse | null,
    puzzleId: "",
    runId: "",
    cloudSavedState: null as SokobanSavedState | null,
    history: "",
    cells: [] as any[],
    player: -1,
    boxPositions: [] as number[],
    moves: 0,
    pushes: 0,
    completedBoxes: 0,
    elapsedSeconds: 0,
    elapsedText: "00:00",
    mistakes: 0,
    completed: false,
    result: null as PuzzleCompletionResult | null,
    modeOptions: [
      { value: "daily", label: "每日仓库" },
      { value: "practice", label: "自由练习" },
    ],
    difficultyOptions: [
      { value: "easy", label: "小仓库" },
      { value: "medium", label: "中仓库" },
      { value: "hard", label: "大仓库" },
    ],
    directionButtons: [
      { code: "U", label: "↑", className: "up" },
      { code: "L", label: "←", className: "left" },
      { code: "D", label: "↓", className: "down" },
      { code: "R", label: "→", className: "right" },
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
    this.setData({ loading: true, submitting: false, completed: false, result: null });
    try {
      const guestSlot = `${this.data.mode}:${this.data.difficulty}`;
      if (!isLoggedIn() && fresh) {
        const previous = loadGuestPuzzleDefinition<SokobanBoardResponse>("sokoban", guestSlot);
        if (previous?.puzzle_id) clearGuestPuzzleState("sokoban", previous.puzzle_id);
        clearGuestPuzzleDefinition("sokoban", guestSlot);
      }
      let board = !isLoggedIn() && this.data.mode === "practice" && !fresh
        ? loadGuestPuzzleDefinition<SokobanBoardResponse>("sokoban", guestSlot)
        : null;
      if (!board) {
        board = await request<SokobanBoardResponse>(
          `/sokoban/board?mode=${this.data.mode}&difficulty=${this.data.difficulty}${fresh ? "&fresh=1" : ""}`,
        );
        if (!isLoggedIn() && this.data.mode === "practice") {
          saveGuestPuzzleDefinition("sokoban", guestSlot, board);
        }
      }
      parseBoard(board);
      const local = !isLoggedIn()
        ? loadGuestPuzzleState<SokobanSavedState>("sokoban", board.puzzle_id)
        : null;
      const saved = isLoggedIn()
        ? resolveCloudPuzzleState("sokoban", board.puzzle_id, board.saved_state)
        : local;
      const history = String(saved?.history || "");
      const elapsedSeconds = Number(saved?.elapsed_seconds || 0);
      this.setData({
        board,
        puzzleId: board.puzzle_id,
        runId: board.run_id || "",
        cloudSavedState: board.saved_state,
        history,
        elapsedSeconds,
        elapsedText: formatTime(elapsedSeconds),
        mistakes: Number(saved?.mistakes || 0),
      });
      this.refreshBoard();
      this.persistGuestState();
      this.startClock();
    } catch (error) {
      showRequestError(error, "推箱子关卡加载失败");
    } finally {
      this.setData({ loading: false });
    }
  },

  refreshBoard() {
    const board = this.data.board;
    if (!board) return;
    const state = replay(board, this.data.history);
    const cells = Array.from({ length: board.rows * board.columns }, (_, index) => {
      const isTarget = targets.has(index);
      const hasBox = state.boxes.has(index);
      return {
        index,
        wall: walls.has(index),
        target: isTarget,
        box: hasBox,
        boxDone: hasBox && isTarget,
        player: state.player === index,
        display: hasBox ? "×" : state.player === index ? "●" : "",
      };
    });
    this.setData({
      cells,
      player: state.player,
      boxPositions: Array.from(state.boxes),
      moves: state.moves,
      pushes: state.pushes,
      completedBoxes: Array.from(state.boxes).filter((index) => targets.has(index)).length,
    });
  },

  persistGuestState() {
    if (isLoggedIn() || !this.data.puzzleId) return;
    saveGuestPuzzleState<SokobanSavedState>("sokoban", this.data.puzzleId, {
      history: this.data.history,
      elapsed_seconds: this.data.elapsedSeconds,
      hints_used: 0,
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
    const state: SokobanSavedState = {
      history: this.data.history,
      elapsed_seconds: this.data.elapsedSeconds,
      hints_used: 0,
      mistakes: this.data.mistakes,
    };
    stageCloudPuzzleShadow("sokoban", this.data.puzzleId, state, this.data.cloudSavedState);
    try {
      await request("/sokoban/save", {
        method: "POST",
        authenticated: true,
        data: {
          run_id: this.data.runId,
          puzzle_id: this.data.puzzleId,
          history: state.history,
          elapsed_seconds: state.elapsed_seconds,
          mistakes: state.mistakes,
        },
      });
      this.setData({ cloudSavedState: state });
      clearCloudPuzzleShadow("sokoban", this.data.puzzleId);
    } catch (error) {
      if (!silent) showRequestError(error, "推箱子进度保存失败");
    }
  },

  move(event: any) {
    const code = String(event.currentTarget.dataset.code || "");
    this.applyMove(code);
  },

  applyMove(code: string) {
    const board = this.data.board;
    const direction = DIRECTIONS[code];
    if (!board || !direction || this.data.completed || this.data.submitting) return;
    const state = replay(board, this.data.history);
    const row = Math.floor(state.player / board.columns);
    const column = state.player % board.columns;
    const nextRow = row + direction.dr;
    const nextColumn = column + direction.dc;
    if (nextRow < 0 || nextRow >= board.rows || nextColumn < 0 || nextColumn >= board.columns) {
      this.invalidMove();
      return;
    }
    const target = nextRow * board.columns + nextColumn;
    if (walls.has(target)) {
      this.invalidMove();
      return;
    }
    if (state.boxes.has(target)) {
      const beyondRow = nextRow + direction.dr;
      const beyondColumn = nextColumn + direction.dc;
      const beyond = beyondRow * board.columns + beyondColumn;
      if (
        beyondRow < 0 || beyondRow >= board.rows || beyondColumn < 0 || beyondColumn >= board.columns ||
        walls.has(beyond) || state.boxes.has(beyond)
      ) {
        this.invalidMove();
        return;
      }
    }
    this.setData({ history: `${this.data.history}${code}` });
    this.refreshBoard();
    wx.vibrateShort({ type: "light" });
    this.queueSave();
    if (this.data.completedBoxes === board.box_count) void this.submitBoard();
  },

  invalidMove() {
    this.setData({ mistakes: this.data.mistakes + 1 });
    wx.vibrateShort({ type: "medium" });
    this.queueSave();
  },

  undoMove() {
    if (!this.data.history || this.data.completed || this.data.submitting) return;
    this.setData({ history: this.data.history.slice(0, -1) });
    this.refreshBoard();
    this.queueSave();
  },

  resetBoard() {
    if (this.data.completed || this.data.submitting) return;
    wx.showModal({
      title: "重新整理仓库？",
      content: "箱子会回到本关初始位置，用时继续累计。",
      confirmText: "重新开始",
      success: (result) => {
        if (!result.confirm) return;
        this.setData({ history: "", mistakes: this.data.mistakes + 1 });
        this.refreshBoard();
        this.queueSave();
      },
    });
  },

  onTouchStart(event: any) {
    const touch = event.touches?.[0];
    touchStart = touch ? { x: touch.clientX, y: touch.clientY } : null;
  },

  onTouchEnd(event: any) {
    const touch = event.changedTouches?.[0];
    if (!touchStart || !touch) return;
    const dx = touch.clientX - touchStart.x;
    const dy = touch.clientY - touchStart.y;
    touchStart = null;
    if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return;
    this.applyMove(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "R" : "L") : (dy > 0 ? "D" : "U"));
  },

  async submitBoard() {
    if (!this.data.board || this.data.submitting || this.data.completed) return;
    this.setData({ submitting: true });
    try {
      const response = await request<PuzzleSubmitResponse>("/sokoban/submit", {
        method: "POST",
        data: {
          run_id: this.data.runId || undefined,
          puzzle_id: this.data.puzzleId,
          difficulty: this.data.difficulty,
          history: this.data.history,
          elapsed_seconds: this.data.elapsedSeconds,
          mistakes: this.data.mistakes,
        },
      });
      if (response.correct && response.result) {
        stopClock();
        clearGuestPuzzleState("sokoban", this.data.puzzleId);
        clearGuestPuzzleDefinition("sokoban", `${this.data.mode}:${this.data.difficulty}`);
        clearCloudPuzzleShadow("sokoban", this.data.puzzleId);
        this.setData({ completed: true, result: response.result });
      }
    } catch (error) {
      showRequestError(error, "关卡结算失败");
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
