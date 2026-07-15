import type { GameState, GuessResponse } from "../../types/api";
import { decorateHistory } from "../../utils/format";
import { getSessionId, saveSessionId } from "../../utils/auth";
import { request, showRequestError } from "../../utils/request";

Page({
  data: {
    attempts: 0,
    correctCount: 0,
    guess: "",
    history: [] as any[],
    rawHistory: [] as any[],
    sortMode: "time" as "time" | "similarity",
    submitting: false,
    loading: true,
    resultText: "",
    resultSuccess: false,
  },

  onLoad() {
    this.loadGame();
  },

  onPullDownRefresh() {
    this.loadGame().finally(() => wx.stopPullDownRefresh());
  },

  async loadGame() {
    this.setData({ loading: true });
    const sessionId = getSessionId();
    try {
      const payload = await request<{ game: GameState }>(
        `/classic/start${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`,
        { method: "POST" },
      );
      saveSessionId(payload.game.session_id);
      this.applyGame(payload.game);
    } catch (error) {
      showRequestError(error, "初始化游戏失败");
    } finally {
      this.setData({ loading: false });
    }
  },

  applyGame(game: GameState) {
    const rawHistory = game.history || [];
    this.setData({
      attempts: game.attempts || 0,
      correctCount: game.correct_count || 0,
      rawHistory,
      history: decorateHistory(rawHistory, this.data.sortMode),
    });
  },

  onGuessInput(event: any) {
    this.setData({ guess: event.detail.value });
  },

  switchSort(event: any) {
    const sortMode = event.currentTarget.dataset.sort as "time" | "similarity";
    this.setData({
      sortMode,
      history: decorateHistory(this.data.rawHistory, sortMode),
    });
  },

  async submitGuess() {
    const word = this.data.guess.trim();
    if (!word || this.data.submitting) return;
    const sessionId = getSessionId();
    this.setData({ submitting: true });
    try {
      const result = await request<GuessResponse>(
        `/guess${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`,
        { method: "POST", data: { word } },
      );
      saveSessionId(result.session_id);
      if (result.is_correct) {
        this.setData({
          guess: "",
          attempts: 0,
          correctCount: result.correct_count,
          rawHistory: [],
          history: [],
          resultText: `恭喜猜中「${result.target_word}」，已开始新一轮`,
          resultSuccess: true,
        });
        wx.vibrateShort({ type: "light" });
      } else {
        const rawHistory = result.history || [];
        this.setData({
          guess: "",
          attempts: result.attempts,
          correctCount: result.correct_count,
          rawHistory,
          history: decorateHistory(rawHistory, this.data.sortMode),
          resultText: result.message && result.message !== "继续加油！" ? result.message : "",
          resultSuccess: false,
        });
      }
    } catch (error) {
      showRequestError(error, "提交失败");
    } finally {
      this.setData({ submitting: false });
    }
  },

  async revealAnswer() {
    const sessionId = getSessionId();
    try {
      const result = await request<any>(
        `/give-up${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`,
        { method: "POST", showLoading: true, loadingText: "换题中" },
      );
      saveSessionId(result.session_id);
      this.setData({
        guess: "",
        attempts: 0,
        correctCount: result.correct_count || this.data.correctCount,
        rawHistory: [],
        history: [],
        resultText: `上一轮答案是「${result.target_word}」`,
        resultSuccess: false,
      });
    } catch (error) {
      showRequestError(error, "查看答案失败");
    }
  },

  async resetGame() {
    const sessionId = getSessionId();
    const confirmed = await new Promise<boolean>((resolve) => {
      wx.showModal({
        title: "重新开始",
        content: "经典模式的累计猜中数量也会清零。",
        success: (result: any) => resolve(Boolean(result.confirm)),
        fail: () => resolve(false),
      });
    });
    if (!confirmed) return;
    try {
      const result = await request<{ game_id: string }>(
        `/reset-game${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`,
        { method: "POST", showLoading: true },
      );
      saveSessionId(result.game_id);
      this.setData({
        guess: "",
        attempts: 0,
        correctCount: 0,
        rawHistory: [],
        history: [],
        resultText: "游戏已重置",
        resultSuccess: false,
      });
    } catch (error) {
      showRequestError(error, "重置失败");
    }
  },
});

export {};
