# DEMO: 4-minute shot list (DRAFT, M1)

> **Status:** the numbers below come from the M1 engine on **mock inputs** (`backend/samesame/mock.py`): the True Price, ranking, filter counts and booking outcomes are computed, but supplier profiles and offers are hand-written. They will change when M2–M4 swap in generated feeds and the fitted Promise model. Final numbers are filled in at M7.

Run `python start.py --demo`, open http://localhost:8000. Press `.` to show the presenter step indicator. **Keys 1–7** jump to each beat with its state loaded, **Space** fires the beat's one action, and **←/→** step between beats. Nothing depends on typing.

| Key | Beat | Who | ~Time | Space does |
|---|---|---|---|---|
| 1 | Today: 37 listings, duplicates scattered through the price list | C | 0:20 | → SameSame |
| 2 | Stacks: 12 hotels, **25 duplicates collapsed**; look-alike trap | A | 0:35 | → back to Today |
| 3 | Hotel detail: Before/After enrichment, then **True Price flip** | B | 0:50 | flips True Price |
| 4 | Book both: one failover to a SAME twin, one first-time confirm | B | 0:35 | Book both |
| 5 | Sightseeing: 9 Floating Market listings → 3 variants, DNA strip | A | 0:30 | groups variants |
| 6 | Ops queue: a real model error, caught | A | 0:25 | (S/V/D keys) |
| 7 | Simulator: lift under default and pessimistic assumptions | C | 0:25 | pessimistic preset |

## Beat notes

**1 → 2 (C, then A).** "Meera in Surat searches Bangkok, near Asok, for a family. Today she sees 37 cards. Count the Novotels." Space. Cards fly into stacks: "12 hotels. 25 duplicates gone." Point at the red pair: "Citadines Sukhumvit 16 and Citadines Sukhumvit 8. Same chain, similar names, one supplier even calls the first 'Citadines Sukhumvit Bangkok'. We keep them apart: 551 m apart, different phone, different soi. Both pins on the map." Point at a chip such as "why: 384 m from Asok BTS · Booked 41× by Indian agents".

**3a: Before/After (A, ~10 s).** On the Novotel page, click **Before · Kestrel only**: 1 image, 3 amenities, 4-word description. Click **After · golden record**: 5 images, 13 amenities, merged description. Hover the address: "every fact shows which supplier said it and how much we trust them."

**3b: True Price (B).** "Kestrel is cheapest at ₹18,600." Space: the board flips and rows reorder. "On True Price it's 7th: ₹23,912. Room only, so ₹3,300 of breakfast; non-refundable, so ₹1,674 of cancellation risk; Kestrel changes price 18% of the time at 21 days. Mynah's breakfast offer at ₹20,100 is really ₹20,744, and it's 1st." **The sticker price lies. True Price doesn't.** Hover any term to show its assumption.

**4: Book both (B).** "The Shah family insisted on the sticker price; the Patels took our pick." Space. Kestrel: price changed ₹18,600 → ₹20,860, failed over to the SAME twin via Heron, confirmed at ₹19,400. Mynah confirmed first time. Then click **Run 1,000×**: "One draw proves nothing. Over 1,000 seeds Kestrel needed rescuing 23.8% of the time, Mynah 1.7%." Say plainly that the scenario seed is 1, the first seed tried.

**5: Sightseeing (A).** "Nine 'floating market' tours from six suppliers." Space: they group into 3 variants. The glowing segments are the differences: shared pickup vs meeting point vs private car; no meals vs Thai lunch; 6 h vs 4.5 h vs 8 h. Click the **Grand Palace** chip to show standard vs skip-the-line vs English guide.

**6: Ops (A).** "This pair scored 0.81 SAME: both are Novotels on Sukhumvit, 1,468 m apart. That's under our 1.5 km rule, so only the precision-first threshold kept it out of an auto-merge." Press **D**: "Model error caught. The label goes into training data and is reversible."

**7: Simulator (C).** Sliders are the assumptions. Space for the pessimistic preset: the lift shrinks but holds. _(M1: closed-form placeholder, labelled MOCK on screen; real 50,000-session simulator in M5.)_

## Fallbacks
- **Live step fails:** every beat is a URL; press its number key to reload it in its starting state.
- **Book both misbehaves:** Run 1,000× shows the distribution without animation.
- **Laptop dies:** a second laptop has run `python start.py --demo` beforehand. The backup hosted URL comes in M7.
