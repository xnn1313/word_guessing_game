import type {
  PuzzleCompletionResult,
  Tile2048StartResponse,
  Tile2048SubmitResponse,
} from "../../types/api";
import { isLoggedIn } from "../../utils/auth";
import { request, showRequestError } from "../../utils/request";

let saveTimer: any = null;
let clockTimer: any = null;

type Direction = "left" | "right" | "up" | "down";

function formatTime(seconds: number): string {
  const safe = Math.max(0, Number(seconds) || 0);
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

function slide(line: number[]): { line: number[]; gained: number } {
  const compact = line.filter((value) => value !== 0);
  const merged: number[] = [];
  let gained = 0;
  for (let index = 0; index < compact.length; index += 1) {
    if (compact[index] === compact[index + 1]) {
      const value = compact[index] * 2;
      merged.push(value);
      gained += value;
      index += 1;
    } else {
      merged.push(compact[index]);
    }
  }
  while (merged.length < line.length) merged.push(0);
  return { line: merged, gained };
}

function moveBoard(board: number[], direction: Direction): { board: number[]; gained: number; moved: boolean } {
  const next = board.slice();
  let gained = 0;
  const apply = (indices: number[]) => {
    const result = slide(indices.map((index) => next[index]));
    gained += result.gained;
    indices.forEach((index, offset) => {
      next[index] = result.line[offset];
    });
  };
  for (let line = 0; line < 4; line += 1) {
    const indices = [0, 1, 2, 3].map((offset) => line * 4 + offset);
    if (direction === "left") apply(indices);
    if (direction === "right") apply(indices.slice().reverse());
    const column = [0, 1, 2, 3].map((row) => row * 4 + line);
    if (direction === "up") apply(column);
    if (direction === "down") apply(column.slice().reverse());
  }
  return { board: next, gained, moved: next.some((value, index) => value !== board[index]) };
}

function addRandomTile(board: number[]): number[] {
  const empty = board.map((value, index) => (value === 0 ? index : -1)).filter((index) => index >= 0);
  if (!empty.length) return board;
  const next = board.slice();
  next[empty[Math.floor(Math.random() * empty.length)]] = Math.random() < 0.1 ? 4 : 2;
  return next;
}

function isGameOver(board: number[]): boolean {
  if (board.includes(0)) return false;
  for (let row = 0; row < 4; row += 1) {
    for (let column = 0; column < 4; column += 1) {
      const index = row * 4 + column;
      if (column < 3 && board[index] === board[index + 1]) return false;
      if (row < 3 && board[index] === board[index + 4]) return false;
    }
  }
  return true;
}

function tileClass(value: number): string {
  if (value === 0) return "empty";
  return value > 2048 ? "super" : `value-${value}`;
}

Page({
  data: {
    loading: true,
    mode: "daily" as "daily" | "practice",
    board: [] as number[],
    cells: [] as Array<{ id: number; value: number; cls: string }>,
    score: 0,
    bestScore: 0,
    moves: 0,
    elapsedSeconds: 0,
    elapsedText: "00:00",
    puzzleId: "",
    runId: "",
    gameOver: false,
    completed: false,
    submitting: false,
    result: null as PuzzleCompletionResult | null,
    dismissResult: false,
  },

  touchStartX: 0,
  touchStartY: 0,

  onLoad() {
    void this.startGame(false);
  },

  onShow() {
    if (this.data.board.length && !this.data.completed && !this.data.gameOver) this.startClock();
  },

  onHide() {
    this.stopClock();
    void this.saveProgress();
  },

  onUnload() {
    this.stopClock();
    if (saveTimer) clearTimeout(saveTimer);
    void this.saveProgress();
  },

  startClock() {
    this.stopClock();
    clockTimer = setInterval(() => {
      if (this.data.completed || this.data.gameOver) return;
      const elapsedSeconds = this.data.elapsedSeconds + 1;
      this.setData({ elapsedSeconds, elapsedText: formatTime(elapsedSeconds) });
    }, 1000);
  },

  stopClock() {
    if (clockTimer) clearInterval(clockTimer);
    clockTimer = null;
  },

  async startGame(fresh: boolean) {
    this.stopClock();
    this.setData({ loading: true, completed: false, gameOver: false, result: null, dismissResult: false });
    try {
      const payload = await request<Tile2048StartResponse>(
        `/games/tile2048/start?mode=${this.data.mode}${fresh ? "&fresh=1" : ""}`,
      );
      this.setBoard(payload.board);
      this.setData({
        puzzleId: payload.puzzle_id,
        runId: payload.run_id || "",
        score: payload.score,
        moves: payload.moves,
        bestScore: payload.best_score || 0,
        elapsedSeconds: payload.elapsed_seconds || 0,
        elapsedText: formatTime(payload.elapsed_seconds || 0),
      });
      this.setData({ loading: false });
      this.startClock();
    } catch (error) {
      this.setData({ loading: false });
      showRequestError(error, "2048 加载失败");
    }
  },

  setBoard(board: number[]) {
    this.setData({
      board,
      cells: board.map((value, index) => ({ id: index, value, cls: tileClass(value) })),
    });
  },

  switchMode(event: any) {
    const mode = event.currentTarget.dataset.value as "daily" | "practice";
    if (mode === this.data.mode) return;
    this.setData({ mode });
    void this.startGame(true);
  },

  startGameTap() {
    void this.startGame(true);
  },

  onTouchStart(event: any) {
    const touch = event.touches && event.touches[0];
    if (!touch) return;
    this.touchStartX = touch.clientX;
    this.touchStartY = touch.clientY;
  },

  onTouchEnd(event: any) {
    if (this.data.loading || this.data.completed || this.data.gameOver) return;
    const touch = event.changedTouches && event.changedTouches[0];
    if (!touch) return;
    const dx = touch.clientX - this.touchStartX;
    const dy = touch.clientY - this.touchStartY;
    if (Math.abs(dx) < 24 && Math.abs(dy) < 24) return;
    const direction: Direction =
      Math.abs(dx) >= Math.abs(dy) ? (dx > 0 ? "right" : "left") : dy > 0 ? "down" : "up";
    this.move(direction);
  },

  move(direction: Direction) {
    const { board, gained, moved } = moveBoard(this.data.board, direction);
    if (!moved) return;
    const withTile = addRandomTile(board);
    const score = this.data.score + gained;
    this.setBoard(withTile);
    this.setData({ score, moves: this.data.moves + 1 });
    if (withTile.some((value) => value >= 2048) && !this.data.completed) {
      this.finishWin(withTile, score, this.data.moves + 1);
      return;
    }
    if (isGameOver(withTile)) {
      this.stopClock();
      this.setData({ gameOver: true });
      return;
    }
    this.scheduleSave();
  },

  scheduleSave() {
    if (!isLoggedIn() || !this.data.runId) return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      saveTimer = null;
      void this.saveProgress();
    }, 700);
  },

  async saveProgress() {
    if (!isLoggedIn() || !this.data.runId || !this.data.puzzleId) return;
    try {
      await request("/games/tile2048/save", {
        method: "POST",
        authenticated: true,
        data: {
          puzzle_id: this.data.puzzleId,
          run_id: this.data.runId,
          board: this.data.board,
          score: this.data.score,
          moves: this.data.moves,
          elapsed_seconds: this.data.elapsedSeconds,
        },
      });
    } catch (error) {
      // 自动存档失败不影响本地对局，下一次移动会重试。
    }
  },

  async finishWin(board: number[], score: number, moves: number) {
    this.stopClock();
    if (saveTimer) clearTimeout(saveTimer);
    const elapsed = this.data.elapsedSeconds;
    this.setData({ completed: true, submitting: true });
    try {
      const response = await request<Tile2048SubmitResponse>("/games/tile2048/submit", {
        method: "POST",
        authenticated: isLoggedIn(),
        data: {
          puzzle_id: this.data.puzzleId,
          run_id: this.data.runId,
          board,
          score,
          moves,
          elapsed_seconds: elapsed,
        },
      });
      this.setData({ result: response.result || null, submitting: false });
    } catch (error) {
      this.setData({ submitting: false });
      showRequestError(error, "成绩提交失败");
    }
  },

  continuePlay() {
    this.setData({ dismissResult: true });
    this.startClock();
  },

  closeResult() {
    this.setData({ dismissResult: true });
  },

  goHub() {
    wx.navigateBack({ delta: 1 });
  },

  noop() {},
});

export {};
