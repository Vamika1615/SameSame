"""Hotel Twin Finder, part 3: constrained clustering and gray-zone routing.

Edges at or above the auto-merge threshold are merged strongest first, unless the merge would put
two listings with a never-merge conflict in one cluster (checked across every member, so a chain of
plausible pairs can't smuggle two branches together). Human review labels act as must-link /
cannot-link. Everything uncertain is routed to review, never merged.
"""
import json

from samesame import config
from samesame.matching.hotels import conflict


def human_links() -> dict[frozenset, bool]:
    out, by_audit = {}, {}
    if config.LABELS_PATH.exists():
        for line in config.LABELS_PATH.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("action") == "label" and r.get("left") and r.get("right"):
                by_audit[r["audit_id"]] = (frozenset((r["left"], r["right"])), r["label"] == "S")
            elif r.get("action") == "undo":
                by_audit.pop(r["audit_id"], None)
    for k, same in by_audit.values():
        out[k] = same
    return out


def cluster(P: list[dict], pairs: list[tuple[int, int]], p, auto: float, gray: float):
    parent = list(range(len(P)))
    members = {i: [i] for i in range(len(P))}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def cross_conflict(ra, rb):
        for i in members[ra]:
            for j in members[rb]:
                r = conflict(P[i], P[j])
                if r:
                    return r
        return None

    human = human_links()
    ids = [x["listing_id"] for x in P]
    decisions = []
    order = sorted(range(len(pairs)), key=lambda k: -p[k])
    for k in order:
        i, j = pairs[k]
        h = human.get(frozenset((ids[i], ids[j])))
        reason = conflict(P[i], P[j])
        if h is False:
            decisions.append((k, "human_different", None)); continue
        if reason:
            decisions.append((k, "blocked" if p[k] >= gray else "different", reason)); continue
        if h is True or p[k] >= auto:
            ri, rj = find(i), find(j)
            if ri == rj:
                decisions.append((k, "auto" if h is None else "human_same", None)); continue
            why = cross_conflict(ri, rj)
            if why:
                decisions.append((k, "blocked", "would join a cluster where " + why)); continue
            parent[rj] = ri
            members[ri] += members.pop(rj)
            decisions.append((k, "auto" if h is None else "human_same", None))
        elif p[k] >= gray:
            decisions.append((k, "gray", None))
        else:
            decisions.append((k, "different", None))
    roots = {}
    cluster_of = {}
    for i in range(len(P)):
        r = find(i)
        roots.setdefault(r, []).append(ids[i])
    for r, ms in roots.items():
        cid = "c-" + min(ms).replace(":", "-")
        for m in ms:
            cluster_of[m] = cid
    return cluster_of, sorted(decisions)
