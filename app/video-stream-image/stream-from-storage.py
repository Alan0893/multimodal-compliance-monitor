#!/usr/bin/env python3
"""Download an MP4 from aws-compatible-storage (S4) and publish it to MediaMTX."""

import os
import socket
import sys
import time

import boto3
from botocore.client import Config


def env(*names, default=""):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def wait_for_tcp(host, port, attempts=60, delay_s=2):
    for attempt in range(1, attempts + 1):
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError as exc:
            print(f"MediaMTX {host}:{port} not ready (attempt {attempt}/{attempts}): {exc}")
            time.sleep(delay_s)
    raise SystemExit(f"MediaMTX {host}:{port} not reachable")


def main():
    endpoint = env("AWS_ENDPOINT_URL", "MINIO_ENDPOINT", default="http://aws-compatible-storage:7480")
    bucket = env("VIDEO_BUCKET", "MINIO_VIDEO_BUCKET", default="data")
    key = env("VIDEO_KEY", "MINIO_VIDEO_KEY", default="combined-video-no-gap-rooftop.mp4")
    host = env("MEDIAMTX_HOST", default="video-stream")
    port = int(env("MEDIAMTX_PORT", default="8554"))
    dest = "/tmp/video.mp4"

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=env("AWS_ACCESS_KEY_ID", "MINIO_ACCESS_KEY", default="s4admin"),
        aws_secret_access_key=env("AWS_SECRET_ACCESS_KEY", "MINIO_SECRET_KEY", default="s4secret"),
        region_name=env("AWS_DEFAULT_REGION", default="us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    last_error = None
    for attempt in range(1, 61):
        try:
            client.download_file(bucket, key, dest)
            break
        except Exception as exc:  # noqa: BLE001 - object may still be uploading
            last_error = exc
            print(f"Download s3://{bucket}/{key} failed (attempt {attempt}/60): {exc}")
            time.sleep(5)
    else:
        raise SystemExit(f"Could not download s3://{bucket}/{key}: {last_error}")

    if not os.path.isfile(dest) or os.path.getsize(dest) <= 0:
        raise SystemExit(f"{dest} missing or empty after download")

    wait_for_tcp(host, port)
    path = env("MEDIAMTX_PATH", default="live")
    rtsp = f"rtsp://{host}:{port}/{path}"
    print(f"Starting FFmpeg stream to {rtsp}")
    os.execvp(
        "ffmpeg",
        [
            "ffmpeg",
            "-re",
            "-stream_loop",
            "-1",
            "-i",
            dest,
            "-c",
            "copy",
            "-f",
            "rtsp",
            rtsp,
        ],
    )


if __name__ == "__main__":
    sys.exit(main())
