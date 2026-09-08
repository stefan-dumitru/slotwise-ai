"""
Geocodes any existing business that has an address but no latitude/longitude
yet — useful after adding the geocoding feature to an already-seeded
database, or retrying businesses that failed to geocode earlier (e.g. due to
a transient Nominatim rate-limit or network error).

Respects Nominatim's ~1 request/second usage policy with a sleep between
calls. Safe to re-run — only touches rows where latitude IS NULL.

Usage:
    python scripts/backfill_geocoding.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app import models
from app.geocoding import geocode_address

db = SessionLocal()

businesses = (
    db.query(models.Business)
    .filter(models.Business.address.isnot(None), models.Business.latitude.is_(None))
    .all()
)

print(f"Businesses needing geocoding: {len(businesses)}")

geocoded = 0
failed = 0
for business in businesses:
    coords = geocode_address(business.address)
    if coords:
        business.latitude, business.longitude = coords
        geocoded += 1
        print(f"  OK   {business.name} -> {coords}")
    else:
        failed += 1
        print(f"  FAIL {business.name} ({business.address!r}) — no match or request failed")
    time.sleep(1)

db.commit()
db.close()
print(f"\nDone. Geocoded: {geocoded}, failed: {failed}")
