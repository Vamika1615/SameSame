"""The synthetic world: six fictional bird-named suppliers and how they really behave.

Everything here is a generator INPUT, written down so it can be inspected and argued with. The app
never reads `BEHAVIOUR` to price anything: the Promise model estimates supplier reliability from the
booking log, which was sampled from this table. The booking sandbox does draw from it, because the
sandbox stands in for the real supplier at booking time.
"""
SUPPLIERS = {"kestrel": "Kestrel", "mynah": "Mynah", "heron": "Heron",
             "bulbul": "Bulbul", "hornbill": "Hornbill", "sunbird": "Sunbird"}

# How each supplier writes its feed. coverage = P(lists a hotel) before star/brand adjustments.
STYLE = {
    "kestrel": dict(coverage=0.80, price=0.94, coord_m=60, centroid_geocode=0.04, phone="digits", phone_missing=0.30,
                    star_half_down=0.30, star_missing=0.05, images=(1, 2), amenity_share=0.25, desc="short", dup_rate=0.03,
                    drop_number=0.08, case="upper", abbreviate=0.7, share=0.30),
    "mynah": dict(coverage=0.70, price=1.00, coord_m=12, centroid_geocode=0.0, phone="intl", phone_missing=0.02,
                  star_half_down=0.0, star_missing=0.0, images=(4, 6), amenity_share=0.85, desc="long", dup_rate=0.0,
                  drop_number=0.0, case="title", abbreviate=0.0, share=0.20),
    "heron": dict(coverage=0.60, price=0.98, coord_m=25, centroid_geocode=0.01, phone="dashed", phone_missing=0.10,
                  star_half_down=0.05, star_missing=0.0, images=(3, 5), amenity_share=0.75, desc="long", dup_rate=0.005,
                  drop_number=0.02, case="title", abbreviate=0.1, share=0.15),
    "bulbul": dict(coverage=0.40, price=1.04, coord_m=40, centroid_geocode=0.02, phone="local", phone_missing=0.15,
                   star_half_down=0.10, star_missing=0.05, images=(2, 4), amenity_share=0.55, desc="medium", dup_rate=0.01,
                   drop_number=0.03, case="title", abbreviate=0.5, share=0.10),
    "hornbill": dict(coverage=0.50, price=1.00, coord_m=20, centroid_geocode=0.0, phone="compact", phone_missing=0.05,
                     star_half_down=0.0, star_missing=0.02, images=(3, 5), amenity_share=0.70, desc="medium", dup_rate=0.0,
                     drop_number=0.04, case="title", abbreviate=0.0, share=0.12),
    "sunbird": dict(coverage=0.45, price=0.97, coord_m=80, centroid_geocode=0.03, phone="intl", phone_missing=0.50,
                    star_half_down=0.15, star_missing=0.10, images=(2, 3), amenity_share=0.45, desc="short", dup_rate=0.01,
                    drop_number=0.25, case="upper", abbreviate=0.2, share=0.13),
}

# Rate plans each supplier sells: (board, refundable_until_days or None, pay_due_days or None, price multiplier)
RATE_PLANS = {
    "kestrel": [("RO", None, None, 1.00), ("BB", None, None, 1.00)],
    "mynah": [("RO", 7, None, 1.05), ("BB", 7, None, 1.05)],
    "heron": [("RO", None, None, 1.00), ("BB", None, None, 1.00)],
    "bulbul": [("RO", 3, 3, 1.04), ("BB", 3, 3, 1.04)],
    "hornbill": [("RO", 7, None, 1.05), ("BB", 7, None, 1.05)],
    "sunbird": [("RO", None, None, 1.00), ("BB", None, None, 1.00)],
}

# The raw words each supplier uses for board and cancellation (keyword search has to cope with these).
RATE_TEXT = {
    "kestrel": {"RO": "RO", "BB": "BB", None: "NRF", "flex": "FC {d}D"},
    "mynah": {"RO": "Room Only", "BB": "Bed and Breakfast", None: "Non-refundable", "flex": "Free Cancellation"},
    "heron": {"RO": "ROOM ONLY", "BB": "ROOM W/ ABF", None: "NON REFUNDABLE", "flex": "REFUNDABLE"},
    "bulbul": {"RO": "Room only", "BB": "Incl. ABF", None: "non-ref", "flex": "cxl free till {h}h"},
    "hornbill": {"RO": "Room only", "BB": "Breakfast incl.", None: "Non refundable", "flex": "refundable"},
    "sunbird": {"RO": "Room only", "BB": "With breakfast", None: "NRF", "flex": "Free cancellation"},
}

# True behaviour at booking, 15-45 days lead: (p_price_change, p_sold_out, p_error, mean increase when repriced)
BEHAVIOUR = {
    ("kestrel", "hotel"): (0.18, 0.07, 0.01, 0.09), ("kestrel", "activity"): (0.12, 0.05, 0.02, 0.08),
    ("mynah", "hotel"): (0.015, 0.01, 0.005, 0.04), ("mynah", "activity"): (0.02, 0.01, 0.005, 0.04),
    ("heron", "hotel"): (0.02, 0.02, 0.01, 0.05), ("heron", "activity"): (0.08, 0.10, 0.04, 0.07),
    ("bulbul", "hotel"): (0.05, 0.04, 0.02, 0.06), ("bulbul", "activity"): (0.04, 0.03, 0.02, 0.05),
    ("hornbill", "hotel"): (0.04, 0.03, 0.01, 0.05), ("hornbill", "activity"): (0.03, 0.02, 0.01, 0.05),
    ("sunbird", "hotel"): (0.08, 0.04, 0.02, 0.07), ("sunbird", "activity"): (0.03, 0.02, 0.01, 0.04),
}
# Lead-time shape: (price-change multiplier, sold-out multiplier). Late bookings hit stale caches and full houses.
LEAD_BUCKETS = [("0-7 days", 0, 7, 1.35, 1.9), ("8-14 days", 8, 14, 1.15, 1.35),
                ("15-45 days", 15, 45, 1.0, 1.0), ("46+ days", 46, 10_000, 0.85, 0.6)]


def lead_bucket(days: int) -> tuple:
    return next(b for b in LEAD_BUCKETS if b[1] <= days <= b[2])


def behaviour(supplier: str, product: str, lead_days: int, volatility: float = 1.0) -> tuple[float, float, float, float]:
    """True outcome probabilities for one attempt. volatility: per-hotel/activity demand multiplier."""
    pc, so, err, inc = BEHAVIOUR[(supplier, product)]
    _, _, _, m_pc, m_so = lead_bucket(lead_days)
    pc, so = min(pc * m_pc * volatility, 0.5), min(so * m_so * volatility, 0.4)
    return pc, so, err, inc
