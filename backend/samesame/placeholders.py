"""Placeholder that stays MOCK until its milestone: the simulator (M5 replaces it with the
50,000-session Monte-Carlo). The UI labels it as mock.
"""
from samesame.schemas import SimArm, SimParams, SimResult


def simulate(p: SimParams) -> SimResult:
    """MOCK: closed-form stand-in with the same knobs as the M5 Monte-Carlo simulator."""
    fail_today = min(0.95, 0.11 * p.failure_scale)
    fail_ss = min(0.95, 0.035 * p.failure_scale)
    base = 0.30
    today_b = base * (1 - p.dup_abandon * 2.2) * (1 - fail_today) * (1 - 0.15 * p.price_sensitivity * 0.3)
    ss_b = base * (1 - p.dup_abandon * 0.3) * (1 - fail_ss)
    arms = [SimArm(arm="today", bookings_per_search=round(today_b, 4), failed_at_booking=round(fail_today, 4), avg_true_cost=22950),
            SimArm(arm="samesame", bookings_per_search=round(ss_b, 4), failed_at_booking=round(fail_ss, 4), avg_true_cost=21310)]
    return SimResult(params=p, arms=arms, lift_bookings_pct=round((ss_b / today_b - 1) * 100, 1),
                     failed_reduction_pct=round((1 - fail_ss / fail_today) * 100, 1),
                     note="MOCK closed-form placeholder; the 50,000-session simulator replaces this in M5.")
