# Third-party notices

The MIT license covers original ThreatMon code, documentation and graphic compositions. It does not relicense dependencies, publisher content, source datasets or trademarks.

## Bundled geography

The application bundles transformed Natural Earth 1:110m land geometry. Natural Earth data is public domain. The exact upstream commit, source hash and transformation are recorded in [docs/map.md](docs/map.md). Natural Earth provides geographic context, not evidence for news claims.

## External metadata

Runtime source caches and databases are excluded from this repository. Source screenshots show attributed excerpts or explicitly synthetic fixtures. No full publisher articles or publisher images are distributed by the ingestion adapters.

| Source | Rights and attribution boundary |
| --- | --- |
| GDELT | Attributed dataset use under [GDELT's policy](https://gdeltproject.org/about.html). Linked publisher material retains its own rights. |
| Global Voices | Named author, original article link, Global Voices attribution and CC BY 3.0 license link under its [attribution policy](https://globalvoices.org/about/global-voices-attribution-policy/). |
| GDACS | Source attribution and its [reuse terms](https://www.gdacs.org/About/termofuse.aspx); third-party rights remain separate. |
| NASA | Agency attribution under its [media guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/); no endorsement or blanket license to third-party content. |
| USGS | USGS-authored data is generally public domain; follow [copyright and credit guidance](https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits). |
| CISA KEV mirror | The upstream `cisagov/kev-data` repository supplies a [CC0 license](https://github.com/cisagov/kev-data/blob/develop/LICENSE). |

See [docs/news.md](docs/news.md) and [docs/source_policy.md](docs/source_policy.md) for implemented source limits. Feed access is not permission to scrape article bodies or reuse publisher imagery.

## Software dependencies

Dependencies are installed from `backend/uv.lock` and `frontend/package-lock.json`; their original license files and notices apply. They are not relicensed under ThreatMon's MIT license.

The release inventory includes LGPL-3.0-only packages `psycopg` and `psycopg-binary`, and LGPL-3.0-or-later Sharp-related image-processing binaries supplied through Next.js dependencies. Redistributing dependency binaries or container images requires preserving and satisfying their upstream license obligations. This repository publishes application source and lockfiles, not a container image or vendored dependency tree.

For an exact installation, inspect the installed package metadata and included license files. The lockfiles, rather than this summary, define the resolved dependency versions.
