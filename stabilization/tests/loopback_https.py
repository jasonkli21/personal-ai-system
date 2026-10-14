"""Disposable real HTTPS listeners; routing is restricted to registered loopback sockets."""

import ipaddress
import socket
import ssl
import threading
import time
from datetime import UTC, datetime, timedelta

import httpx
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


class LoopbackHTTPS:
    def __init__(self, directory):
        self.directory = directory
        self.targets, self.servers = {}, []
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "synthetic-loopback")]
        )
        now = datetime.now(UTC)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=2))
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
                ),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        self.cert_path, self.key_path = (
            directory / "loopback-cert.pem",
            directory / "loopback-key.pem",
        )
        self.cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        self.key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        self.key_path.chmod(0o600)
        self.context = ssl.create_default_context(cafile=str(self.cert_path))

    def start(self, name, app):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(32)
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="error",
                access_log=False,
                lifespan="off",  # TestClient already owns each application's lifecycle.
                ssl_certfile=str(self.cert_path),
                ssl_keyfile=str(self.key_path),
            )
        )
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [listener]}, daemon=True
        )
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not server.started:
            server.should_exit = True
            thread.join(2)
            listener.close()
            raise RuntimeError("synthetic_loopback_start_failed")
        self.targets[name + ".example.invalid"] = port
        self.servers.append((server, thread, listener))

    def transport(self, api=httpx):
        targets, context = self.targets, self.context

        class Transport(api.BaseTransport):
            def __init__(self):
                self.inner = api.HTTPTransport(verify=context, retries=0)

            def handle_request(self, request):
                if request.url.scheme != "https" or request.url.host not in targets:
                    raise ValueError("non_synthetic_network_target")
                rewritten = api.Request(
                    request.method,
                    request.url.copy_with(
                        host="127.0.0.1", port=targets[request.url.host]
                    ),
                    headers=request.headers,
                    content=request.read(),
                    extensions=request.extensions,
                )
                return self.inner.handle_request(rewritten)

            def close(self):
                self.inner.close()

        return Transport()

    def close(self):
        for server, thread, listener in reversed(self.servers):
            server.should_exit = True
            thread.join(5)
            listener.close()
        self.servers.clear()
