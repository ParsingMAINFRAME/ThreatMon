# Repository graphics

The hero and social card are HTML/CSS compositions of the actual ThreatMon interface. No generated screenshot, invented live reading or publisher imagery is used. The pictured news hotspots are explicitly fictional demo scenarios.

- `hero.html` renders at 1600 × 1060; exported as `../images/threatmon-hero.jpg`.
- `social-preview.html` renders at 1280 × 640; exported as `../images/threatmon-social-preview.jpg`.
- Both use the unaltered UI capture `../images/release-demo-workspace.png`. The compositions crop its edges but do not change its contents.
- `release-demo-desktop.jpg` and `release-demo-mobile.jpg` show the offline demo. `release-fetched-desktop.jpg` and `release-source-status.jpg` show stored September 30 source snapshots at their actual age during October 2 capture.

To reproduce the compositions, open the HTML locally in a browser, set the exact viewport above at device scale 1, wait for the image to load, then capture the viewport without browser chrome. Fonts use local Georgia, Arial and Consolas with no downloads. Rendering can vary slightly across systems.

The social card meets GitHub's [recommended 1280 × 640 dimensions and under-1 MB limit](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview). Uploading it to the repository's **Settings > Social preview** is a separate setting from committing the asset.

Original composition and UI code use the repository MIT license. Natural Earth basemap data is public domain; see [map attribution](../map.md). Fetched article metadata remains subject to its original source terms, not the code license.
