import unittest

from illuminate_mcp.domain_router import DomainRouter


class DomainRouterTests(unittest.TestCase):
    def test_routes_lms_keywords(self) -> None:
        router = DomainRouter(("CDM_SIS", "CDM_LMS"))
        domain = router.resolve("Show me course enrollments by section")
        self.assertEqual(domain, "CDM_LMS")

    def test_routes_sis_keywords(self) -> None:
        router = DomainRouter(("CDM_LMS", "CDM_SIS"))
        domain = router.resolve("What is the average GPA by major?")
        self.assertEqual(domain, "CDM_SIS")

    def test_fallback_first_allowed_domain(self) -> None:
        router = DomainRouter(("CDM_SIS", "CDM_LMS"))
        domain = router.resolve("hello world")
        self.assertEqual(domain, "CDM_SIS")

    def test_routes_aly_keywords(self) -> None:
        router = DomainRouter(("CDM_LMS", "CDM_ALY"))
        domain = router.resolve("Show analytics dashboard retention metrics")
        self.assertEqual(domain, "CDM_ALY")


    def test_routes_clb_keywords(self) -> None:
        router = DomainRouter(("CDM_LMS", "CDM_CLB"))
        domain = router.resolve("Show collaborate session attendance")
        self.assertEqual(domain, "CDM_CLB")

    def test_routes_media_keywords(self) -> None:
        router = DomainRouter(("CDM_LMS", "CDM_MEDIA"))
        domain = router.resolve("How many video views this month?")
        self.assertEqual(domain, "CDM_MEDIA")

    def test_routes_learn_keywords(self) -> None:
        router = DomainRouter(("CDM_LMS", "LEARN"))
        domain = router.resolve("Query the blackboard learn source table")
        self.assertEqual(domain, "LEARN")

    def test_routes_map_keywords(self) -> None:
        router = DomainRouter(("CDM_LMS", "CDM_MAP"))
        domain = router.resolve("Show cross-system user mapping")
        self.assertEqual(domain, "CDM_MAP")


if __name__ == "__main__":
    unittest.main()
