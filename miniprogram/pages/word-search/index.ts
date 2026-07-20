import type {
  CloudPuzzleShadowToken,
} from "../../utils/puzzle-storage";
import type {
  PuzzleCompletionResult,
  PuzzleDifficulty,
  WordSearchBoardResponse,
  WordSearchPathCell,
  WordSearchSavedState,
  WordSearchSubmitResponse,
  WordSearchTheme,
  WordSearchThemeCatalog,
} from "../../types/api";
import { getToken, getUsername, isLoggedIn } from "../../utils/auth";
import {
  clearCloudPuzzleShadow,
  clearGuestPuzzleDefinition,
  clearGuestPuzzleState,
  confirmCloudPuzzleShadow,
  failCloudPuzzleShadowRequest,
  loadGuestPuzzleDefinition,
  loadGuestPuzzleState,
  markCloudPuzzleShadowInFlight,
  resolveCloudPuzzleState,
  saveGuestPuzzleDefinition,
  saveGuestPuzzleState,
  stageCloudPuzzleShadow,
} from "../../utils/puzzle-storage";
import { LatestTaskQueue } from "../../utils/latest-task-queue";
import { ApiError, request, showRequestError } from "../../utils/request";

let clockTimer: any = null;
let saveTimer: any = null;
let invalidTimer: any = null;
let boardRect: { left: number; top: number; width: number; height: number } | null = null;
let boardLayoutTop = 0;
let currentScrollTop = 0;
let dragStart: WordSearchPathCell | null = null;
let dragMoved = false;
let dragLockedPath: WordSearchPathCell[] | null = null;
let pendingDragTouch: any = null;
let dragSession = 0;
let suppressNextTap = false;

const DEFAULT_THEMES: Array<{ key: WordSearchTheme; title: string; description: string }> = [
  { key: "classic", title: "成语万花筒", description: "常用成语" },
  { key: "nature", title: "自然万象", description: "山水风云" },
  { key: "animals", title: "动物世界", description: "飞禽走兽" },
  { key: "character", title: "品格修养", description: "品德志向" },
  { key: "emotion", title: "心情百态", description: "情绪感受" },
];

interface WordSearchSaveTask {
  loggedIn: boolean;
  silent: boolean;
  boardId: string;
  runId: string;
  cloudShadow: CloudPuzzleShadowToken<WordSearchSavedState> | null;
  authToken: string;
  accountUsername: string;
  state: WordSearchSavedState;
}

const wordSearchSaveQueue = new LatestTaskQueue<WordSearchSaveTask>(
  async (task) => {
    if (!task.loggedIn) {
      saveGuestPuzzleState("word_search", task.boardId, task.state);
      return;
    }
    if (task.authToken !== getToken() || task.accountUsername !== String(getUsername() || "").trim()) {
      throw new Error("登录账号已变更，已停止旧账号的成语连线云存档");
    }
    if (!task.runId) throw new Error("成语连线云存档缺少运行标识");
    markCloudPuzzleShadowInFlight(task.cloudShadow);
    try {
      await request("/word-search/save", {
        method: "POST",
        authenticated: true,
        data: {
          run_id: task.runId,
          board_id: task.boardId,
          found_paths: task.state.found_paths,
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
    if (!task.silent) showRequestError(error, "成语连线进度保存失败");
  },
);

function sameCell(left: WordSearchPathCell, right: WordSearchPathCell): boolean {
  return left.row === right.row && left.column === right.column;
}

function cellKey(cell: WordSearchPathCell): string {
  return `${cell.row}:${cell.column}`;
}

function samePath(left: WordSearchPathCell[], right: WordSearchPathCell[]): boolean {
  if (left.length !== right.length) return false;
  const direct = left.every((cell, index) => sameCell(cell, right[index]));
  const reversed = left.every((cell, index) => sameCell(cell, right[right.length - 1 - index]));
  return direct || reversed;
}

function formatTime(seconds: number): string {
  const safe = Math.max(0, Number(seconds) || 0);
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

function exactPath(start: WordSearchPathCell, end: WordSearchPathCell): WordSearchPathCell[] {
  const rowDistance = end.row - start.row;
  const columnDistance = end.column - start.column;
  const rowSteps = Math.abs(rowDistance);
  const columnSteps = Math.abs(columnDistance);
  if (!(rowDistance === 0 || columnDistance === 0 || rowSteps === columnSteps)) return [];
  const steps = Math.max(rowSteps, columnSteps);
  if (steps !== 3) return [];
  const rowStep = Math.sign(rowDistance);
  const columnStep = Math.sign(columnDistance);
  return Array.from({ length: 4 }, (_, index) => ({
    row: start.row + rowStep * index,
    column: start.column + columnStep * index,
  }));
}

function dragPath(
  start: WordSearchPathCell,
  end: WordSearchPathCell,
  rows: number,
  columns: number,
): WordSearchPathCell[] {
  const rowDistance = end.row - start.row;
  const columnDistance = end.column - start.column;
  const absoluteRow = Math.abs(rowDistance);
  const absoluteColumn = Math.abs(columnDistance);
  if (absoluteRow === 0 && absoluteColumn === 0) return [start];

  let rowStep = Math.sign(rowDistance);
  let columnStep = Math.sign(columnDistance);
  if (absoluteRow * 2 < absoluteColumn) rowStep = 0;
  else if (absoluteColumn * 2 < absoluteRow) columnStep = 0;

  const rowCapacity = rowStep > 0 ? rows - 1 - start.row : rowStep < 0 ? start.row : 3;
  const columnCapacity = columnStep > 0
    ? columns - 1 - start.column
    : columnStep < 0
      ? start.column
      : 3;
  const capacity = Math.min(rowStep === 0 ? 3 : rowCapacity, columnStep === 0 ? 3 : columnCapacity, 3);
  const distance = Math.min(3, capacity, Math.max(absoluteRow, absoluteColumn));
  return Array.from({ length: distance + 1 }, (_, index) => ({
    row: start.row + rowStep * index,
    column: start.column + columnStep * index,
  }));
}

function stopClock(): void {
  if (clockTimer) clearInterval(clockTimer);
  clockTimer = null;
}

function stopTransientTimers(): void {
  stopClock();
  if (invalidTimer) clearTimeout(invalidTimer);
  invalidTimer = null;
}

Page({
  data: {
    loading: true,
    submitting: false,
    mode: "daily" as "daily" | "practice",
    difficulty: "easy" as PuzzleDifficulty,
    theme: "classic" as WordSearchTheme,
    themeOptions: DEFAULT_THEMES,
    board: null as WordSearchBoardResponse | null,
    boardId: "",
    runId: "",
    cloudSavedState: null as WordSearchSavedState | null,
    cells: [] as any[],
    foundEntryIds: [] as string[],
    foundPaths: [] as WordSearchPathCell[][],
    selectedPath: [] as WordSearchPathCell[],
    selectionInvalid: false,
    selectionText: "拖过四个字，或依次点击起点和终点",
    hintCursor: -1,
    elapsedSeconds: 0,
    elapsedText: "00:00",
    mistakes: 0,
    foundCount: 0,
    completed: false,
    result: null as PuzzleCompletionResult | null,
    modeOptions: [
      { value: "daily", label: "每日一局" },
      { value: "practice", label: "自由练习" },
    ],
    difficultyOptions: [
      { value: "easy", label: "简单" },
      { value: "medium", label: "中等" },
      { value: "hard", label: "困难" },
    ],
  },

  onLoad() {
    currentScrollTop = 0;
    boardLayoutTop = 0;
    boardRect = null;
    void this.initialize();
  },

  onShow() {
    if (this.data.board && !this.data.completed) this.startClock();
  },

  onHide() {
    stopClock();
    void this.flushSave().catch((error) => showRequestError(error, "连线进度保存失败，本地备份已保留"));
  },

  onUnload() {
    stopTransientTimers();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    boardRect = null;
    boardLayoutTop = 0;
    currentScrollTop = 0;
    boardLayoutTop = 0;
    void this.flushSave().catch((error) => showRequestError(error, "连线进度保存失败，本地备份已保留"));
  },

  async initialize() {
    try {
      const catalog = await request<WordSearchThemeCatalog>("/word-search/themes");
      if (catalog.themes?.length) this.setData({ themeOptions: catalog.themes });
    } catch (_) {
      // 默认主题足够启动游戏，主题接口失败不阻塞棋盘加载。
    }
    await this.loadBoard();
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

  guestSlot(): string {
    return `${this.data.mode}:${this.data.difficulty}:${this.data.theme}`;
  },

  async loadBoard(forceNew = false) {
    stopTransientTimers();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    boardRect = null;
    this.setData({
      loading: true,
      submitting: false,
      completed: false,
      result: null,
      selectedPath: [],
      selectionInvalid: false,
      selectionText: "拖过四个字，或依次点击起点和终点",
      hintCursor: -1,
    });
    try {
      const slot = this.guestSlot();
      if (!isLoggedIn() && forceNew) {
        clearGuestPuzzleDefinition("word_search", slot);
        if (this.data.boardId) clearGuestPuzzleState("word_search", this.data.boardId);
      }
      const canResumeDefinition = !isLoggedIn() && this.data.mode === "practice" && !forceNew;
      let board = canResumeDefinition
        ? loadGuestPuzzleDefinition<WordSearchBoardResponse>("word_search", slot)
        : null;
      if (!board) {
        board = await request<WordSearchBoardResponse>(
          `/word-search/board?mode=${this.data.mode}&difficulty=${this.data.difficulty}&theme=${this.data.theme}${forceNew ? "&fresh=1" : ""}`,
        );
        if (!isLoggedIn() && this.data.mode === "practice") {
          saveGuestPuzzleDefinition("word_search", slot, board);
        }
      }
      const loggedIn = isLoggedIn();
      const local = !loggedIn
        ? loadGuestPuzzleState<WordSearchSavedState>("word_search", board.board_id)
        : null;
      const saved = loggedIn
        ? resolveCloudPuzzleState("word_search", board.board_id, board.saved_state)
        : local;
      this.setData({
        board,
        boardId: board.board_id,
        runId: board.run_id || "",
        cloudSavedState: board.saved_state,
        foundEntryIds: [...(saved?.found_entry_ids || [])],
        foundPaths: [...(saved?.found_paths || [])],
        elapsedSeconds: Number(saved?.elapsed_seconds || 0),
        elapsedText: formatTime(Number(saved?.elapsed_seconds || 0)),
        mistakes: Number(saved?.mistakes || 0),
      });
      this.refreshBoard();
      wx.nextTick(() => this.measureBoard());
      this.startClock();
    } catch (error) {
      showRequestError(error, "成语连线加载失败");
    } finally {
      this.setData({ loading: false });
    }
  },

  refreshBoard() {
    const board = this.data.board;
    if (!board) return;
    const selectedKeys = new Set(this.data.selectedPath.map(cellKey));
    const foundKeys = new Set(this.data.foundPaths.flat().map(cellKey));
    const startKey = this.data.selectedPath.length ? cellKey(this.data.selectedPath[0]) : "";
    const endKey = this.data.selectedPath.length > 1
      ? cellKey(this.data.selectedPath[this.data.selectedPath.length - 1])
      : "";
    const cells = board.grid.flatMap((row, rowIndex) => row.map((character, columnIndex) => {
      const key = `${rowIndex}:${columnIndex}`;
      return {
        key,
        row: rowIndex,
        column: columnIndex,
        character,
        selected: selectedKeys.has(key),
        found: foundKeys.has(key),
        endpoint: key === startKey || key === endKey,
      };
    }));
    const foundCount = this.data.foundEntryIds.length;
    this.setData({
      cells,
      foundCount,
    });
  },

  measureBoard(onReady?: () => void) {
    const board = this.data.board;
    if (!board) return;
    const query = wx.createSelectorQuery().in(this);
    query.select(".word-search-board").boundingClientRect();
    query.select(".search-cell").boundingClientRect();
    query.exec((results: any[]) => {
      const container = results?.[0];
      const firstCell = results?.[1];
      if (firstCell?.width && firstCell?.height) {
        boardLayoutTop = firstCell.top + currentScrollTop;
        boardRect = {
          left: firstCell.left,
          top: firstCell.top,
          width: firstCell.width * board.columns,
          height: firstCell.height * board.rows,
        };
      } else if (container?.width && container?.height) {
        boardLayoutTop = container.top + currentScrollTop;
        boardRect = container;
      }
      onReady?.();
    });
  },

  cellFromTouch(touch: any): WordSearchPathCell | null {
    const board = this.data.board;
    if (!board || !boardRect || !touch) return null;
    const x = Number(touch.clientX ?? touch.pageX) - boardRect.left;
    const y = Number(touch.clientY ?? touch.pageY) - boardRect.top;
    const column = Math.min(board.columns - 1, Math.max(0, Math.floor(x / boardRect.width * board.columns)));
    const row = Math.min(board.rows - 1, Math.max(0, Math.floor(y / boardRect.height * board.rows)));
    return { row, column };
  },

  onBoardTouchStart(event: any) {
    if (!this.data.board || this.data.loading || this.data.submitting || this.data.completed) return;
    const touch = event.touches?.[0];
    const dataset = event.target?.dataset || {};
    const row = Number(dataset.row);
    const column = Number(dataset.column);
    dragSession += 1;
    const session = dragSession;
    if (boardRect && boardLayoutTop) {
      boardRect = { ...boardRect, top: boardLayoutTop - currentScrollTop };
    }
    dragStart = Number.isInteger(row) && Number.isInteger(column)
      ? { row, column }
      : null;
    dragMoved = false;
    dragLockedPath = null;
    pendingDragTouch = null;
    this.measureBoard(() => {
      if (session !== dragSession) return;
      if (!dragStart) dragStart = this.cellFromTouch(touch);
      if (pendingDragTouch) this.updateDragFromTouch(pendingDragTouch);
    });
  },

  onPageScroll(event: any) {
    currentScrollTop = Math.max(0, Number(event.scrollTop) || 0);
    if (boardRect && boardLayoutTop) {
      boardRect = { ...boardRect, top: boardLayoutTop - currentScrollTop };
    }
  },

  onBoardTouchMove(event: any) {
    if (!this.data.board || this.data.submitting || this.data.completed) return;
    const touch = event.touches?.[0];
    pendingDragTouch = touch;
    this.updateDragFromTouch(touch);
  },

  updateDragFromTouch(touch: any) {
    if (!dragStart || !this.data.board || !boardRect || !touch || dragLockedPath) return;
    const current = this.cellFromTouch(touch);
    if (!current) return;
    const path = dragPath(dragStart, current, this.data.board.rows, this.data.board.columns);
    if (path.length <= 1) return;
    dragMoved = true;
    if (path.length === 4) dragLockedPath = path.map((cell) => ({ ...cell }));
    this.setData({
      selectedPath: path,
      selectionInvalid: false,
      selectionText: path.length === 4 ? "已选四个字，松手后自动检查" : `已连接 ${path.length} 个字`,
    });
    this.refreshBoard();
  },

  onBoardTouchEnd() {
    if (pendingDragTouch && !dragLockedPath) this.updateDragFromTouch(pendingDragTouch);
    const moved = dragMoved;
    dragStart = null;
    dragMoved = false;
    dragLockedPath = null;
    pendingDragTouch = null;
    dragSession += 1;
    if (!moved) return;
    suppressNextTap = true;
    setTimeout(() => { suppressNextTap = false; }, 350);
    if (this.data.selectedPath.length === 4) {
      this.setData({ selectionText: "正在检查这条连线…" });
      void this.submitSelectedPath();
      return;
    }
    wx.showToast({ title: "请连续选择四个字", icon: "none" });
    this.clearSelection();
  },

  onBoardTouchCancel() {
    const completedPath = this.data.selectedPath.length === 4;
    dragStart = null;
    dragMoved = false;
    dragLockedPath = null;
    pendingDragTouch = null;
    dragSession += 1;
    suppressNextTap = true;
    setTimeout(() => { suppressNextTap = false; }, 350);
    if (completedPath) {
      this.setData({ selectionText: "正在检查这条连线…" });
      void this.submitSelectedPath();
    } else {
      this.clearSelection();
    }
  },

  tapCell(event: any) {
    if (suppressNextTap) {
      suppressNextTap = false;
      return;
    }
    if (!this.data.board || this.data.loading || this.data.submitting || this.data.completed) return;
    const cell = {
      row: Number(event.currentTarget.dataset.row),
      column: Number(event.currentTarget.dataset.column),
    };
    if (this.data.selectedPath.length !== 1) {
      this.setData({
        selectedPath: [cell],
        selectionInvalid: false,
        selectionText: "已选起点，再点击末字",
      });
      this.refreshBoard();
      return;
    }
    const start = this.data.selectedPath[0];
    if (sameCell(start, cell)) {
      this.clearSelection();
      return;
    }
    const path = exactPath(start, cell);
    if (path.length !== 4) {
      wx.showToast({ title: "末字需与起点相隔三格并位于直线", icon: "none" });
      return;
    }
    this.setData({ selectedPath: path, selectionText: "正在检查这条连线…" }, () => {
      this.refreshBoard();
      void this.submitSelectedPath();
    });
  },

  showHint() {
    if (!this.data.board || this.data.loading || this.data.completed) return;
    const found = new Set(this.data.foundEntryIds);
    const available = this.data.board.entries
      .map((entry, index) => ({ entry, index }))
      .filter((item) => !found.has(item.entry.id));
    if (!available.length) {
      wx.showToast({ title: "所有成语都已找到", icon: "none" });
      return;
    }
    const next = available.find((item) => item.index > this.data.hintCursor) || available[0];
    this.setData({ hintCursor: next.index });
    wx.showModal({
      title: "成语提示",
      content: next.entry.clue,
      showCancel: false,
      confirmText: "知道了",
    });
  },

  clearSelection() {
    this.setData({
      selectedPath: [],
      selectionInvalid: false,
      selectionText: "拖过四个字，或依次点击起点和终点",
    });
    this.refreshBoard();
  },

  async submitSelectedPath() {
    if (!this.data.board || this.data.submitting || this.data.selectedPath.length !== 4) return;
    const path = this.data.selectedPath.map((cell) => ({ ...cell }));
    if (this.data.foundPaths.some((foundPath) => samePath(foundPath, path))) {
      wx.showToast({ title: "这个成语已经找到了", icon: "none" });
      this.clearSelection();
      return;
    }
    this.setData({ submitting: true });
    try {
      await this.flushSave();
      const response = await request<WordSearchSubmitResponse>("/word-search/submit", {
        method: "POST",
        acceptedStatusCodes: [422],
        data: {
          run_id: this.data.runId || undefined,
          board_id: this.data.boardId,
          found_paths: this.data.foundPaths,
          path,
          elapsed_seconds: this.data.elapsedSeconds,
          mistakes: this.data.mistakes,
        },
      });
      if (!response.correct) {
        const mistakes = Number(response.mistakes ?? this.data.mistakes + 1);
        const state = this.currentState({ mistakes });
        clearCloudPuzzleShadow("word_search", this.data.boardId);
        if (!isLoggedIn()) saveGuestPuzzleState("word_search", this.data.boardId, state);
        this.setData({
          mistakes,
          cloudSavedState: state,
          selectionInvalid: true,
          selectionText: "这条连线不是本题成语，再试一次",
        });
        this.refreshBoard();
        if (invalidTimer) clearTimeout(invalidTimer);
        invalidTimer = setTimeout(() => this.clearSelection(), 520);
        return;
      }

      const foundPaths = [...this.data.foundPaths, path];
      const foundEntryIds = response.status === "completed"
        ? this.data.board.entries.map((entry) => entry.id)
        : [...(response.found_entry_ids || this.data.foundEntryIds)];
      const state: WordSearchSavedState = {
        found_entry_ids: foundEntryIds,
        found_paths: foundPaths,
        elapsed_seconds: this.data.elapsedSeconds,
        mistakes: this.data.mistakes,
      };
      clearCloudPuzzleShadow("word_search", this.data.boardId);
      if (!isLoggedIn()) saveGuestPuzzleState("word_search", this.data.boardId, state);
      this.setData({
        foundPaths,
        foundEntryIds,
        selectedPath: [],
        selectionInvalid: false,
        selectionText: response.status === "completed" ? "全部成语已找到" : "找到一个！继续寻找",
        cloudSavedState: state,
      });
      this.refreshBoard();
      wx.vibrateShort({ type: response.status === "completed" ? "medium" : "light" });

      if (response.status === "completed") {
        stopClock();
        clearCloudPuzzleShadow("word_search", this.data.boardId);
        if (!isLoggedIn()) {
          clearGuestPuzzleState("word_search", this.data.boardId);
          if (this.data.mode === "practice") {
            clearGuestPuzzleDefinition("word_search", this.guestSlot());
          }
        }
        this.setData({ completed: true, result: response.result || null });
      } else {
        setTimeout(() => {
          if (!this.data.completed && !this.data.selectedPath.length) {
            this.setData({ selectionText: "拖过四个字，或依次点击起点和终点" });
          }
        }, 900);
      }
    } catch (error) {
      showRequestError(error, "连线校验失败");
    } finally {
      this.setData({ submitting: false });
    }
  },

  currentState(overrides: Partial<WordSearchSavedState> = {}): WordSearchSavedState {
    return {
      found_entry_ids: [...this.data.foundEntryIds],
      found_paths: this.data.foundPaths.map((path) => path.map((cell) => ({ ...cell }))),
      elapsed_seconds: this.data.elapsedSeconds,
      mistakes: this.data.mistakes,
      ...overrides,
    };
  },

  createSaveTask(silent = false): WordSearchSaveTask | null {
    if (!this.data.board || this.data.completed) return null;
    const state = this.currentState();
    const authToken = getToken();
    const accountUsername = String(getUsername() || "").trim();
    const loggedIn = Boolean(authToken);
    const cloudShadow = loggedIn
      ? stageCloudPuzzleShadow("word_search", this.data.boardId, state, this.data.cloudSavedState)
      : null;
    return {
      loggedIn,
      silent,
      boardId: this.data.boardId,
      runId: this.data.runId,
      cloudShadow,
      authToken,
      accountUsername,
      state,
    };
  },

  queueSave() {
    const task = this.createSaveTask(true);
    if (!task) return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => wordSearchSaveQueue.enqueue(task), 500);
  },

  async flushSave() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    const task = this.createSaveTask(true);
    if (task) await wordSearchSaveQueue.flush(task);
  },

  async applySettings(patch: Record<string, any>, forceNew = false) {
    if (this.data.loading || this.data.submitting) return;
    try {
      await this.flushSave();
    } catch (error) {
      showRequestError(error, "连线进度未同步，已取消切换");
      return;
    }
    this.setData(patch, () => this.loadBoard(forceNew));
  },

  switchMode(event: any) {
    const mode = event.currentTarget.dataset.value as "daily" | "practice";
    if (mode !== this.data.mode) void this.applySettings({ mode });
  },

  switchDifficulty(event: any) {
    const difficulty = event.currentTarget.dataset.value as PuzzleDifficulty;
    if (difficulty !== this.data.difficulty) void this.applySettings({ difficulty });
  },

  switchTheme(event: any) {
    const theme = event.currentTarget.dataset.value as WordSearchTheme;
    if (theme !== this.data.theme) void this.applySettings({ theme });
  },

  newBoard() {
    if (this.data.loading || this.data.submitting) return;
    if (this.data.mode === "daily") {
      void this.applySettings({ mode: "practice" }, true);
    } else {
      void this.applySettings({}, true);
    }
  },

  goHub() {
    wx.reLaunch({ url: "/pages/hub/index" });
  },
});

export {};
