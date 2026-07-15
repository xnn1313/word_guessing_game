import type { CampaignLevel, GameState, GuessResponse } from "../../types/api";
import { decorateHistory } from "../../utils/format";
import { requireLogin, saveSessionId } from "../../utils/auth";
import { request, showRequestError } from "../../utils/request";

Page({
  data: {
    levelId: "",
    level: null as CampaignLevel | null,
    attempts: 0,
    totalStars: 0,
    guess: "",
    history: [] as any[],
    submitting: false,
    completed: false,
    earnedStars: 0,
    nextLevel: null as CampaignLevel | null,
    resultText: "",
    loading: true,
  },

  onLoad(options: Record<string, string>) {
    if (!requireLogin()) {
      setTimeout(() => wx.navigateBack(), 300);
      return;
    }
    const levelId = decodeURIComponent(options.levelId || "");
    this.setData({ levelId, totalStars: wx.getStorageSync("word_game_campaign_stars") || 0 });
    this.startLevel(levelId);
  },

  async startLevel(levelId?: string) {
    const targetLevelId = levelId || this.data.levelId;
    if (!targetLevelId) return;
    this.setData({ loading: true });
    try {
      const payload = await request<{ game: GameState; level: CampaignLevel }>("/campaign/start", {
        method: "POST",
        data: { level_id: targetLevelId },
        authenticated: true,
      });
      saveSessionId(payload.game.session_id);
      this.setData({
        levelId: targetLevelId,
        level: payload.level,
        attempts: 0,
        guess: "",
        history: [],
        completed: false,
        earnedStars: 0,
        nextLevel: null,
        resultText: "",
      });
    } catch (error) {
      showRequestError(error, "进入关卡失败");
      setTimeout(() => wx.navigateBack(), 700);
    } finally {
      this.setData({ loading: false });
    }
  },

  onGuessInput(event: any) {
    this.setData({ guess: event.detail.value });
  },

  async submitGuess() {
    const word = this.data.guess.trim();
    if (!word || this.data.submitting || this.data.completed) return;
    this.setData({ submitting: true });
    try {
      const result = await request<GuessResponse>("/guess", {
        method: "POST",
        data: { word },
        authenticated: true,
      });
      saveSessionId(result.session_id);
      const history = decorateHistory(result.history || [], "time");
      if (result.is_correct && result.campaign_result) {
        const campaignResult = result.campaign_result;
        wx.setStorageSync("word_game_campaign_stars", campaignResult.total_stars);
        this.setData({
          guess: "",
          attempts: result.attempts,
          history,
          completed: true,
          earnedStars: campaignResult.earned_stars,
          totalStars: campaignResult.total_stars,
          nextLevel: campaignResult.next_level,
          resultText: `答案是「${result.target_word}」`,
        });
        wx.vibrateShort({ type: "medium" });
      } else {
        this.setData({
          guess: "",
          attempts: result.attempts,
          history,
          resultText: result.message && result.message !== "继续加油！" ? result.message : "",
        });
      }
    } catch (error) {
      showRequestError(error, "提交失败");
    } finally {
      this.setData({ submitting: false });
    }
  },

  async revealAnswer() {
    try {
      const result = await request<any>("/give-up", {
        method: "POST",
        authenticated: true,
        showLoading: true,
        loadingText: "重试本关",
      });
      saveSessionId(result.session_id);
      this.setData({
        attempts: 0,
        guess: "",
        history: [],
        resultText: `本关答案是「${result.target_word}」，已重新开始`,
      });
    } catch (error) {
      showRequestError(error, "查看答案失败");
    }
  },

  goNext() {
    if (!this.data.nextLevel) {
      wx.navigateBack();
      return;
    }
    const levelId = this.data.nextLevel.id;
    wx.redirectTo({ url: `/pages/campaign-game/index?levelId=${encodeURIComponent(levelId)}` });
  },

  retry() {
    this.startLevel();
  },
});

export {};
