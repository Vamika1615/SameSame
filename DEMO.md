# DEMO: 4-minute shot list (DRAFT, M2)

> **Status:** the numbers below are computed on the **M2 synthetic supplier layer** (300 real OSM hotels, 6 generated supplier feeds, 24,000-attempt booking log; see [DATA.md](DATA.md)).
> - Hotel clusters and room mappings are still generator truth until the M3 matcher.
> - Beats 6 and 7 still run on M1 mock inputs (labelled on screen).
> - Numbers will move again in M3–M5; final numbers are filled in at M7.

Run `python start.py --demo`, open http://localhost:8000.
- Press `.` to show the presenter step indicator.
- **Keys 1–7** jump to each beat with its state loaded.
- **Space** fires the beat's one action.
- **←/→** step between beats.

Nothing depends on typing.

| Key | Beat | Who | ~Time | Space does |
|---|---|---|---|---|
| 1 | Today: 131 listings, duplicates scattered through the price list | C | 0:20 | → SameSame |
| 2 | Stacks: 29 hotels, **102 duplicates collapsed**; look-alike trap | A | 0:35 | → back to Today |
| 3 | Hotel detail: Before/After enrichment, then **True Price flip** | B | 0:50 | flips True Price |
| 4 | Book both: one failover to a SAME twin, one first-time confirm | B | 0:35 | Book both |
| 5 | Sightseeing: 9 Floating Market listings → 3 variants, DNA strip | A | 0:30 | groups variants |
| 6 | Ops queue: a model error, caught (mock pairs until M3) | A | 0:25 | (S/V/D keys) |
| 7 | Simulator: lift under default and pessimistic assumptions (mock until M5) | C | 0:25 | pessimistic preset |

## Beat notes

**1 → 2 (C, then A).**
1. Set the scene: "Meera in Surat searches Bangkok, within 500 m of Asok BTS, 4★ and up. Today she sees 131 cards from six suppliers. Same hotels, spelt six ways: `BAAN SUKHUMVIT SOI 18 BKK`, `Baan Sukhumvit Soi 18`…"
2. Press Space. The cards fly into stacks: "29 hotels. 102 duplicates gone."
3. Point at the red pair: "Citadines Sukhumvit 16 and Citadines Sukhumvit 8. Same brand, and one supplier even drops the soi number. We keep them apart. They're 580 m apart, while 95% of one hotel's listings sit within 100 m. They have different phones and a different branch, and both pins are on the map."
4. Point at the #1 card's chips: "True Price from ₹20,799 · Mynah 97% honoured · 460 m from Asok BTS".

**3a: Before/After (A, ~10 s).**
1. On Radisson Blu Plaza (key 3), click **Before · Kestrel only**: 2 images, 3 amenities, one line of description.
2. Click **After · golden record**: 8 de-duplicated images and 18 amenities.
3. Hover the stars: "Bulbul says 3.5★. Every fact shows which supplier said it and how much we trust them, and trust is measured: Mynah agrees with the majority 99% of the time, Sunbird 80%."

**3b: True Price (B).**
1. "Kestrel is cheapest at ₹18,600."
2. Press Space. The board flips and the rows reorder.
3. "On True Price it's 4th: ₹23,859.
   - Room only, so ₹3,360 of breakfast at the catalogue median.
   - Non-refundable, so ₹1,674 of cancellation risk.
   - Kestrel changes price at booking 19% of the time at this lead time. That's measured on 2,500 of our own booking attempts.

   Mynah's breakfast offer at ₹20,100 is really ₹20,799, and it's 1st."
4. **The sticker price lies. True Price doesn't.** Hover any term to show its assumption.

**4: Book both (B).**
1. "The Shah family insisted on the cheapest sticker. The Patels took our pick." Press Space.
2. Kestrel's price changes ₹18,600 → ₹20,860. The booking fails over to the SAME twin via Sunbird (same room, room only, no worse cancellation) and confirms at ₹18,930. Mynah confirms first time.
3. Click **Run 1,000×**: "One draw proves nothing. Over 1,000 seeds Kestrel needed rescuing 31% of the time, Mynah 2%."
4. Say plainly that the scenario seed is 1, the first seed tried.

**5: Sightseeing (A).**
1. "Nine 'floating market' tours from six suppliers." Press Space: they group into 3 variants.
2. The glowing segments are the differences:
   - shared pickup vs meeting point vs private car
   - no meals vs Thai lunch
   - 6 h vs 4.5 h vs 8 h
3. "Keyword search finds hotel pickup on 2 of these listings. Variant DNA knows it's 6."
4. Click the **Grand Palace** chip to show standard vs skip-the-line vs English guide.

**6: Ops (A).** "This pair scored 0.81 SAME. Both are Novotels on Sukhumvit, 1,468 m apart. That's under our 1.5 km rule, so only the precision-first threshold kept it out of an auto-merge." Press **D**: "Model error caught. The label goes into training data and is reversible." _(M1 mock pair; M3 replaces it with the matcher's real gray zone.)_

**7: Simulator (C).** Sliders are the assumptions. Space for the pessimistic preset: the lift shrinks but holds. _(Closed-form placeholder, labelled MOCK on screen; the real 50,000-session simulator comes in M5.)_

## Fallbacks
- **Live step fails:** every beat is a URL; press its number key to reload it in its starting state.
- **Book both misbehaves:** Run 1,000× shows the distribution without animation.
- **Laptop dies:** a second laptop has run `python start.py --demo` beforehand. The backup hosted URL comes in M7.
