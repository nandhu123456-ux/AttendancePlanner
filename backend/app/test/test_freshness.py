import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from fastapi import HTTPException
from jose import jwt

# Add app directory to path so 'services' can be imported directly (matches
# the convention used by the other test modules).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.security as security
import services.sync_service as sync_service
from services.gitam_portal import InvalidCredentials, PortalError
from services.sync_service import ensure_fresh_portal_data

TEST_SECRET = "test-secret-key"

PATCHED_NAMES = [
    "get_database", "get_session", "remove_session", "save_session",
    "attempt_relogin", "fetch_current_data", "sync_portal_data",
    "_rebuild_plan", "decrypt_password", "invalidate_user_tokens",
]


class _Collection:
    def __init__(self, doc=None):
        self.doc = doc

    def find_one(self, *_args, **_kwargs):
        return self.doc

    def update_one(self, *_args, **_kwargs):
        pass


class _Database:
    def __init__(self, doc=None):
        self.users = _Collection(doc)


def _stale_user(encrypted="encrypted-payload"):
    # pymongo returns naive UTC datetimes; keep that shape on purpose.
    return {
        "student_id": "student",
        "lastSyncAt": datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2),
        "encryptedPassword": encrypted,
    }


def _patch_all(user_doc, session=None, relogin=None, fetch=None, decrypt=None):
    """Patch every external dependency used by ensure_fresh_portal_data."""
    db = _Database(user_doc)
    relogin_exc = relogin if isinstance(relogin, BaseException) else None
    fetch_exc = fetch if isinstance(fetch, BaseException) else None
    return [
        patch.object(sync_service, "get_database", return_value=db),
        patch.object(sync_service, "get_session", return_value=session),
        patch.object(sync_service, "remove_session"),
        patch.object(sync_service, "save_session"),
        patch.object(sync_service, "attempt_relogin", side_effect=relogin_exc, return_value=None if relogin_exc else Mock()),
        patch.object(sync_service, "fetch_current_data", side_effect=fetch_exc, return_value=None if fetch_exc else fetch),
        patch.object(sync_service, "sync_portal_data"),
        patch.object(sync_service, "_rebuild_plan"),
        patch.object(sync_service, "decrypt_password", side_effect=decrypt if isinstance(decrypt, BaseException) else None,
                     return_value=decrypt if isinstance(decrypt, str) else None),
        patch.object(sync_service, "invalidate_user_tokens"),
    ]


class _Patches:
    """Start a list of patches and expose their mocks by name."""

    def __init__(self, patches):
        self.patches = patches
        self.mocks = {}

    def __enter__(self):
        started = [p.start() for p in self.patches]
        self.mocks = dict(zip(PATCHED_NAMES, started))
        return self.mocks

    def __exit__(self, *_args):
        for p in self.patches:
            p.stop()
class EnsureFreshPortalDataTests(unittest.TestCase):
    def setUp(self):
        sync_service._last_reauth_attempt.clear()

    def tearDown(self):
        sync_service._last_reauth_attempt.clear()

    def test_fresh_data_skips_the_portal_entirely(self):
        user = {"student_id": "student", "lastSyncAt": datetime.now(timezone.utc).replace(tzinfo=None)}
        with _Patches(_patch_all(user)) as mocks:
            result = ensure_fresh_portal_data("student")
        self.assertEqual(result["status"], "fresh")
        mocks["fetch_current_data"].assert_not_called()
        mocks["attempt_relogin"].assert_not_called()

    def test_stale_data_with_live_session_resyncs(self):
        with _Patches(_patch_all(_stale_user(), session=Mock(), fetch={"subjects": []})) as mocks:
            result = ensure_fresh_portal_data("student")
        self.assertEqual(result["status"], "resynced")
        mocks["fetch_current_data"].assert_called_once()
        mocks["sync_portal_data"].assert_called_once()
        mocks["attempt_relogin"].assert_not_called()

    def test_dead_session_with_rejected_relogin_invalidates_tokens(self):
        # The portal enforces its CAPTCHA -> InvalidCredentials -> the TRACK_75
        # session must be invalidated so stale data is never served as current.
        patches = _patch_all(_stale_user(), session=None, relogin=InvalidCredentials("CAPTCHA required"))
        with _Patches(patches) as mocks:
            result = ensure_fresh_portal_data("student")
        self.assertEqual(result["status"], "invalidated")
        mocks["invalidate_user_tokens"].assert_called_once_with("student")
        mocks["attempt_relogin"].assert_called_once()

    def test_transient_portal_outage_keeps_the_session_valid(self):
        patches = _patch_all(_stale_user(), session=None, relogin=PortalError("portal down"))
        with _Patches(patches) as mocks:
            result = ensure_fresh_portal_data("student")
        self.assertEqual(result["status"], "unreachable")
        mocks["invalidate_user_tokens"].assert_not_called()

    def test_reauth_cooldown_prevents_repeated_portal_logins(self):
        patches = _patch_all(_stale_user(), session=None, relogin=InvalidCredentials("CAPTCHA required"))
        with _Patches(patches) as mocks:
            first = ensure_fresh_portal_data("student")
            second = ensure_fresh_portal_data("student")
        self.assertEqual(first["status"], "invalidated")
        self.assertEqual(second["status"], "unreachable")
        mocks["attempt_relogin"].assert_called_once()

    def test_missing_stored_credentials_invalidates_tokens(self):
        with _Patches(_patch_all(_stale_user(encrypted=None))) as mocks:
            result = ensure_fresh_portal_data("student")
        self.assertEqual(result["status"], "invalidated")
        mocks["attempt_relogin"].assert_not_called()
        mocks["invalidate_user_tokens"].assert_called_once()

    def test_undecryptable_credentials_invalidate_tokens(self):
        patches = _patch_all(_stale_user(), decrypt=RuntimeError("cannot decrypt"))
        with _Patches(patches) as mocks:
            result = ensure_fresh_portal_data("student")
        self.assertEqual(result["status"], "invalidated")
        mocks["invalidate_user_tokens"].assert_called_once()


class TokenInvalidationTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(security, "SECRET_KEY", TEST_SECRET)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _token(self, iat_epoch):
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {"student_id": "student", "exp": now + timedelta(hours=1), "iat": iat_epoch},
            TEST_SECRET,
            algorithm="HS256",
        )

    def test_tokens_issued_before_invalidation_are_rejected(self):
        invalidated_before = int(datetime.now(timezone.utc).timestamp()) - 60
        db = _Database({"student_id": "student", "token_invalidated_at": invalidated_before})
        old_token = self._token(invalidated_before - 3600)
        with patch.object(security, "get_database", return_value=db):
            with self.assertRaises(HTTPException) as raised:
                security.verify_token(f"Bearer {old_token}")
        self.assertEqual(raised.exception.status_code, 401)

    def test_tokens_issued_after_invalidation_are_accepted(self):
        invalidated_before = int(datetime.now(timezone.utc).timestamp()) - 60
        db = _Database({"student_id": "student", "token_invalidated_at": invalidated_before})
        fresh_token = self._token(int(datetime.now(timezone.utc).timestamp()))
        with patch.object(security, "get_database", return_value=db):
            payload = security.verify_token(f"Bearer {fresh_token}")
        self.assertEqual(payload["student_id"], "student")

    def test_tokens_are_accepted_when_no_invalidation_exists(self):
        db = _Database({"student_id": "student"})
        token = self._token(int(datetime.now(timezone.utc).timestamp()))
        with patch.object(security, "get_database", return_value=db):
            payload = security.verify_token(f"Bearer {token}")
        self.assertEqual(payload["student_id"], "student")


if __name__ == "__main__":
    unittest.main()
