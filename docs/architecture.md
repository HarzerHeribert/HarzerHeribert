# One README, unreasonable infrastructure

A small, standard-library Python program turns anonymous GitHub REST responses into a typed-by-validation public model and six deterministic SVG artifacts. GitHub serves the committed images. There is no backend, database, paid API, JavaScript in the README, or external visual service.

## Local commands

Python 3.12 is the CI runtime, supplied by the pinned Ubuntu 24.04 runner family. No pip install is required; `requirements.txt` deliberately contains no packages. GitHub Actions are pinned to full commit SHAs. The runner image and Python security patches may advance; renderer behavior is covered by golden hashes.

```sh
python3 -I -m unittest discover -s tests -v
# Run from this repository. The shell obtains only THIS repository's revision.
env -i PATH="$PATH" python3 -I scripts/generate.py --revision "$(git rev-parse HEAD)"
python3 -I scripts/verify.py
```

For an offline deterministic rerender of the last public snapshot:

```sh
python3 -I scripts/generate.py --revision "$(git rev-parse HEAD)" --fixture assets/generated/snapshot.json
```

Offline rendering preserves the snapshot's original timestamp and revision. It validates provenance structure, but cannot attest that a manually edited fixture came from GitHub. The publishing workflow never uses this mode. Production generation validates every output before replacing artifacts; transport, data or XML failures leave previous artifacts untouched. File replacement is atomic per file, not a multi-file filesystem transaction; CI only uploads after successful completion.

## Layout

- `src/public_data.py`: fixed anonymous transport, pagination, allowlist, normalization, strict provenance/model validation.
- `src/render.py`: shared SVG primitives, independently tuned dark/light palettes, deterministic hero, activity and topology layouts.
- `scripts/generate.py`: fresh collection, validation, render and staged artifact replacement.
- `scripts/verify.py`: offline model, SVG policy and exact rerender checks.
- `tests/`: synthetic public fixtures, policy/transport/render tests and six golden output hashes.
- `assets/generated/`: six SVGs and the minimal public snapshot/source audit.
- `.github/workflows/profile.yml`: isolated anonymous build and credentialed publication.

## Public endpoints

All data requests use `https://api.github.com`, anonymously:

| Route | Use |
| --- | --- |
| `/users/HarzerHeribert` | Verify public identity; optional publicly returned display name |
| `/users/HarzerHeribert/repos?type=owner&per_page=100&page=N` | Enumerate owned, anonymously visible public repositories; includes forks if present |
| `/repos/HarzerHeribert/{repo}` | Independently reverify visibility, topics, description, primary language and last push time |
| `/repos/HarzerHeribert/{repo}/languages` | Actual language bytes; per-repository proportions and distinct language count |
| `/repos/HarzerHeribert/{repo}/releases?per_page=100&page=N` | Full paginated public release catalog; drafts rejected |
| `/users/HarzerHeribert/events/public?per_page=100&page=N` | Up to three pages of this user's public events, filtered to reverified owned repositories |

API source URLs, status, anonymous authentication declaration and SHA-256 response digests are committed with each snapshot. Entity `sourceUrl` links point to public GitHub resources. No GitHub-returned API URL is followed: paths are constructed through the allowlist. API response bodies are not cached or committed.

## Metric contract

- **Public repos:** currently anonymously listed and individually resolved owned repositories, including the profile repository itself. Not the account's private-inclusive total.
- **Repos in sample:** distinct repositories in retained public events for the displayed 30 UTC dates.
- **Languages:** distinct keys in the public language-byte endpoints, across indexed repositories. The inventory's thin rail is primary-language byte proportion, not a score, skill level or completion percentage.
- **Push events:** public `PushEvent` records in the displayed period. A batch may represent more than one commit. These are not commit counts.
- **Public releases:** entries in the complete currently public release catalogs; includes prereleases, excludes drafts. A page/budget failure prevents publishing incomplete totals.
- **Event bus:** supported, deduplicated, publicly flagged events for currently indexed repositories. Circle: push; diamond: PR/review; double circle: release; square: issue/comment; star: watch/star; gray: repository/ref event. Bus positions express chronological order, not time distance. It shows the latest twelve sampled events. Motion is a decorative signal. The compact hero labels this as recent public events; the expanded signal view and image descriptions explain the sample limits.
- **Public signal:** counts per UTC date, ending on the partial build date. Height is normalized to the largest sampled daily count, with actual counts printed above nonempty bars. A zero cell means no event in the sample, not proof of no public activity. The feed can be delayed, incomplete or truncated at 300 events; the graph is always labeled as a bounded sample. No 365-day history is invented.
- **Topology:** repository → GitHub-reported primary language. Topic labels come directly from GitHub. No inferred dependency, SAP association, personal name, expertise or semantic category is introduced.
- **Revision:** real source Git commit used by the generator, not the later asset commit. Timestamp is UTC collection start; failure never advances it. No live-status or security slogans are displayed.

## Rate limits and failures

Two builds per day, at 05:23 and 17:23 UTC, plus manual and source-change triggers. The client hard-stops after 50 anonymous requests, below GitHub's usual 60-request hourly anonymous allowance. Other users of a shared runner IP can still exhaust it. No retries using credentials, no private cache fallback, no partial catalog totals. 403/429, transport failures, invalid JSON, redirects, missing repositories and pagination exhaustion fail visibly in Actions. The last snapshot remains, visibly dated. Public events alone are intentionally sampled, always disclosed as such.

The current small inventory needs approximately `2 + 3R + E` requests (user/list, three per repository, one to three event pages), plus pagination when necessary. At larger scale, the fail-closed budget will need a reviewed batching design; it must never silently weaken the privacy policy.

## Rendering and accessibility

The dark theme uses graphite, cold white, cyan and restrained orange. Light uses warm paper, graphite, engineering blue and registration orange, with separate contrast choices. All artwork uses native SVG primitives, system font fallbacks and a subtle dot grid. Ambient movement runs on 24/28-second cycles; a reduced-motion media query disables animation. No event is fabricated to fill the bus.

GitHub displays SVGs as images: internal links and interactions are unreliable, so navigation remains in the compact README below the instruments. `<picture>` selects a palette; dark is the fallback. SVG title/description and README alt text supply accessible descriptions; the public JSON is the exact machine-readable equivalent. Individual animation behavior, font metrics and reduced-motion propagation may vary with GitHub/browser image rendering. Every image remains complete as a static frame. No fonts, scripts, images or animation libraries are fetched externally. GitHub may cache an earlier image even after a successful build.

## Security

Read [the public-data threat model](security.md) before changing transport, schema or workflow. Only the isolated publication job has `contents: write`. Build has no repository permissions. No other GitHub permissions or secrets are requested. Artifact-only commits and path-filtered push triggers prevent recursion; scheduled Actions can still be delayed or automatically disabled by GitHub after prolonged repository inactivity.
