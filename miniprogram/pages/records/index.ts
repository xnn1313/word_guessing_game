import type { GameOverviewItem, GamesOverview, PuzzleGameKey } from "../../types/api";
import { isLoggedIn } from "../../utils/auth";
import { request, showRequestError } from "../../utils/request";

const routes: Record<PuzzleGameKey, string> = {
  word: "/pages/home/index",
  sudoku: "/pages/sudoku/index",
  idiom: "/pages/idiom/index",
  memory: "/pages/memory/index",
};

const marks: Record<PuzzleGameKey, string> = {
  word: "词",
  sudoku: "数",
  idiom: "成",
  memory: "记",
};

function formatPlayedAt(value: string | null): string {
  if (!value) return "还没有游玩记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "最近玩过";
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  const time = `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  return sameDay ? `今天 ${time}` : `${date.getMonth() + 1} 月 ${date.getDate()} 日 ${time}`;
}

Page({
  data: {
    loading: true,
    totalStars: 0,
    completedToday: 0,
    availableGames: 4,
    records: [] as Array<GameOverviewItem & { mark: string; playedText: string }>,
  },

  onShow() {
    if (!isLoggedIn()) {
      wx.redirectTo({ url: "/pages/auth/index" });
      return;
    }
    this.loadRecords();
  },

  async loadRecords() {
    this.setData({ loading: true });
    try {
      const overview = await request<GamesOverview>("/games/overview", { authenticated: true });
      this.setData({
        totalStars: Number(overview.summary.total_stars || 0),
        completedToday: Number(overview.summary.completed_today || 0),
        availableGames: Number(overview.summary.available_games || 4),
        records: overview.games.map((item) => ({
          ...item,
          mark: marks[item.key],
          playedText: formatPlayedAt(item.last_played_at),
        })),
      });
    } catch (error) {
      showRequestError(error, "训练记录加载失败");
    } finally {
      this.setData({ loading: false });
    }
  },

  openGame(event: any) {
    const key = event.currentTarget.dataset.key as PuzzleGameKey;
    const url = routes[key];
    if (url) wx.navigateTo({ url });
  },

  openHub() {
    wx.reLaunch({ url: "/pages/hub/index" });
  },

  openProfile() {
    wx.redirectTo({ url: "/pages/profile/index" });
  },
});

export {};
