"""Predicted-location maths for cell-tower fixes (no Home Assistant imports)."""
from __future__ import annotations

import math

# Zones further than this from the main cluster are treated as outliers.
CLUSTER_RADIUS_M = 250


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371000 * math.asin(math.sqrt(a))


def _parse(zones: list[dict]) -> list[dict]:
    parsed = []
    for z in zones or []:
        try:
            parsed.append(
                {
                    "lat": float(z["lat"]),
                    "lon": float(z["lon"]),
                    "radius": float(z.get("radius") or 0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return parsed


def predict_location(zones: list[dict], cluster_radius_m: float = CLUSTER_RADIUS_M) -> dict | None:
    """Centroid of the largest cluster of zones, ignoring far-away outliers.

    Each zone is a seed; its cluster is every zone within cluster_radius_m of it.
    The largest cluster wins. If two disjoint clusters tie there is no basis to
    prefer one, so every zone is used and "ambiguous" is set.

    Returns latitude, longitude, accuracy (metres, covers every used zone's
    extent), the zones used/excluded, and an ambiguous flag; or None if there
    are no usable zones.
    """
    pts = _parse(zones)
    if not pts:
        return None

    clusters = []
    for seed in pts:
        members = frozenset(
            i
            for i, z in enumerate(pts)
            if haversine_m(seed["lat"], seed["lon"], z["lat"], z["lon"]) <= cluster_radius_m
        )
        clusters.append(members)

    best_size = max(len(c) for c in clusters)
    best = {c for c in clusters if len(c) == best_size}
    ambiguous = len(best) > 1
    chosen = set(range(len(pts))) if ambiguous else next(iter(best))

    used = [pts[i] for i in sorted(chosen)]
    lat = sum(z["lat"] for z in used) / len(used)
    lon = sum(z["lon"] for z in used) / len(used)
    accuracy = max(haversine_m(lat, lon, z["lat"], z["lon"]) + z["radius"] for z in used)

    return {
        "latitude": lat,
        "longitude": lon,
        "accuracy": round(accuracy),
        "zones_used": len(used),
        "zones_excluded": len(pts) - len(used),
        "ambiguous": ambiguous,
    }
