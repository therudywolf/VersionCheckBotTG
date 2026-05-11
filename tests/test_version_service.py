"""Tests for intelligent release matching."""
import os

os.environ.setdefault("BOT_TOKEN", "123456:ABCdefGHIjklMNOpqrsTUVwxyz")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/versioncheckbot_tests.db")

from bot.services.version_service import VersionService


class TestVersionServiceMatching:
    """Test version matching without external API calls."""

    def test_find_release_by_patch_version(self):
        service = VersionService()
        releases = [
            {"name": "3.12", "latest": {"name": "3.12.13"}, "isMaintained": True},
            {"name": "3.11", "latest": {"name": "3.11.15"}, "isMaintained": True},
        ]

        release = service.find_release(releases, "3.11.4")

        assert release["name"] == "3.11"

    def test_find_release_by_major_cycle(self):
        service = VersionService()
        releases = [
            {"cycle": "23", "latest": "23.11.1", "eol": "2027-01-01"},
            {"cycle": "22", "latest": "22.9.0", "eol": "2026-01-01"},
        ]

        release = service.find_release(releases, "22.x")

        assert release["cycle"] == "22"

    def test_v1_product_alias_extraction(self):
        service = VersionService()
        products, aliases = service._extract_products({
            "result": [
                {"name": "nodejs", "aliases": ["node", "node.js"]},
                {"name": "postgresql", "aliases": ["postgres"]},
            ]
        })

        assert products == ["nodejs", "postgresql"]
        assert aliases["node.js"] == "nodejs"
        assert aliases["postgres"] == "postgresql"

    def test_release_status_uses_eol_date_not_support_date(self):
        service = VersionService()
        release = {
            "cycle": "3.11",
            "latest": "3.11.15",
            "support": "2024-04-01",
            "eol": "2027-10-31",
        }

        assert service.release_status(release) == "supported"
