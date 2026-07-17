import type {
  PuzzleCompletionResult,
  PuzzleDifficulty,
  PuzzleHintResponse,
  PuzzleSubmitResponse,
  SudokuPuzzleResponse,
  SudokuSavedState,
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

function stopClock(): void {
  if (clockTimer) clearInterval(clockTimer);
  clockTimer = null;
}

function formatTime(seconds: number): string {
  const safe = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safe / 60);
  return `${String(minutes).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

Page({
  data: {
    loading: true,
    mode: "daily" as "daily" | "practice",
    difficulty: "medium" as PuzzleDifficulty,
    puzzleId: "",
    puzzleDate: "",
    givens: "",
    runId: "",
    grid: [] as string[],
    notes: {} as Record<string, number[]>,
    cells: [] as any[],
    selectedIndex: -1,
    noteMode: false,
    elapsedSeconds: 0,
    elapsedText: "00:00",
    hintsUsed: 0,
    maxHints: 3,
    mistakes: 0,
    invalidCells: [] as number[],
    submitting: false,
    hinting: false,
    completed: false,
    result: null as PuzzleCompletionResult | null,
    digits: [1, 2, 3, 4, 5, 6, 7, 8, 9],
    modeOptions: [
      { value: "daily", label: "每日挑战" },
      { value: "practice", label: "自由练习" },
    ],
    difficultyOptions: [
      { value: "easy", label: "简单" },
      { value: "medium", label: "中等" },
      { value: "hard", label: "困难" },
    ],
  },

  onLoad() {
    this.loadPuzzle();
  },

  onShow() {
    if (this.data.puzzleId && !this.data.completed) this.startClock();
  },

  onHide() {
    stopClock();
    this.flushSave();
  },

  onUnload() {
    stopClock();
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

  async loadPuzzle(forceNew = false) {
    stopClock();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    this.setData({ loading: true, completed: false, result: null, invalidCells: [] });
    try {
      const guestSlot = `${this.data.mode}:${this.data.difficulty}`;
      const canResumeLocally = !isLoggedIn() && this.data.mode === "practice" && !forceNew;
      let payload = canResumeLocally
        ? loadGuestPuzzleDefinition<SudokuPuzzleResponse>("sudoku", guestSlot)
        : null;
      if (!payload) {
        payload = await request<SudokuPuzzleResponse>(
          `/sudoku/puzzle?mode=${this.data.mode}&difficulty=${this.data.difficulty}`,
        );
        if (!isLoggedIn() && this.data.mode === "practice") {
          saveGuestPuzzleDefinition("sudoku", guestSlot, payload);
        }
      }
      const local = !isLoggedIn()
        ? loadGuestPuzzleState<SudokuSavedState>("sudoku", payload.puzzle_id)
        : null;
      const saved = payload.saved_state || local;
      const validSavedGrid =
        saved?.grid && saved.grid.length === 81 ? saved.grid : payload.givens;
      const grid = validSavedGrid.split("");
      this.setData({
        puzzleId: payload.puzzle_id,
        puzzleDate: payload.puzzle_date || "",
        givens: payload.givens,
        runId: payload.run_id || "",
        grid,
        notes: saved?.notes || {},
        selectedIndex: -1,
        noteMode: false,
        elapsedSeconds: Number(saved?.elapsed_seconds || 0),
        elapsedText: formatTime(Number(saved?.elapsed_seconds || 0)),
        hintsUsed: Number(saved?.hints_used || 0),
        mistakes: Number(saved?.mistakes || 0),
        maxHints: Number(payload.limits?.max_hints || 3),
      });
      this.refreshCells();
      this.startClock();
    } catch (error) {
      showRequestError(error, "数独题目加载失败");
    } finally {
      this.setData({ loading: false });
    }
  },

  refreshCells() {
    const invalid = new Set(this.data.invalidCells);
    const cells = this.data.grid.map((value: string, index: number) => {
      const row = Math.floor(index / 9);
      const column = index % 9;
      return {
        index,
        value: value === "0" ? "" : value,
        given: this.data.givens[index] !== "0",
        selected: index === this.data.selectedIndex,
        invalid: invalid.has(index),
        noteText: (this.data.notes[String(index)] || []).join(""),
        boxRight: column === 2 || column === 5,
        boxBottom: row === 2 || row === 5,
        sameValue:
          Boolean(value && value !== "0") &&
          this.data.selectedIndex >= 0 &&
          this.data.grid[this.data.selectedIndex] === value,
      };
    });
    this.setData({ cells });
  },

  selectCell(event: any) {
    const index = Number(event.currentTarget.dataset.index);
    if (!Number.isInteger(index) || this.data.givens[index] !== "0") return;
    this.setData({ selectedIndex: index });
    this.refreshCells();
  },

  inputDigit(event: any) {
    const index = this.data.selectedIndex;
    const value = Number(event.currentTarget.dataset.value);
    if (index < 0 || this.data.givens[index] !== "0" || this.data.completed) return;
    const grid = [...this.data.grid];
    const notes = { ...this.data.notes };
    if (this.data.noteMode && value > 0 && grid[index] === "0") {
      const current = [...(notes[String(index)] || [])];
      const position = current.indexOf(value);
      if (position >= 0) current.splice(position, 1);
      else current.push(value);
      current.sort((a, b) => a - b);
      notes[String(index)] = current;
    } else {
      grid[index] = value > 0 ? String(value) : "0";
      delete notes[String(index)];
    }
    this.setData({
      grid,
      notes,
      invalidCells: this.data.invalidCells.filter((item: number) => item !== index),
    });
    this.refreshCells();
    this.queueSave();
  },

  toggleNoteMode() {
    this.setData({ noteMode: !this.data.noteMode });
  },

  switchMode(event: any) {
    const mode = event.currentTarget.dataset.value as "daily" | "practice";
    if (mode === this.data.mode) return;
    this.flushSave();
    this.setData({ mode }, () => this.loadPuzzle());
  },

  switchDifficulty(event: any) {
    const difficulty = event.currentTarget.dataset.value as PuzzleDifficulty;
    if (difficulty === this.data.difficulty) return;
    this.flushSave();
    this.setData({ difficulty }, () => this.loadPuzzle());
  },

  queueSave() {
    if (!this.data.puzzleId || this.data.completed) return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => this.saveProgress(true), 500);
  },

  flushSave() {
    if (!this.data.puzzleId || this.data.completed) return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = null;
    this.saveProgress(true);
  },

  async saveProgress(silent = false) {
    const state: SudokuSavedState = {
      grid: this.data.grid.join(""),
      notes: this.data.notes,
      elapsed_seconds: this.data.elapsedSeconds,
      hints_used: this.data.hintsUsed,
      mistakes: this.data.mistakes,
    };
    if (!isLoggedIn()) {
      saveGuestPuzzleState("sudoku", this.data.puzzleId, state);
      return;
    }
    if (!this.data.runId) return;
    try {
      await request("/sudoku/save", {
        method: "POST",
        authenticated: true,
        data: {
          run_id: this.data.runId,
          puzzle_id: this.data.puzzleId,
          grid: state.grid,
          notes: state.notes,
          elapsed_seconds: state.elapsed_seconds,
          mistakes: state.mistakes,
        },
      });
    } catch (error) {
      if (!silent) showRequestError(error, "数独进度保存失败");
    }
  },

  async requestHint() {
    if (this.data.hinting || this.data.hintsUsed >= this.data.maxHints) return;
    this.setData({ hinting: true });
    try {
      const hint = await request<PuzzleHintResponse>("/sudoku/hint", {
        method: "POST",
        data: {
          run_id: this.data.runId || undefined,
          puzzle_id: this.data.puzzleId,
          grid: this.data.grid.join(""),
        },
      });
      const index = Number(hint.index);
      const grid = [...this.data.grid];
      const notes = { ...this.data.notes };
      grid[index] = String(hint.value);
      delete notes[String(index)];
      this.setData({
        grid,
        notes,
        selectedIndex: index,
        hintsUsed: hint.hints_used,
        invalidCells: this.data.invalidCells.filter((item: number) => item !== index),
      });
      this.refreshCells();
      this.queueSave();
    } catch (error) {
      showRequestError(error, "获取提示失败");
    } finally {
      this.setData({ hinting: false });
    }
  },

  async submitPuzzle() {
    if (this.data.submitting || this.data.completed) return;
    this.setData({ submitting: true });
    try {
      const response = await request<PuzzleSubmitResponse>("/sudoku/submit", {
        method: "POST",
        acceptedStatusCodes: [422],
        data: {
          run_id: this.data.runId || undefined,
          puzzle_id: this.data.puzzleId,
          grid: this.data.grid.join(""),
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
        wx.showToast({ title: "还有格子不正确", icon: "none" });
        return;
      }
      stopClock();
      if (!isLoggedIn()) {
        clearGuestPuzzleState("sudoku", this.data.puzzleId);
        if (this.data.mode === "practice") {
          clearGuestPuzzleDefinition("sudoku", `${this.data.mode}:${this.data.difficulty}`);
        }
      }
      this.setData({ completed: true, result: response.result || null, invalidCells: [] });
      this.refreshCells();
      wx.vibrateShort({ type: "medium" });
    } catch (error) {
      showRequestError(error, "提交数独失败");
    } finally {
      this.setData({ submitting: false });
    }
  },

  clearInputs() {
    if (this.data.completed) return;
    const grid = this.data.givens.split("");
    this.setData({ grid, notes: {}, invalidCells: [], selectedIndex: -1 });
    this.refreshCells();
    this.queueSave();
  },

  playAgain() {
    if (this.data.mode === "daily") {
      this.setData({ mode: "practice" }, () => this.loadPuzzle(true));
    } else {
      this.loadPuzzle(true);
    }
  },
});

export {};
