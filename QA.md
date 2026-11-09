# Q&A: grounded answers

Every answer points at something on screen or in the code. Numbers come from METRICS.md, which is regenerated on every build.

## Remix

**What if one component fails mid-trip?**
At booking, each part goes through the same router as hotels.
- **Price change, sold out or error:** the router rebooks a **SAME twin of that part only**: same ticket DNA and slot, or same route, direction and mode, under no stricter cancellation. Never a VARIANT. (`remix/book.py`, test `test_failover_only_to_same_twins_of_the_failed_part`.)
- **No twin left:** TBO cancels the parts already booked (free cancellations cost only friction, non-refundable ones are lost and counted), then buys the best package so the client still travels. For a gap Remix there is no package, so TBO refunds the agent.

The cost of all this is priced in before the Remix is published, as "assembly risk". Over seeds 1–1,000, the helicopter Remix needs unwinding about 7% of the time; METRICS shows that next to the package's outcomes. **Mid-trip** (after booking, on the day) is supplier operations, which this prototype doesn't simulate; the guarantee is TBO's.

**Do supplier contracts allow bundling?**
Not always, so every part carries `resale_terms`. 313 of the R1 parts are "Package only: not for resale in bundles", which is 35% of Kestrel's rates and 10% of other suppliers'. The engine never uses one, not even as a failover twin (test `test_never_uses_a_package_only_rate`). In production this field comes from the contract, and the approvals queue is where someone checks it.

**Who supports the traveller when three suppliers are involved?**
TBO. The agent sees one product, one price, one Promise and one cancellation rule. TBO holds the supplier relationships, runs the failover and carries the price-change risk; that's why TBO's cost includes those risks and the agent's True Price doesn't. The recipe card names each supplier so ops knows whom to call.

**Isn't this just a package?**
A package is one supplier's bundle. A Remix:
- is assembled by TBO from **different** suppliers' parts;
- is published only when it is the **SAME** experience as an existing package (by Variant DNA), or something agents search for that **nobody sells**;
- is priced on True Price, not sticker.

For each gap Remix, the gap finder checks that no packaged variant is SAME (test `test_gap_remixes_are_new_products...`).

**Why would parts be cheaper than packages?**
Sometimes they aren't, and we show it. A package price includes the packager's bundled transfer and margin.
- **Remix wins** where a standalone transfer costs less than that, mostly private pickups and premium products: helicopter +12%, ski and theme parks with lunch +5–7%.
- **The package wins** where operators pool their own shared transfers: the morning desert safari by ₹4,006, the private desert safari by ₹3,178, the dhow cruise by ₹371. METRICS lists every case.

Part prices come from disclosed tariffs set before any result was seen (DATA.md). Tickets carry no planted discount: their net factor averages ~1.0.

**How is margin vs agent saving decided?**
Remix computes the gap between the best package's True Price and TBO's expected cost of the Remix. The agent gets a configurable share of it (default 50%) and TBO keeps the rest. Guardrails then require all of these:
- the agent saves ≥ 3%;
- TBO's margin is ≥ 4%;
- the Remix Promise is ≥ 95%;
- the car arrives ≥ 20 min before the slot.

All are sliders in Remix Studio, and every verdict recomputes.

**Who approves a Remix?**
The product/supply team, in Ops → Remix approvals. They see the recipe, suppliers, sell price, margin, saving, Promise, cancellation rule and any **unverified** field (one the package doesn't state). The log is append-only, undo appends a row, and each approval snapshots the numbers. If a rebuild changes them, the Remix returns to the queue.

**How do you know the Remix is the SAME product?**
- **Pickup, meals, access and stops** must be equal.
- **Every descriptive field the package states** (option, slot, cancellation) must be equal too. If the package states something no part states, the Remix is a different product. This rule was added when the engine tried to rebuild a *private* desert safari from a *shared* 4x4 ticket.
- **Fields only the Remix states** (where the package is silent) are flagged for the approver.

**Isn't the Remix Promise optimistic?**
Somewhat, and we measure it. The sandbox secures 1–3 points fewer Remixes than estimated, because the estimate assumes parts fail independently and uses each supplier's average reliability. The same rule blocks the Connected Trip: four parts multiply to 92.9%, under the 95% floor.

**Is any of this real data?**
Everything else is synthetic and labelled:
- **Real:** hotel names and locations (OpenStreetMap), attraction names, photos (Wikimedia, credited) and descriptions (Wikipedia).
- **Synthetic:** suppliers, prices, parts, booking logs and agent searches.

The engines learn only from the logs, never from the generator's behaviour table (a test enforces it).

## Supplier naming

**Suppliers send spreadsheets where one hotel is "Radisson Plaza Room", "Radisson Room" or "RP Room". Do you handle that?**
Yes, on the **Supplier Sheets** page. Drop in the sheet (CSV or Excel):
- **Hotel names:** a short code like "RP" is written out from the candidate's name ("RP read as Radisson Plaza") before names are compared. It then goes through the same trained Twin Finder as the catalogue, with distance, phone, stars and address. Above the auto-merge bar it is matched; between the bars a person picks; below it, "new to TBO".
- **Room names:** the hotel's name is removed first ("~~Hyatt Place~~ Superior King"), then the room is read as tier + bed + view and mapped to the hotel's catalogue room. A name that is only the hotel ("Radisson Room") can't be mapped by any rule, so a person picks from a dropdown. It is never guessed.
- **Duplicates inside the sheet:** the same hotel under two names is flagged ("also in this sheet as ...").

On Weaver's synthetic 136-row sheet, 27/27 automatic hotel matches, 4/4 new-hotel calls and 63/63 automatic room mappings are right (METRICS.md). It is synthetic, and we wrote both sides, so that is an upper bound. Real TBO sheets would need the hand-labelling loop the Ops queue already has.

**What if a sheet has no coordinates?**
The model needs distance, so it doesn't guess. The page suggests catalogue hotels by name and sends the hotel to a person.

## Matching and pricing (still apply)

**Your precision is 99.7%: aren't you grading your own homework?**
Partly, and METRICS says so:
- The hotel model is scored out-of-fold and never trains on held-out brand families.
- We wrote both the generator and the matcher, so the numbers are an upper bound.
- The independent check is a teammate's hand labels on the frozen held-out set.

**What is True Price?**
Sticker, plus:
- the cost to fill missing needs;
- cancellation risk;
- price-change risk;
- failure risk (the next SAME twin + friction);
- minus the value of paying later.

The outcomes are mutually exclusive, so nothing is double-counted. Every term shows its assumption.

**Where does supplier reliability come from?**
A hierarchical Beta-binomial fitted on the booking log. Thin cells borrow from the supplier and the market, so a new supplier starts near average. It beats per-cell counts on the last 30 days of the log, and by the most when data is thin.
