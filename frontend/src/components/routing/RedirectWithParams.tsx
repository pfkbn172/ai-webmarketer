import { Navigate, useParams } from 'react-router-dom';

/**
 * 旧URL `/content-briefs/:id` を `/production/briefs/:id` のようにパラメータ込みで
 * リダイレクトするための簡易コンポーネント。
 *
 * 使い方:
 *   <Route path="content-briefs/:id"
 *          element={<RedirectWithParams to="/production/briefs/:id" />} />
 *
 * `:name` プレースホルダを useParams() の値で埋めて Navigate する。
 */
export default function RedirectWithParams({ to }: { to: string }) {
  const params = useParams();
  let resolved = to;
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) {
      resolved = resolved.replace(`:${k}`, v);
    }
  }
  return <Navigate to={resolved} replace />;
}
