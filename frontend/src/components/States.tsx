import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

export function Loading({ what = "Loading" }: { what?: string }) {
  return (
    <div className="flex items-center gap-3 p-10 text-ink-mute">
      <Loader2 className="h-5 w-5 animate-spin" /> {what}…
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="m-6 rounded-xl border border-danger-500/30 bg-danger-50 p-6">
      <div className="flex items-center gap-2 font-semibold text-danger-700"><AlertTriangle className="h-5 w-5" /> Something went wrong</div>
      <p className="mt-2 font-mono text-sm text-ink-soft">{error}</p>
      {onRetry && <button onClick={onRetry} className="mt-4 rounded-lg bg-ink px-4 py-2 text-white">Retry</button>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="m-6 flex flex-col items-center rounded-xl border border-dashed border-paper-line p-12 text-center text-ink-mute">
      <Inbox className="h-8 w-8" />
      <div className="mt-3 text-lg font-semibold text-ink-soft">{title}</div>
      {children && <div className="mt-1 max-w-md">{children}</div>}
    </div>
  );
}
