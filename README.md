# taurus SideStore source

A source that follows the releases of [samj-exe/taurus](https://github.com/samj-exe/taurus).
A GitHub Action checks for a new release every 30 minutes and rewrites `source.json`, so SideStore
shows each new taurus build as an update.

## Good to know

- SideStore doesn't install updates silently. It shows an update on the app's page, and updating
  is one tap (or automatic when your apps refresh in the background).
- taurus keeps Spotify's bundle ID, so it installs over the real Spotify.
- The redesigned UI needs iOS 26; the legacy UI works on iOS 16.1+.
- If taurus ever publishes a release without an `.ipa` asset, the source keeps the last good one.
