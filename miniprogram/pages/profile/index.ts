import type { CampaignCatalog } from "../../types/api";
import { clearAuth, getUsername, isLoggedIn } from "../../utils/auth";
import { request, showRequestError } from "../../utils/request";

Page({
  data: {
    loggedIn: false,
    username: "",
    avatarText: "?",
    totalStars: 0,
    maxStars: 780,
    loading: false,
  },

  onShow() {
    const loggedIn = isLoggedIn();
    const username = getUsername();
    this.setData({ loggedIn, username, avatarText: username.slice(0, 1) || "?" });
    if (loggedIn) this.loadProgress();
  },

  async loadProgress() {
    this.setData({ loading: true });
    try {
      const catalog = await request<CampaignCatalog>("/campaign", { authenticated: true });
      this.setData({ totalStars: catalog.total_stars, maxStars: catalog.max_stars });
    } catch (error) {
      showRequestError(error, "读取进度失败");
    } finally {
      this.setData({ loading: false });
    }
  },

  goLogin() {
    wx.navigateTo({ url: "/pages/auth/index" });
  },

  openHub() {
    wx.reLaunch({ url: "/pages/hub/index" });
  },

  openRecords() {
    if (!this.data.loggedIn) {
      wx.navigateTo({ url: "/pages/auth/index" });
      return;
    }
    wx.redirectTo({ url: "/pages/records/index" });
  },

  async logout() {
    const result = await new Promise<boolean>((resolve) => {
      wx.showModal({
        title: "退出账号",
        content: "本地登录状态会清除，服务器存档仍然保留。",
        success: (response: any) => resolve(Boolean(response.confirm)),
        fail: () => resolve(false),
      });
    });
    if (!result) return;
    try {
      await request<{ message: string }>("/auth/logout", { method: "POST", authenticated: true });
    } catch (error) {
      // Token 失效时也应允许清理本地状态。
    }
    clearAuth();
    wx.showToast({ title: "已退出", icon: "success" });
    setTimeout(() => wx.reLaunch({ url: "/pages/hub/index" }), 400);
  },
});

export {};
