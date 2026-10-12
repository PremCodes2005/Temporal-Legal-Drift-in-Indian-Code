# Official-source access decision (v2)

Date: 2026-10-12. This **supersedes** v1 for e-Gazette only; v1 is kept unchanged. Probing used about 6 requests in total, identified by User-Agent, with ≥3 s pauses. Nothing here claims complete official coverage.

## India Code — unchanged from v1 (`SUPPORTED_MACHINE_INTERFACE`)

DSpace 9.1 REST. Discovery lists items newest-first by `dc.date.accessioned`, down to a persisted cursor. Downloads come from bitstream `/content` links; the served rendition is stamped, so its SHA-256 is the identity (v1 addendum).

**Skipping unchanged documents:** a known item is **not re-downloaded** when its repository MD5, size and `lastModified` all equal the last verified observation.

## e-Gazette — `SUPPORTED_FRAGILE_HTML_DISCOVERY` (was `ACCESS_LIMITED`)

| Property | Observed 2026-10-12 |
| --- | --- |
| Host and access | `https://egazette.gov.in/`, an ASP.NET WebForms public site. No login, no CAPTCHA on the path below. |
| Session | `GET /` redirects to a cookieless session URL `/(S(<token>))/default.aspx`. A direct `RecentUploads.aspx` request without the session redirects to `error.aspx`. |
| Discovery | `GET /(S(...))/RecentUploads.aspx?Category=1`, labelled **"Bills & Acts"** on the home page. It returns an HTML table of 20 rows, newest-first. |
| Row fields | Ministry, Department, Office, Subject, Category, Part/Section, Issue Date, Publish Date, Gazette ID (e.g. `CG-DL-E-10102026-277026`), file size. |
| Pagination | Further pages need WebForms postbacks (`Page$2`…). **Only page 1 is read per daily run**; postback pagination is not automated. |
| Download | The site's download button posts back and opens `ViewPDF.aspx`, which embeds `../WriteReadData/{year}/{number}.pdf`. That static path is served directly: `GET https://egazette.gov.in/WriteReadData/2026/277026.pdf` returned `application/pdf`, 609,484 bytes (listed 0.58 MB), with `Last-Modified` and `ETag`. |
| Identity | Gazette ID is the official ID. `{number}` is the numeric suffix; `{year}` is taken from the Publish Date. Downloads are **verified**: PDF signature, content type, and size within 15 % of the listed size. Otherwise the result is `REVIEW_REQUIRED`, never a guess. |
| Scope filter | PDFs are downloaded only for rows in Part II–Section 1, or whose subject names an Act, Amendment or Ordinance. Other rows are kept as metadata observations. |
| robots.txt | HTTP 404 (none published). No API or terms of machine access found. |
| Rate policy | One discovery attempt per 24 h, at most 20 rows, ≥2 s between requests, 50 MB per file. |
| Failure behaviour | A table missing its expected span IDs raises `SourceShapeError` (`SOURCE_SHAPE_CHANGED`). Network failure is `SOURCE_UNAVAILABLE`. Both are recorded, and the source waits for its next window. |

**Fragility.** This is HTML parsing of a public page, not an API. The listing markup, session scheme or `WriteReadData` path may change without notice, and the year-folder rule is inferred from one verified sample. The connector therefore validates every assumption and abstains on mismatch. Manual import (v1) remains available.

**Legal boundary.** A Gazette publication is not commencement. A new row is a *discovery*: not evidence that a provision changed, and not a changed scenario answer.

## Gate

Both sources have a verified, permitted, bounded access method with documented fragility. No authentication, CAPTCHA or access control is bypassed.
