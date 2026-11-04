# DEMO: 4-minute shot list (DRAFT, Dubai)

> **Status:** the demo runs in **Dubai**: real OpenStreetMap hotels, real Wikimedia photos (own or labelled stock) and Wikipedia text. Every number below is computed by the pipeline:
> - stacks, rooms and sightseeing variants are predicted by the Twin Finder, scored out-of-fold
> - Promise comes from the 24,000-attempt booking log
>
> Only the simulator (beat 7, lower half) is still mock until M5. Final numbers come at M7.

Run `python3 start.py --demo` and open http://localhost:8000.
- Press `.` to show the presenter step indicator.
- **Keys 1–7** jump to each beat with its state loaded.
- **Space** fires the beat's one action.
- **←/→** step between beats.

Nothing depends on typing.

| Key | Beat | Who | ~Time | Space does |
|---|---|---|---|---|
| 1 | Today: 84 listings near Baniyas Square, duplicates scattered | C | 0:20 | → SameSame |
| 2 | Stacks: 21 hotels, **63 duplicates collapsed**; look-alike trap | A | 0:35 | → back to Today |
| 3 | Hyatt Place Baniyas Square: Before/After, then the **True Price flip** | B | 0:50 | flips True Price |
| 4 | Book both: one failover to a SAME twin, one first-time confirm | B | 0:35 | Book both |
| 5 | Sightseeing: 9 desert-safari listings → 3 variants, DNA strip | A | 0:30 | groups variants |
| 6 | Ops queue: a model near-miss, caught | A | 0:25 | (S/V/D keys) |
| 7 | Held-out precision / recall, then the simulator (mock until M5) | C | 0:25 | pessimistic preset |

## Beat notes

**1 → 2 (C, then A).**
1. Set the scene: "Meera in Surat has a family flying to Dubai. They want Deira, near Baniyas Square Metro, 4★ and up, breakfast. Today she sees 84 cards from six suppliers. Look at the top: `Best Western Plus Pearl Creek Hotel`, then `BEST WESTERN PLUS PEARL CREEK HTL` two cards later: the same hotel, sold twice."
2. Press Space. "21 hotels. 63 duplicates gone. Every stack was scored by a model that never saw that hotel's labels."
3. Point at the red pair: "Flora Hotel Apts. and Flora Al Souq Hotel. Same brand, 198 m apart, while 95% of one hotel's listings sit within 110 m. They have different phones and different streets. We keep them apart, and both pins are on the map."
4. Point at a photo badge: "Real Wikimedia photos. The badge says whether it's this hotel or a stock photo, and hovering shows the credit."

**3a: Before/After (A, ~10 s).**
1. On Hyatt Place Dubai Baniyas Square (key 3), click **Before · Kestrel only**: 4 amenities and a one-line description.
2. Click **After · golden record**: 13 amenities, credited.
3. "Trust is measured: Mynah agrees with the majority 97% of the time, Bulbul 69%."
4. Scroll to **Reference data**: the real OSM record (15 Al Suq Al Kabeer St, +971 4 404 1234, hyatt.com), matched 13 m from our merged location.

**3b: True Price (B).**
1. "Kestrel is cheapest at ₹18,600." Press Space.
2. "On True Price it's 4th: ₹24,178.
   - ₹3,600 of breakfast at the catalogue median.
   - ₹1,674 of cancellation risk.
   - Kestrel reprices at booking 19% of the time, measured on 2,543 of our attempts.

   Mynah's ₹20,100 breakfast offer is really ₹20,760, and it's 1st."
3. **The sticker price lies. True Price doesn't.**

**4: Book both (B).**
1. Press Space. Kestrel's price changes ₹18,600 → ₹20,860, so the booking fails over to the SAME twin via Sunbird and confirms at ₹19,230. Mynah confirms first time.
2. Click **Run 1,000×**: "At this hotel Kestrel needed rescuing 39% of the time. Mynah, 2%."
3. Say plainly that seed 1 is the first seed tried.

**5: Sightseeing (A).**
1. "Nine desert-safari listings." Read the Wikipedia line at the top for context.
2. Press Space: 3 variants, read from supplier text alone. The glowing segments are the differences:
   - morning dune bashing with sandboarding, no meals, non-refundable
   - evening shared 4x4 with BBQ dinner
   - private 4x4 with BBQ dinner
3. "Keyword search finds hotel pickup on 4 listings. Variant DNA knows it's all 9."
4. Click **Burj Khalifa**: daytime vs sunset prime time vs the SKY VIP lounge. One Kestrel ticket doesn't say which slot it sells, so it's kept apart, sent to review, and ranked last.

**6: Ops (A).**
1. "Two hotels both called just 'Rove', 1.1 km apart, with no branch in the name. The model leaned SAME at 0.9906, a hair under our 0.9907 auto-merge bar, so a person decides."
2. Press **D**: "Different branches. Caught. The label trains the next build. It's reversible with U."
3. If asked about mistakes: "One pair like this did get merged elsewhere in the catalogue; METRICS.md reports it."

**7: Metrics (C).**
1. Point at the panel on the Simulator page: "Held-out brand families the model never trained on: precision is 100% for hotels, rooms and activities. Across the whole catalogue, hotel precision is 99.7%: one real look-alike pair of 42 was merged, the two Roves."
2. Then the caveat, unprompted: "We wrote the generator too, and saw these totals while building, so this is held-out, not blind. C's hand labels are the independent check."
3. Then the simulator: press Space for the pessimistic preset _(mock until M5)_.

## Fallbacks
- **Live step fails:** every beat is a URL; press its number key to reload it in its starting state.
- **Book both misbehaves:** Run 1,000× shows the distribution without animation.
- **Laptop dies:** a second laptop has run `python3 start.py --demo` beforehand.
- **Ops queue already labelled from a rehearsal:** press U to undo, or delete `data/build/review_labels.jsonl` before going on stage.
