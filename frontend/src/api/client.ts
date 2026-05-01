import axios from 'axios';

// Nginx 配下では /marketer/api/v1 が API ベース。dev サーバでも vite proxy で同じパス。
export const apiClient = axios.create({
  baseURL: '/marketer/api/v1',
  withCredentials: true, // Cookie を送る(認証は httpOnly Cookie)
  headers: { 'Content-Type': 'application/json' },
});

// 401 を上位で扱いやすくするためにエラーをそのまま投げる
apiClient.interceptors.response.use(
  (res) => res,
  (err) => Promise.reject(err),
);
