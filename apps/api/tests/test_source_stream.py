import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.source_stream import open_source_stream


class Body(io.BytesIO):
    pass


class FakeS3:
    def __init__(self):
        self.calls = []
        self.body = Body(b"safe")

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        return {"Body": self.body}


class SourceStreamTests(unittest.TestCase):
    def settings(self):
        return SimpleNamespace(
            fe_cloudfront_bucket="approved-bucket",
            fe_cloudfront_prefix="approved/cf/",
            fe_akamai_bucket="another-bucket",
            fe_akamai_prefix="approved/akamai/",
        )

    def test_approved_remote_path_uses_get_object_only(self):
        client = FakeS3()
        with open_source_stream(self.settings(), "s3://approved-bucket/approved/cf/file.gz", client) as stream:
            self.assertEqual(stream.read(), b"safe")
        self.assertEqual(client.calls, [{"Bucket": "approved-bucket", "Key": "approved/cf/file.gz"}])
        self.assertTrue(client.body.closed)

    def test_arbitrary_bucket_is_rejected_without_aws_call(self):
        client = FakeS3()
        with self.assertRaises(PermissionError):
            with open_source_stream(self.settings(), "s3://unapproved/approved/cf/file.gz", client):
                pass
        self.assertEqual(client.calls, [])

    def test_prefix_escape_is_rejected(self):
        client = FakeS3()
        with self.assertRaises(PermissionError):
            with open_source_stream(self.settings(), "s3://approved-bucket/private/other-file.gz", client):
                pass
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
