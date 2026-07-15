const TOKEN_KEY = "word_game_token";
const USERNAME_KEY = "word_game_username";
const SESSION_KEY = "word_game_session_id";

export function getToken(): string {
  return wx.getStorageSync(TOKEN_KEY) || "";
}

export function getUsername(): string {
  return wx.getStorageSync(USERNAME_KEY) || "";
}

export function saveAuth(token: string, username: string): void {
  wx.setStorageSync(TOKEN_KEY, token);
  wx.setStorageSync(USERNAME_KEY, username);
}

export function clearAuth(): void {
  wx.removeStorageSync(TOKEN_KEY);
  wx.removeStorageSync(USERNAME_KEY);
  wx.removeStorageSync(SESSION_KEY);
}

export function isLoggedIn(): boolean {
  return Boolean(getToken());
}

export function getSessionId(): string {
  return wx.getStorageSync(SESSION_KEY) || "";
}

export function saveSessionId(sessionId?: string): void {
  if (sessionId) wx.setStorageSync(SESSION_KEY, sessionId);
}

export function requireLogin(redirect = true): boolean {
  if (isLoggedIn()) return true;
  if (redirect) {
    wx.showModal({
      title: "需要登录",
      content: "登录后才能保存闯关进度和进入双人竞速。",
      confirmText: "去登录",
      success: (result: any) => {
        if (result.confirm) wx.navigateTo({ url: "/pages/auth/index" });
      },
    });
  }
  return false;
}
