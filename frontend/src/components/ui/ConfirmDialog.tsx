import { useState } from 'react';

import { Button } from '@/components/ui/Button';

/**
 * window.confirm() を置き換えるための軽量ダイアログ。
 * 使い方:
 *   const dialog = useConfirm();
 *   const ok = await dialog.confirm({ title: '削除しますか?', destructive: true });
 *   if (ok) ... ;
 *
 *   {dialog.element}  // ルートに置く
 */

type ConfirmOptions = {
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
};

type State = ConfirmOptions & {
  open: boolean;
  resolve?: (ok: boolean) => void;
};

export function useConfirm() {
  const [state, setState] = useState<State>({ open: false, title: '' });

  const confirm = (opts: ConfirmOptions): Promise<boolean> =>
    new Promise<boolean>((resolve) => {
      setState({ ...opts, open: true, resolve });
    });

  const close = (ok: boolean) => {
    state.resolve?.(ok);
    setState((s) => ({ ...s, open: false, resolve: undefined }));
  };

  const element = state.open ? (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={() => close(false)}
    >
      <div
        className="mx-4 w-full max-w-md rounded-lg bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-base font-semibold">{state.title}</div>
        {state.message && (
          <p className="mt-2 text-sm text-muted-foreground">{state.message}</p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => close(false)}>
            {state.cancelLabel ?? 'キャンセル'}
          </Button>
          <Button
            variant={state.destructive ? 'destructive' : 'primary'}
            onClick={() => close(true)}
          >
            {state.confirmLabel ?? 'OK'}
          </Button>
        </div>
      </div>
    </div>
  ) : null;

  return { confirm, element };
}
