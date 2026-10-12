# Official-source access decision (v3)

Date: 2026-10-12. This **supersedes v2 for e-Gazette transport only**. v1 and v2 are kept unchanged. India Code is unchanged.

## e-Gazette: `SUPPORTED_FRAGILE_HTML_DISCOVERY` (live-verified)

| Property | v3 |
| --- | --- |
| TLS | The server omits its intermediate. The connector pins Let's Encrypt's verified Generation Y intermediates, keeps hostname and certificate verification, and disables partial-chain trust (ADR 0010). |
| Session | `GET /` sets the cookieless session URL plus cookies. The listing request reuses the cookie jar and sends `Referer: <session>/default.aspx`, as a browser following the home-page link would. Without these the site redirects to `error.aspx`, which the connector reports as `SOURCE_SHAPE_CHANGED`. |
| Access | Anonymous public pages only. No CAPTCHA was encountered or bypassed, no login, no postbacks. |

## Live record (2026-10-12, all UTC)

1. **16:26, scheduled run:** `SOURCE_UNAVAILABLE` (`CERTIFICATE_VERIFY_FAILED`). The 24 h window moved to 2026-10-13T16:26.
2. **16:41, audited manual retry** (`--source egazette`) after the TLS fix: TLS succeeded, then `SOURCE_SHAPE_CHANGED` (redirect to `error.aspx`). The cause was found by one diagnostic of 2 GETs.
3. **16:42, second audited manual retry** after adding the cookie jar and Referer: `OK`. 20 listing rows were stored as metadata observations. None matched the amending-instrument filter, so no download.
4. **Audited `manual_import`** of one listed document, `CG-DL-E-12102026-277080` ("appointment of the date 15th October 2026 for MSMED Amendment Act 2026"):
   - downloaded through the pinned-TLS connector: 401,709 bytes, SHA-256 `17f43a73…2260`;
   - stored immutably, parsed `OK`, text fidelity `READABLE`;
   - extraction found 0 amendment events and 1 unresolved record (correct: a commencement notification);
   - applicability `NOT_DETERMINED`, review queue `HUMAN_REVIEW_PENDING`, 2 overlay chunks labelled unreviewed.

Manual retries do not move the 24 h window: e-Gazette remained next eligible at 2026-10-13T16:26.

## Known limits

- **Commencement notifications** (such as the MSMED item) are not selected by the daily filter, which targets amending instruments. They matter for temporal applicability and need a separate, reviewed policy.
- **Hindi text:** in this PDF the Hindi text layer extracted with broken Devanagari glyph mapping, yet the fidelity check (Latin-script heuristic) rated it `READABLE`. The English half is intact. Treat Hindi text from monitored PDFs as unverified.
