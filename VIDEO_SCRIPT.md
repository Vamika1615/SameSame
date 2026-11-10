# VIDEO SCRIPT: Remix, a solution to Track 2 (about 6 minutes, one narrator)

Every number below was read from the running app on 10 Nov 2026 and is computed by the engine, not typed in. If a rebuild moves a number, say what the screen says.

## The problem statement, and where the video answers it

TBO's brief for Track 2, Multi-supplier Inventory, in its own words, mapped to the scene that answers each part:

| The brief asks us to… | Shown in scene |
|---|---|
| **Hotels:** identify and consolidate duplicate hotel listings across suppliers | 2 |
| …map equivalent room types | 4, 5 |
| …enrich property content and images | 4 |
| …compare bookable options on price, availability, cancellation, payment terms and supplier reliability | 3 |
| **Sightseeing:** identify duplicate or equivalent tours across suppliers… | 6 |
| …while distinguishing different inclusions (transfers, meals, options, duration, access, cancellation), without losing meaningful differences | 6 |
| Optimise listing-page ranking for both | 2, 6 |
| **Objective:** increase price competitiveness and drive higher booking conversion | 3, 7, 8 |
| (and make it trustworthy enough to run) | 9 |

**One line to remember:** *the brief asks us to clean up multi-supplier inventory. We do that, and then use the clean inventory to sell better products.*

---

## Before you record

1. Start the stage build: `python3 start.py --demo`, then open http://localhost:8000. If you use dev mode (`python3 start.py`), open http://localhost:5173.
2. Use a browser window about **1440 px wide** at 100% zoom, and hide the bookmarks bar.
3. **Don't press S, V or D on the "Uncertain matches" page.** Those keys save real training labels for the next build. If you do press one, press **U** to undo it.
4. If you press **Approve** on camera, it stays recorded. Afterwards, undo it from the decision log, or delete `data/build/remix_approvals.jsonl`.
5. Record each scene as its own clip; it's easier to retake one than the whole thing.

---

## Scene 1: The problem (0:00–0:35)

**Do:** Open the home page, then go to **Catalogue → Hotels** and click **As suppliers list them**. Scroll slowly.

**Say:**
> "TBO sells hotels and tours from many suppliers at once. The same hotel arrives again and again, under different names, prices and terms. Here's a search near Baniyas Square in Deira: **86 listings**. An agent can't tell which are the same hotel, which deal is really cheapest, or which supplier will actually honour the booking.
>
> TBO's brief asks us to fix exactly this, for hotels and sightseeing: find the duplicates, keep the real differences, compare offers properly, and rank what matters. That's what Remix does. Then it goes one step further."

---

## Scene 2: Duplicates merged, look-alikes kept apart, ranking explained (0:35–1:20)
*Answers: "consolidate duplicate hotel listings", "optimise listing-page ranking"*

**Do:**
1. Click **One card per hotel**. The title changes to **20 hotels from 86 supplier listings**.
2. Point at the red **Looks the same, isn't** card on the right: Flora Al Souq Hotel vs Flora Hotel Apts.
3. Hover **why** on the #1 card, Best Western Plus Pearl Creek.

**Say:**
> "One click: **86 listings become 20 real hotels**, with 66 duplicates merged. It matches on name, location, phone, address and photos together, so it isn't fooled by a renamed listing.
>
> Just as important is what it *doesn't* merge. These two Flora hotels look identical, but they're 198 metres apart, with different phones and different streets. They're kept apart, because merging them would send a guest to the wrong building.
>
> And the ranking explains itself. Best Western is first because of its True Price, a supplier that honours 95% of bookings, and 379 metres from the metro. Every rank is a transparent score, never a black box."

---

## Scene 3: Comparing bookable offers on what they really cost (1:20–2:25)
*Answers: "accurate comparison of bookable options based on price, availability, cancellation, payment terms and supplier reliability". This is the core of the brief: spend the most time here.*

**Do:**
1. Open **Hyatt Place Dubai Baniyas Square**. You can go straight to `/hotels/demo`.
2. On the **Offers** tab, pause on the table: 11 offers from 6 suppliers.
3. Turn on **Rank by True Price**. The rows reorder.
4. Scroll down and click **Book both**.

**Say:**
> "Here's one hotel sold by six suppliers: 11 offers. Every column the brief names is here: price, availability, cancellation, payment terms, and each supplier's reliability.
>
> On sticker price, Kestrel looks best at **₹18,600**. But it's non-refundable, has no breakfast, and Kestrel honours only 73% of bookings at this lead time.
>
> Switch on **True Price**: the sticker plus the client's missing breakfast, the cancellation risk, the risk of a price change and the risk of a failed booking. Kestrel drops to **fourth, at ₹24,175**. Mynah's **₹20,100** offer, with breakfast and free cancellation, is really the best deal at **₹20,773**. Hover any number to see its assumption.
>
> Now let's book both. Kestrel's booking fails, so the system moves it to **the identical room from Sunbird at ₹19,230**. It's never a different room, only an identical one. Mynah confirms first time. That's how a cheaper-looking offer becomes a failed booking, and how we prevent it."

---

## Scene 4: Rooms mapped and content enriched (2:25–2:50)
*Answers: "map equivalent room types", "enrich property content and images"*

**Do:** Click the **Rooms** tab, then the **About the hotel** tab and toggle **Before / After**.

**Say:**
> "Every supplier names rooms differently: 'SUP 1KG', 'Superior Room, 1 King Bed', 'SUPERIOR KING'. They all map to one room type, with a confidence score.
>
> The hotel's details are merged too. Kestrel alone gives us 4 amenities; the combined record has 13, each showing which suppliers said so."

---

## Scene 5: The real-world mess: supplier rate sheets (2:50–3:25)
*Answers: "map equivalent room types" and "product matching", for data as suppliers actually send it*

**Do:**
1. Go to **Catalogue → Supplier sheets** and click **Try Weaver's sheet**.
2. Open the **HP Dubai Baniyas Square** row.
3. Click the **Needs a person** filter.

**Say:**
> "Suppliers send spreadsheets where one hotel is written as 'Hyatt Place', 'HYATT PLACE DXB' or just 'HP', and a room is 'HP SUP KG'. Here's a sample sheet from a made-up supplier: **136 rows, 33 hotel names, 30 real hotels**.
>
> 'HP' is read as Hyatt Place, confirmed by location and phone. In the room names, the hotel's own name is struck out before the room is read.
>
> Checked against the answer key for this synthetic sheet, all 27 automatic hotel matches and all 63 automatic room mappings are correct. Anything it isn't sure of, like a room called just 'Sandras Inn Room', goes to a person instead of being guessed."

---

## Scene 6: Sightseeing: same tour, different product (3:25–4:10)
*Answers: "identify duplicate or equivalent tours… distinguishing transfers, meals, options, duration, access, cancellation… without losing meaningful differences", "ranking"*

**Do:**
1. Go to **Catalogue → Tours** and pick **Desert Safari**.
2. Click **As suppliers list them** (9 listings), then **Grouped by product**.
3. Point at the glowing segments in the colour strip on a card, then click the **Hotel pickup** filter chip.

**Say:**
> "Tours are harder than hotels: there's no industry standard for matching them. Here are **nine desert-safari listings**. They're not nine products and they're not one. They're **three**.
>
> Remix reads each listing into its parts: pickup, meals, duration, access, option and cancellation. The glowing parts are what actually differs. The cheapest option has *no dinner*, lasts four hours and is non-refundable; the next has a BBQ dinner, lasts six hours and offers free cancellation. Identical listings are merged, and the real differences stay visible.
>
> And the filters understand them: **9 listings include a hotel pickup**, but a keyword search of supplier text finds only 4, because suppliers write 'collection from your hotel', not 'pickup'."

---

## Scene 7: Turning clean inventory into a better price (4:10–5:00)
*Answers the objective: "increase price competitiveness and drive higher booking conversion"*

**Do:**
1. Go to **Remix → Rebuild packages**. The Helicopter Tour is selected.
2. Point at the headline comparison.
3. Open **Is it really the same experience?**
4. Click **Book Remix**.

**Say:**
> "Once we know exactly what's the same, we can do something new. This helicopter tour with private pickup is sold by Kestrel as one package, at a True Price of **₹67,341**.
>
> Remix rebuilds the identical experience from parts other suppliers already sell: Bulbul's ticket and cars from Mynah and Sunbird. The agent pays **₹59,329** and **saves ₹8,011, nearly 12%**, and TBO still keeps **₹7,977, a 13.5% margin**.
>
> It's only offered if it's the same experience, field by field. Book it: Mynah's car fails, the identical car from Heron takes over, and the whole trip is confirmed.
>
> And we're honest about it: of 30 packages, only 4 pass every rule, and in 7 the supplier's own package is cheaper, so we say so."

---

## Scene 8: Products nobody sells yet (5:00–5:25)
*Answers: "improve product discoverability" and "conversion"*

**Do:** Go to **Remix → New products**. Dubai Dolphinarium is selected.

**Say:**
> "Agents also search for things nobody sells as one product. The Dubai Dolphinarium with a private pickup from Deira was searched for **86 times** in 90 days, and there are zero packages. Remix builds it: the agent saves about 5% compared with booking the pieces separately, and TBO keeps about 5%. That's **18 new products** from searches TBO already sees."

---

## Scene 9: Why TBO can trust it (5:25–5:55)
*Answers what the CTO and Head of Operations will ask: is it accurate, and who is in control?*

**Do:**
1. Go to **Review → Remix approvals**. Point at a card's **Approve** button, but don't press it.
2. Go to **Insights → Business case** and scroll to **How accurately duplicates are found**.

**Say:**
> "Nothing is sold until a person approves it. Every decision is logged and can be undone, and anything the model isn't sure about comes to a person, never a guess.
>
> On brands the model never trained on, duplicate detection is **100% precise** for hotels, rooms and tours, and **none of 42 real look-alike hotel pairs** were wrongly merged. All supplier data here is synthetic and labelled so, and we built both sides, so treat these numbers as an upper bound."

---

## Scene 10: Close (5:55–6:15)

**Do:** Return to the home page.

**Say:**
> "So, against TBO's brief: duplicates found and consolidated, rooms mapped, content enriched, offers compared on what they really cost, tours matched without losing what makes them different, and rankings that explain themselves. Then we use that clean inventory to make products that are cheaper for the agent and still profitable for TBO.
>
> Remix: new products from parts suppliers already sell."

---

## If you need a 3-minute cut

Keep scenes **1, 2, 3, 6, 7 and 10**, and trim each spoken paragraph to its first sentence or two. In that cut, drop scene 4 and mention rooms in one line during scene 3: "and the rooms are mapped across suppliers, too."

## Things not to say

- **Don't quote the "+32% bookings" figure** on Insights → Business case. That chart is still a labelled placeholder. The Remix figure in the box below it (18% of tour searches matched, about ₹52,000 TBO margin per 1,000 searches) is fine, but say "simulated".
- **Don't claim the demo hotel gains photos** in Before/After; it gains amenities (4 → 13) and a fuller description.
- **Don't call the data real.** Hotels, attractions and photos are real; suppliers, prices and bookings are synthetic.
- **Don't show TBO's real rate sheets** in the video.
