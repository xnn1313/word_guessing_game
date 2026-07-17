import type { BattleState } from "../../types/api";
import { requireLogin } from "../../utils/auth";
import { ApiError, request, showRequestError } from "../../utils/request";

Page({
  data: {
    joinCode: "",
    creating: false,
    joining: false,
    checking: true,
  },

  onLoad(options: Record<string, string>) {
    if (!requireLogin()) {
      setTimeout(() => wx.navigateBack(), 300);
      return;
    }
    if (options.room) this.setData({ joinCode: String(options.room).toUpperCase() });
  },

  onShow() {
    if (!requireLogin(false)) return;
    this.resumeRoom();
  },

  async resumeRoom() {
    this.setData({ checking: true });
    try {
      await request<BattleState>("/battle/current", { authenticated: true });
      wx.navigateTo({ url: "/pages/battle-room/index" });
    } catch (error) {
      if (!(error instanceof ApiError) || error.statusCode !== 404) {
        showRequestError(error, "读取房间失败");
      }
    } finally {
      this.setData({ checking: false });
    }
  },

  onCodeInput(event: any) {
    const joinCode = String(event.detail.value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
    this.setData({ joinCode });
  },

  async createRoom() {
    if (this.data.creating || this.data.checking) return;
    this.setData({ creating: true });
    try {
      await request<BattleState>("/battle/create", {
        method: "POST",
        authenticated: true,
        showLoading: true,
        loadingText: "创建房间",
      });
      wx.navigateTo({ url: "/pages/battle-room/index" });
    } catch (error) {
      showRequestError(error, "创建房间失败");
    } finally {
      this.setData({ creating: false });
    }
  },

  async joinRoom() {
    if (this.data.joining || this.data.checking) return;
    const code = this.data.joinCode.trim();
    if (code.length !== 6) {
      wx.showToast({ title: "请输入六位房间码", icon: "none" });
      return;
    }
    this.setData({ joining: true });
    try {
      await request<BattleState>("/battle/join", {
        method: "POST",
        data: { code },
        authenticated: true,
        showLoading: true,
        loadingText: "加入房间",
      });
      wx.navigateTo({ url: "/pages/battle-room/index" });
    } catch (error) {
      showRequestError(error, "加入房间失败");
    } finally {
      this.setData({ joining: false });
    }
  },
});

export {};
