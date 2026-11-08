#!/usr/bin/env python3
"""
GoGo Central notifications integration tests (PikaNews frontend).

STATIC / MOCKED: these tests assert file invariants by reading the shipped
frontend files. No Firebase SDK, no service worker, no Notification API and
no network are involved. They validate the fail-closed configuration gate and
the wiring only. They do NOT prove live FCM delivery - live delivery is a
manual post-deployment verification step on a real device.
"""

import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(REPO_ROOT, "frontend")


def read(relative_path):
    with open(os.path.join(FRONTEND, relative_path), "r", encoding="utf-8") as f:
        return f.read()


def test_module_is_fail_closed_until_backend_deployed():
    """Empty apiBase/vapidPublicKey must keep the whole feature inert."""
    module = read("js/gogo-notifications.js")
    assert "apiBase: ''" in module, "apiBase must stay empty until the backend is deployed"
    assert "vapidPublicKey: ''" in module, "vapidPublicKey must stay empty until the VAPID key exists"
    assert "validateConfig" in module, "module must validate its config"
    assert "disabled" in module, "validation must report the disabled state"


def test_module_targets_pika_news_with_relative_worker_url():
    """Worker URL must be relative so the scope stays inside /pikanews/."""
    module = read("js/gogo-notifications.js")
    assert "appId: 'pika-news'" in module, "module must register as the pika-news product"
    assert "swUrl: 'firebase-messaging-sw.js'" in module, "worker URL must be relative"
    assert "swScope: ''" in module, "scope must default to the worker's own directory"
    assert "swUrl: '/" in module is False, "root-scope worker URL would escape /pikanews/"


def test_module_uses_explicit_opt_in_only():
    """Permission may only be requested inside the Enable click handler."""
    module = read("js/gogo-notifications.js")
    assert "requestPermission" in module
    # The SDK loads lazily; nothing requests anything at page load.
    assert "gstatic.com/firebasejs" in module


def test_module_contains_no_secrets_or_backend_credentials():
    """Only the public Firebase web config may ship to the browser."""
    module = read("js/gogo-notifications.js")
    worker = read("firebase-messaging-sw.js")
    for content in (module, worker):
        assert "service-account" not in content.lower()
        assert "private_key" not in content.lower()
        assert "BEGIN PRIVATE" not in content
        assert "FIREBASE_SERVICE_ACCOUNT" not in content


def test_background_worker_invariants():
    """Background messages only: no fetch handler, GoGo-domain-only links."""
    worker = read("firebase-messaging-sw.js")
    assert "firebase-messaging-compat.js" in worker
    assert "onBackgroundMessage" in worker
    assert "showNotification" in worker
    assert "notificationclick" in worker
    assert "tag:" in worker, "collapsing tag prevents duplicate ecosystem notifications"
    assert "addEventListener('fetch'" not in worker, "worker must not install a fetch handler"
    assert "gogocompany.in" in worker, "link allowlist must be GoGo-domain-only"


def test_index_mounts_the_container_and_loads_the_module_last():
    index = read("index.html")
    assert 'data-gogo-notifications' in index, "index.html must carry the opt-in container"
    assert 'js/gogo-notifications.js' in index, "index.html must load the module"
    assert index.index("js/ads.js") < index.index("js/gogo-notifications.js"), \
        "module must load after the site's own scripts"


if __name__ == "__main__":
    failures = 0
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(fn)]:
        try:
            fn()
            print(f"  OK {fn.__name__}")
        except AssertionError as e:
            print(f"  FAIL {fn.__name__}: {e}")
            failures += 1
    print(f"notifications tests: {'PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    raise SystemExit(0 if failures == 0 else 1)
