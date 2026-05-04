import axios from 'axios';

// Nginx 配下では /marketer/api/v1 が API ベース。dev サーバでも vite proxy で同じパス。
export const apiClient = axios.create({
  baseURL: '/marketer/api/v1',
  withCredentials: true, // Cookie を送る(認証は httpOnly Cookie)
  headers: { 'Content-Type': 'application/json' },
});

// 401 を上位で扱いやすくするためにエラーをそのまま投げる。
// バックエンドが返す { detail: "..." } を Error.message に昇格させて、
// useMutation の error.message をそのまま画面に出せるようにする。
apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err?.response?.data?.detail;
    if (typeof detail === 'string' && detail) {
      err.message = detail;
    }
    return Promise.reject(err);
  },
);
