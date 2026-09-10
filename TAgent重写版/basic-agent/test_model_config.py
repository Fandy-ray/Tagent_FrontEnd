import json
import math
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


from app.repository.provider_repository import ModelProviderRegistry, RegistryLoadError, load_model_registry


from app.service.provider_service import parse_ephemeral_provider


def provider_payload(model_id: str, **overrides):
    payload = {
        "name": model_id,
        "served_model_id": model_id,
        "base_url": "http://127.0.0.1:9000/v1/",
        "upstream_model": f"upstream-{model_id}",
        "auth_mode": "bearer",
        "api_key": f"secret-{model_id}",
        "temperature": 0.1,
        "enabled": True,
    }
    payload.update(overrides)
    return payload


class EphemeralProviderTest(unittest.TestCase):
    def test_preserves_stable_update_revision_for_client_cache(self):
        payload = provider_payload(
            "private",
            created_at="1000",
            updated_at="2000",
        )
        provider = parse_ephemeral_provider(payload)
        self.assertEqual(provider.created_at, "1000")
        self.assertEqual(provider.updated_at, "2000")


class RegistryTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            prefix=".test-model-config-", dir=Path(__file__).resolve().parent
        )
        self.path = Path(self.temp_dir.name) / "model_providers.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_json(self, data):
        self.path.write_text(json.dumps(data, allow_nan=True), encoding="utf-8")

    def test_migrates_v1_to_v2_and_masks_secret(self):
        self.write_json(
            {
                "version": 1,
                "default_model_id": "teacher-a",
                "providers": [
                    {
                        **provider_payload("teacher-a"),
                        "created_at": "2026-07-09T00:00:00Z",
                        "updated_at": "2026-07-09T00:00:00Z",
                    }
                ],
            }
        )

        public = ModelProviderRegistry(self.path).public_registry()
        raw = json.loads(self.path.read_text(encoding="utf-8"))

        self.assertEqual(raw["version"], 2)
        self.assertEqual(raw["providers"][0]["auth_mode"], "bearer")
        self.assertEqual(public["providers"][0]["api_key_masked"], "****er-a")
        self.assertTrue(public["providers"][0]["has_api_key"])
        self.assertNotIn("api_key", public["providers"][0])

    def test_missing_registry_does_not_import_process_environment(self):
        env = {
            "OPENAI_API_KEY": "env-secret",
            "OPENAI_BASE_URL": "https://api.example.com/v1/",
            "OPENAI_MODEL": "example-model",
            "AGENT_MODEL_ID": "teacher-env",
        }
        with patch.dict(os.environ, env, clear=True):
            registry = load_model_registry(self.path)

        self.assertEqual(registry.get_default_model_id(), "")
        self.assertEqual(registry.enabled_providers(), [])
        self.assertFalse(self.path.exists())

    def test_supports_no_auth_and_erases_old_key_when_auth_mode_changes(self):
        registry = ModelProviderRegistry(self.path)
        registry.create_provider(provider_payload("teacher-local"))

        updated = registry.update_provider(
            "teacher-local",
            {"auth_mode": "none", "api_key": ""},
        )

        self.assertEqual(updated["auth_mode"], "none")
        self.assertFalse(updated["has_api_key"])
        self.assertEqual(updated["api_key_masked"], "")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(raw["providers"][0]["api_key"], "")

    def test_bearer_create_requires_key_and_blank_edit_preserves_key(self):
        registry = ModelProviderRegistry(self.path)
        with self.assertRaisesRegex(ValueError, "api_key"):
            registry.create_provider(provider_payload("missing", api_key=""))

        registry.create_provider(provider_payload("teacher-a"))
        registry.update_provider("teacher-a", {"name": "renamed", "api_key": ""})
        self.assertEqual(registry.get_enabled_provider("teacher-a").api_key, "secret-teacher-a")

    def test_default_always_points_to_an_enabled_provider(self):
        registry = ModelProviderRegistry(self.path)
        registry.create_provider(provider_payload("teacher-a"))
        registry.create_provider(provider_payload("teacher-b"))
        registry.set_default_model("teacher-a")

        registry.update_provider("teacher-a", {"enabled": False})
        self.assertEqual(registry.get_default_model_id(), "teacher-b")

        registry.delete_provider("teacher-b")
        self.assertEqual(registry.get_default_model_id(), "")

        registry.update_provider("teacher-a", {"enabled": True})
        self.assertEqual(registry.get_default_model_id(), "teacher-a")

    def test_rejects_unknown_version_corruption_duplicates_and_nan(self):
        invalid_documents = [
            "{not-json",
            json.dumps({"version": 99, "default_model_id": "", "providers": []}),
            json.dumps(
                {
                    "version": 2,
                    "default_model_id": "teacher-a",
                    "providers": [provider_payload("teacher-a"), provider_payload("teacher-a")],
                }
            ),
            json.dumps(
                {
                    "version": 2,
                    "default_model_id": "teacher-a",
                    "providers": [provider_payload("teacher-a", temperature=math.nan)],
                },
                allow_nan=True,
            ),
        ]

        for document in invalid_documents:
            with self.subTest(document=document[:30]):
                self.path.write_text(document, encoding="utf-8")
                with self.assertRaises(RegistryLoadError):
                    ModelProviderRegistry(self.path).public_registry()

    def test_rejects_invalid_url_temperature_auth_mode_and_disabled_default(self):
        registry = ModelProviderRegistry(self.path)
        invalid = [
            provider_payload("bad-url", base_url="file:///etc/passwd"),
            provider_payload("bad-temp", temperature=2.1),
            provider_payload("bad-auth", auth_mode="query"),
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    registry.create_provider(payload)

        self.write_json(
            {
                "version": 2,
                "default_model_id": "teacher-a",
                "providers": [provider_payload("teacher-a", enabled=False)],
            }
        )
        with self.assertRaises(RegistryLoadError):
            registry.public_registry()

        self.write_json(
            {
                "version": 2,
                "default_model_id": "",
                "providers": [provider_payload("teacher-a")],
            }
        )
        with self.assertRaises(RegistryLoadError):
            registry.public_registry()

    def test_failed_atomic_replace_keeps_previous_file_intact(self):
        registry = ModelProviderRegistry(self.path)
        registry.create_provider(provider_payload("teacher-a"))
        before = self.path.read_bytes()

        with patch("app.repository.provider_repository.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                registry.update_provider("teacher-a", {"name": "should-not-persist"})

        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_concurrent_creates_do_not_lose_updates(self):
        registry = ModelProviderRegistry(self.path)
        errors = []

        def create(index):
            try:
                registry.create_provider(provider_payload(f"teacher-{index}"))
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        threads = [threading.Thread(target=create, args=(index,)) for index in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(registry.list_providers()), 12)


if __name__ == "__main__":
    unittest.main()
