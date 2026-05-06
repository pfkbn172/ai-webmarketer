import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { deleteBrief, getBrief, publishBriefToWp, type ContentBrief } from '@/api/content_briefs';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

export default function ContentBriefDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const briefId = id ?? '';

  const detail = useQuery<ContentBrief, Error>({
    queryKey: ['content_brief', briefId],
    queryFn: () => getBrief(briefId),
    enabled: !!briefId,
  });

  const publish = useMutation({
    mutationFn: () => publishBriefToWp(briefId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['content_brief', briefId] });
      qc.invalidateQueries({ queryKey: ['content_briefs'] });
    },
  });

  const remove = useMutation({
    mutationFn: () => deleteBrief(briefId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['content_briefs'] });
      navigate('/content-briefs');
    },
  });

  if (detail.isPending) return <div className="p-8 text-center">読込中…</div>;
  if (detail.isError || !detail.data) {
    return <div className="p-8 text-center text-red-600">読み込みに失敗しました</div>;
  }
  const b = detail.data;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>{b.title}</CardTitle>
          <p className="mt-2 text-sm text-muted-foreground">{b.meta_description ?? '(meta未設定)'}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            <span className="rounded bg-slate-100 px-2 py-0.5">主軸: {b.primary_keyword}</span>
            {b.target_url_slug && (
              <span className="rounded bg-slate-100 px-2 py-0.5">slug: /{b.target_url_slug}/</span>
            )}
            {b.cluster_ids.map((c) => (
              <span key={c} className="rounded bg-blue-100 px-2 py-0.5 text-blue-800">
                {c}
              </span>
            ))}
            <span className="rounded bg-slate-100 px-2 py-0.5">状態: {b.status}</span>
            {b.wp_draft_id && (
              <span className="rounded bg-emerald-100 px-2 py-0.5 text-emerald-800">
                WP下書き #{b.wp_draft_id}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <Button onClick={() => publish.mutate()} disabled={publish.isPending}>
            {publish.isPending ? '送信中…' : '📝 WordPress下書きにする'}
          </Button>
          {publish.isSuccess && publish.data && (
            <span className="text-sm text-emerald-700">
              下書き作成完了 (post id: {publish.data.wp_draft_id})
              {publish.data.wp_post_url && (
                <>
                  &nbsp;
                  <a
                    className="text-blue-700 underline"
                    target="_blank"
                    rel="noreferrer"
                    href={publish.data.wp_post_url}
                  >
                    WPで開く
                  </a>
                </>
              )}
            </span>
          )}
          {publish.isError && (
            <span className="text-sm text-red-600">
              {(publish.error as Error)?.message ?? 'WP送信に失敗しました'}
            </span>
          )}
          <Link to="/content-briefs" className="ml-auto text-sm text-blue-700 hover:underline">
            ← 一覧に戻る
          </Link>
          <Button
            variant="secondary"
            onClick={() => {
              if (confirm('このブリーフを削除しますか?')) remove.mutate();
            }}
          >
            削除
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">採用キーワード ({b.selected_keywords.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2 text-xs">
            {b.selected_keywords.map((k) => (
              <span key={k} className="rounded border border-slate-200 px-2 py-1">
                {k}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">h2 構成案 ({b.h2_outline.length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {b.h2_outline.map((h, i) => (
            <div key={i} className="rounded border-l-4 border-blue-500 bg-slate-50 p-3">
              <div className="font-semibold">
                h2#{i + 1}: {h.h2}
              </div>
              {h.target_keywords.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1 text-xs">
                  対策キーワード:
                  {h.target_keywords.map((k) => (
                    <span key={k} className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">
                      {k}
                    </span>
                  ))}
                </div>
              )}
              {h.rationale && (
                <p className="mt-1 text-xs text-muted-foreground">{h.rationale}</p>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {b.related_keywords.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">関連キーワード(本文に散りばめる)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2 text-xs">
              {b.related_keywords.map((k) => (
                <span key={k} className="rounded bg-slate-100 px-2 py-1">
                  {k}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {b.rationale && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">選定根拠</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed">{b.rationale}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
