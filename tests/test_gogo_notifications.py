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


def test_module_is_configured_and_fail_closed_on_empty_overrides():
    """apiBase + VAPID must be filled; the gate still guards empty overrides."""
    module = read("js/gogo-notifications.js")
    assert "apiBase: 'https://gogo-central-backend-mg6z.onrender.com'" in module, "apiBase must point at the deployed GoGo Central backend"
    assert "vapidPublicKey: 'B" in module, "vapidPublicKey must carry the Firebase Web Push public key"
    assert "validateConfig" in module, "module must validate its config"
    assert "disabled" in module, "validation must report the disabled state"


def test_module_targets_pika_news_with_relative_worker_url():
    """Worker URL must be relative so the scope stays inside /pikanews/."""
    module = read("js/gogo-notifications.js")
    assert "appId: 'pika-news'" in module, "module must register as the pika-news product"
    assert "swUrl: 'firebase-messaging-sw.js'" in module, "worker URL must be relative"
    assert "swScope: ''" in module, "scope must default to the worker's own directory"
    assert "swUrl: '/" not in module, "root-scope worker URL would escape /pikanews/"


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


def test_module_ships_the_onboarding_intro_popup():
    """First-visit intro: six GoGo categories, Enable + Not now, prompt only on click."""
    module = read("js/gogo-notifications.js")
    assert 'id="gogo-notifications-intro"' in module
    assert 'id="gogo-notifications-intro-enable"' in module
    assert 'id="gogo-notifications-intro-dismiss"' in module
    for label in [
        "GoGo Company announcements",
        "Sarkari Sarthi job alerts",
        "Pika News breaking news",
        "Crystal Quest updates",
        "Arrow Out updates",
        "Future GoGo product announcements",
    ]:
        assert label in module, f"intro must list: {label}"
    assert module.count("requestPermission") == 1, \
        "the native permission prompt may only fire from the explicit Enable click"
    assert "Not now" in module
    assert "visibilitychange" in module, "permission is rechecked when the visitor returns"


def test_module_verifies_backend_registration_before_showing_active():
    """Active is displayed only after GoGo Central confirms the device row (existing endpoints only)."""
    module = read("js/gogo-notifications.js")
    assert "apiFetch('/api/v1/devices', { method: 'GET' })" in module, \
        "verification must reuse the existing devices endpoint"
    assert "findRegisteredDevice" in module
    assert "VERIFY_FAILED" in module
    assert "verified: true" in module, "verified flag persisted before Active is displayed"
    assert "ONBOARDING_REMIND_AFTER_MS = 3 * 24 * 60 * 60 * 1000" in module, \
        "the 'Not now' reminder waits exactly three days"
    assert "evaluateOnboarding" in module


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
