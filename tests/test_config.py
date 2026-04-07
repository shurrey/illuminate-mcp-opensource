import unittest

from illuminate_mcp.config import AppConfig
from illuminate_mcp.exceptions import ConfigError


class ConfigTests(unittest.TestCase):
    def test_defaults_load(self) -> None:
        config = AppConfig.from_env({})
        self.assertEqual(config.allowed_domains, ("CDM_LMS", "CDM_TLM", "CDM_ALY"))
        self.assertFalse(config.require_query_confirmation)
        self.assertEqual(config.monthly_credit_budget, 100.0)
        self.assertFalse(config.enable_metadata_introspection)
        self.assertFalse(config.enable_persistent_feedback)
        self.assertFalse(config.enable_planner_probes)

    def test_invalid_approval_mode_raises(self) -> None:
        with self.assertRaises(ConfigError):
            AppConfig.from_env({"DEFAULT_SESSION_APPROVAL_MODE": "always"})

    def test_execution_requires_credentials(self) -> None:
        with self.assertRaises(ConfigError):
            AppConfig.from_env({"ENABLE_QUERY_EXECUTION": "true"})

    def test_metadata_introspection_requires_credentials(self) -> None:
        with self.assertRaises(ConfigError):
            AppConfig.from_env({"ENABLE_METADATA_INTROSPECTION": "true"})

    def test_persistent_feedback_requires_path(self) -> None:
        with self.assertRaises(ConfigError):
            AppConfig.from_env(
                {
                    "ENABLE_PERSISTENT_FEEDBACK": "true",
                    "FEEDBACK_STORE_PATH": "",
                }
            )

    def test_planner_probes_require_execution(self) -> None:
        with self.assertRaises(ConfigError):
            AppConfig.from_env(
                {
                    "ENABLE_PLANNER_PROBES": "true",
                    "ENABLE_QUERY_EXECUTION": "false",
                }
            )

    def test_warehouse_credits_rate_must_be_non_negative(self) -> None:
        with self.assertRaises(ConfigError):
            AppConfig.from_env({"WAREHOUSE_CREDITS_PER_HOUR": "-1"})

    def test_enable_learn_schema_adds_learn_to_domains(self) -> None:
        config = AppConfig.from_env({"ENABLE_LEARN_SCHEMA": "true"})
        self.assertTrue(config.enable_learn_schema)
        self.assertIn("LEARN", config.allowed_domains)
        self.assertIn("LEARN", config.allowed_schemas)

    def test_enable_learn_schema_no_duplicate_when_already_present(self) -> None:
        config = AppConfig.from_env({
            "ENABLE_LEARN_SCHEMA": "true",
            "ALLOWED_DOMAINS": "CDM_LMS,LEARN",
            "ALLOWED_SCHEMAS": "CDM_LMS,LEARN",
        })
        self.assertEqual(config.allowed_domains.count("LEARN"), 1)
        self.assertEqual(config.allowed_schemas.count("LEARN"), 1)

    def test_learn_schema_disabled_by_default(self) -> None:
        config = AppConfig.from_env({})
        self.assertFalse(config.enable_learn_schema)
        self.assertNotIn("LEARN", config.allowed_domains)

if __name__ == "__main__":
    unittest.main()
