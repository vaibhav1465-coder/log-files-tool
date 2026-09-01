import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.remote_sources import RemoteSourceError, SourceDefinition, configured_sources, discover_objects, source_catalog


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def paginate(self, **kwargs):
        self.calls.append(kwargs)
        return self.pages.get(kwargs["Prefix"], [])


class FakeS3:
    def __init__(self, pages):
        self.paginator = FakePaginator(pages)

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return self.paginator


def item(key: str, size: int = 10):
    return {"Key": key, "Size": size, "ETag": '"etag"', "LastModified": datetime(2026, 8, 30, tzinfo=timezone.utc)}


class RemoteSourceTests(unittest.TestCase):
    def settings(self):
        return SimpleNamespace(
            fe_cloudfront_bucket="private-cf-example",
            fe_cloudfront_prefix="approved/cf/distribution",
            fe_akamai_bucket="private-akamai-example",
            fe_akamai_prefix="approved/akamai/publication/",
        )

    def test_catalog_does_not_expose_bucket_or_prefix(self):
        catalog = source_catalog(self.settings())
        self.assertEqual({entry["id"] for entry in catalog}, {"financial-express-cloudfront", "financial-express-akamai"})
        self.assertTrue(all("bucket" not in entry and "prefix" not in entry for entry in catalog))

    def test_missing_private_configuration_disables_source(self):
        settings = self.settings()
        settings.fe_cloudfront_bucket = ""
        self.assertNotIn("financial-express-cloudfront", configured_sources(settings))

    def test_cloudfront_uses_exact_hour_prefixes(self):
        source = SourceDefinition("financial-express-cloudfront", "FE CF", "CloudFront", "bucket", "approved/cf")
        base = "approved/cf/2026/08/30/"
        s3 = FakeS3({
            f"{base}05/": [{"Contents": [item(f"{base}05/a.gz", 20)]}],
            f"{base}06/": [{"Contents": [item(f"{base}06/b.gz", 30)]}],
        })
        objects = discover_objects(s3, source, date(2026, 8, 30), 5, 7, max_objects=10, max_total_bytes=100)
        self.assertEqual([obj.size_bytes for obj in objects], [20, 30])
        self.assertEqual(len(s3.paginator.calls), 2)

    def test_akamai_filters_only_requested_hours(self):
        source = SourceDefinition("financial-express-akamai", "FE Akamai", "Akamai", "bucket", "approved/akamai/")
        s3 = FakeS3({"approved/akamai/": [{"Contents": [
            item("approved/akamai/property.eclf_S.202408290200-0300-3.gz"),
            item("approved/akamai/property.eclf_S.202408290300-0400-3.gz"),
        ]}]})
        objects = discover_objects(s3, source, date(2024, 8, 29), 2, 3, max_objects=10, max_total_bytes=100)
        self.assertEqual(len(objects), 1)
        self.assertIn("0200-0300", objects[0].key)

    def test_cloudfront_scan_limit_fails_closed_during_listing(self):
        source = SourceDefinition("financial-express-cloudfront", "FE CF", "CloudFront", "bucket", "approved/cf")
        base = "approved/cf/2026/08/30/05/"
        s3 = FakeS3({base: [{"Contents": [item(base + "a.gz"), item(base + "b.gz")]}]})
        with self.assertRaises(RemoteSourceError):
            discover_objects(
                s3,
                source,
                date(2026, 8, 30),
                5,
                6,
                max_objects=10,
                max_total_bytes=100,
                max_scanned_keys=1,
            )

    def test_object_and_byte_limits_fail_closed(self):
        source = SourceDefinition("financial-express-cloudfront", "FE CF", "CloudFront", "bucket", "approved/cf")
        base = "approved/cf/2026/08/30/05/"
        s3 = FakeS3({base: [{"Contents": [item(base + "a.gz", 60), item(base + "b.gz", 60)]}]})
        with self.assertRaises(RemoteSourceError):
            discover_objects(s3, source, date(2026, 8, 30), 5, 6, max_objects=10, max_total_bytes=100)


if __name__ == "__main__":
    unittest.main()
