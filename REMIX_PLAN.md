# REMIX PLAN

**Remix makes new products from parts suppliers already sell.** It splits each supplier's tour into parts (entry ticket, transfer, meal) and builds TBO's own version from the cheapest *reliable* parts across suppliers. It's published only when the Remix is the SAME experience as the package (by Variant DNA), cheaper on True Price, and leaves TBO a margin.

Remix sits on top of the existing engines. Twin Finder, Variant DNA, the Promise model, True Price and the failover sandbox are reused as they are. The Python package stays `samesame`.

## Top risks
1. **Remix rarely beats packages.** Pooled shared transfers inside a package are cheap, and three suppliers mean three chances to fail. *Mitigation:* model part prices from public-style tariffs, set the parameters before seeing any result, and stop at the R2 gate if Remix almost never wins. Losses are reported, not hidden.
2. **"Exactly the same" on real text.** Packages state some fields and stay silent on others, and a Remix must not quietly drop or add an attribute. *Mitigation:* parts are read by the same Variant DNA extractor as packages. Strict fields (pickup, meals, access, stops) must match, and so must every descriptive field that both sides state. A field only one side states is shown as "unverified", and that Remix needs a human approval before it is published.
3. **Timing realism.** A transfer that arrives after the sunset slot is worthless. *Mitigation:* a zone-to-meeting-point travel-time table built from real coordinates, a stated buffer, fixed shared-transfer timetables, and the infeasible reasons shown.
4. **Scope versus a stable demo.** Five milestones touch data, engines, UI and docs. *Mitigation:* the demo runs at the end of every milestone, all 48 existing tests keep passing, and the UI waits for the R2 gate.
5. **"Isn't this just a package?"** *Answer we must be able to show:* no single supplier sells it; parts come from different suppliers under bundleable resale terms; TBO carries the failover; and the Remix comes with one combined Promise and one cancellation rule.

## Milestones
| | Scope | Done when |
|---|---|---|
| **R1** | Component catalogue: entry tickets, zone-to-meeting-point transfers (shared/private, vehicle size, timetables), a lunch add-on. Every part has a meeting point, time window, price, cancellation rule and `resale_terms`. Booking-log attempts for parts, so the Promise model covers them. DATA.md documents the price parameters. | Pipeline builds; Promise rows exist for `ticket` and `transfer`; tests green |
| **R2** | Recipe search (enumerate parts per role, keep feasible ones, take the lowest True Price). Remix pricing: TBO cost = component True Prices + assembly risk; Remix Promise with per-part failover; strictest cancellation rule. Sell price from the agent-saving share and minimum margin. Guardrails. Tests. **Gate:** honest coverage and saving numbers. | Numbers reported; stop if Remix almost never wins |
| **R3** | Rebrand the chrome to Remix. Sightseeing becomes Remix Studio (packaged variants next to the Remix, recipe card, timeline, True Price proof, margin, cancellation). Book Remix in the sandbox with per-part failover and compensation. New presenter beats. | Beats 1–4 run live |
| **R4** | Gap Remixes from agents' search/filter events in the log (new generator events, disclosed): "New product: nobody sells this". A Remix approvals queue in Ops (approve/undo, logged). | Beats 5 and 7 run |
| **R5** | Connected Trip (hotel + DXB transfer + activity Remix as one product). METRICS.md: coverage, savings, margin, Promise, sandbox outcomes over seeds 1–1,000, where packages win, and a pessimistic preset. Simulator gets the Remix margin (marked simulated). README, DEMO.md, QA.md and PROGRESS.md. | Beats 6 and 8; docs done |

## Decisions taken without asking (also logged in PROGRESS.md)
- **Parts are structured** (meeting point, slots, vehicle and timetable come from supplier APIs), but their *text* goes through the same Variant DNA extractor as packages, so both sides share one vocabulary.
- **Duration** stays descriptive, as it is in Variant DNA. Packages quote one duration for every hotel zone, so the Remix shows its door-to-door time from the client's zone instead.
- **A Remix needs at least two parts.** A ticket-only package has nothing to remix: buying the same ticket elsewhere is what SameSame already does.
- **Who carries what risk:** TBO sells the Remix with a guarantee and carries the price-change and failover risk. The agent's True Price for a Remix is the sell price plus cancellation risk under the strictest part's rule.
- **Sell price:** the agent gets a share of the gap between the best package's True Price and TBO's expected cost; TBO keeps the rest. The defaults, set before any result was seen, are:
  - agent share of the gap: 50%
  - publish only if the agent saves ≥ 3%
  - TBO margin ≥ 4%
  - Remix Promise ≥ 95%
  - timing buffer: 20 minutes

  All of these are adjustable and shown on screen.
