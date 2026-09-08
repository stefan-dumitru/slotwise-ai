"""
Best-effort address -> (latitude, longitude) geocoding via OpenStreetMap's
free Nominatim API. No API key required, but usage policy requires a real
User-Agent identifying the application and caps requests at ~1/second:
https://operations.osmfoundation.org/policies/nominatim/

Never raises — geocoding failures (network issues, no match, rate limiting)
should never block creating or updating a business; they just leave
latitude/longitude unset.
"""

import json
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SlotWiseApp/1.0 (appointment booking platform; https://github.com/stefan-dumitru/slotwise-ai)"


def geocode_address(address: str) -> tuple[float, float] | None:
    if not address or not address.strip():
        return None

    query = urllib.parse.urlencode({"q": address, "format": "json", "limit": 1})
    request = urllib.request.Request(
        f"{NOMINATIM_URL}?{query}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            results = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    if not results:
        return None

    try:
        return float(results[0]["lat"]), float(results[0]["lon"])
    except (KeyError, ValueError, TypeError):
        return None
