#!/usr/bin/env python3
"""Build a SideStore / AltStore source from the GitHub releases of samj-exe/taurus.

SideStore checks that the version in the source matches the version inside the downloaded IPA
(CFBundleShortVersionString). taurus keeps Spotify's own version number (e.g. 9.1.78), not its
release number (e.g. 0.50.1), so this script opens each new IPA once, reads the real version
from its Info.plist, and remembers it in ipa-cache.json so later runs don't download it again.

Usage:
    python3 generate_source.py                      # writes source.json + ipa-cache.json
    GITHUB_TOKEN=... python3 generate_source.py     # higher API rate limit
"""
import argparse
import json
import os
import plistlib
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile

REPO = "samj-exe/taurus"
OUT = "source.json"
CACHE = "ipa-cache.json"
KEEP_RELEASES = 3  # only the newest few releases are looked at

ICON = "https://thumb.wikimedia.org/wikipedia/commons/thumb/7/74/Spotify_App_Logo.svg/960px-Spotify_App_Logo.svg.png"
TINT = "0A4B00"

SCREENSHOTS = [
    "https://github.com/samj-exe/taurus/raw/stable/docs/screenshots/now-playing.webp",
    "https://github.com/samj-exe/taurus/raw/stable/docs/screenshots/playlist.webp",
    "https://github.com/samj-exe/taurus/raw/stable/docs/screenshots/live-activity.webp",
    "https://github.com/samj-exe/taurus/raw/stable/docs/screenshots/home.webp",
]

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


def read_ipa_info(url):
    """Download an IPA and return the version fields from its Info.plist."""
    req = urllib.request.Request(url, headers={"User-Agent": "taurus-source"})
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "app.ipa")
        with urllib.request.urlopen(req, timeout=300) as resp, open(path, "wb") as out:
            shutil.copyfileobj(resp, out)
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", n)]
            if not names:
                raise ValueError("no Info.plist found in the IPA")
            info = plistlib.loads(z.read(names[0]))
    return {
        "version": info["CFBundleShortVersionString"],
        "build": info.get("CFBundleVersion"),
        "minOS": info.get("MinimumOSVersion"),
    }


def build_versions(releases, cache):
    candidates = []
    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        ipas = [a for a in rel.get("assets", []) if a["name"].lower().endswith(".ipa")]
        if ipas:
            candidates.append((rel, ipas[0]))
    candidates.sort(key=lambda c: c[1].get("updated_at") or c[0]["published_at"], reverse=True)

    versions = {}
    for rel, asset in candidates[:KEEP_RELEASES]:
        url = asset["browser_download_url"]
        key = f"{url}|{asset['size']}"
        info = cache.get(key)
        if info is None:
            try:
                print(f"Reading {asset['name']} ...")
                info = read_ipa_info(url)
            except Exception as e:  # keep going with the other releases
                print(f"Warning: could not read {asset['name']}: {e}", file=sys.stderr)
                continue
            cache[key] = info

        # Several taurus releases can ship the same Spotify version; keep only the newest one.
        if info["version"] in versions:
            continue

        taurus_version = rel["tag_name"].lstrip("vV")
        notes = (rel.get("body") or "").strip()
        entry = {
            "version": info["version"],
            "date": asset.get("updated_at") or rel["published_at"],
            "downloadURL": url,
            "size": asset["size"],
            "minOSVersion": info.get("minOS") or MIN_IOS,
            "localizedDescription": f"taurus {taurus_version}" + (f"\n\n{notes}" if notes else ""),
        }
        if info.get("build"):
            entry["buildVersion"] = info["build"]
        versions[info["version"]] = entry
    return list(versions.values())


def build_source(versions):
    return {
        "name": "taurus",
        "identifier": "source.taurus.auto",
        "subtitle": "Get the latest update of taurus with ease.",
        "description": (
            "A no-jailbreak Theos tweak that rebuilds Spotify for iOS in Liquid Glass, "
            "injected into your own decrypted IPA and signed with your own certificate."
        ),
        "iconURL": ICON,
        "website": f"https://github.com/{REPO}",
        "tintColor": TINT,
        "apps": [
            {
                "name": "Spotify",
                "bundleIdentifier": BUNDLE_ID,
                "developerName": "samj.",
                "subtitle": "Spotify with built-in Premium and a Liquid Glass UI",
                "localizedDescription": (
                    "Open-sourced fork of chroma.pw with built-in Spotify Premium. "
                    "The redesigned UI needs iOS 26; the legacy UI supports iOS 16.1 and later."
                ),
                "iconURL": ICON,
                "tintColor": TINT,
                "screenshotURLs": SCREENSHOTS,
                "versions": versions,
                "appPermissions": {"entitlements": [], "privacy": {}},
            }
        ],
        "news": [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default=OUT)
    ap.add_argument("--cache", default=CACHE)
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--releases-json", help="read releases from a file instead of the API (testing)")
    args = ap.parse_args()

    if args.releases_json:
        with open(args.releases_json) as f:
            releases = json.load(f)
    else:
        releases = fetch_releases(args.repo)

    cache = {}
    if os.path.exists(args.cache):
        with open(args.cache) as f:
            cache = json.load(f)

    versions = build_versions(releases, cache)
    if not versions:
        sys.exit("No usable release with an .ipa asset was found; leaving the source untouched.")

    with open(args.cache, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
        f.write("\n")
    with open(args.output, "w") as f:
        json.dump(build_source(versions), f, indent=2)
        f.write("\n")
    print(f"Wrote {args.output}: latest is {versions[0]['version']} ({len(versions)} version(s))")


if __name__ == "__main__":
    main()
