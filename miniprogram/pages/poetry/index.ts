import type {
  PoetryAnswerResponse,
  PoetryQuestion,
  PoetryQuizResponse,
  PoetrySavedState,
  PoetryStudyNote,
  PuzzleCompletionResult,
  PuzzleDifficulty,
} from "../../types/api";
import { getUsername, isLoggedIn } from "../../utils/auth";
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

function stopTimers(): void {
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
    mode: "daily" as "daily" | "practice",
    difficulty: "easy" as PuzzleDifficulty,
    quiz: null as PoetryQuizResponse | null,
    puzzleId: "",
    runId: "",
    cloudSavedState: null as PoetrySavedState | null,
    question: null as PoetryQuestion | null,
    questionNumber: 1,
    progressPercent: 0,
    correctCount: 0,
    mistakes: 0,
    elapsedSeconds: 0,
    elapsedText: "00:00",
    selectedAnswer: "",
    correctAnswer: "",
    feedbackTone: "" as "" | "correct" | "wrong",
    feedbackText: "请选择你认为正确的答案",
    answerRevealed: false,
    study: null as PoetryStudyNote | null,
    pendingNextQuestion: null as PoetryQuestion | null,
    pendingResult: null as PuzzleCompletionResult | null,
    continueLabel: "下一题",
    completed: false,
    result: null as PuzzleCompletionResult | null,
    modeOptions: [
      { value: "daily", label: "每日题签" },
      { value: "practice", label: "自由练习" },
    ],
    difficultyOptions: [
      { value: "easy", label: "初识" },
      { value: "medium", label: "进阶" },
      { value: "hard", label: "雅集" },
    ],
  },

  onLoad() {
    void this.loadQuiz();
  },

  onShow() {
    if (this.data.quiz && !this.data.completed && !this.data.answerRevealed) this.startClock();
  },

  onHide() {
    if (clockTimer) clearInterval(clockTimer);
    clockTimer = null;
    void this.saveProgress(true);
  },

  onUnload() {
    stopTimers();
    void this.saveProgress(true);
  },

  startClock() {
    if (clockTimer) clearInterval(clockTimer);
    clockTimer = setInterval(() => {
      if (this.data.loading || this.data.completed) return;
      const elapsedSeconds = this.data.elapsedSeconds + 1;
      this.setData({ elapsedSeconds, elapsedText: formatTime(elapsedSeconds) });
    }, 1000);
  },

  async loadQuiz(fresh = false) {
    stopTimers();
    this.setData({
      loading: true,
      submitting: false,
      completed: false,
      result: null,
      selectedAnswer: "",
      correctAnswer: "",
      feedbackTone: "",
      feedbackText: "请选择你认为正确的答案",
      answerRevealed: false,
      study: null,
      pendingNextQuestion: null,
      pendingResult: null,
      continueLabel: "下一题",
    });
    try {
      const guestSlot = `${this.data.mode}:${this.data.difficulty}`;
      if (!isLoggedIn() && fresh) {
        const previous = loadGuestPuzzleDefinition<PoetryQuizResponse>("poetry", guestSlot);
        if (previous?.puzzle_id) clearGuestPuzzleState("poetry", previous.puzzle_id);
        clearGuestPuzzleDefinition("poetry", guestSlot);
      }
      let quiz = !isLoggedIn() && this.data.mode === "practice" && !fresh
        ? loadGuestPuzzleDefinition<PoetryQuizResponse>("poetry", guestSlot)
        : null;
      if (!quiz) {
        quiz = await request<PoetryQuizResponse>(
          `/poetry/quiz?mode=${this.data.mode}&difficulty=${this.data.difficulty}${fresh ? "&fresh=1" : ""}`,
        );
        if (!isLoggedIn() && this.data.mode === "practice") {
          saveGuestPuzzleDefinition("poetry", guestSlot, quiz);
        }
      }
      const local = !isLoggedIn()
        ? loadGuestPuzzleState<PoetrySavedState & { question?: PoetryQuestion }>("poetry", quiz.puzzle_id)
        : null;
      const saved = isLoggedIn()
        ? resolveCloudPuzzleState("poetry", quiz.puzzle_id, quiz.saved_state)
        : local;
      const question = local?.question && local.question.index === Number(saved?.question_index || 0)
        ? local.question
        : quiz.question;
      const elapsedSeconds = Number(saved?.elapsed_seconds || 0);
      this.setData({
        quiz,
        puzzleId: quiz.puzzle_id,
        runId: quiz.run_id || "",
        cloudSavedState: quiz.saved_state,
        question,
        questionNumber: question.index + 1,
        progressPercent: Math.round((question.index / question.total) * 100),
        correctCount: Number(saved?.correct_count || 0),
        mistakes: Number(saved?.mistakes || 0),
        elapsedSeconds,
        elapsedText: formatTime(elapsedSeconds),
      });
      this.persistGuestState();
      this.startClock();
    } catch (error) {
      showRequestError(error, "诗词题组加载失败");
    } finally {
      this.setData({ loading: false });
    }
  },

  persistGuestState() {
    if (isLoggedIn() || !this.data.puzzleId || !this.data.question) return;
    const savedQuestion = this.data.answerRevealed && this.data.pendingNextQuestion
      ? this.data.pendingNextQuestion
      : this.data.question;
    saveGuestPuzzleState("poetry", this.data.puzzleId, {
      question_index: savedQuestion.index,
      correct_count: this.data.correctCount,
      elapsed_seconds: this.data.elapsedSeconds,
      hints_used: 0,
      mistakes: this.data.mistakes,
      question: savedQuestion,
    });
  },

  async saveProgress(silent = false) {
    if (!this.data.puzzleId || this.data.completed || this.data.answerRevealed) return;
    this.persistGuestState();
    if (!isLoggedIn() || !this.data.runId || !this.data.question) return;
    const state: PoetrySavedState = {
      question_index: this.data.question.index,
      correct_count: this.data.correctCount,
      elapsed_seconds: this.data.elapsedSeconds,
      hints_used: 0,
      mistakes: this.data.mistakes,
    };
    const shadow = stageCloudPuzzleShadow("poetry", this.data.puzzleId, state, this.data.cloudSavedState);
    try {
      await request("/poetry/save", {
        method: "POST",
        authenticated: true,
        data: {
          run_id: this.data.runId,
          puzzle_id: this.data.puzzleId,
          question_index: state.question_index,
          correct_count: state.correct_count,
          elapsed_seconds: state.elapsed_seconds,
          mistakes: state.mistakes,
        },
      });
      this.setData({ cloudSavedState: state });
      clearCloudPuzzleShadow("poetry", this.data.puzzleId);
    } catch (error) {
      if (!silent) showRequestError(error, "诗词进度保存失败");
      // 保留 shadow，下次加载时恢复。
      void shadow;
    }
  },

  async chooseAnswer(event: any) {
    const question = this.data.question;
    const answer = String(event.currentTarget.dataset.answer || "");
    if (!question || this.data.submitting || this.data.completed || this.data.answerRevealed || !answer) return;
    this.setData({ submitting: true, selectedAnswer: answer });
    try {
      const response = await request<PoetryAnswerResponse>("/poetry/submit", {
        method: "POST",
        data: {
          run_id: this.data.runId || undefined,
          puzzle_id: this.data.puzzleId,
          difficulty: this.data.difficulty,
          question_id: question.id,
          question_index: question.index,
          answer,
          correct_count: this.data.correctCount,
          mistakes: this.data.mistakes,
          elapsed_seconds: this.data.elapsedSeconds,
        },
      });
      const correctCount = Number(response.correct_count ?? this.data.correctCount);
      const mistakes = Number(response.mistakes ?? this.data.mistakes);
      this.setData({
        correctCount,
        mistakes,
        correctAnswer: response.correct_answer || "",
        feedbackTone: response.correct ? "correct" : "wrong",
        feedbackText: response.correct ? "答对了，顺便读懂这首诗" : `正确答案：${response.correct_answer || ""}`,
        answerRevealed: true,
        study: response.study || {
          source: response.explanation || "作品出处",
          excerpt: `${question.context} · ${response.correct_answer || ""}`,
          meaning: "把上下句放在一起读，先看诗中写了什么画面，再体会作者的语气和情感。",
          key_terms: "结合题目与完整诗句理解",
        },
        pendingNextQuestion: response.next_question || null,
        pendingResult: response.result || null,
        continueLabel: response.status === "completed" ? "查看本局成绩" : "读懂了，下一题",
        submitting: false,
      });
      stopTimers();
      clearCloudPuzzleShadow("poetry", this.data.puzzleId);
      const confirmedQuestionIndex = response.next_question?.index ?? question.total;
      this.setData({
        cloudSavedState: isLoggedIn() ? {
          question_index: confirmedQuestionIndex,
          correct_count: correctCount,
          elapsed_seconds: this.data.elapsedSeconds,
          hints_used: 0,
          mistakes,
        } : null,
      });
      if (response.status === "completed" && response.result) {
        this.finishQuiz(response.result, true);
        return;
      }
      this.persistGuestState();
    } catch (error) {
      this.setData({ submitting: false, selectedAnswer: "" });
      showRequestError(error, "答案提交失败");
    }
  },

  continueQuiz() {
    if (!this.data.answerRevealed) return;
    if (this.data.completed) {
      this.setData({ answerRevealed: false });
      return;
    }
    const next = this.data.pendingNextQuestion;
    if (!next) return;
    this.setData({
      question: next,
      questionNumber: next.index + 1,
      progressPercent: Math.round((next.index / next.total) * 100),
      selectedAnswer: "",
      correctAnswer: "",
      feedbackTone: "",
      feedbackText: "请选择你认为正确的答案",
      answerRevealed: false,
      study: null,
      pendingNextQuestion: null,
      pendingResult: null,
      continueLabel: "下一题",
      submitting: false,
    });
    this.persistGuestState();
    this.startClock();
  },

  finishQuiz(result: PuzzleCompletionResult, keepStudy = false) {
    if (clockTimer) clearInterval(clockTimer);
    clockTimer = null;
    clearGuestPuzzleState("poetry", this.data.puzzleId);
    clearGuestPuzzleDefinition("poetry", `${this.data.mode}:${this.data.difficulty}`);
    this.setData({
      completed: true,
      result,
      progressPercent: 100,
      submitting: false,
      answerRevealed: keepStudy,
    });
  },

  switchMode(event: any) {
    const mode = event.currentTarget.dataset.value as "daily" | "practice";
    if (!mode || mode === this.data.mode || this.data.submitting) return;
    void this.saveProgress(true).finally(() => {
      this.setData({ mode });
      void this.loadQuiz();
    });
  },

  switchDifficulty(event: any) {
    const difficulty = event.currentTarget.dataset.value as PuzzleDifficulty;
    if (!difficulty || difficulty === this.data.difficulty || this.data.submitting) return;
    void this.saveProgress(true).finally(() => {
      this.setData({ difficulty });
      void this.loadQuiz();
    });
  },

  newQuiz() {
    if (this.data.mode === "daily") {
      this.setData({ mode: "practice" });
    }
    void this.loadQuiz(true);
  },

  goHub() {
    wx.reLaunch({ url: "/pages/hub/index" });
  },
});

export {};
