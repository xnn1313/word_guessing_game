import type { BattlePlayer, BattleState } from "../../types/api";
import { decorateHistory } from "../../utils/format";
import { clearAuth } from "../../utils/auth";
import { ApiError, request, showRequestError } from "../../utils/request";

let pollTimer: any = null;
let refreshPending = false;

function stopPolling(): void {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

function decoratePlayers(players: BattlePlayer[]): any[] {
  const result: any[] = players.map((player) => ({
    ...player,
    displayBest: `${Number(player.best_similarity).toFixed(2)}%`,
    roleText: `${player.is_self ? "你" : "对手"}${player.is_host ? " · 房主" : ""}${player.rematch_ready ? " · 已确认再战" : ""}`,
    empty: false,
  }));
  while (result.length < 2) {
    result.push({ empty: true, username: "等待好友", attempts: 0, displayBest: "0.00%", roleText: "尚未加入" });
  }
  return result;
}

Page({
  data: {
    state: null as BattleState | null,
    code: "------",
    statusText: "连接中",
    players: [] as any[],
    history: [] as any[],
    remainingSeconds: 90,
    timerUrgent: false,
    guess: "",
    waiting: true,
    playing: false,
    finished: false,
    canStart: false,
    isHost: false,
    submitting: false,
    resultTitle: "",
    resultAnswer: "",
    rematchLabel: "再来一局",
    rematchDisabled: false,
    loading: true,
  },

  onLoad() {
    this.refreshState(false);
  },

  onShow() {
    this.startPolling();
  },

  onHide() {
    stopPolling();
  },

  onUnload() {
    stopPolling();
  },

  onShareAppMessage() {
    return {
      title: `来和我双人猜词，房间码 ${this.data.code}`,
      path: `/pages/battle/index?room=${this.data.code}`,
    };
  },

  startPolling() {
    stopPolling();
    pollTimer = setInterval(() => this.refreshState(true), 1000);
  },

  async refreshState(silent = true) {
    if (refreshPending) return;
    refreshPending = true;
    try {
      const state = await request<BattleState>("/battle/current", { authenticated: true });
      this.applyState(state);
    } catch (error) {
      if (error instanceof ApiError && error.statusCode === 401) {
        clearAuth();
        stopPolling();
        wx.reLaunch({ url: "/pages/auth/index" });
      } else if (!silent) {
        showRequestError(error, "读取房间失败");
        setTimeout(() => wx.navigateBack(), 700);
      }
    } finally {
      refreshPending = false;
      this.setData({ loading: false });
    }
  },

  applyState(state: BattleState) {
    const waiting = state.state === "waiting";
    const playing = state.state === "playing";
    const finished = state.state === "finished";
    let resultTitle = "";
    let resultAnswer = "";
    if (finished) {
      resultTitle = state.winner_username ? `${state.winner_username} 获胜` : "本局平局";
      if (state.finish_reason === "opponent_left") resultTitle = "对手已离开房间";
      resultAnswer = `答案：${state.target_word || "-"}`;
    }
    let rematchLabel = "再来一局";
    if (!state.can_rematch) rematchLabel = "对手已离开，无法再战";
    else if (state.rematch_ready) rematchLabel = "已确认，等待对手";

    this.setData({
      state,
      code: state.code,
      statusText: waiting ? "等待玩家" : playing ? "比赛中" : "已结束",
      players: decoratePlayers(state.players),
      history: decorateHistory(state.my_history || [], "time"),
      remainingSeconds: state.remaining_seconds,
      timerUrgent: playing && state.remaining_seconds <= 15,
      waiting,
      playing,
      finished,
      canStart: state.can_start,
      isHost: state.is_host,
      resultTitle,
      resultAnswer,
      rematchLabel,
      rematchDisabled: !state.can_rematch || state.rematch_ready,
      guess: playing && this.data.finished ? "" : this.data.guess,
    });
    if (finished && !state.can_rematch) stopPolling();
  },

  copyCode() {
    wx.setClipboardData({ data: this.data.code });
  },

  onGuessInput(event: any) {
    this.setData({ guess: event.detail.value });
  },

  async startGame() {
    if (!this.data.canStart || !this.data.state) return;
    try {
      const state = await request<BattleState>("/battle/start", {
        method: "POST",
        data: { code: this.data.code },
        authenticated: true,
        showLoading: true,
        loadingText: "开始比赛",
      });
      this.applyState(state);
    } catch (error) {
      showRequestError(error, "开始比赛失败");
    }
  },

  async submitGuess() {
    const word = this.data.guess.trim();
    if (!word || !this.data.playing || this.data.submitting) return;
    this.setData({ submitting: true });
    try {
      const state = await request<BattleState>("/battle/guess", {
        method: "POST",
        data: { word },
        authenticated: true,
      });
      this.setData({ guess: "" });
      this.applyState(state);
      if (state.guess_result?.is_correct) wx.vibrateShort({ type: "medium" });
    } catch (error) {
      showRequestError(error, "提交猜测失败");
    } finally {
      this.setData({ submitting: false });
    }
  },

  async requestRematch() {
    if (!this.data.finished || this.data.rematchDisabled) return;
    this.setData({ rematchDisabled: true });
    try {
      const state = await request<BattleState>("/battle/rematch", {
        method: "POST",
        authenticated: true,
      });
      this.applyState(state);
      this.startPolling();
    } catch (error) {
      this.setData({ rematchDisabled: false });
      showRequestError(error, "确认再战失败");
    }
  },

  async leaveRoom() {
    const confirmed = await new Promise<boolean>((resolve) => {
      wx.showModal({
        title: "离开房间",
        content: this.data.playing ? "比赛正在进行，离开后对手将直接获胜。" : "确定离开当前房间吗？",
        success: (result: any) => resolve(Boolean(result.confirm)),
        fail: () => resolve(false),
      });
    });
    if (!confirmed) return;
    stopPolling();
    try {
      await request<{ message: string }>("/battle/leave", {
        method: "POST",
        authenticated: true,
        showLoading: true,
        loadingText: "离开房间",
      });
    } catch (error) {
      showRequestError(error, "离开房间失败");
      this.startPolling();
      return;
    }
    if (getCurrentPages().length > 1) {
      wx.navigateBack();
    } else {
      wx.reLaunch({ url: "/pages/battle/index" });
    }
  },
});

export {};
