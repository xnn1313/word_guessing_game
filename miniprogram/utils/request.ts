import { API_BASE, REQUEST_TIMEOUT } from "../config/index";
import { clearAuth, getToken } from "./auth";

export class ApiError extends Error {
  statusCode: number;

  constructor(message: string, statusCode = 0) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
  }
}

interface RequestOptions {
  method?: "GET" | "POST";
  data?: Record<string, any>;
  authenticated?: boolean;
  showLoading?: boolean;
  loadingText?: string;
}

export function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.authenticated && !token) {
    return Promise.reject(new ApiError("请先登录", 401));
  }

  if (options.showLoading) {
    wx.showLoading({ title: options.loadingText || "加载中", mask: true });
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE}${path}`,
      method: options.method || "GET",
      data: options.data,
      header: headers,
      timeout: REQUEST_TIMEOUT,
      success: (response: any) => {
        const statusCode = Number(response.statusCode || 0);
        const data = response.data || {};
        if (statusCode >= 200 && statusCode < 300) {
          resolve(data as T);
          return;
        }
        if (statusCode === 401 && token) clearAuth();
        reject(new ApiError(data.error || `请求失败（${statusCode}）`, statusCode));
      },
      fail: (error: any) => {
        const detail = error?.errMsg || "无法连接服务器";
        reject(new ApiError(detail.includes("timeout") ? "计算超时，请重试" : detail));
      },
      complete: () => {
        if (options.showLoading) wx.hideLoading();
      },
    });
  });
}

export function showRequestError(error: unknown, fallback = "操作失败，请重试"): void {
  const message = error instanceof Error ? error.message : fallback;
  wx.showToast({ title: message || fallback, icon: "none", duration: 2600 });
}
