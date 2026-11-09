# DEMO: Remix, 4 minutes, 3 presenters (Dubai)

> Every number below is computed by the pipeline from synthetic suppliers over real OpenStreetMap hotels and real Dubai attractions; nothing is typed in. If a rebuild moves a number, the screen is right and this page is stale: rerun `python -m samesame.eval.report` and update from METRICS.md.
>
> Spoken line, never on screen: **"Skyscanner compares products. Remix makes new ones."**

Run `python3 start.py --demo` and open http://localhost:8000.
- Press `.` for the step indicator.
- **Keys 1–8** jump to a beat with its state loaded.
- **Space** fires the beat's one action.
- **←/→** step between beats.

| Key | Beat | Who | ~Time | Space does |
|---|---|---|---|---|
| 1 | The problem: one Burj Khalifa experience, many packages | A | 0:15 | → Variant DNA |
| 2 | Remix Studio: helicopter package vs the Remix, recipe card | B | 0:35 | shows the arithmetic |
| 3 | True Price proof: cheaper on True Price, and TBO keeps a margin | B | 0:30 | hides the arithmetic |
| 4 | Book Remix live: a part fails, a SAME twin takes over | B | 0:30 | Book Remix |
| 5 | Gap Remix: a product nobody sells, created | C | 0:30 | next gap |
| 6 | Connected Trip: hotel + airport cars + tour, one product | C | 0:30 | book the trip |
| 7 | Trust: approvals queue + held-out matching | A | 0:25 | (A / R keys) |
| 8 | Business case (simulated) | C | 0:25 | pessimistic preset |

## Script

**1 (A).** "Meera, an agent in Surat, searches Burj Khalifa: six listings from six suppliers." Press Space. "Variant DNA: four products, and it shows exactly how they differ: slot, lounge, cancellation. That's the foundation: we know when two things are the SAME. Now watch what that lets TBO do."

**2 (B).** Remix Studio opens on the **Helicopter Tour with private hotel pickup**. The engine chose it by rule: the publishable Remix with the largest rupee saving.
- "Kestrel sells this as one package: ₹65,940 for two; True Price ₹67,341."
- "Remix splits it into parts other suppliers already sell: Bulbul's ticket ₹46,380, a Mynah car out ₹1,960, a Sunbird car back ₹1,700. Three suppliers, and no single supplier sells this combination."
- Point at the green checks: "SAME on every field the package states, never a VARIANT. If the package promises 'private' and no part says so, it isn't built."
- Point at the funnel: "30 multi-part products. 17 can be rebuilt identically, 10 are cheaper, and **4 pass every guardrail**. The package wins 7 times, and we show those too."

**3 (B).** Press Space for the arithmetic.
- "On True Price, not sticker: the agent pays ₹59,329 instead of ₹67,341, saving **₹8,011 (11.9%)**."
- "TBO's expected cost is ₹51,099, including every part's price-change and failover risk, plus the risk of unwinding. TBO keeps **₹7,977 (13.5%)**."
- "The split is a setting on the right; so are the guardrails." Drag *Minimum TBO margin* past 14%: it turns red and is blocked. Reset.

**4 (B).** Key 4, then Space.
- Riskiest part first: "Transfer out via Mynah failed → SAME transfer out via Heron, confirmed. Whole trip confirmed."
- "Seed 22 is the first seed that shows a failover, and it says so on screen."
- Press **Run 1,000×**: "Over a thousand draws the Remix confirms cleanly 82% of the time. 7% need unwinding, and then TBO buys the package, so the client still travels. We report that: the sandbox secures 93.0% against our 95.7% estimate."

**5 (C).** Key 5, Gap Finder.
- "Agents searched for the **Dubai Dolphinarium, standard seat, with private pickup from Deira** 86 times in 90 days, and nobody sells it."
- "Remix builds it from three suppliers. Against booking the pieces yourself (₹9,425 True Price), the agent saves 4.9% and TBO keeps 5.2%."
- Press Space to step through the next gaps: "18 of 78 searched-for gaps pass every guardrail."

**6 (C).** Key 6: the golden-case hotel, Hyatt Place Baniyas Square, with the Connected Trip card on top.
- "The hotel ranked #1 on True Price, airport cars both ways, and the helicopter Remix. One price, ₹83,146, against ₹93,438 booked separately."
- Then the honest part: "**It's blocked.** Four independent parts multiply to a 92.9% Promise, under our 95% floor. Remix doesn't sell it, and the slider shows what it would take."
- Press Space: the trip books, and the car fails over to a SAME twin.

**7 (A).** Key 7, Ops → Remix approvals.
- "Nothing is sold until a person approves it: recipe, suppliers, margin, Promise, cancellation."
- Press **A** on the top card: "Logged, and reversible with undo. If a rebuild changes the numbers, it comes back to the queue."
- Scroll to the held-out table: "The matching underneath: hotels 100% precision on held-out brand families. Labels are the generator's, so it's an upper bound, and we say so."

**8 (C).** Key 8.
- "Simulated, and labelled so. 18% of sightseeing searches hit a publishable Remix: about ₹52,000 TBO margin and ₹52,000 agent savings per 1,000 searches."
- Press Space for the pessimistic preset: "Transfers dearer, parts failing 1.5× as often. Margin halves to ₹29,000, and the Remixes that survive are the ones with wide gaps."

## Fallbacks
- **Laptop slow or the server not up:** the screens still load from the prebuilt data in `data/build` (no network). Say the numbers from this page.
- **Book Remix shows a different story:** the seed on screen is the scenario. Press **Book Remix** again for seed 22, or say "fresh seed, fresh draw: that's the point".
- **Someone changed a guardrail:** the "Reset to defaults" link is under the sliders.
- **Approvals already decided from a rehearsal:** undo from the decision log, or delete `data/build/remix_approvals.jsonl` before going on stage.
- **Asked about supplier naming ("RP Room", "Radisson Room"):** open **Supplier Sheets** and press **Try Weaver's sheet** (or Space). "HP Dubai Baniyas Square" resolves to Hyatt Place Dubai Baniyas Square ("HP read as Hyatt Place"), with the hotel's name struck out of each room name. Filter **Needs a person** to show what isn't guessed.
- **Asked where the old hotel beats went:** the True Price flip and "Book both" on the hotel page still work at `/hotels/demo?tp=1&book=1`.
