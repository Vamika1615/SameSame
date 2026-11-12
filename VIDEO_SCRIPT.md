# VIDEO SCRIPT: Canon, a solution to Track 2 (about 6 minutes, one narrator)

Every number below is computed by the app, not typed in. If a rebuild moves a number, say what the screen says.

## The problem statement, and where the video answers it

| TBO's Track 2 brief asks us to… | Scene |
|---|---|
| improve inventory quality and product matching across suppliers | 2, 3 |
| **Hotels:** identify and consolidate duplicate hotel listings across suppliers | 2, 3 |
| …map equivalent room types | 2, 5 |
| …enrich property content and images | 5 |
| …compare bookable options on price, availability, cancellation, payment terms and supplier reliability | 4 |
| **Sightseeing:** match equivalent tours while keeping different inclusions (transfers, meals, options, duration, access, cancellation) | 6 |
| optimise listing-page ranking | 3, 6 |
| **Objective:** increase price competitiveness and booking conversion | 4, 8 |

**One line to remember:** *every supplier sheet, one clean catalogue. Then the clean catalogue sells better.*

## Before you record
1. Run `python3 start.py --demo` and open http://localhost:8000, in a browser window about 1440 px wide at 100% zoom.
2. **Delete `data/imports/`** first, so the catalogue starts with no imports and the sample imports fresh.
3. Don't press S, V or D on *Uncertain matches → Between supplier listings*: those keys save training labels (press U to undo).
4. Record each scene as its own clip.

---

## Scene 1: The problem (0:00–0:30)
**Do:** Open the home page, then **Catalogue → Agent search** and click **As suppliers list them**. Scroll.

**Say:**
> "TBO buys the same hotels and tours from many suppliers. Each one sends its own rate sheets, in its own layout, and names the same hotel and room its own way. Here's one search in Deira: 86 listings. Which are the same hotel? Which deal is really cheapest? Which supplier will actually honour it?
>
> Canon answers that: every supplier sheet, one clean catalogue."

## Scene 2: Import a supplier's rate sheet (0:30–1:45)
*Answers: product matching, consolidating duplicates, mapping room types*

**Do:**
1. Go to **Catalogue → Import sheets** and click **Plover's sheet**. Point at the summary.
2. Open **Hyatt Place Dubai Baniyas Square** and show its rooms.
3. Open **WF Hotel**, click **White Fort Hotel**, then **Add to catalogue**.
4. Point at the **Terms on the sheet**.

**Say:**
> "This is how supplier rates really arrive: a price grid. A block per hotel, seasons across, Sun–Wed and Thu–Sat prices, a code per room, two tabs for two rate plans, and the terms hidden in footnotes. This sample is synthetic, but it uses the same layout as real contracts.
>
> Canon reads all of it: **432 rates across 5 hotels**. Three are hotels we already sell, matched by name. Their rooms map to ours: code SK1S is our Superior King, DT2P our Deluxe Twin with pool view.
>
> 'WF Hotel' is a short code. Canon reads it as White Fort, but with no location in the sheet it won't decide alone, so I confirm it. Logged, and reversible. And one hotel isn't in our catalogue at all, so it's added as new.
>
> The footnotes become terms an agent can use: 5% off for one to four nights, mark up 20%, a $60 fee if the minimum stay isn't met. Add to catalogue, and it's live."

## Scene 3: One catalogue (1:45–2:35)
*Answers: consolidating duplicates, ranking*

**Do:**
1. Go to **Catalogue → All hotels** and click **With sheet rates**.
2. Go to **Agent search** and click **One card per hotel**.
3. Point at **Looks the same, isn't**, then hover **why** on the #1 card.

**Say:**
> "The catalogue now holds **320 hotels**: the six suppliers' 1,267 listings consolidated, plus the hotel the sheet added. Five carry Plover's contracted rates.
>
> In that same Deira search, 86 listings become **20 real hotels**. It matches on name, location, phone, address and photos together. And it knows what *not* to merge: these two Flora hotels are 198 metres apart with different phones, so they stay separate.
>
> The ranking explains itself: Best Western is first on True Price, a supplier that honours 95% of bookings, and 379 metres from the metro."

## Scene 4: Compare what a booking really costs (2:35–3:35)
*Answers: comparison on price, availability, cancellation, payment terms and supplier reliability; price competitiveness*

**Do:**
1. Open **Hyatt Place Dubai Baniyas Square** and turn on **Rank by True Price**.
2. Click the **Sheet rates** tab.
3. Go back to **Offers** and click **Book both**.

**Say:**
> "One hotel, 11 offers from 6 suppliers, with every column the brief names. On sticker, Kestrel's **₹18,600** looks best. But it's non-refundable, has no breakfast, and Kestrel honours only 73% of bookings. On **True Price** (sticker plus missing breakfast, cancellation risk, price-change risk and failed-booking risk) it drops to **4th, at ₹24,175**. Mynah's ₹20,100 with breakfast and free cancellation is really best, at **₹20,773**.
>
> And here are the rates we just imported, on this hotel's own rooms, right next to the supplier offers.
>
> Book both: Kestrel's booking fails, so it moves to **the identical room from Sunbird at ₹19,230**, never a different room. Mynah confirms first time."

## Scene 5: Rooms and content (3:35–3:55)
*Answers: map room types, enrich content*

**Do:** Click the **Rooms** tab, then **About the hotel** and toggle **Before / After**.

**Say:**
> "Every supplier names rooms differently ('SUP 1KG', 'Superior Room, 1 King Bed', 'SUPERIOR KING'): one room type. And the hotel's details are merged: Kestrel alone gives 4 amenities, the combined record 13."

## Scene 6: Tours: the same tour isn't always the same product (3:55–4:35)
*Answers the sightseeing brief*

**Do:**
1. Go to **Catalogue → Tours** and pick **Desert Safari**.
2. Click **As suppliers list them**, then **Grouped by product**.
3. Click the **Hotel pickup** chip.

**Say:**
> "Nine desert-safari listings. Not nine products, and not one: **three**. Canon reads each listing's pickup, meals, duration, access, option and cancellation. The glowing parts are what differs: the cheapest has no dinner and is non-refundable. Identical listings are merged, and the differences stay visible.
>
> Filters understand it too: **9 listings include hotel pickup**, while a keyword search finds 4."

## Scene 7: People decide the rest (4:35–5:00)
**Do:**
1. Go to **Catalogue → Uncertain matches** and show both tabs.
2. Go to **Insights → Business case** and scroll to **How accurately duplicates are found**.

**Say:**
> "Canon decides alone only when it's sure. Everything else waits for a person, whether it comes from an imported sheet or from supplier listings, and every decision can be undone.
>
> On brands the model never trained on, duplicate detection is **100% precise** for hotels, rooms and tours, and none of 42 real look-alike pairs were merged. We built both sides, so treat that as an upper bound."

## Scene 8: What a clean catalogue makes possible (5:00–5:40)
*Answers: price competitiveness*

**Do:** Go to **Bundles → Rebuild packages** and click **Book bundle**.

**Say:**
> "Because Canon knows exactly what is the same, it can rebuild a supplier's package from other suppliers' parts. Kestrel sells this helicopter tour with private pickup at a True Price of ₹67,341. The identical bundle costs the agent **₹59,329**, saving **nearly 12%**, and TBO keeps **13.5%**. A car fails while booking, and the identical car from another supplier takes over.
>
> Only 4 of 30 packages pass every rule, and where the supplier's package is cheaper, we say so."

## Scene 9: Close (5:40–6:00)
**Do:** Return to the home page.

**Say:**
> "Against TBO's brief: duplicates consolidated, rooms mapped, content enriched, offers compared on what they really cost, tours matched without losing what makes them different, and rankings that explain themselves. All of it starts from the sheets suppliers already send.
>
> Canon: every supplier sheet, one clean catalogue."

---

## 3-minute cut
Keep scenes **1, 2, 3, 4, 9**, and give tours a single line in scene 3: "Tours too: nine safari listings, three products."

## Things not to say
- Don't quote the "+32% bookings" chart on Business case; it's a labelled placeholder.
- Don't show or name TBO's real rate sheets on camera. If asked, say the reader was tested locally on real sample sheets, which are not in the product.
- Don't call the data real: hotels, attractions and photos are real; suppliers, prices and sample sheets are synthetic.
