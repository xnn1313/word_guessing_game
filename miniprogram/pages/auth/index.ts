import type { AuthPayload } from "../../types/api";
import { saveAuth, saveSessionId } from "../../utils/auth";
import { request, showRequestError } from "../../utils/request";

Page({
  data: {
    mode: "login" as "login" | "register",
    username: "",
    password: "",
    submitting: false,
  },

  switchMode(event: any) {
    this.setData({ mode: event.currentTarget.dataset.mode, password: "" });
  },

  onUsernameInput(event: any) {
    this.setData({ username: event.detail.value });
  },

  onPasswordInput(event: any) {
    this.setData({ password: event.detail.value });
  },

  async submit() {
    const username = this.data.username.trim();
    const password = this.data.password;
    if (username.length < 2 || password.length < 6) {
      wx.showToast({ title: "用户名至少 2 位，密码至少 6 位", icon: "none" });
      return;
    }
    if (this.data.submitting) return;

    this.setData({ submitting: true });
    try {
      const payload = await request<AuthPayload>(`/mobile/auth/${this.data.mode}`, {
        method: "POST",
        data: { username, password },
        showLoading: true,
        loadingText: this.data.mode === "login" ? "登录中" : "注册中",
      });
      saveAuth(payload.token, payload.username);
      saveSessionId(payload.game.session_id);
      wx.showToast({
        title: this.data.mode === "login" ? "登录成功" : "注册成功",
        icon: "success",
      });
      setTimeout(() => {
        if (getCurrentPages().length > 1) wx.navigateBack();
        else wx.reLaunch({ url: "/pages/home/index" });
      }, 450);
    } catch (error) {
      showRequestError(error, "登录失败");
    } finally {
      this.setData({ submitting: false });
    }
  },
});

export {};
