import { ArrowRight, CheckCircle2, ChevronDown, Download, FileSpreadsheet, Loader2, Repeat2, Upload, UserRound } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import type { SheetHotel, SheetResult, SheetRoom, SheetSample } from "@/contracts";
import { inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState } from "@/components/States";
import { Tip, cn } from "@/components/ui";

type Filter = "all" | "person" | "codes" | "twice" | "new";
type Pick = { hotel?: string; rooms: Record<string, string> };   // a person's decisions, kept on this page and in the download

const DECISION = {
  matched: { label: "Same hotel", cls: "bg-ok-50 text-ok-700" },
  review: { label: "A person decides", cls: "bg-warn-50 text-warn-500" },
  new: { label: "New to TBO", cls: "bg-sky-100 text-accent-700" },
} as const;

/** A supplier's rate spreadsheet in, one row per real hotel and room out. */
export default function SheetsPage() {
  const sample = useApi<SheetSample>("/api/sheets/sample");
  const [res, setRes] = useState<{ status: "idle" | "loading" | "ready" | "error"; data?: SheetResult; error?: string }>({ status: "idle" });
  const [picks, setPicks] = useState<Record<string, Pick>>({});
  const [filter, setFilter] = useState<Filter>("all");
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const run = useCallback(async (req: () => Promise<Response>) => {
    setRes({ status: "loading" }); setPicks({}); setFilter("all");
    try {
      const r = await req();
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail ?? `${r.status} ${r.statusText}`);
      setRes({ status: "ready", data: body as SheetResult });
    } catch (e) { setRes({ status: "error", error: (e as Error).message }); }
  }, []);
  const upload = (f: File) => { const fd = new FormData(); fd.append("file", f); run(() => fetch("/api/sheets/ingest", { method: "POST", body: fd })); };
  const trySample = useCallback(() => run(() => fetch("/api/sheets/sample/ingest", { method: "POST" })), [run]);
  usePresenterAction(trySample);

  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-10 pt-8">
      <PageHeader title="Map a supplier's rate sheet"
        subtitle={<>Suppliers write one hotel as “Hyatt Place”, “HP” or “HYATT PLACE DXB”, and one room as “HP SUP KG CV”. Drop in their spreadsheet: every row is matched to one hotel and room in the catalogue, or handed to a person.</>} />
      <section onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) upload(f); }}
        className={cn("mt-6 flex flex-wrap items-center gap-5 rounded-2xl border-2 border-dashed bg-paper px-6 py-5 transition-colors",
          drag ? "border-sun-500 bg-sun-50" : "border-paper-line")}>
        <FileSpreadsheet className="h-10 w-10 text-accent-500" />
        <div className="min-w-0 flex-1">
          <div className="text-[16px] font-semibold">Drop a CSV or Excel file here</div>
          <div className="text-sm text-ink-mute">It needs a hotel column and a room column; anything else (location, phone, stars, price) helps. Nothing is saved.
            {sample.status === "ready" && <> No sheet handy? Download the sample from Weaver, a made-up supplier: {Object.entries(sample.data.files).map(([f, url], i) => <span key={f}>{i ? " · " : ""}<a href={url} className="font-medium text-accent-700 hover:underline">{f.toUpperCase()}</a></span>)}.</>}</div>
        </div>
        <input ref={input} type="file" accept=".csv,.xlsx,.xlsm,.txt" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
        <button onClick={() => input.current?.click()} className="inline-flex items-center gap-2 rounded-full border border-paper-line px-4 py-2 text-sm font-medium text-ink-soft hover:border-accent-500">
          <Upload className="h-4 w-4" />Choose file</button>
        <button onClick={trySample} disabled={res.status === "loading"} className="inline-flex items-center gap-2 rounded-full bg-accent-700 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-900 disabled:opacity-60">
          {res.status === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}Try Weaver’s sheet</button>
      </section>

      {res.status === "loading" && <div className="mt-8 flex items-center gap-3 text-ink-mute"><Loader2 className="h-5 w-5 animate-spin" />Reading the sheet and matching every hotel against the catalogue…</div>}
      {res.status === "error" && <div className="mt-6"><ErrorState error={res.error ?? "Something went wrong"} /></div>}
      {res.status === "ready" && res.data && <Result r={res.data} picks={picks} setPicks={setPicks} filter={filter} setFilter={setFilter} />}
    </div>
  );
}

function Result({ r, picks, setPicks, filter, setFilter }: { r: SheetResult; picks: Record<string, Pick>; setPicks: (f: (p: Record<string, Pick>) => Record<string, Pick>) => void;
  filter: Filter; setFilter: (f: Filter) => void }) {
  const s = r.summary;
  const isCode = (h: SheetHotel) => h.decision !== "new" && !!h.candidates[0]?.reasons[0]?.includes(" read as ");
  const needsPerson = (h: SheetHotel) => (h.decision === "review" && !picks[h.sheet_id]?.hotel) || h.rooms.some((x) => x.status === "person" && !picks[h.sheet_id]?.rooms[x.raw]);
  const shown = useMemo(() => r.hotels.filter((h) => filter === "all" || (filter === "person" && needsPerson(h)) || (filter === "codes" && isCode(h))
    || (filter === "twice" && !!h.also_as) || (filter === "new" && h.decision === "new")), [r, filter, picks]); // eslint-disable-line react-hooks/exhaustive-deps
  const open = r.hotels.filter(needsPerson).length;
  const tabs: [Filter, string, number][] = [["all", "All", r.hotels.length], ["person", "Needs a person", open], ["codes", "Short codes", s.short_codes],
    ["twice", "Listed twice", r.hotels.filter((h) => h.also_as).length], ["new", "New to TBO", s.new]];
  return (
    <>
      <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="rounded-2xl border border-paper-line bg-paper p-6">
          <div className="text-xs font-medium text-ink-mute">{r.file}</div>
          <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 font-display text-[28px] font-semibold text-ink">
            <span>{s.rows} rows</span><ArrowRight className="h-6 w-6 self-center text-ink-mute" /><span>{s.names} hotel names</span>
            <ArrowRight className="h-6 w-6 self-center text-ink-mute" /><span className="text-sun-600">{s.hotels} real hotels</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-sm font-semibold">
            <span className="rounded-full bg-ok-50 px-3 py-1 text-ok-700">{s.matched} matched automatically</span>
            <span className="rounded-full bg-sky-100 px-3 py-1 text-accent-700">{s.new} new to TBO</span>
            <span className="rounded-full bg-warn-50 px-3 py-1 text-warn-500">{s.review} for a person</span>
            <span className="rounded-full bg-sand-200 px-3 py-1 text-ink-soft">{s.listed_twice} listed twice under two names</span>
            <span className="rounded-full bg-sand-200 px-3 py-1 text-ink-soft">{s.short_codes} short codes read</span>
          </div>
          <div className="mt-3 text-[15px] text-ink-soft">Rooms: <b>{s.room_names}</b> room names → <b className="text-ok-700">{s.rooms_mapped}</b> mapped to a catalogue room,
            {" "}<b className="text-warn-500">{s.rooms_person}</b> for a person, <b>{s.rooms_new}</b> new rooms of new hotels.</div>
          <div className="mt-3 text-xs text-ink-mute">
            Columns read: {Object.entries(r.sheet.columns).map(([k, v]) => `${v} → ${k}`).join(" · ")}
            {r.sheet.unused_columns.length > 0 && <> · ignored: {r.sheet.unused_columns.join(", ")}</>}
            {r.sheet.truncated && <> · only the first 5,000 rows were read</>}
          </div>
          <div className="mt-1 text-xs text-ink-mute">Same Twin Finder model and thresholds as the catalogue: auto-merge at p ≥ {r.thresholds.auto_merge.toFixed(3)}, a person from {r.thresholds.review_floor.toFixed(2)}. Short codes are written out before comparing.</div>
        </div>
        {r.check ? (
          <div className="rounded-2xl border border-ok-500/40 bg-paper p-6">
            <div className="flex items-center gap-2 text-lg font-semibold text-ok-700"><CheckCircle2 className="h-5 w-5" />Checked against Weaver’s answer key</div>
            <ul className="mt-2 space-y-1 text-[15px]">
              <li><b>{r.check.hotels.matched_right}</b> of {r.check.hotels.matched_right + r.check.hotels.matched_wrong} automatic hotel matches right</li>
              <li><b>{r.check.hotels.new_right}</b> of {r.check.hotels.new_right + r.check.hotels.new_wrong} “new to TBO” right</li>
              <li><b>{r.check.rooms.mapped_right}</b> of {r.check.rooms.mapped_right + r.check.rooms.mapped_wrong} automatic room mappings right</li>
              <li>{r.check.hotels.review} hotels and {r.check.rooms.person} room names sent to a person (top suggestion right for {r.check.hotels.review_top_right} of {r.check.hotels.review} hotels)</li>
            </ul>
            <div className="mt-2 text-xs text-ink-mute">{r.check.note} Synthetic data; we wrote both the generator and the matcher, so treat this as an upper bound.</div>
          </div>
        ) : (
          <div className="rounded-2xl border border-paper-line bg-paper p-6 text-[15px] text-ink-soft">
            <div className="text-lg font-semibold text-ink">Your sheet</div>
            There is no answer key for an uploaded sheet, so nothing is scored. Matches above the auto-merge bar are applied; everything else is listed under <b>Needs a person</b>.
          </div>
        )}
      </section>

      <div className="mt-6 flex flex-wrap items-center gap-2">
        {tabs.map(([k, label, n]) => (
          <button key={k} onClick={() => setFilter(k)} className={cn("rounded-full border px-4 py-1.5 text-sm font-semibold",
            filter === k ? "border-accent-700 bg-accent-700 text-white" : "border-paper-line bg-paper text-ink-soft hover:border-accent-500")}>{label} <span className="opacity-70">{n}</span></button>
        ))}
        <button onClick={() => download(r, picks)} className="ml-auto inline-flex items-center gap-2 rounded-full border border-accent-700 px-4 py-1.5 text-sm font-semibold text-accent-700 hover:bg-accent-50">
          <Download className="h-4 w-4" />Download cleaned sheet</button>
      </div>
      <ul className="mt-3 space-y-3">
        {shown.map((h) => <HotelRow key={h.sheet_id} h={h} pick={picks[h.sheet_id] ?? { rooms: {} }}
          setPick={(p) => setPicks((all) => ({ ...all, [h.sheet_id]: p }))} />)}
        {!shown.length && <li className="rounded-2xl bg-paper px-5 py-6 text-ink-mute shadow-card">Nothing here{filter === "person" ? ": every hotel and room is resolved." : "."}</li>}
      </ul>
    </>
  );
}

function HotelRow({ h, pick, setPick }: { h: SheetHotel; pick: Pick; setPick: (p: Pick) => void }) {
  const [open, setOpen] = useState(h.decision !== "matched" || h.rooms.some((x) => x.status === "person"));
  const top = h.candidates[0];
  const chosen = pick.hotel ? (pick.hotel === "new" ? null : h.candidates.find((c) => c.cluster_id === pick.hotel)) : h.decision === "matched" ? top : null;
  const d = DECISION[h.decision];
  return (
    <li className="rounded-2xl border border-paper-line bg-paper">
      <button onClick={() => setOpen(!open)} className="grid w-full grid-cols-[minmax(0,1fr)_28px_minmax(0,1.2fr)_auto] items-center gap-4 px-5 py-3.5 text-left">
        <div className="min-w-0">
          <div className="truncate font-mono text-[15px] font-semibold">{h.name}</div>
          <div className="truncate text-xs text-ink-mute">rows {rangeText(h.rows)} · {h.rooms.length} room name{h.rooms.length === 1 ? "" : "s"}{h.lat == null && " · no coordinates"}</div>
        </div>
        <ArrowRight className="h-5 w-5 text-ink-mute" />
        <div className="min-w-0">
          <div className="truncate text-[17px] font-semibold text-accent-700">
            {pick.hotel === "new" ? "New to TBO (your decision)" : chosen ? chosen.name : h.decision === "new" ? "New hotel: not in the catalogue" : `${top?.name ?? "?"}?`}
          </div>
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {(chosen ?? top)?.reasons.slice(0, 4).map((x, i) => (
              <span key={i} className={cn("rounded-full px-2 py-0.5 text-xs", i === 0 && x.includes(" read as ") ? "bg-sun-100 font-semibold text-sun-700" : "bg-sky-50 text-ink-soft")}>{x}</span>))}
            {h.also_as && <span className="inline-flex items-center gap-1 rounded-full bg-sand-200 px-2 py-0.5 text-xs font-semibold text-ink-soft"><Repeat2 className="h-3 w-3" />also in this sheet as “{h.also_as.join("”, “")}”</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {top?.p != null && h.decision !== "new" && <Tip content="p(SAME) from Twin Finder's LightGBM model"><span className="font-mono text-sm text-ink-mute">p {top.p.toFixed(3)}</span></Tip>}
          <span className={cn("rounded-full px-3 py-1 text-xs font-bold uppercase", pick.hotel ? "bg-ok-50 text-ok-700" : d.cls)}>{pick.hotel ? "decided" : d.label}</span>
          <ChevronDown className={cn("h-5 w-5 text-ink-mute transition-transform", open && "rotate-180")} />
        </div>
      </button>
      {open && (
        <div className="border-t border-paper-line px-5 pb-4 pt-3">
          <div className="text-sm text-ink-soft">{h.why}{h.address && <> · <span className="text-ink-mute">{h.address}</span></>}</div>
          {h.decision === "review" && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <UserRound className="h-4 w-4 text-warn-500" /><span className="text-sm font-semibold">Which hotel is this?</span>
              {h.candidates.map((c) => (
                <button key={c.cluster_id} onClick={() => setPick({ ...pick, hotel: c.cluster_id })} className={cn("rounded-full border px-3 py-1 text-sm",
                  pick.hotel === c.cluster_id ? "border-ok-500 bg-ok-50 font-semibold text-ok-700" : "border-paper-line hover:border-accent-500")}>
                  {c.name}{c.p != null && <span className="ml-1 text-ink-mute">p {c.p.toFixed(2)}</span>}</button>))}
              <button onClick={() => setPick({ ...pick, hotel: "new" })} className={cn("rounded-full border px-3 py-1 text-sm",
                pick.hotel === "new" ? "border-ok-500 bg-ok-50 font-semibold text-ok-700" : "border-paper-line hover:border-accent-500")}>New hotel</button>
            </div>
          )}
          <table className="mt-3 w-full text-[15px]">
            <thead><tr className="text-left text-xs uppercase text-ink-mute"><th className="py-1 font-semibold">Room as written</th><th className="font-semibold">TBO room</th><th className="font-semibold">Why</th><th className="text-right font-semibold">Rates</th></tr></thead>
            <tbody>{h.rooms.map((x) => <RoomRow key={x.raw} x={x} h={h} pick={pick} setPick={setPick} />)}</tbody>
          </table>
        </div>
      )}
    </li>
  );
}

function RoomRow({ x, h, pick, setPick }: { x: SheetRoom; h: SheetHotel; pick: Pick; setPick: (p: Pick) => void }) {
  const chosen = pick.rooms[x.raw];
  const opts = h.options;
  return (
    <tr className="border-t border-paper-line/70 align-top">
      <td className="py-1.5 pr-3 font-mono text-sm"><RawRoom x={x} /></td>
      <td className="py-1.5 pr-3">
        {x.status === "mapped" ? <span className="font-semibold text-ok-700">{x.room}</span>
          : x.status === "new" ? <span className="text-accent-700">New room: {x.parsed}</span>
          : opts.length && pick.hotel !== "new" ? (
            <select value={chosen ?? ""} onChange={(e) => setPick({ ...pick, rooms: { ...pick.rooms, [x.raw]: e.target.value } })}
              className={cn("max-w-[260px] rounded-lg border px-2 py-1 text-sm", chosen ? "border-ok-500 bg-ok-50" : "border-warn-500 bg-warn-50")}>
              <option value="">Pick the room…</option>
              {opts.map((o) => <option key={o.room_id} value={o.room_id}>{o.name}</option>)}
              <option value="new">A room we don't have</option>
            </select>
          ) : <span className="text-warn-500">a person adds it</span>}
      </td>
      <td className="py-1.5 pr-3 text-sm text-ink-soft">{x.why}{x.status === "mapped" && x.confidence < 1 && <span className="text-ink-mute"> · confidence {x.confidence.toFixed(2)}</span>}</td>
      <td className="whitespace-nowrap py-1.5 text-right text-sm tabular-nums text-ink-soft">
        {x.prices.slice(0, 2).map((p, i) => <div key={i}>{p.meal ?? "Rate"} {inr(p.price)}</div>)}
      </td>
    </tr>
  );
}

/** The room name with the hotel's own words greyed out: that is what the parser removed before reading it. */
function RawRoom({ x }: { x: SheetRoom }) {
  if (!x.hotel_words) return <>{x.raw}</>;
  const n = x.hotel_words.split(" ").length;
  const toks = x.raw.split(/\s+/);
  const lead = toks.slice(0, n).join(" ").toLowerCase().replace(/[^a-z0-9 ]/g, "") === x.hotel_words;
  if (!lead) return <>{x.raw}</>;
  return <><Tip content="The hotel's own name, removed before reading the room"><span className="text-ink-mute line-through decoration-ink-mute/50">{toks.slice(0, n).join(" ")}</span></Tip> {toks.slice(n).join(" ")}</>;
}

function rangeText(rows: number[]) {
  return rows.length > 3 ? `${rows[0]}–${rows[rows.length - 1]}` : rows.join(", ");
}

function download(r: SheetResult, picks: Record<string, Pick>) {
  const head = ["sheet_row", "hotel_as_written", "tbo_hotel_id", "tbo_hotel", "hotel_decision", "room_as_written", "tbo_room_id", "tbo_room", "room_status", "meal", "price", "cancellation"];
  const esc = (v: unknown) => { const t = v == null ? "" : String(v); return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t; };
  const out = [head.join(",")];
  for (const h of r.hotels) {
    const p = picks[h.sheet_id];
    const cand = p?.hotel && p.hotel !== "new" ? h.candidates.find((c) => c.cluster_id === p.hotel) : h.decision === "matched" ? h.candidates[0] : null;
    const dec = p?.hotel ? (p.hotel === "new" ? "new (person)" : "same (person)") : h.decision === "matched" ? "same (auto)" : h.decision === "new" ? "new (auto)" : "needs a person";
    for (const x of h.rooms) {
      const room = p?.rooms[x.raw];
      const rid = x.status === "mapped" ? x.room_id : room && room !== "new" ? room : null;
      const rname = x.status === "mapped" ? x.room : room === "new" ? "new room (person)" : rid ? h.options.find((o) => o.room_id === rid)?.name : x.status === "new" ? `new: ${x.parsed}` : "";
      const rstat = x.status === "mapped" ? "mapped (auto)" : room ? "decided (person)" : x.status === "new" ? "new" : "needs a person";
      const prices = x.prices.length ? x.prices : [{ meal: null, price: null, cancel: null }];
      x.rows.forEach((row, i) => {
        const pr = prices[i] ?? prices[0];
        out.push([row, h.name, cand?.cluster_id, cand?.name, dec, x.raw, rid, rname, rstat, pr.meal, pr.price, pr.cancel].map(esc).join(","));
      });
    }
  }
  const url = URL.createObjectURL(new Blob([out.join("\n")], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url; a.download = r.file.replace(/\.(csv|xlsx|xlsm|txt)$/i, "") + "_cleaned.csv"; a.click();
  URL.revokeObjectURL(url);
}
