"""Object storage adapter for production media artifacts."""

from pathlib import Path


class S3Storage:
    name = "s3"

    def __init__(self, bucket: str, region: str | None = None) -> None:
        import boto3
        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

    def upload(self, local_path: str, key: str, *, content_type: str | None = None) -> str:
        extra = {"ContentType": content_type} if content_type else {}
        self.client.upload_file(local_path, self.bucket, key, ExtraArgs=extra)
        return f"s3://{self.bucket}/{key}"

    def download(self, key: str, local_path: str) -> str:
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(destination))
        return str(destination)
