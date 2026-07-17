import type {
  IdiomCatalog,
  IdiomEntry,
  IdiomPuzzleResponse,
  IdiomSavedState,
  PuzzleCompletionResult,
  PuzzleDifficulty,
  PuzzleHintResponse,
  PuzzleSubmitResponse,
} from "../../types/api";
import { getToken, getUsername, isLoggedIn } from "../../utils/auth";
import type { CloudPuzzleShadowToken } from "../../utils/puzzle-storage";
import {
  clearCloudPuzzleShadow,
  clearGuestPuzzleState,
  confirmCloudPuzzleShadow,
  failCloudPuzzleShadowRequest,
  getGuestIdiomProgress,
  loadGuestPuzzleState,
  markCloudPuzzleShadowInFlight,
  resolveCloudPuzzleState,
  saveGuestIdiomResult,
  saveGuestPuzzleState,
  stageCloudPuzzleShadow,
} from "../../utils/puzzle-storage";
import { LatestTaskQueue } from "../../utils/latest-task-queue";
import { ApiError, request, showRequestError } from "../../utils/request";

let clockTimer: any = null;
let saveTimer: any = null;

interface IdiomSaveTask {
  loggedIn: boolean;
  silent: boolean;
  puzzleId: string;
  runId: string;
  cloudShadow: CloudPuzzleShadowToken<IdiomSavedState> | null;
  authToken: string;
  accountUsername: string;
  state: IdiomSavedState;
}

const idiomSaveQueue = new LatestTaskQueue<IdiomSaveTask>(
  async (task) => {
    if (!task.loggedIn) {
      saveGuestPuzzleState("idiom", task.puzzleId, task.state);
      return;
    }
    if (task.authToken !== getToken() || task.accountUsername !== String(getUsername() || "").trim()) {
      throw new Error("登录账号已变更，已停止旧账号的成语云存档");
    }
    if (!task.runId) throw new Error("成语云存档缺少运行标识");
    markCloudPuzzleShadowInFlight(task.cloudShadow);
    try {
      await request("/idiom/save", {
        method: "POST",
        authenticated: true,
        data: {
          run_id: task.runId,
          puzzle_id: task.puzzleId,
          grid: task.state.grid,
          elapsed_seconds: task.state.elapsed_seconds,
          mistakes: task.state.mistakes,
        },
      });
    } catch (error) {
      if (error instanceof ApiError && error.statusCode >= 400 && error.statusCode < 500) {
        failCloudPuzzleShadowRequest(task.cloudShadow);
      }
      throw error;
    }
    confirmCloudPuzzleShadow(task.cloudShadow);
  },
  (error, task) => {
    if (!task.silent) showRequestError(error, "成语进度保存失败");
  },
);

function stopClock(): void {
  if (clockTimer) clearInterval(clockTimer);
  clockTimer = null;
}

function formatTime(seconds: number): string {
  const safe = Math.max(0, Number(seconds) || 0);
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

function entryCoordinates(entry: IdiomEntry): string[] {
  const coordinates: string[] = [];
  for (let offset = 0; offset < entry.length; offset += 1) {
    const row = entry.start.row + (entry.direction === "down" ? offset : 0);
    const column = entry.start.column + (entry.direction === "across" ? offset : 0);
    coordinates.push(`${row},${column}`);
  }
  return coordinates;
}

Page({
  data: {
    view: "catalog" as "catalog" | "game",
    loading: true,
    categories: [] as any[],
    totalStars: 0,
    maxStars: 0,
    dailyDifficulty: "medium" as PuzzleDifficulty,
    dailyOptions: [
      { value: "easy", label: "简单" },
      { value: "medium", label: "中等" },
      { value: "hard", label: "困难" },
    ],
    puzzle: null as IdiomPuzzleResponse | null,
    puzzleMode: "level" as "daily" | "level",
    runId: "",
    cloudSavedState: null as IdiomSavedState | null,
    grid: [] as string[],
    cells: [] as any[],
    entries: [] as IdiomEntry[],
    characterBank: [] as string[],
    selectedIndex: -1,
    activeEntryId: "entry-1",
    elapsedSeconds: 0,
    elapsedText: "00:00",
    hintsUsed: 0,
    maxHints: 3,
    mistakes: 0,
    invalidCells: [] as number[],
    hinting: false,
    submitting: false,
    completed: false,
    result: null as PuzzleCompletionResult | null,
  },

  onLoad() {
    this.loadCatalog();
  },

  onShow() {
    if (this.data.view === "game" && this.data.puzzle && !this.data.completed) this.startClock();
  },

  onHide() {
    stopClock();
    void this.flushSave().catch((error) => showRequestError(error, "成语进度保存失败，本地备份已保留"));
  },

  onUnload() {
    stopClock();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    void this.flushSave().catch((error) => showRequestError(error, "成语进度保存失败，本地备份已保留"));
  },

  startClock() {
    stopClock();
    clockTimer = setInterval(() => {
      if (this.data.completed || this.data.view !== "game") return;
      const elapsedSeconds = this.data.elapsedSeconds + 1;
      this.setData({ elapsedSeconds, elapsedText: formatTime(elapsedSeconds) });
      if (elapsedSeconds % 15 === 0) this.queueSave();
    }, 1000);
  },

  async loadCatalog() {
    this.setData({ loading: true });
    try {
      const catalog = await request<IdiomCatalog>("/idiom/catalog");
      const guestProgress = isLoggedIn() ? {} : getGuestIdiomProgress();
      let guestStars = 0;
      const categories = catalog.categories.map((category, categoryIndex) => {
        const levels = category.levels.map((level, index) => {
          const local = guestProgress[level.id];
          const previous = index > 0 ? guestProgress[category.levels[index - 1].id] : null;
          if (local) guestStars += Number(local.stars || 0);
          return {
            ...level,
            unlocked: isLoggedIn() ? level.unlocked : index === 0 || Boolean(previous),
            stars: isLoggedIn() ? level.stars : Number(local?.stars || 0),
            best_score: isLoggedIn() ? level.best_score : local?.best_score || null,
            starText: local || level.stars
              ? "★".repeat(isLoggedIn() ? level.stars : Number(local?.stars || 0))
              : "",
          };
        });
        return {
          ...category,
          expanded: categoryIndex === 0,
          levels,
          completed_levels: levels.filter((level) => level.stars > 0).length,
        };
      });
      this.setData({
        categories,
        totalStars: isLoggedIn() ? catalog.total_stars : guestStars,
        maxStars: catalog.max_stars,
      });
    } catch (error) {
      showRequestError(error, "成语关卡加载失败");
    } finally {
      this.setData({ loading: false });
    }
  },

  toggleCategory(event: any) {
    const id = event.currentTarget.dataset.id;
    this.setData({
      categories: this.data.categories.map((category: any) => ({
        ...category,
        expanded: category.id === id ? !category.expanded : false,
      })),
    });
  },

  openLevel(event: any) {
    if (this.data.loading || this.data.submitting || this.data.hinting) return;
    const id = String(event.currentTarget.dataset.id || "");
    const unlocked = Boolean(event.currentTarget.dataset.unlocked);
    if (!unlocked) {
      wx.showToast({ title: "请先完成上一关", icon: "none" });
      return;
    }
    this.loadPuzzle(`/idiom/puzzle?mode=level&level_id=${encodeURIComponent(id)}`);
  },

  switchDailyDifficulty(event: any) {
    if (this.data.loading) return;
    this.setData({ dailyDifficulty: event.currentTarget.dataset.value });
  },

  openDaily() {
    if (this.data.loading) return;
    this.loadPuzzle(
      `/idiom/puzzle?mode=daily&difficulty=${this.data.dailyDifficulty}`,
    );
  },

  async loadPuzzle(path: string) {
    stopClock();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    this.setData({ loading: true, completed: false, result: null, invalidCells: [] });
    try {
      const puzzle = await request<IdiomPuzzleResponse>(path);
      const loggedIn = isLoggedIn();
      const local = !loggedIn
        ? loadGuestPuzzleState<IdiomSavedState>("idiom", puzzle.puzzle_id)
        : null;
      const saved = loggedIn
        ? resolveCloudPuzzleState("idiom", puzzle.puzzle_id, puzzle.saved_state)
        : local;
      const initialGrid = saved?.grid?.length === puzzle.cells.length
        ? saved.grid
        : puzzle.cells.map((cell) => cell.value || "");
      this.setData({
        view: "game",
        puzzle,
        puzzleMode: puzzle.mode,
        runId: puzzle.run_id || "",
        cloudSavedState: puzzle.saved_state,
        grid: [...initialGrid],
        entries: puzzle.entries,
        characterBank: puzzle.character_bank,
        selectedIndex: puzzle.cells.findIndex((cell) => cell.type === "input"),
        activeEntryId: puzzle.entries[0]?.id || "",
        elapsedSeconds: Number(saved?.elapsed_seconds || 0),
        elapsedText: formatTime(Number(saved?.elapsed_seconds || 0)),
        hintsUsed: Number(saved?.hints_used || 0),
        mistakes: Number(saved?.mistakes || 0),
        maxHints: Number(puzzle.limits?.max_hints || 3),
      });
      this.refreshCells();
      this.startClock();
    } catch (error) {
      showRequestError(error, "成语题目加载失败");
    } finally {
      this.setData({ loading: false });
    }
  },

  refreshCells() {
    const puzzle = this.data.puzzle;
    if (!puzzle) return;
    const invalid = new Set(this.data.invalidCells);
    const activeEntry = this.data.entries.find((entry) => entry.id === this.data.activeEntryId);
    const activeCoordinates = new Set(activeEntry ? entryCoordinates(activeEntry) : []);
    this.setData({
      cells: puzzle.cells.map((cell, index) => ({
        ...cell,
        index,
        value: this.data.grid[index] || cell.value || "",
        selected: index === this.data.selectedIndex,
        invalid: invalid.has(index),
        activeEntry: activeCoordinates.has(`${cell.row},${cell.column}`),
        gridRow: cell.row + 1,
        gridColumn: cell.column + 1,
      })),
    });
  },

  selectCell(event: any) {
    const index = Number(event.currentTarget.dataset.index);
    if (!this.data.puzzle || this.data.puzzle.cells[index]?.type !== "input") return;
    const cell = this.data.puzzle.cells[index];
    const entry = this.data.entries.find((item) =>
      entryCoordinates(item).includes(`${cell.row},${cell.column}`),
    );
    this.setData({ selectedIndex: index, activeEntryId: entry?.id || this.data.activeEntryId });
    this.refreshCells();
  },

  selectEntry(event: any) {
    const id = String(event.currentTarget.dataset.id || "");
    const entry = this.data.entries.find((item) => item.id === id);
    if (!entry || !this.data.puzzle) return;
    const coordinates = entryCoordinates(entry);
    const selectedIndex = this.data.puzzle.cells.findIndex(
      (cell) => cell.type === "input" && coordinates.includes(`${cell.row},${cell.column}`),
    );
    this.setData({ activeEntryId: id, selectedIndex });
    this.refreshCells();
  },

  inputCharacter(event: any) {
    const value = String(event.currentTarget.dataset.value || "");
    const index = this.data.selectedIndex;
    if (
      !value ||
      index < 0 ||
      !this.data.puzzle ||
      this.data.completed ||
      this.data.submitting ||
      this.data.hinting
    ) return;
    if (this.data.puzzle.cells[index]?.type !== "input") return;
    const grid = [...this.data.grid];
    grid[index] = value;
    const invalidCells = this.data.invalidCells.filter((item: number) => item !== index);
    let nextIndex = index;
    const activeEntry = this.data.entries.find((entry) => entry.id === this.data.activeEntryId);
    if (activeEntry) {
      const coordinates = entryCoordinates(activeEntry);
      const candidates = this.data.puzzle.cells
        .map((cell, cellIndex) => ({ cell, cellIndex }))
        .filter(({ cell }) => cell.type === "input" && coordinates.includes(`${cell.row},${cell.column}`));
      const currentPosition = candidates.findIndex((item) => item.cellIndex === index);
      const next = candidates.slice(currentPosition + 1).find((item) => !grid[item.cellIndex]);
      if (next) nextIndex = next.cellIndex;
    }
    this.setData({ grid, invalidCells, selectedIndex: nextIndex });
    this.refreshCells();
    this.queueSave();
  },

  eraseCharacter() {
    const index = this.data.selectedIndex;
    if (
      index < 0 ||
      !this.data.puzzle ||
      this.data.puzzle.cells[index]?.type !== "input" ||
      this.data.submitting ||
      this.data.hinting
    ) return;
    const grid = [...this.data.grid];
    grid[index] = "";
    this.setData({
      grid,
      invalidCells: this.data.invalidCells.filter((item: number) => item !== index),
    });
    this.refreshCells();
    this.queueSave();
  },

  queueSave() {
    if (!this.data.puzzle || this.data.completed) return;
    if (saveTimer) clearTimeout(saveTimer);
    const task = this.createSaveTask(true);
    if (task) saveTimer = setTimeout(() => idiomSaveQueue.enqueue(task), 500);
  },

  async flushSave() {
    if (!this.data.puzzle || this.data.completed || this.data.view !== "game") return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    const task = this.createSaveTask(true);
    if (task) await idiomSaveQueue.flush(task);
  },

  createSaveTask(silent = false): IdiomSaveTask | null {
    if (!this.data.puzzle || this.data.completed || this.data.view !== "game") return null;
    const state: IdiomSavedState = {
      grid: [...this.data.grid],
      elapsed_seconds: this.data.elapsedSeconds,
      hints_used: this.data.hintsUsed,
      mistakes: this.data.mistakes,
    };
    const authToken = getToken();
    const accountUsername = String(getUsername() || "").trim();
    const loggedIn = Boolean(authToken);
    const cloudShadow = loggedIn
      ? stageCloudPuzzleShadow("idiom", this.data.puzzle.puzzle_id, state, this.data.cloudSavedState)
      : null;
    return {
      loggedIn,
      silent,
      puzzleId: this.data.puzzle.puzzle_id,
      runId: this.data.runId,
      cloudShadow,
      authToken,
      accountUsername,
      state,
    };
  },

  saveProgress(silent = false) {
    const task = this.createSaveTask(silent);
    if (task) idiomSaveQueue.enqueue(task);
  },

  async requestHint() {
    if (!this.data.puzzle || this.data.hinting || this.data.hintsUsed >= this.data.maxHints) return;
    this.setData({ hinting: true });
    try {
      await this.flushSave();
      const hint = await request<PuzzleHintResponse>("/idiom/hint", {
        method: "POST",
        data: {
          run_id: this.data.runId || undefined,
          puzzle_id: this.data.puzzle.puzzle_id,
          grid: this.data.grid,
          entry_id: this.data.activeEntryId,
        },
      });
      const index = this.data.puzzle.cells.findIndex(
        (cell) => cell.row === hint.row && cell.column === hint.column,
      );
      if (index >= 0) {
        const grid = [...this.data.grid];
        grid[index] = String(hint.value);
        this.setData({
          grid,
          selectedIndex: index,
          hintsUsed: hint.hints_used,
          invalidCells: this.data.invalidCells.filter((item: number) => item !== index),
        });
        this.refreshCells();
        this.queueSave();
      }
    } catch (error) {
      showRequestError(error, "获取提示失败");
    } finally {
      this.setData({ hinting: false });
    }
  },

  async submitPuzzle() {
    if (!this.data.puzzle || this.data.submitting || this.data.completed) return;
    this.setData({ submitting: true });
    try {
      await this.flushSave();
      const response = await request<PuzzleSubmitResponse>("/idiom/submit", {
        method: "POST",
        acceptedStatusCodes: [422],
        data: {
          run_id: this.data.runId || undefined,
          puzzle_id: this.data.puzzle.puzzle_id,
          grid: this.data.grid,
          elapsed_seconds: this.data.elapsedSeconds,
          mistakes: this.data.mistakes,
          hints_used: this.data.hintsUsed,
        },
      });
      if (!response.correct) {
        this.setData({
          invalidCells: response.invalid_cells || [],
          mistakes: this.data.mistakes + 1,
        });
        this.refreshCells();
        this.queueSave();
        wx.showToast({ title: "还有文字不正确", icon: "none" });
        return;
      }
      stopClock();
      clearCloudPuzzleShadow("idiom", this.data.puzzle.puzzle_id);
      const result = response.result || null;
      if (!isLoggedIn()) {
        clearGuestPuzzleState("idiom", this.data.puzzle.puzzle_id);
        if (this.data.puzzleMode === "level" && result) {
          saveGuestIdiomResult(this.data.puzzle.puzzle_id, result.stars, result.score);
        }
      }
      this.setData({ completed: true, result, invalidCells: [] });
      this.refreshCells();
      wx.vibrateShort({ type: "medium" });
    } catch (error) {
      showRequestError(error, "提交成语失败");
    } finally {
      this.setData({ submitting: false });
    }
  },

  goNext() {
    const nextLevelId = this.data.result?.next_level_id;
    if (this.data.puzzleMode === "level" && nextLevelId) {
      this.loadPuzzle(`/idiom/puzzle?mode=level&level_id=${encodeURIComponent(nextLevelId)}`);
      return;
    }
    this.backToCatalog();
  },

  async backToCatalog() {
    if (this.data.submitting || this.data.hinting) return;
    stopClock();
    try {
      await this.flushSave();
    } catch (error) {
      showRequestError(error, "成语进度未同步，已留在当前关卡");
      this.startClock();
      return;
    }
    this.setData({ view: "catalog", puzzle: null, completed: false, result: null });
    this.loadCatalog();
  },
});

export {};
