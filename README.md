# wolfe-island-gtfs-rt

Unofficial [GTFS-RT](https://gtfs.org/realtime/) service-alerts feed for the
Wolfe Island Ferry (Kingston ⟷ Marysville, Ontario), generated from the
Ontario 511 public status API.

**This project is not affiliated with the Ministry of Transportation, Ontario
511, or the Wolfe Island Ferry service.** It's a small converter that turns an
existing public data source into a standard transit format.

## What it does

Ontario 511 already publishes live ferry status (the same data behind the
[@MTOFerryWI](https://twitter.com/MTOFerryWI) alerts and the 511 map) via a
free, unauthenticated REST API:

```
GET https://511on.ca/api/v2/get/ferryterminals?format=json
```

This repo polls that endpoint every 5 minutes via GitHub Actions, and when
the Wolfe Island (Kingston–Marysville) terminal is anything other than
normal "In Service," it emits a [GTFS-Realtime](https://gtfs.org/realtime/)
`FeedMessage` containing one `Alert` entity, mapped like this:

| 511 `Status`             | GTFS-RT `Alert.Effect`  |
| ------------------------ | ----------------------- |
| In Service                | *(no alert emitted)*    |
| Not In Service             | `NO_SERVICE`            |
| In Service Off Schedule    | `SIGNIFICANT_DELAYS`    |

The alert is tied to `route_id: wolfe_island_ferry` and stops
`marysville_dock` / `kingston_terminal`, matching the static GTFS feed this
was built alongside (not included in this repo — bring your own, or adjust
the IDs in `wolfe_island_gtfs_rt.py` to match yours).

## Output

The generated feed is committed to this repo as
[`gtfs-rt-alerts.pb`](./gtfs-rt-alerts.pb) on every run. With GitHub Pages
enabled on this branch, it's servable at a stable URL like:

```
https://<your-username>.github.io/wolfe-island-gtfs-rt/gtfs-rt-alerts.pb
```

Point any GTFS-RT consumer (OneBusAway, OpenTripPlanner, Transit apps, etc.)
at that URL as a Service Alerts feed.

## Running it yourself

```bash
pip install -r requirements.txt
python wolfe_island_gtfs_rt.py --once      # single poll, writes gtfs-rt-alerts.pb
python wolfe_island_gtfs_rt.py             # polls forever, once a minute
```

## Known limitations

- **Polling cadence:** GitHub Actions cron has a practical minimum of ~5
  minutes and can lag further under load. For faster updates, run
  `wolfe_island_gtfs_rt.py` (no `--once`) continuously on an always-on host
  instead of relying on Actions.
- **Dock changes not covered:** 511 publishes a *separate* terminal record
  for "Wolfe Island Ferry (Kingston - Dawson)," used during winter ice
  conditions or low-water diversions. This script only watches the
  Marysville record. If you want an alert when the ferry switches docks,
  watch both records and map dock changes to `Alert.Effect.DETOUR` or
  similar.
- **Rate limit:** the 511 API allows 10 calls/minute; this script makes one
  call per run, well within that.

## License

MIT — see [LICENSE](./LICENSE).
