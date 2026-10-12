# S1 — Official-source access decision (v1)

Date: 2026-10-12. The probe was bounded to 7 requests in total, with User-Agent `TemporalLegalDriftResearch/1.0`. Decisions apply to `monitoring/` connectors. Nothing here claims complete official coverage.

## India Code — `SUPPORTED_MACHINE_INTERFACE`

| Property | Observed |
| --- | --- |
| Interface | DSpace REST API, `https://indiacode.gov.in/server/api`. The root reports **DSpace 9.1**. The REST contract is documented by the DSpace project, but India Code itself publishes no API terms. |
| Discovery cursor | `GET /server/api/discover/search/objects?dsoType=ITEM&sort=dc.date.accessioned,DESC&size=N` returns items newest-first, 130,977 items at probe time, newest accessioned `2026-10-09T12:39:23Z`. |
| Identity | Item `uuid` and handle (e.g. `123456789/620497`). `lastModified` is exposed per item. |
| Content | `GET /server/api/core/items/{uuid}/bundles?embed=bitstreams` → `ORIGINAL` bundle → bitstream name, `sizeBytes`, **MD5** `checkSum`, and `/core/bitstreams/{id}/content`. |
| Authentication | None for read access. |
| robots.txt | `https://indiacode.gov.in/robots.txt` returned **HTTP 500**; robots policy could not be verified. |
| Rate policy adopted | At most one discovery attempt per 24 h (§0.7); at most 5 pages × 20 items per run; 2 s between requests; 50 MB per file. Only PDF downloads from `indiacode.gov.in`; redirects must stay on the allowlist. |
| Fidelity | Many items are section-level records or older scanned PDFs. Every download enters the review queue; nothing is treated as an applicable amendment on discovery. |

**Risk:** the endpoint shape is the DSpace contract as *observed*, not a published India Code service agreement. The connector validates the response shape and records `SOURCE_UNAVAILABLE` or `ACCESS_LIMITED` instead of guessing if it changes.

## e-Gazette — `ACCESS_LIMITED`

| Property | Observed |
| --- | --- |
| Interface | `https://egazette.gov.in/` is an ASP.NET WebForms site with a session token in the URL (`/(S(...))/default.aspx`) and `__VIEWSTATE`. |
| Recent uploads | `RecentUploads.aspx?Category=1` fetched directly redirects to `error.aspx`; listings need browser-session navigation and postbacks. |
| robots.txt | HTTP 404. |
| API | None documented or observed. |

**Decision:** there is no reliable, documented machine interface, and emulating session/postback flows would be fragile and could circumvent intended access patterns. e-Gazette is therefore served only by a **reviewed manual-import adapter**: a reviewer supplies a PDF obtained from the portal plus its gazette ID and URL. The source is marked `ACCESS_LIMITED` in health output, and live synchronization is **not** claimed.

## Gate

At least one lawful, reliable path exists for each claimed source: India Code by machine interface, e-Gazette by manual import. No completeness is claimed. **S1 passes** with these scopes.

## Addendum (2026-10-12, after the first real run)

India Code serves a **stamped rendition** of each PDF, not the stored file. Example: bitstream `31964ea2…`, stored at 52,196 bytes with MD5 `94221004…`; the served file is 53,831 bytes with MD5 `e9f1676d…`. Two downloads of the served file were byte-identical (SHA-256 `bf965611…`).

**Decision:**
- The **served-bytes SHA-256** is the integrity and identity basis.
- The repository MD5 is recorded as `REPOSITORY_MD5_VERIFIED`, `SERVED_RENDITION_DIFFERS_FROM_REPOSITORY_MD5` or `NO_REPOSITORY_CHECKSUM`.
- A difference is not treated as corruption.

**Consequence:** in-transit corruption that still yields a valid PDF signature cannot be detected against the repository checksum.
