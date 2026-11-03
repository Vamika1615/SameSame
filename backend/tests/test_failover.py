"""The router fails over to SAME twins only. Never a VARIANT, never to worse cancellation terms."""
import random

from samesame.booking.sandbox import BookableOffer, Profile, book, same_twins

ALWAYS_FAIL = Profile(0.0, 1.0, 0.0, 0.0)
ALWAYS_OK = Profile(0.0, 0.0, 0.0, 0.0)

POOL = [
    BookableOffer("a", "Kestrel", 18600, "R1:RO", cancel_rank=0),
    BookableOffer("variant-bb", "Mynah", 18000, "R1:BB", cancel_rank=93),     # cheaper, but a VARIANT
    BookableOffer("variant-room", "Heron", 17000, "R2:RO", cancel_rank=0),   # cheaper, different room
    BookableOffer("twin", "Hornbill", 19400, "R1:RO", cancel_rank=93),
]


def test_same_twins_excludes_variants():
    assert [o.offer_id for o in same_twins(POOL[0], POOL)] == ["twin"]


def test_failover_lands_on_same_twin_only():
    profiles = {"Kestrel": ALWAYS_FAIL, "Mynah": ALWAYS_OK, "Heron": ALWAYS_OK, "Hornbill": ALWAYS_OK}
    r = book(POOL[0], POOL, profiles.__getitem__, random.Random(0))
    assert r.status == "confirmed" and r.via_failover
    assert r.final_supplier == "Hornbill"
    touched = {s.offer_id for s in r.steps}
    assert not touched & {"variant-bb", "variant-room"}


def test_no_twin_means_fail_not_variant():
    pool = [o for o in POOL if o.offer_id != "twin"]
    r = book(pool[0], pool, lambda s: ALWAYS_FAIL if s == "Kestrel" else ALWAYS_OK, random.Random(0))
    assert r.status == "failed"
    assert r.steps[-1].event == "failed"


def test_never_fails_over_to_worse_cancellation():
    flexible = BookableOffer("flex", "Mynah", 20000, "R1:RO", cancel_rank=93)
    strict = BookableOffer("strict", "Kestrel", 19000, "R1:RO", cancel_rank=0)
    assert same_twins(flexible, [flexible, strict]) == []


def test_same_seed_same_outcome():
    prof = lambda s: Profile(0.3, 0.2, 0.1, 0.08)  # noqa: E731
    a = book(POOL[0], POOL, prof, random.Random(42))
    b = book(POOL[0], POOL, prof, random.Random(42))
    assert a == b
