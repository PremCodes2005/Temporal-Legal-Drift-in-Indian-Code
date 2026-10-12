"""Pinned-intermediate TLS against a local server that, like egazette.gov.in, sends only its leaf certificate."""

from __future__ import annotations

import socket
import ssl
import threading
import unittest
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from temporal_legal_drift.acquisition.fetch import UrllibTransport
from temporal_legal_drift.acquisition.tls import LETS_ENCRYPT_GEN_Y_CHAIN, pinned_intermediate_context
from temporal_legal_drift.errors import AcquisitionError
from temporal_legal_drift.monitoring import EGazetteConnector

TLS = Path(__file__).resolve().parents[1] / "fixtures/tls"  # throwaway localhost-only test PKI, valid to 2126
INTERMEDIATE = (TLS / "intermediate.pem").read_text()
PIN = {sha256(ssl.PEM_cert_to_DER_cert(INTERMEDIATE)).hexdigest(): INTERMEDIATE}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.end_headers()
        self.wfile.write(b"%PDF-1.4 ok")

    def log_message(self, *args) -> None:
        pass


class LeafOnlyServer:
    def __init__(self, leaf: str) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(TLS / f"{leaf}.pem", TLS / f"{leaf}.key")  # leaf only, no intermediate
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.handle_error = lambda request, address: None  # rejected handshakes are the expected outcome
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True, do_handshake_on_connect=False)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def handshake(self, context: ssl.SSLContext, hostname: str = "localhost") -> None:
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as raw, \
                context.wrap_socket(raw, server_hostname=hostname) as tls:
            tls.getpeercert()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


class PinnedIntermediateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = LeafOnlyServer("leaf")

    def tearDown(self) -> None:
        self.server.close()

    def test_leaf_only_server_fails_without_the_pin(self) -> None:
        # Reproduces the live e-Gazette CERTIFICATE_VERIFY_FAILED.
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.server.handshake(ssl.create_default_context(cafile=str(TLS / "root.pem")))

    def test_pinned_intermediate_completes_the_chain_to_a_trusted_root(self) -> None:
        context = pinned_intermediate_context(PIN, cafile=str(TLS / "root.pem"))
        response = UrllibTransport(context).fetch(f"https://localhost:{self.server.port}/a.pdf", timeout=5,
                                                  maximum_bytes=100, validate_url=lambda url: None)
        self.assertEqual(response.payload, b"%PDF-1.4 ok")

    def test_pinned_intermediate_is_never_a_trust_anchor(self) -> None:
        unrelated = str(TLS / "rogue_leaf.pem")  # trust store without the test root
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.server.handshake(pinned_intermediate_context(PIN, cafile=unrelated))

    def test_hostname_is_still_checked(self) -> None:
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.server.handshake(pinned_intermediate_context(PIN, cafile=str(TLS / "root.pem")), "egazette.gov.in")

    def test_transport_reports_invalid_chain_as_acquisition_error(self) -> None:
        with self.assertRaises(AcquisitionError):
            UrllibTransport(ssl.create_default_context(cafile=str(TLS / "root.pem"))).fetch(
                f"https://localhost:{self.server.port}/a.pdf", timeout=5, maximum_bytes=100, validate_url=lambda url: None)


class RogueServerTests(unittest.TestCase):
    def test_leaf_from_another_ca_is_rejected(self) -> None:
        server = LeafOnlyServer("rogue_leaf")
        try:
            with self.assertRaises(ssl.SSLCertVerificationError):
                server.handshake(pinned_intermediate_context(PIN, cafile=str(TLS / "root.pem")))
        finally:
            server.close()


class _CookieHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        if self.path == "/home":
            self.send_header("Set-Cookie", "session=abc; Path=/")
        self.end_headers()
        self.wfile.write(f"{self.headers.get('Cookie')}|{self.headers.get('Referer')}".encode())

    def log_message(self, *args) -> None:
        pass


class SessionTests(unittest.TestCase):
    def test_cookie_jar_and_referer_carry_the_session_to_the_next_request(self) -> None:
        from http.cookiejar import CookieJar

        server = ThreadingHTTPServer(("127.0.0.1", 0), _CookieHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            transport = UrllibTransport(cookie_jar=CookieJar())
            transport.fetch(f"{base}/home", timeout=5, maximum_bytes=100, validate_url=lambda url: None)
            listing = transport.fetch(f"{base}/list", timeout=5, maximum_bytes=100, validate_url=lambda url: None,
                                      headers={"Referer": f"{base}/home"})
            self.assertEqual(listing.payload.decode(), f"session=abc|{base}/home")
        finally:
            server.shutdown()
            server.server_close()


class PinnedBundleTests(unittest.TestCase):
    def test_tampered_pin_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            pinned_intermediate_context({"0" * 64: INTERMEDIATE}, cafile=str(TLS / "root.pem"))

    def test_egazette_uses_the_verified_lets_encrypt_chain_with_full_checks(self) -> None:
        context = EGazetteConnector().transport.ssl_context
        self.assertEqual(len(LETS_ENCRYPT_GEN_Y_CHAIN), 8)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertFalse(context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN)


if __name__ == "__main__":
    unittest.main()
