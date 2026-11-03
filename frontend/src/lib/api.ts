import { useEffect, useState } from "react";

export async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${path}`);
  return r.json() as Promise<T>;
}

export type Loadable<T> = { status: "loading" } | { status: "error"; error: string } | { status: "ready"; data: T };

export function useApi<T>(path: string | null): Loadable<T> & { reload: () => void } {
  const [state, setState] = useState<Loadable<T>>({ status: "loading" });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) return;
    let alive = true;
    setState({ status: "loading" });
    getJSON<T>(path)
      .then((data) => alive && setState({ status: "ready", data }))
      .catch((e: Error) => alive && setState({ status: "error", error: e.message }));
    return () => { alive = false; };
  }, [path, tick]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}

// Indian digit grouping: ₹1,24,020
export const inr = (n: number) => "₹" + Math.round(n).toLocaleString("en-IN");
