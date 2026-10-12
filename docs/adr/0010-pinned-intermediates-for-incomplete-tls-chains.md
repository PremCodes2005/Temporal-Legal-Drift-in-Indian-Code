# ADR 0010: Pinned intermediates for a server that omits its TLS chain

Status: **accepted 2026-10-12**. Implementation: `acquisition/tls.py`, `acquisition/fetch.py` (`UrllibTransport(ssl_context, cookie_jar)`), `monitoring/egazette.py`. Tests: `tests/unit/test_tls.py`.

## Context

`egazette.gov.in` sends only its leaf certificate (issuer Let's Encrypt YR2) and not the intermediate. Browsers and curl fetch the missing intermediate from the leaf's AIA URL. OpenSSL, and therefore Python, does not, so every request failed with `CERTIFICATE_VERIFY_FAILED`.

## Decision

- **What is pinned:** for the e-Gazette connector only, the TLS context adds Let's Encrypt's published Generation Y intermediates (YR1–3, YE1–3) and the Root YR / Root YE cross-signs by ISRG Root X1 / X2.
  - These are chain-building material only. `VERIFY_X509_PARTIAL_CHAIN` is cleared (Python 3.13+ sets it by default), so a chain must still end at a self-signed root in the system trust store.
  - `check_hostname` and `CERT_REQUIRED` stay on.
- **How each certificate was checked:**
  - its bytes from https://letsencrypt.org/certs/gen-y/ were compared with the bytes from its AIA URL;
  - it was verified to the trust store with `openssl verify`;
  - its DER SHA-256 was recorded. A pinned certificate whose hash differs is refused.
- **Why the whole set:** Let's Encrypt chooses among these intermediates at issuance, so a renewed e-Gazette certificate stays covered.
- **What was rejected:**
  - disabling verification or falling back to an insecure download;
  - fetching AIA URLs at runtime, which is unauthenticated HTTP and widens the attack surface;
  - trusting the intermediates as anchors.

## Consequences

- **Expiry:** the pins expire on 2028-09-02 (intermediates) and 2032-09-02 (cross-signs).
- **Failure mode:** a certificate from a CA outside the set fails visibly as `SOURCE_UNAVAILABLE` and needs a new, verified pin.
- **Tests:** regression tests use a local leaf-only TLS server with a throwaway test PKI (`tests/fixtures/tls/`).
- **Session handling:** the same change adds a per-connector cookie jar and a `Referer` header for the listing request. Without them the site serves `error.aspx`, which is now a visible `SOURCE_SHAPE_CHANGED`.
