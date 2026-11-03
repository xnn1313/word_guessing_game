import type {
  MinesweeperCell,
  MinesweeperSaveResponse,
  MinesweeperStartResponse,
  MinesweeperView,
  PuzzleCompletionResult,
  PuzzleDifficulty,
} from "../../types/api";
import { isLoggedIn } from "../../utils/auth";
import { ApiError, request, showRequestError } from "../../utils/request";

let clockTimer: any = null;

type CellView = MinesweeperCell & { text: string; cls: string };

function formatTime(seconds: number): string {
  const safe = Math.max(0, Number(seconds) || 0);
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

function toCellViews(view: MinesweeperView): CellView[] {
  return view.cells.map((cell) => {
    const text =
      cell.state === "mine" ? "💣" : cell.state === "flagged" ? "🚩" : cell.adjacent ? String(cell.adjacent) : "";
    return {
      ...cell,
      text,
      cls: `cell-${cell.state}${cell.adjacent ? ` adj-${cell.adjacent}` : ""}`,
    };
  });
}

Page({
  data: {
    loggedIn: false,
    loading: true,
    mode: "daily" as "daily" | "practice",
    difficulty: "easy" as PuzzleDifficulty,
    rows: 9,
    cols: 9,
    cells: [] as CellView[],
    status: "playing" as "playing" | "won" | "lost",
    flags: 0,
    remaining: 10,
    elapsedSeconds: 0,
    elapsedText: "00:00",
    puzzleId: "",
    runId: "",
    result: null as PuzzleCompletionResult | null,
    submitting: false,
    difficultyOptions: [
      { value: "easy", label: "9×9 · 10 雷" },
      { value: "medium", label: "12×12 · 22 雷" },
      { value: "hard", label: "16×16 · 40 雷" },
    ],
  },

  onLoad() {
    this.setData({ loading: false });
    if (isLoggedIn()) void this.start(false);
  },

  onShow() {
    const loggedIn = isLoggedIn();
    this.setData({ loggedIn });
    if (loggedIn && !this.data.puzzleId && !this.data.loading) {
      void this.start(false);
    }
  },

  onHide() {
    this.stopClock();
  },

  onUnload() {
    this.stopClock();
  },

  startClock() {
    this.stopClock();
    clockTimer = setInterval(() => {
      if (this.data.status !== "playing") return;
      const elapsedSeconds = this.data.elapsedSeconds + 1;
      this.setData({ elapsedSeconds, elapsedText: formatTime(elapsedSeconds) });
    }, 1000);
  },

  stopClock() {
    if (clockTimer) clearInterval(clockTimer);
    clockTimer = null;
  },

  async start(fresh: boolean) {
    if (!isLoggedIn()) {
      this.setData({ loggedIn: false, loading: false });
      return;
    }
    this.stopClock();
    this.setData({ loading: true, result: null, status: "playing", puzzleId: "", runId: "" });
    try {
      const payload = await request<MinesweeperStartResponse>(
        `/games/minesweeper/start?mode=${this.data.mode}&difficulty=${this.data.difficulty}${fresh ? "&fresh=1" : ""}`,
        { authenticated: true },
      );
      this.setData({
        rows: payload.rows,
        cols: payload.cols,
        puzzleId: payload.puzzle_id,
        runId: payload.run_id || "",
        elapsedSeconds: payload.elapsed_seconds || 0,
        elapsedText: formatTime(payload.elapsed_seconds || 0),
        loading: false,
      });
      this.applyView(payload.view);
      this.startClock();
    } catch (error) {
      this.setData({ loading: false });
      showRequestError(error, "扫雷棋盘加载失败");
    }
  },

  applyView(view: MinesweeperView) {
    this.setData({
      cells: toCellViews(view),
      rows: view.rows,
      cols: view.cols,
      status: view.status,
      flags: view.flags,
      remaining: view.remaining_mines,
    });
  },

  async send(action: "reveal" | "flag", index: number) {
    if (!this.data.runId || this.data.status !== "playing") return;
    const response = await request<MinesweeperSaveResponse>("/games/minesweeper/save", {
      method: "POST",
      authenticated: true,
      data: {
        puzzle_id: this.data.puzzleId,
        run_id: this.data.runId,
        action,
        cell: index,
        elapsed_seconds: this.data.elapsedSeconds,
      },
    });
    this.applyView(response.view);
    if (response.result) {
      this.stopClock();
      this.setData({ result: response.result, status: "won" });
    } else if (response.status === "lost") {
      this.stopClock();
      this.setData({ status: "lost" });
    }
  },

  reveal(event: any) {
    if (!isLoggedIn()) {
      this.goLogin();
      return;
    }
    const index = Number(event.currentTarget.dataset.index);
    this.send("reveal", index).catch((error) => {
      if (error instanceof ApiError && error.statusCode === 409) {
        void this.start(true);
        return;
      }
      showRequestError(error, "翻开失败");
    });
  },

  flag(event: any) {
    if (!isLoggedIn()) {
      this.goLogin();
      return;
    }
    const index = Number(event.currentTarget.dataset.index);
    this.send("flag", index).catch((error) => showRequestError(error, "标记失败"));
  },

  switchMode(event: any) {
    const mode = event.currentTarget.dataset.value as "daily" | "practice";
    if (mode === this.data.mode) return;
    this.setData({ mode });
    void this.start(true);
  },

  switchDifficulty(event: any) {
    const difficulty = event.currentTarget.dataset.value as PuzzleDifficulty;
    if (difficulty === this.data.difficulty) return;
    this.setData({ difficulty });
    void this.start(true);
  },

  restart() {
    void this.start(true);
  },

  goLogin() {
    wx.navigateTo({ url: "/pages/auth/index" });
  },

  goHub() {
    wx.navigateBack({ delta: 1 });
  },
});

export {};
