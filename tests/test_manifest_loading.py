from pathlib import Path
import unittest

from src.brain.platform.manifest import Manifest


class ManifestLoadingTest(unittest.TestCase):
    def test_load_existing_manifest(self) -> None:
        manifest = Manifest.load(Path("e:/AuroraBot/src/applications/qq/manifest.yaml"))
        self.assertEqual(manifest.package, "im.polaris.qq")
        self.assertTrue(manifest.tools)


if __name__ == "__main__":
    unittest.main()
