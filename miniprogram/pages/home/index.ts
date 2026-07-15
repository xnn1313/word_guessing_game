import { getUsername, isLoggedIn, requireLogin } from "../../utils/auth";

Page({
  data: {
    loggedIn: false,
    username: "",
  },

  onShow() {
    this.setData({
      loggedIn: isLoggedIn(),
      username: getUsername(),
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
