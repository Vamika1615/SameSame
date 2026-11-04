# DEMO: 4-minute shot list (DRAFT, M3 + review)

> **Status:** every number below is computed by the pipeline:
> - hotel stacks, rooms and sightseeing variants predicted by the Twin Finder, scored **out-of-fold**: no hotel is scored by a model that saw its labels
> - Promise from the 24,000-attempt booking log
> - real Wikimedia photos where licensed, stock photos labelled as stock
>
> Only the simulator (beat 7, lower half) is still mock until M5. Final numbers come at M7.

Run `python3 start.py --demo`, open http://localhost:8000.
- Press `.` to show the presenter step indicator.
- **Keys 1–7** jump to each beat with its state loaded.
- **Space** fires the beat's one action.
- **←/→** step between beats.

Nothing depends on typing.

| Key | Beat | Who | ~Time | Space does |
|---|---|---|---|---|
| 1 | Today: 135 listings, duplicates scattered through the price list | C | 0:20 | → SameSame |
| 2 | Stacks: 36 hotels, **99 duplicates collapsed**; look-alike trap | A | 0:35 | → back to Today |
| 3 | Hotel detail: Before/After enrichment, then **True Price flip** | B | 0:50 | flips True Price |
| 4 | Book both: one failover to a SAME twin, one first-time confirm | B | 0:35 | Book both |
| 5 | Sightseeing: 9 Floating Market listings → 3 variants, DNA strip | A | 0:30 | groups variants |
| 6 | Ops queue: a model near-miss, caught | A | 0:25 | (S/V/D keys) |
| 7 | Held-out precision / recall, then the simulator (mock until M5) | C | 0:25 | pessimistic preset |

## Beat notes

**1 → 2 (C, then A).**
1. Set the scene: "Meera in Surat searches Bangkok, within 500 m of Asok BTS, 4★ and up. Today she sees 135 cards from six suppliers."
2. Press Space. The cards fly into stacks: "36 hotels. 99 duplicates gone. Every stack you see was scored by a model that never saw that hotel's labels; it worked from names, coordinates, phones and photos."
3. Point at the red pair: "Citadines Sukhumvit 16 and Citadines Sukhumvit 8. Same brand, but they're 552 m apart, while 95% of one hotel's listings sit within 90 m. They have different phones and a different branch, and a never-merge rule makes this structural."
4. If asked about the photos: "Real Wikimedia photos. The badge says whether it's this hotel or a stock photo of a room elsewhere, and hovering shows the credit."

**3a: Before/After (A, ~10 s).**
1. On Radisson Blu Plaza (key 3), click **Before · Kestrel only**: 1 image and 5 amenities.
2. Click **After · golden record**: 13 amenities.
3. Hover the stars: "Kestrel says 3.5★. Trust is measured: Hornbill agrees with the majority 99% of the time, Bulbul and Sunbird 72%."
4. Scroll to **Reference data**: "And here is the real OpenStreetMap record we matched it to, 2 m from our merged location."

**3b: True Price (B).**
1. "Kestrel is cheapest at ₹18,600." Press Space.
2. "On True Price it's 3rd: ₹23,671.
   - ₹3,120 of breakfast at the catalogue median.
   - ₹1,674 of cancellation risk.
   - Kestrel reprices at booking 19% of the time, measured on 2,510 of our attempts.

   Mynah's ₹20,100 breakfast offer is really ₹20,794, and it's 1st."
3. **The sticker price lies. True Price doesn't.**

**4: Book both (B).**
1. Press Space. Kestrel's price changes ₹18,600 → ₹20,860, so the booking fails over to the SAME twin via Heron and confirms at ₹19,140. Mynah confirms first time.
2. Click **Run 1,000×**: "Kestrel needed rescuing 21% of the time, Mynah 1.4%."
3. Say plainly that seed 1 is the first seed tried.

**5: Sightseeing (A).**
1. "Nine 'floating market' tours." Read the Wikipedia line at the top: real context.
2. Press Space: 3 variants, read from supplier text alone. The glowing segments are the differences: meeting point vs shared pickup vs private car, no meals vs lunch, 4.5 h vs 6 h vs 8 h.
3. "Keyword search finds hotel pickup on 2 listings. Variant DNA knows it's 6."
4. Click **Rooftop SkyWalk**: one Kestrel ticket doesn't say which slot it sells, so it's kept apart and sent to review.

**6: Ops (A).**
1. "Two different hotels, both listed as plain 'Citadines', 832 m apart. The model scored them SAME at 0.993, a hair under our 0.994 auto-merge bar, so they came here instead of into a booking."
2. Press **D**: "Caught. The label trains the next build and acts as a cannot-link. It's reversible with U."

**7: Metrics (C).**
1. Point at the panel on the Simulator page: "Held-out brand families the model never trained on: 79 hotel pairs, 40 room pairs, 30 activity pairs. Precision is 100% on all three; recall is 95%, 90% and 100%. Across the whole catalogue, 0 of 68 real look-alike pairs were merged, and every one was scored out-of-fold."
2. Then the caveat, unprompted: "We wrote the generator too, and we saw these totals while building, so this is held-out, not blind. C's hand labels are the independent check."
3. Then the simulator: press Space for the pessimistic preset _(mock until M5)_.

## Fallbacks
- **Live step fails:** every beat is a URL; press its number key to reload it in its starting state.
- **Book both misbehaves:** Run 1,000× shows the distribution without animation.
- **Laptop dies:** a second laptop has run `python start.py --demo` beforehand. The backup hosted URL comes in M7.
- **Ops queue already labelled from a rehearsal:** press U to undo, or delete `data/build/review_labels.jsonl` before going on stage.
