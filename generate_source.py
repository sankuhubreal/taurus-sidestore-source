#!/usr/bin/env python3
"""Build a SideStore / AltStore source from the GitHub releases of samj-exe/taurus.

Every release that carries an .ipa becomes one entry in the app's "versions" list
(newest first), so SideStore sees a new version as soon as this file is regenerated.

Usage:
    python3 generate_source.py                 # writes source.json
    python3 generate_source.py -o out.json
    GITHUB_TOKEN=... python3 generate_source.py   # higher API rate limit
"""
import argparse
import json
import os
import re
import sys
import urllib.request

REPO = "samj-exe/taurus"
OUT = "source.json"
MAX_VERSIONS = 10

ICON = "https://thumb.wikimedia.org/wikipedia/commons/thumb/7/74/Spotify_App_Logo.svg/960px-Spotify_App_Logo.svg.png"
TINT = "0A4B00"

# The mod keeps Spotify's own bundle id (it installs over the real Spotify).
BUNDLE_ID = "com.spotify.client"
MIN_IOS = "16.1"


def fetch_releases(repo):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases?per_page=30",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "taurus-source"},
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def build_versions(releases):
    versions = []
    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        ipas = [a for a in rel.get("assets", []) if a["name"].lower().endswith(".ipa")]
        if not ipas:
            continue
        asset = ipas[0]
        version = rel["tag_name"].lstrip("vV")
        m = re.search(r"(\d+(?:\.\d+)+)", asset["name"])
        if m:
            version = m.group(1)
        notes = (rel.get("body") or "").strip()
        entry = {
            "version": version,
            "date": asset.get("updated_at") or rel["published_at"],
            "downloadURL": asset["browser_download_url"],
            "size": asset["size"],
            "minOSVersion": MIN_IOS,
        }
        if notes:
            entry["localizedDescription"] = notes
        versions.append(entry)
    versions.sort(key=lambda v: v["date"], reverse=True)
    return versions[:MAX_VERSIONS]


def build_source(versions):
    return {
        "name": "taurus",
        "identifier": "source.taurus.auto",
        "subtitle": "Always the newest taurus release",
        "description": f"Auto-generated from the releases of github.com/{REPO}.",
        "iconURL": ICON,
        "website": f"https://github.com/{REPO}",
        "tintColor": TINT,
        "apps": [
            {
                "name": "taurus",
                "bundleIdentifier": BUNDLE_ID,
                "developerName": "samj.",
                "subtitle": "Spotify with built-in Premium and a Liquid Glass UI",
                "localizedDescription": (
                    "Open-sourced fork of chroma.pw with built-in Spotify Premium. "
                    "The redesigned UI needs iOS 26; the legacy UI supports iOS 16.1 and later."
                ),
                "iconURL": ICON,
                "tintColor": TINT,
                "versions": versions,
                "appPermissions": {"entitlements": [], "privacy": {}},
            }
        ],
        "news": [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default=OUT)
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--releases-json", help="read releases from a file instead of the API (testing)")
    args = ap.parse_args()

    if args.releases_json:
        with open(args.releases_json) as f:
            releases = json.load(f)
    else:
        releases = fetch_releases(args.repo)

    versions = build_versions(releases)
    if not versions:
        sys.exit("No published release with an .ipa asset was found; leaving the source untouched.")

    with open(args.output, "w") as f:
        json.dump(build_source(versions), f, indent=2)
        f.write("\n")
    print(f"Wrote {args.output}: latest is {versions[0]['version']} ({len(versions)} version(s))")


if __name__ == "__main__":
    main()