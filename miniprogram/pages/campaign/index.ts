import type { CampaignCatalog, CampaignCategory } from "../../types/api";
import { requireLogin } from "../../utils/auth";
import { request, showRequestError } from "../../utils/request";

function decorateCategories(categories: CampaignCategory[]): any[] {
  return categories.map((category, index) => ({
    ...category,
    expanded: index === 0,
    progressText: `${category.stars}/${category.max_stars} 星`,
    levels: category.levels.map((level) => ({
      ...level,
      starText: level.stars ? "★".repeat(level.stars) + "☆".repeat(3 - level.stars) : "☆☆☆",
    })),
  }));
}

Page({
  data: {
    totalStars: 0,
    maxStars: 780,
    categories: [] as any[],
    loading: true,
  },

  onLoad() {
    if (!requireLogin()) {
      setTimeout(() => wx.navigateBack(), 300);
      return;
    }
    this.loadCatalog();
  },

  onPullDownRefresh() {
    this.loadCatalog().finally(() => wx.stopPullDownRefresh());
  },

  async loadCatalog() {
    this.setData({ loading: true });
    try {
      const catalog = await request<CampaignCatalog>("/campaign", { authenticated: true });
      wx.setStorageSync("word_game_campaign_stars", catalog.total_stars);
      this.setData({
        totalStars: catalog.total_stars,
        maxStars: catalog.max_stars,
        categories: decorateCategories(catalog.categories),
      });
    } catch (error) {
      showRequestError(error, "读取关卡失败");
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
    const levelId = event.currentTarget.dataset.id;
    const unlocked = event.currentTarget.dataset.unlocked;
    if (!unlocked) {
      wx.showToast({ title: "请先完成上一关", icon: "none" });
      return;
    }
    wx.navigateTo({ url: `/pages/campaign-game/index?levelId=${encodeURIComponent(levelId)}` });
  },
});

export {};
