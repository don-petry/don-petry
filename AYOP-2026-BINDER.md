# AYOP 2026 Coaching Binder

`index.html` in this branch is a self-contained, interactive coaching binder for
**Coach Joel Claudio** for AYOP 2026 (America's Youth on Parade — July 14–18,
Notre Dame / South Bend, IN). It has four tabs: **Schedule**, **Roster**,
**Athletes** (per-athlete call sheets), and a day-of **Runsheet**. Lane/time data
was verified against the official NBTA Schedule (7/9), Lane Assignments & Splits
(7/10), and Rhythmic (7/9) documents.

## Live link (share this)

<https://raw.githack.com/don-petry/don-petry/ayop-2026-binder/index.html>

The file has no external dependencies, so that URL renders the full binder in any
browser — no login or plan required. If this branch is merged to `main`, the
equivalent link is `https://raw.githack.com/don-petry/don-petry/main/index.html`,
and enabling GitHub Pages (Settings → Pages → Deploy from `main` / root) serves it
at `https://don-petry.github.io/don-petry/`.

## ⚠️ Privacy

This page publicly lists eight minors by name and age with the exact times and
locations they'll be during the event, and `raw.githack` links are indexable.
Share it deliberately.

## How to take it down later

The link stops working the moment the file (or branch) is gone:

- **Delete the branch:** `git push origin --delete ayop-2026-binder`
  (or on GitHub: the branch list → trash icon). Kills the branch link above.
- **If it was merged to `main`:** delete the file —
  `git rm index.html AYOP-2026-BINDER.md && git commit -m "Remove AYOP binder" && git push`
- **If GitHub Pages was enabled:** also turn it off in Settings → Pages.
