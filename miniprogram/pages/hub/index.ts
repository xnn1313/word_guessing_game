import type { GameOverviewItem, GamesOverview } from "../../types/api";
import { getUsername, isLoggedIn } from "../../utils/auth";
import { request } from "../../utils/request";

type TaskKey = GameOverviewItem["key"];

interface GameMeta {
  icon: string;
  tone: string;
  url: string;
  trail?: boolean;
}

const META: Record<TaskKey, GameMeta> = {
  word: { icon: "词", tone: "amber", url: "/pages/classic/index", trail: true },
  sudoku: { icon: "数", tone: "blue", url: "/pages/sudoku/index" },
  idiom: { icon: "成", tone: "pink", url: "/pages/idiom/index?daily=1", trail: true },
  memory: { icon: "记", tone: "violet", url: "/pages/memory/index" },
  word_search: { icon: "连", tone: "cyan", url: "/pages/word-search/index" },
  poetry: { icon: "诗", tone: "gold", url: "/pages/poetry/index" },
  sokoban: { icon: "箱", tone: "green", url: "/pages/sokoban/index", trail: true },
  arrow_maze: { icon: "迷", tone: "indigo", url: "/pages/arrow-maze/index", trail: true },
  tile2048: { icon: "2048", tone: "amber", url: "/pages/game-2048/index" },
  minesweeper: { icon: "雷", tone: "mint", url: "/pages/minesweeper/index" },
};

const ORDER: TaskKey[] = [
  "word",
  "sudoku",
  "idiom",
  "memory",
  "word_search",
  "poetry",
  "sokoban",
  "arrow_maze",
  "tile2048",
  "minesweeper",
];

const TRAIL_TITLES: Partial<Record<TaskKey, string>> = {
  word: "猜词 · 分类闯关",
  idiom: "成语 · 字里行间",
  sokoban: "推箱子 · 仓库路线",
  arrow_maze: "箭头迷宫 · 罗盘航线",
};


const BATTLE_TRAIL = {
  key: "battle",
  title: "双人竞速",
  icon: "战",
  tone: "rose",
  url: "/pages/battle/index",
  trail: true,
  trailTitle: "对战 · 双人竞速",
  available: true,
  progressText: "好友对决 · 90 秒",
  percent: 0,
  completed: false,
  started: false,
};

function buildTask(game: GameOverviewItem | undefined, key: TaskKey): any {
  const meta = META[key];
  const fallbackTitle = {
    word: "猜词实验室",
    sudoku: "每日数独",
    idiom: "成语填字",
    memory: "记忆翻牌",
    word_search: "成语连线",
    poetry: "诗词大会",
    sokoban: "推箱子",
    arrow_maze: "箭头迷宫",
    tile2048: "2048",
    minesweeper: "每日扫雷",
  }[key];
  return {
    key,
    title: game?.title || fallbackTitle,
    icon: meta.icon,
    tone: meta.tone,
    url: meta.url,
    trail: Boolean(meta.trail),
    trailTitle: TRAIL_TITLES[key] || fallbackTitle,
    available: (game?.availability || "available") === "available",
    progressText: game?.progress_text || "开始挑战",
    percent: Math.max(0, Math.min(100, Number(game?.progress_percent || 0))),
    completed: Boolean(game?.daily_completed),
    bestScore: game?.best_score ?? null,
    lastPlayedAt: game?.last_played_at || "",
    started: Number(game?.progress_percent || 0) > 0 || Boolean(game?.last_played_at),
  };
}

Page({
  data: {
    statusBarHeight: 20,
    navHeight: 44,
    dateText: "",
    tab: "today",
    loggedIn: false,
    username: "",
    avatarText: "游",
    completedToday: 0,
    dailyTotal: 10,
    totalStars: 0,
    trailPercent: 0,
    tasks: [] as any[],
    trails: [] as any[],
    lastTask: null as any,
    loading: true,
  },

  onLoad() {
    this.setupNav();
    this.setDateText();
    const fallbackTasks = ORDER.map((key) => buildTask(undefined, key));
    this.setData({
      tasks: fallbackTasks,
      trails: [...fallbackTasks.filter((task) => task.trail), BATTLE_TRAIL],
      lastTask: fallbackTasks[0],
    });
    wx.showShareMenu({ menus: ["shareAppMessage", "shareTimeline"] });
  },

  onShow() {
    const username = getUsername();
    this.setData({ loggedIn: isLoggedIn(), username, avatarText: username.slice(0, 1) || "游" });
    this.loadOverview();
  },

  setupNav() {
    try {
      const info = wx.getWindowInfo();
      const capsule = wx.getMenuButtonBoundingClientRect();
      const statusBarHeight = Number(info.statusBarHeight || 20);
      const navHeight = Math.max(40, (capsule.top - statusBarHeight) * 2 + capsule.height);
      this.setData({ statusBarHeight, navHeight });
    } catch (error) {
      this.setData({ statusBarHeight: 20, navHeight: 44 });
    }
  },

  setDateText() {
    const now = new Date();
    const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
    this.setData({
      dateText: `${now.getMonth() + 1}月${now.getDate()}日 · 周${weekdays[now.getDay()]}`,
    });
  },

  async loadOverview() {
    try {
      const overview = await request<GamesOverview>("/games/overview");
      const byKey = Object.fromEntries(overview.games.map((item) => [item.key, item]));
      const tasks = ORDER.map((key) => buildTask(byKey[key], key));
      const trails = [...tasks.filter((task) => task.trail), BATTLE_TRAIL];
      const lastKey = overview.summary.last_game_key;
      const lastTask =
        tasks.find((task) => task.key === lastKey) ||
        tasks.find((task) => task.started && !task.completed) ||
        tasks[0];
      this.setData({
        tasks,
        trails,
        lastTask,
        trailPercent: trails.length
          ? Math.round(trails.reduce((sum, task) => sum + task.percent, 0) / trails.length)
          : 0,
        completedToday: Number(overview.summary.completed_today || 0),
        dailyTotal: Number(overview.summary.daily_total || 10),
        totalStars: Number(overview.summary.total_stars || 0),
        loading: false,
      });
    } catch (error) {
      // 离线时保留本地入口，具体页面会提示网络错误。
      this.setData({ loading: false });
    }
  },

  switchTab(event: any) {
    this.setData({ tab: event.currentTarget.dataset.tab });
  },

  openTask(event: any) {
    const task = this.findTask(event.currentTarget.dataset.key);
    this.navigateToTask(task);
  },

  openTrail(event: any) {
    const key = event.currentTarget.dataset.key;
    const task =
      this.findTask(key) || (this.data.trails as any[]).find((item) => item.key === key);
    if (!task) return;
    this.navigateToTask({ ...task, url: task.key === "word" ? "/pages/campaign/index" : task.url });
  },

  openContinue() {
    this.navigateToTask(this.data.lastTask);
  },

  findTask(key: string) {
    return (this.data.tasks as any[]).find((task) => task.key === key);
  },

  navigateToTask(task: any) {
    if (!task) return;
    if (!task.available) {
      wx.showToast({ title: "这个游戏正在维护中", icon: "none" });
      return;
    }
    wx.navigateTo({ url: task.url });
  },

  openRecords() {
    wx.navigateTo({ url: this.data.loggedIn ? "/pages/records/index" : "/pages/auth/index" });
  },

  openProfile() {
    wx.navigateTo({ url: this.data.loggedIn ? "/pages/profile/index" : "/pages/auth/index" });
  },

  onShareAppMessage() {
    return {
      title: "十款益智游戏，今天一起练练脑力",
      path: "/pages/hub/index?from=share",
    };
  },

  onShareTimeline() {
    return {
      title: "脑力游乐场｜今天也来做一页任务",
      query: "from=timeline",
    };
  },
});

export {};
