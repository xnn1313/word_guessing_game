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
    trainingValue: "0 / 7 完成",
    trainingNote: "挑一个游戏，为今天的大脑热热身",
    availableGames: 8,
    dailyTotal: 7,
    completedToday: 0,
    totalStars: 0,
    wordGame: fallbackGame("word", "猜词实验室"),
    sudokuGame: fallbackGame("sudoku", "每日数独"),
    idiomGame: fallbackGame("idiom", "成语填字"),
    memoryGame: fallbackGame("memory", "记忆翻牌"),
    wordSearchGame: fallbackGame("word_search", "成语连线"),
    poetryGame: fallbackGame("poetry", "诗词大会"),
    sokobanGame: fallbackGame("sokoban", "推箱子"),
    arrowMazeGame: fallbackGame("arrow_maze", "箭头迷宫"),
  },

  onLoad() {
    wx.showShareMenu({
      menus: ["shareAppMessage", "shareTimeline"],
    });
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
      const dailyTotal = Number(overview.summary.daily_total || 7);
      this.setData({
        availableGames: Number(overview.summary.available_games || 8),
        dailyTotal,
        completedToday,
        totalStars: Number(overview.summary.total_stars || 0),
        trainingLabel: completedToday ? "今日训练进度" : "今日脑力训练",
        trainingValue: `${completedToday} / ${dailyTotal} 完成`,
        trainingNote: completedToday
          ? `已获得 ${overview.summary.total_stars || 0} 颗星，继续保持`
          : "挑一个游戏，为今天的大脑热热身",
        wordGame: games.word || this.data.wordGame,
        sudokuGame: games.sudoku || this.data.sudokuGame,
        idiomGame: games.idiom || this.data.idiomGame,
        memoryGame: games.memory || this.data.memoryGame,
        wordSearchGame: games.word_search || this.data.wordSearchGame,
        poetryGame: games.poetry || this.data.poetryGame,
        sokobanGame: games.sokoban || this.data.sokobanGame,
        arrowMazeGame: games.arrow_maze || this.data.arrowMazeGame,
      });
    } catch (error) {
      // 大厅保留本地入口，具体游戏页会显示网络错误。
    } finally {
      this.setData({ loading: false });
    }
  },

  openWordGame() {
    this.openGame(this.data.wordGame, "/pages/home/index");
  },

  openSudoku() {
    this.openGame(this.data.sudokuGame, "/pages/sudoku/index");
  },

  openIdiom() {
    this.openGame(this.data.idiomGame, "/pages/idiom/index");
  },

  openMemory() {
    this.openGame(this.data.memoryGame, "/pages/memory/index");
  },

  openWordSearch() {
    this.openGame(this.data.wordSearchGame, "/pages/word-search/index");
  },

  openPoetry() {
    this.openGame(this.data.poetryGame, "/pages/poetry/index");
  },

  openSokoban() {
    this.openGame(this.data.sokobanGame, "/pages/sokoban/index");
  },

  openArrowMaze() {
    this.openGame(this.data.arrowMazeGame, "/pages/arrow-maze/index");
  },

  openGame(game: GameOverviewItem, url: string) {
    if (game.availability !== "available") {
      wx.showToast({
        title: game.availability === "maintenance" ? "游戏维护中，请稍后再试" : "游戏即将上线",
        icon: "none",
      });
      return;
    }
    wx.navigateTo({ url });
  },

  openRecords() {
    wx.navigateTo({ url: this.data.loggedIn ? "/pages/records/index" : "/pages/auth/index" });
  },

  openProfile() {
    wx.navigateTo({ url: this.data.loggedIn ? "/pages/profile/index" : "/pages/auth/index" });
  },

  onShareAppMessage() {
    return {
      title: "八款益智游戏，今天一起练练脑力",
      path: "/pages/hub/index?from=share",
    };
  },

  onShareTimeline() {
    return {
      title: "脑力游乐场｜每天十分钟，换一种脑力热身",
      query: "from=timeline",
    };
  },
});

export {};
