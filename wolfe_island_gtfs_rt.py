#!/usr/bin/env python3
"""
Wolfe Island Ferry -> GTFS-RT Service Alerts

Source of truth: Ontario 511 REST API (the same feed that drives the
@MTOFerryWI status shown on the map / X account), NOT X/Twitter itself.

  GET https://511on.ca/api/v2/get/ferryterminals?format=json

No API key required. Rate limit: 10 calls / 60s, so poll no more than
once every ~10-15s (once a minute is plenty for a ferry).

This script polls that endpoint, finds the Wolfe Island (Kingston -
Marysville) terminal record, and emits a GTFS-RT FeedMessage containing
a single Alert entity when the ferry is anything other than normal
"In Service" -- matching it to the static GTFS feed's
route_id=wolfe_island_ferry and stop_ids marysville_dock /
kingston_terminal (from the zip you uploaded).

Run continuously (e.g. via cron/systemd) writing gtfs-rt-alerts.pb,
which any GTFS-RT consumer (OneBusAway, Transit app backends, etc.)
can be pointed at.
"""

import json
import time
import urllib.request
from google.transit import gtfs_realtime_pb2 as gtfs_rt

SOURCE_URL = "https://511on.ca/api/v2/get/ferryterminals?format=json"

# This must be the specific terminal record for the Kingston<->Marysville
# route (511 lists a separate "Kingston - Dawson" record used only during
# winter/low-water diversions -- check both if you want to alert on a
# dock change too).
TARGET_LOCATION_DESCRIPTION = "Wolfe Island Ferry (Kingston - Marysville)"

# From the GTFS static feed you uploaded (routes.txt / stops.txt)
ROUTE_ID = "wolfe_island_ferry"
STOP_IDS = ["marysville_dock", "kingston_terminal"]

OUTPUT_PATH = "gtfs-rt-alerts.pb"
POLL_SECONDS = 60


def fetch_terminal_status():
    with urllib.request.urlopen(SOURCE_URL, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for terminal in data:
        if terminal.get("LocationDescription") == TARGET_LOCATION_DESCRIPTION:
            return terminal
    raise RuntimeError("Wolfe Island Marysville terminal record not found in feed")


def status_to_effect(status: str):
    """Map 511's Status enum to a GTFS-RT Alert.Effect."""
    status = (status or "").strip().lower()
    if status == "in service":
        return None  # no alert needed
    if status == "not in service":
        return gtfs_rt.Alert.NO_SERVICE
    if status == "in service off schedule":
        return gtfs_rt.Alert.SIGNIFICANT_DELAYS
    # "No Status Available" or anything unrecognized -> don't alert
    return None


def build_feed_message(terminal: dict):
    feed = gtfs_rt.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.incrementality = gtfs_rt.FeedHeader.FULL_DATASET
    feed.header.timestamp = int(time.time())

    effect = status_to_effect(terminal.get("Status"))
    if effect is None:
        # Emit an empty FULL_DATASET feed -- this correctly clears any
        # previously-published alert once service returns to normal.
        return feed

    entity = feed.entity.add()
    entity.id = f"wolfe-island-status-{terminal.get('Id')}"
    alert = entity.alert

    alert.effect = effect
    alert.cause = gtfs_rt.Alert.UNKNOWN_CAUSE

    header = alert.header_text.translation.add()
    header.language = "en"
    header.text = f"Wolfe Island Ferry: {terminal.get('Status')}"

    desc = alert.description_text.translation.add()
    desc.language = "en"
    details = terminal.get("Details") or "No further details provided."
    desc.text = details

    # If 511 gave us an ETA for return to service, expose it as the
    # alert's active period end (epoch seconds, same units 511 returns).
    active_period = alert.active_period.add()
    active_period.start = int(time.time())
    return_ts = terminal.get("EstimatedReturnToServiceTime")
    if return_ts:
        active_period.end = int(return_ts)

    informed = alert.informed_entity.add()
    informed.route_id = ROUTE_ID
    for stop_id in STOP_IDS:
        informed = alert.informed_entity.add()
        informed.route_id = ROUTE_ID
        informed.stop_id = stop_id

    alert.url.translation.add(language="en", text=terminal.get("Website") or "")

    return feed


def run_once():
    terminal = fetch_terminal_status()
    feed = build_feed_message(terminal)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(feed.SerializeToString())
    print(
        f"[{time.strftime('%H:%M:%S')}] status={terminal.get('Status')!r} "
        f"-> wrote {OUTPUT_PATH} ({len(feed.entity)} alert entities)"
    )


def run_forever():
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"error: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    import sys

    if "--once" in sys.argv:
        run_once()
    else:
        run_forever()
