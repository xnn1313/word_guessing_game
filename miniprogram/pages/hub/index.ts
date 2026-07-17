import type { GameOverviewItem, GamesOverview } from "../../types/api";
import { getUsername, isLoggedIn } from "../../utils/auth";
import { request } from "../../utils/request";

const fallbackGame = (key: GameOverviewItem["key"], title: string): GameOverviewItem => ({
  key,
  title,
  availability: "available",
  progress_text: "开始挑战",
  progress_percent: 0,
  best_score: null,
  daily_completed: false,
  last_played_at: null,
});

Page({
  data: {
    loggedIn: false,
    username: "",
    avatarText: "游",
    loading: false,
    trainingLabel: "今日脑力训练",
    trainingValue: "0 / 3 完成",
    trainingNote: "挑一个游戏，为今天的大脑热热身",
    availableGames: 4,
    completedToday: 0,
    totalStars: 0,
    wordGame: fallbackGame("word", "猜词实验室"),
    sudokuGame: fallbackGame("sudoku", "每日数独"),
    idiomGame: fallbackGame("idiom", "成语填字"),
    memoryGame: fallbackGame("memory", "记忆翻牌"),
  },

  onShow() {
    const loggedIn = isLoggedIn();
    const username = getUsername();
    this.setData({ loggedIn, username, avatarText: username.slice(0, 1) || "游" });
    this.loadOverview();
  },

  async loadOverview() {
    if (this.data.loading) return;
    this.setData({ loading: true });
    try {
      const overview = await request<GamesOverview>("/games/overview");
      const games = Object.fromEntries(overview.games.map((item) => [item.key, item])) as Record<
        GameOverviewItem["key"],
        GameOverviewItem
      >;
      const completedToday = Number(overview.summary.completed_today || 0);
      this.setData({
        availableGames: Number(overview.summary.available_games || 4),
        completedToday,
        totalStars: Number(overview.summary.total_stars || 0),
        trainingLabel: completedToday ? "今日训练进度" : "今日脑力训练",
        trainingValue: `${completedToday} / 3 完成`,
        trainingNote: completedToday
          ? `已获得 ${overview.summary.total_stars || 0} 颗星，继续保持`
          : "挑一个游戏，为今天的大脑热热身",
        wordGame: games.word || this.data.wordGame,
        sudokuGame: games.sudoku || this.data.sudokuGame,
        idiomGame: games.idiom || this.data.idiomGame,
        memoryGame: games.memory || this.data.memoryGame,
      });
    } catch (error) {
      // 大厅保留本地入口，具体游戏页会显示网络错误。
    } finally {
      this.setData({ loading: false });
    }
  },

  openWordGame() {
    wx.navigateTo({ url: "/pages/home/index" });
  },

  openSudoku() {
    wx.navigateTo({ url: "/pages/sudoku/index" });
  },

  openIdiom() {
    wx.navigateTo({ url: "/pages/idiom/index" });
  },

  openMemory() {
    wx.navigateTo({ url: "/pages/memory/index" });
  },

  openRecords() {
    wx.navigateTo({ url: this.data.loggedIn ? "/pages/profile/index" : "/pages/auth/index" });
  },

  openProfile() {
    wx.navigateTo({ url: this.data.loggedIn ? "/pages/profile/index" : "/pages/auth/index" });
  },
});

export {};
