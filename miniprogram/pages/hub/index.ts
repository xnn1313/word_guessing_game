import { getUsername, isLoggedIn } from "../../utils/auth";

Page({
  data: {
    loggedIn: false,
    username: "",
    avatarText: "游",
    trainingLabel: "今日脑力训练",
    trainingValue: "先来一局",
    trainingNote: "完成一局，为今天的大脑热热身",
    campaignStars: 0,
  },

  onShow() {
    const loggedIn = isLoggedIn();
    const username = getUsername();
    const campaignStars = Number(wx.getStorageSync("word_game_campaign_stars")) || 0;
    this.setData({
      loggedIn,
      username,
      avatarText: username.slice(0, 1) || "游",
      campaignStars,
      trainingLabel: campaignStars > 0 ? "猜词闯关进度" : "今日脑力训练",
      trainingValue: campaignStars > 0 ? `${campaignStars} 颗星` : "先来一局",
      trainingNote: campaignStars > 0 ? "闯关进度已同步，继续今天的训练" : "完成一局，为今天的大脑热热身",
    });
  },

  openWordGame() {
    wx.navigateTo({ url: "/pages/home/index" });
  },

  showComingSoon(event: any) {
    const name = event.currentTarget.dataset.name || "新游戏";
    wx.showToast({ title: `${name}正在准备中`, icon: "none" });
  },

  openRecords() {
    wx.navigateTo({ url: this.data.loggedIn ? "/pages/profile/index" : "/pages/auth/index" });
  },

  openProfile() {
    wx.navigateTo({ url: this.data.loggedIn ? "/pages/profile/index" : "/pages/auth/index" });
  },
});

export {};
