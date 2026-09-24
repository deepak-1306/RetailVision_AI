"""
Shelf zone configuration.

A shelf zone is a rectangular region of the camera frame (normalized 0-1
coordinates) that maps to a physical shelf/aisle in the store. Behaviour
classification and the recommendation engine both key off of which zone a
customer's track is spending time in.

For a real deployment these would be calibrated per-camera and stored in the
database; for the hackathon demo we ship a sensible 3x2 grid default that
works reasonably for a single wide-angle aisle camera.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ShelfZone:
    name: str
    x1: float  # normalized [0,1]
    y1: float
    x2: float
    y2: float

    def contains(self, cx: float, cy: float) -> bool:
        return self.x1 <= cx <= self.x2 and self.y1 <= cy <= self.y2


DEFAULT_SHELF_ZONES: list[ShelfZone] = [
    ShelfZone("Zone A - Left Shelf", 0.0, 0.0, 0.33, 1.0),
    ShelfZone("Zone B - Center Shelf", 0.33, 0.0, 0.66, 1.0),
    ShelfZone("Zone C - Right Shelf", 0.66, 0.0, 1.0, 1.0),
]


def resolve_zone(cx: float, cy: float, zones: list[ShelfZone] = DEFAULT_SHELF_ZONES) -> str:
    for zone in zones:
        if zone.contains(cx, cy):
            return zone.name
    return "Unzoned"
