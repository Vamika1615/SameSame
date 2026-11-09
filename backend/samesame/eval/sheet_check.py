"""Score a Supplier Sheets result against Weaver's answer key (weaver_truth). Weaver's synthetic sample only."""
import polars as pl

from samesame import config, store


def score(result: dict) -> dict:
    """Weaver's sample only: compare what the page decided with the generator's answer key (weaver_truth)."""
    key = {r["row"]: r for r in pl.read_parquet(config.BUILD / "weaver_truth.parquet").to_dicts()}
    truth = {r["listing_id"]: r["hotel_id"] for r in pl.read_parquet(config.BUILD / "hotel_truth.parquet").to_dicts()}
    s = store.get()
    cluster_hotel: dict = {}
    for lid, cid in s.cluster_of.items():
        cluster_hotel.setdefault(cid, []).append(truth[lid])
    cluster_hotel = {c: max(set(hs), key=hs.count) for c, hs in cluster_hotel.items()}
    rt = {r["supplier_room_id"]: r["room_id"] for r in pl.read_parquet(config.BUILD / "room_truth.parquet").to_dicts()}
    room_votes: dict = {}
    for sr, r in s.supplier_rooms.items():
        room_votes.setdefault(r["room_id"], []).append(rt[sr])
    room_truth = {c: max(set(v), key=v.count) for c, v in room_votes.items()}
    h = {"matched_right": 0, "matched_wrong": 0, "new_right": 0, "new_wrong": 0, "review": 0, "review_top_right": 0}
    r_ = {"mapped_right": 0, "mapped_wrong": 0, "person": 0, "new": 0}
    for x in result["hotels"]:
        k = key[x["rows"][0]]
        top = x["candidates"][0] if x["candidates"] else None
        right_top = top is not None and not k["new_hotel"] and cluster_hotel.get(top["cluster_id"]) == k["hotel_id"]
        if x["decision"] == "matched":
            h["matched_right" if right_top else "matched_wrong"] += 1
        elif x["decision"] == "new":
            h["new_right" if k["new_hotel"] else "new_wrong"] += 1
        else:
            h["review"] += 1
            h["review_top_right"] += right_top or (k["new_hotel"] and top is None)
        for room in x["rooms"]:
            if room["status"] == "mapped":
                r_["mapped_right" if room_truth.get(room["room_id"]) == key[room["rows"][0]]["room_id"] else "mapped_wrong"] += 1
            else:
                r_[room["status"]] += 1
    return {"hotels": h, "rooms": r_, "note": "Checked against the generator's answer key for Weaver's synthetic sample sheet. "
            "The engine above never reads it; only this check does."}
