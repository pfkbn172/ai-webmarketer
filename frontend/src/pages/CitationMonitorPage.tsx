import { useQuery } from '@tanstack/react-query';

import { apiClient } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

type CitationCell = { llm: string; self_cited: number; total: number };
type CitationRow = { query_id: string; query_text: string; cells: CitationCell[] };

const LLMS = ['chatgpt', 'claude', 'perplexity', 'gemini', 'aio'];

export default function CitationMonitorPage() {
  const { data, isPending } = useQuery<CitationRow[], Error>({
    queryKey: ['citations', 'summary'],
    queryFn: async () => (await apiClient.get<CitationRow[]>('/citation-logs/summary')).data,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI 引用モニタ(直近 28 日)</CardTitle>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : !data || data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            ターゲットクエリを登録 + 引用モニタジョブを実行するとデータが表示されます
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-2 pr-4">クエリ</th>
                  {LLMS.map((l) => (
                    <th key={l} className="py-2 px-2">
                      {l}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.query_id} className="border-t border-border">
                    <td className="py-2 pr-4">{r.query_text}</td>
                    {LLMS.map((l) => {
                      const cell = r.cells.find((c) => c.llm === l);
                      const value = cell ? `${cell.self_cited}/${cell.total}` : '—';
                      const cls =
                        !cell || cell.total === 0
                          ? 'text-muted-foreground'
                          : cell.self_cited === 0
                          ? 'text-destructive'
                          : 'text-foreground';
                      return (
                        <td key={l} className={`py-2 px-2 ${cls}`}>
                          {value}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
