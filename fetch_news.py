#!/usr/bin/env python3
"""
Runs on GitHub Actions. Reads the Forex Factory calendar feed, keeps USD high-impact
events, and writes news.json. The trading bot reads news.json from this repo.

If the feed can't be read, this script exits with an error and leaves the old news.json
in place, so the bot keeps the last good data.
"""
import json
import sys
import time
import urllib.request

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
OUT_FILE = "news.json"
KEEP_COUNTRY = "USD"
KEEP_IMPACT = "High"
TRIES = 3


# FOMC: pause only for the Tier 1 leaders' speeches, and for minutes and rate decisions.
# Tier 2 and 3 speeches are ignored, since the feed title doesn't show the topic.
FOMC_SPEECH_WORDS = ("SPEAKS", "SPEECH", "TESTIF", "REMARKS", "MEMBER")
FOMC_TIER1 = ("WARSH", "WILLIAMS", "WALLER")


def fomc_pause(title):
    """True if this FOMC event should pause trading. None if it isn't an FOMC event."""
    t = title.upper()
    if "FOMC" not in t:
        return None
    if any(w in t for w in FOMC_SPEECH_WORDS):
        return any(name in t for name in FOMC_TIER1)
    return True                      # minutes and rate decisions


def is_blackout_event(e):
    """High-impact USD releases, plus the FOMC events fomc_pause() allows."""
    title = e.get("title", "")
    fomc = fomc_pause(title)
    if fomc is not None:
        return fomc
    return e.get("impact") == KEEP_IMPACT


def read_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0 news-feed"})
    last_error = None
    for attempt in range(1, TRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # network or bad JSON: retry, then fail
            last_error = e
            print(f"attempt {attempt} failed: {e}")
            time.sleep(10 * attempt)
    raise RuntimeError(f"feed unavailable after {TRIES} tries: {last_error}")


def main():
    events = read_feed()
    kept = [
        {"date": e["date"], "country": e["country"], "impact": e["impact"], "title": e.get("title", "")}
        for e in events
        if e.get("country") == KEEP_COUNTRY and is_blackout_event(e)
    ]
    out = {"fetched_at": time.time(), "source": FEED_URL, "events": kept}
    with open(OUT_FILE, "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {len(kept)} USD high-impact event(s) to {OUT_FILE}")
    for e in kept:
        print("  ", e["date"], e["title"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
