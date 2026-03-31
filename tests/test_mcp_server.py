import unittest

from illuminate_mcp.config import AppConfig
from illuminate_mcp.mcp_server import MCPServer


class MCPServerCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = MCPServer(AppConfig.from_env({}))

    def test_prompts_get_supported(self) -> None:
        response = self.server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "prompts/get",
                "params": {"name": "explore_lms_entities", "arguments": {}},
            }
        )
        self.assertIsNotNone(response)
        result = response["result"]
        self.assertIn("messages", result)
        self.assertGreaterEqual(len(result["messages"]), 1)

    def test_tool_error_returns_is_error_payload(self) -> None:
        response = self.server.handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "run_query", "arguments": {}},
            }
        )
        self.assertIsNotNone(response)
        result = response["result"]
        self.assertTrue(result["isError"])
        self.assertIn("structuredContent", result)
        self.assertEqual(result["structuredContent"]["error_type"], "ToolError")


if __name__ == "__main__":
    unittest.main()
