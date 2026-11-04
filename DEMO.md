# DEMO: 4-minute shot list (DRAFT, M3)

> **Status:** every number below is computed by the M3 pipeline:
> - 300 real OSM hotels and 6 generated supplier feeds
> - hotel stacks, rooms and sightseeing variants predicted by the Twin Finder (no generator truth on screen)
> - Promise from the 24,000-attempt booking log
>
> Only the simulator (beat 7, lower half) is still mock until M5. Final numbers are filled in at M7.

Run `python start.py --demo`, open http://localhost:8000.
- Press `.` to show the presenter step indicator.
- **Keys 1–7** jump to each beat with its state loaded.
- **Space** fires the beat's one action.
- **←/→** step between beats.

Nothing depends on typing.

| Key | Beat | Who | ~Time | Space does |
|---|---|---|---|---|
| 1 | Today: 135 listings, duplicates scattered through the price list | C | 0:20 | → SameSame |
| 2 | Stacks: 31 hotels, **104 duplicates collapsed**; look-alike trap | A | 0:35 | → back to Today |
| 3 | Hotel detail: Before/After enrichment, then **True Price flip** | B | 0:50 | flips True Price |
| 4 | Book both: one failover to a SAME twin, one first-time confirm | B | 0:35 | Book both |
| 5 | Sightseeing: 9 Floating Market listings → 3 variants, DNA strip | A | 0:30 | groups variants |
| 6 | Ops queue: a model near-miss, caught | A | 0:25 | (S/V/D keys) |
| 7 | Blind-set precision / recall, then the simulator (mock until M5) | C | 0:25 | pessimistic preset |

## Beat notes

**1 → 2 (C, then A).**
1. Set the scene: "Meera in Surat searches Bangkok, within 500 m of Asok BTS, 4★ and up. Today she sees 135 cards from six suppliers."
2. Press Space. The cards fly into stacks: "31 hotels. 104 duplicates gone. Nobody told the model which listings match; it worked it out from names, coordinates, phones and photos."
3. Point at the red pair: "Citadines Sukhumvit 16 and Citadines Sukhumvit 8. Same brand, but they're 537 m apart, while 95% of one hotel's listings sit within 110 m. They have different phones and a different branch. A never-merge rule makes this structural, not a coin flip."

**3a: Before/After (A, ~10 s).**
1. On Radisson Blu Plaza (key 3), click **Before · Kestrel only**: 1 image and 5 amenities.
2. Click **After · golden record**: 8 de-duplicated images and 14 amenities.
3. Hover the stars: "Kestrel says 3.5★. Every fact shows who said it and how much we trust them, and trust is measured: Mynah agrees with the majority 97% of the time, Bulbul 69%."
4. Scroll to the rooms: "`SUP 1KG`, `Superior Room, 1 King Bed`, `SUPERIOR KING` are one room. The percentage is how sure the parser is."

**3b: True Price (B).**
1. "Kestrel is cheapest at ₹18,600."
2. Press Space. The board flips and the rows reorder.
3. "On True Price it's 3rd: ₹23,926.
   - Room only, so ₹3,360 of breakfast at the catalogue median.
   - Non-refundable, so ₹1,674 of cancellation risk.
   - Kestrel reprices at booking 18% of the time at this lead time, measured on 2,555 of our own attempts.

   Mynah's breakfast offer at ₹20,100 is really ₹20,763, and it's 1st."
4. **The sticker price lies. True Price doesn't.**

**4: Book both (B).**
1. "The Shah family took the cheapest sticker. The Patels took our pick." Press Space.
2. Kestrel is sold out at booking. It fails over to the SAME twin via Sunbird (same room, room only, no worse cancellation) and confirms at ₹19,200. Mynah confirms first time.
3. Click **Run 1,000×**: "Kestrel needed rescuing 19% of the time, Mynah 2%."
4. Say plainly that seed 1 is the first seed tried.

**5: Sightseeing (A).**
1. "Nine 'floating market' tours from six suppliers." Press Space: they group into 3 variants, read from the supplier text alone.
2. The glowing segments are the differences:
   - shared pickup vs meeting point vs private car
   - no meals vs lunch
   - 6 h vs 4.5 h vs 8 h
3. "Keyword search finds hotel pickup on 2 of these listings. Variant DNA knows it's 6."
4. Click **Rooftop SkyWalk** to show the honest edge case: one Kestrel ticket doesn't say which slot it sells. It's kept apart and sent to review, not guessed.

**6: Ops (A).**
1. "Sofitel Bangkok Sukhumvit and 'Paradox Krungthep Sukhumwit': two different hotels 73 m apart, one name in a romanisation the model never trained on. The model leaned SAME at 0.86. Our auto-merge bar is 0.90, so it came here instead of into a booking."
2. Press **D**: "Caught. The label trains the next build and acts as a cannot-link. It's reversible with U."

**7: Metrics (C).**
1. Point at the blind-set panel on the Simulator page: "These are held-out brand families the model never saw, frozen before we looked: 77 hotel pairs, 40 room pairs, 30 activity pairs. Precision is 100% on all three; recall is 100% for hotels and rooms and 87% for activities. Across the whole catalogue, 0 of 74 real look-alike pairs were merged."
2. Then the caveat, unprompted: "We wrote the generator too, so read this as an upper bound. C is hand-labelling the blind set as an independent check."
3. Then the simulator: press Space for the pessimistic preset. _(Closed-form placeholder, labelled MOCK; the real one comes in M5.)_

## Fallbacks
- **Live step fails:** every beat is a URL; press its number key to reload it in its starting state.
- **Book both misbehaves:** Run 1,000× shows the distribution without animation.
- **Laptop dies:** a second laptop has run `python start.py --demo` beforehand. The backup hosted URL comes in M7.
- **Ops queue already labelled from a rehearsal:** press U to undo, or delete `data/build/review_labels.jsonl` before going on stage.
