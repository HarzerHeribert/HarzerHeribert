# Public-source boundary

**The collector has no GitHub credential input.** Private GitHub data must never enter collection, normalization, snapshots, tests derived from production data, or rendering. Filtering secrets out of an authenticated response is not an acceptable substitute.

## Trusted path

1. The build job has `permissions: {}`. It checks out this specific public repository using anonymous Git HTTPS. No checkout credential helper is persisted.
2. Generation runs under `env -i PATH=/usr/bin:/bin python3 -I`. It receives only an explicit source revision. No token, home directory, user Python packages, proxy setting, or credential environment variable is passed to the Python process.
3. `src/public_data.py` uses `http.client.HTTPSConnection` with certificate verification and a literal `api.github.com` host. This client does not load `.netrc`, Git/gh settings, cookies, or proxy configuration. It has no Authorization/header argument, authentication mode, shell execution, filesystem reads, or environment reads. The only request headers are Accept, User-Agent and the GitHub API version.
4. A closed route allowlist permits only this user's public profile, owned public repository list, public events, and individually named public repository metadata/languages/releases. `/user`, GraphQL, organizations, arbitrary query parameters, foreign owners, URL-encoded paths, redirects and alternate hosts are denied. There is no authenticated fallback.
5. Each repository is resolved again anonymously on every run and must return both `private: false` and `visibility: public`. Failure aborts publication. Public events are explicitly checked and only events for repositories reverified in this build enter the model.
6. Normalization drops event payloads, emails, author names, commit messages, issue bodies, profile location, organizations and unrelated fields. Releases retain their public tag, ID, date and URL. Every entity has explicit public provenance. Languages and topics are fields of their provenanced repository; their anonymous endpoint response digest is retained in the source audit.
7. Schema validation rejects unexpected fields, missing provenance, malformed data, foreign links, missing anonymous resolution receipts, credential-shaped strings, future activity and authenticated audit entries. Rendering always calls validation. SVG text is XML escaped; no scripts, external images, foreignObject, embedded fonts or event handlers are permitted.
8. Only after tests, fresh anonymous collection, rendering and verification succeed are the generated artifacts transferred to a separate publish job. That job alone has `contents: write`; its repository-scoped token is supplied only to the final Git write step. It never runs the collector. It stages only `assets/generated/` and refuses to publish against a different source revision. Push races fail instead of force-pushing.

## What the guarantee means

In this implementation, private GitHub APIs cannot be accessed by the collection transport: there is neither an accepted private route nor an authentication channel. This is a guarantee about the reviewed code and its workflow, not a claim that Python is a security sandbox. A malicious maintainer who rewrites the workflow, a compromised runner/interpreter, GitHub incorrectly returning private data anonymously, or a compromised certificate authority is outside this boundary. The public source audit is traceability, not a cryptographic attestation of GitHub's response. A fabricated offline fixture with forged receipts cannot prove anonymous resolution; the production workflow always collects fresh data and never accepts fixtures.

The policy is documented here rather than displayed as a status slogan on the artwork. No production input is taken from unrelated local repositories or authenticated GitHub account APIs. `gh` was used administratively to create this public repository, and Git is used to publish it; neither is a data collector.

## Retention, visibility changes and scope

There is no historical data cache and no private-inclusive contribution endpoint. Each snapshot replaces the last using current anonymously accessible repositories. Repositories absent from the current public list are omitted, along with their events. If one becomes private between listing and resolution, the build fails closed. A later run can remove it after the public listing catches up.

Previously committed public data remains public in Git history; a repository becoming private does not retroactively erase data that was previously public. Failed builds preserve the last successful snapshot, with its visible timestamp. There is also an unavoidable interval between collection and publication during which visibility can change. GitHub image caches and scheduled-workflow delays add freshness lag. Do not interpret the console as a real-time visibility or activity oracle.

The source user is fixed. Foreign repository events are discarded even if publicly observable. Private-inclusive contribution totals, private organization membership, `viewer`, and `/user` are never queried. Public GitHub event `PushEvent` records are labeled **push events/batches**, never counted as individual commits. No private activity is inferred from timing, gaps, totals or missing metadata.

## Verification

Run `python3 -I -m unittest discover -s tests -v` and `python3 -I scripts/verify.py`. Tests exercise forbidden endpoints/parameters, exact wire headers, rejected redirects, unresolved and private repositories, public provenance, schema injection, credential-shaped text, foreign links, API failures and rate limiting. The import boundary test keeps credential-capable local data libraries out of the collector; the workflow test keeps the write token out of generation.

The fixtures in unit tests are explicitly synthetic public test data and never feed production artifacts. No secret is read in order to test for its absence.
