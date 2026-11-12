# DEMO: Canon, 4 minutes, 3 presenters (Dubai)

> Every number below is computed by the app from synthetic suppliers over real OpenStreetMap hotels and real Dubai attractions; nothing is typed in. If a rebuild moves a number, the screen is right and this page is stale.
>
> One line to remember: **"Every supplier sheet, one clean catalogue."**

Run `python3 start.py --demo` and open http://localhost:8000. Before going on stage, delete `data/imports/` so the catalogue starts with no imports.
- Press `.` for the step indicator.
- **Keys 1–8** jump to a beat.
- **Space** fires the beat's one action.
- **←/→** step between beats.

| Key | Beat | Who | ~Time | Space does |
|---|---|---|---|---|
| 1 | Import a supplier's rate sheet | A | 0:45 | imports the Plover sample |
| 2 | 86 listings become 20 hotels | A | 0:30 | one card per hotel |
| 3 | Offers compared on True Price | B | 0:30 | toggles True Price |
| 4 | Book both: a failed booking fails over | B | 0:20 | Book both |
| 5 | Tours: same tour, different product | C | 0:30 | grouped by product |
| 6 | Uncertain matches go to a person | C | 0:20 | (click to decide) |
| 7 | Bundles: what a clean catalogue makes possible | B | 0:30 | shows the arithmetic |
| 8 | Business case and matching quality | C | 0:15 | pessimistic preset |

## Script

**1 (A). Import.** Key 1, then Space.
- "Suppliers send TBO rate sheets like this one: a price grid, a block per hotel, seasons across, Sun–Wed and Thu–Sat columns, a code per room, two tabs for two rate plans, terms in the footnotes. Synthetic, in the layout real contracts use."
- Point at the summary: "**432 rates, 5 hotels.** Three are hotels we already sell, matched by name. One, 'WF Hotel', is a short code, so a person decides. One isn't in our catalogue at all."
- Open **WF Hotel**, click **White Fort Hotel**: "Decided, logged, reversible." Then **Add to catalogue**.
- Open Hyatt Place's rooms: "Every room maps by tier, bed and view: SK1S is our Superior King. The footnotes became terms: 5% off for 1–4 nights, mark up 20%, a $60 minimum-stay fee."

**2 (A). One catalogue.** Key 2.
- "The six suppliers we already have list this one area **86 times**." Space: "**20 real hotels.** It matches on name, location, phone, address and photos together."
- Point at **Looks the same, isn't**: "Two Flora hotels, 198 m apart, different phones and streets: kept apart, because merging them sends a guest to the wrong building."

**3 (B). True Price.** Key 3.
- "Hyatt Place, 11 offers from 6 suppliers: price, availability, cancellation, payment terms, reliability."
- Space: "Kestrel's ₹18,600 looks cheapest but is non-refundable, without breakfast, from a supplier that honours 73% of bookings. On True Price it's **4th at ₹24,175**; Mynah's ₹20,100 with breakfast is really the best deal at **₹20,773**."
- Click the **Sheet rates** tab: "And Plover's contracted rates sit right here, on this hotel's own rooms."

**4 (B). Book both.** Key 4, Space.
- "Kestrel's booking fails, so it moves to **the identical room from Sunbird at ₹19,230**, never a different room. Mynah confirms first time."

**5 (C). Tours.** Key 5, Space.
- "Six Burj Khalifa listings are four products. The glowing parts are what really differs: time slot, lounge, cancellation."

**6 (C). People decide the rest.** Key 6.
- "Anything Canon isn't sure about waits here: hotels and rooms from imported sheets, and supplier listings the matcher couldn't call. Nothing uncertain is ever merged."

**7 (B). Bundles.** Key 7, Space.
- "Because the catalogue knows exactly what is the same, it can do one more thing: rebuild a supplier's package from other suppliers' parts. Helicopter tour: Kestrel's package at a True Price of ₹67,341 becomes **₹59,329**; the agent saves **11.9%**, and TBO keeps **13.5%**. Only 4 of 30 packages pass every rule, and we say so."

**8 (C). Evidence.** Key 8.
- "On brand families the model never trained on, duplicate detection is **100% precise** for hotels, rooms and tours, and 0 of 42 real look-alike pairs were merged. We wrote both sides, so treat that as an upper bound."
- Space for the pessimistic preset (bundle margin roughly halves).

## Fallbacks
- **The import shows "same file: same import":** it was imported before. Remove it on the import page, or delete `data/imports/` before the demo.
- **Laptop slow or server not up:** the screens load from the prebuilt data in `data/build` (no network). Say the numbers from this page.
- **Asked about real TBO sheets:** the reader was tested locally on TBO's sample sheets: AVA Cancún (CSV and a 4-tab workbook), Hard Rock (5 hotels, about 5,100 rates), UNICO and a rotated-grid file. The 2027 AVA sheet attached to the hotel the 2026 sheet created. A contract workbook mixing rack, net and promo columns is refused clearly. None of those files are in the repo or the demo.
- **Someone changed a bundle guardrail:** open **Publish rules** and press "Reset to defaults".
