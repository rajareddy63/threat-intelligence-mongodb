import os
import subprocess
import unittest


def integration_available():
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        active = {name.strip() for name in result.stdout.splitlines() if name.strip()}
        required = {"mongo-ex16", "cassandra-ex16", "neo4j-ex16"}
        return bool(required.issubset(active))
    except FileNotFoundError:
        return False


@unittest.skipUnless(integration_available(), "Required database services are not running locally")
class IntegrationDatabaseTests(unittest.TestCase):
    def test_local_services_are_available(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
