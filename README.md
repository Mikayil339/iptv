# Protected IPTV updater

This repository maintains a playlist for Azerbaijan, Turkey, Russia and a separate free sports group. Viewer access is through a secret link provided directly by the owner; the link and its access key are never stored here.

The previous public raw playlist endpoint has been removed from the current branch. Historical commits can still contain older public channel lists; they do not grant access to the protected service or to its future updates.

## Updates

GitHub Actions runs every six hours (approximately 04:23, 10:23, 16:23, 22:23 Asia/Baku). It authenticates to the playlist service using a short-lived GitHub OIDC identity restricted to this repository, the main branch and the exact refresh workflow. No viewer key or permanent GitHub credential is needed in Actions.

The service stores the playlist, channel health and fallback sources privately. Only aggregate health counts are committed here. Do not upload generated playlist, source, health or revision files to this repository.

The updater refreshes known public sources, checks HLS and media fragments, discovers additional HD channels and approved free sports broadcasts, and prefers HD alternatives with a faster measured response where available. Temporary failures are retried; a failing channel is not removed automatically. After two consecutive failing runs, a verified fallback is selected.

Free sports does not mean every competition is available. Match rights and regional restrictions apply. No paid-channel credentials, DRM circumvention, or guaranteed access to paid football competitions are provided. Published source resolution labels and response times are useful indicators, not a guarantee of quality or speed on every viewer's internet connection.

## Manual run

Actions → Refresh protected IPTV playlist → Run workflow.

Tests: `python -m unittest discover -s tests -v`.

A GitHub schedule may be delayed or disabled by GitHub inactivity rules. Check Actions if updates stop.
