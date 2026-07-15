import { getUsername, isLoggedIn, requireLogin } from "../../utils/auth";

Page({
  data: {
    loggedIn: false,
    username: "",
    avatarText: "?",
  },

  onShow() {
    this.setData({
      loggedIn: isLoggedIn(),
      username: getUsername(),
      avatarText: getUsername().slice(0, 1) || "?",
    });
  },

  openClassic() {
    wx.navigateTo({ url: "/pages/classic/index" });
  },

  openCampaign() {
    if (!requireLogin()) return;
    wx.navigateTo({ url: "/pages/campaign/index" });
  },

  openBattle() {
    if (!requireLogin()) return;
    wx.navigateTo({ url: "/pages/battle/index" });
  },

  openProfile() {
    wx.navigateTo({ url: this.data.loggedIn ? "/pages/profile/index" : "/pages/auth/index" });
  },
});

export {};
