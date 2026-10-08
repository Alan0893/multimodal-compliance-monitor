#!/usr/bin/env python3
"""Upload model and video objects to aws-compatible-storage (S4).

Idempotent: existing objects are left in place. Replaces the former minio/mc uploader.
"""

import os
import sys
import time

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


def env(*names, default=""):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=env("AWS_ENDPOINT_URL", "MINIO_ENDPOINT", default="http://aws-compatible-storage:7480"),
        aws_access_key_id=env("AWS_ACCESS_KEY_ID", "MINIO_ACCESS_KEY", default="s4admin"),
        aws_secret_access_key=env("AWS_SECRET_ACCESS_KEY", "MINIO_SECRET_KEY", default="s4secret"),
        region_name=env("AWS_DEFAULT_REGION", default="us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def wait_for_s3(client, attempts=60, delay_s=2):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            client.list_buckets()
            print("S3 connection established")
            return
        except Exception as exc:  # noqa: BLE001 - readiness retry
            last_error = exc
            print(f"S3 not ready (attempt {attempt}/{attempts}): {exc}")
            time.sleep(delay_s)
    raise SystemExit(f"S3 not reachable: {last_error}")


def ensure_bucket(client, name):
    try:
        client.create_bucket(Bucket=name)
        print(f"Created bucket {name}")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"} or status == 409:
            print(f"Bucket {name} already exists")
            return
        raise


def object_exists(client, bucket, key):
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
            return False
        raise


def upload_file(client, local_path, bucket, key):
    client.upload_file(local_path, bucket, key)
    print(f"Uploaded {local_path} to s3://{bucket}/{key}")


def upload_tree(client, local_dir, bucket, prefix):
    local_dir = local_dir.rstrip("/")
    for root, _, files in os.walk(local_dir):
        for name in files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, local_dir).replace(os.sep, "/")
            key = f"{prefix.rstrip('/')}/{rel}"
            upload_file(client, path, bucket, key)


def regen_ovms_config():
    mount_base = os.environ.get("OVMS_CLUSTER_MOUNT_BASE", "/mnt/models")
    nireq = os.environ.get("OVMS_CONFIG_NIREQ", "2")
    plugin = os.environ.get("OVMS_CONFIG_PLUGIN_CONFIG") or '{"PERFORMANCE_HINT": "THROUGHPUT"}'
    shape = os.environ.get("OVMS_CONFIG_SHAPE", "")
    out = "/tmp/ovms-config.json"
    blocks = []
    ovms_root = "/upload/models/ovms"
    for name in sorted(os.listdir(ovms_root)):
        directory = os.path.join(ovms_root, name)
        if not os.path.isdir(directory) or name.endswith("-onnx"):
            continue
        if not os.path.isfile(os.path.join(directory, "1", f"{name}.xml")):
            continue
        body = (
            "    {\n"
            '      "config": {\n'
            f'        "name": "{name}",\n'
            f'        "base_path": "{mount_base}/{name}",\n'
            f'        "nireq": {nireq},\n'
            f'        "plugin_config": {plugin}'
        )
        if shape:
            body += f",\n        \"shape\": {shape}"
        body += "\n      }\n    }"
        blocks.append(body)
    content = "{\n  \"model_config_list\": [\n" + ",\n".join(blocks) + "\n  ]\n}\n"
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"Regenerated config.json (nireq={nireq})")
    return out


def list_top(client, bucket):
    print(f"--- {bucket} bucket ---")
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Delimiter": "/"}
        if token:
            kwargs["ContinuationToken"] = token
        response = client.list_objects_v2(**kwargs)
        for prefix in response.get("CommonPrefixes", []):
            print(prefix["Prefix"])
        for obj in response.get("Contents", []):
            print(obj["Key"])
        if not response.get("IsTruncated"):
            break
        token = response.get("NextContinuationToken")


def main():
    print("=== PPE Compliance Monitor Data Uploader ===")
    client = s3_client()
    wait_for_s3(client)

    buckets = [
        name.strip()
        for name in env("BUCKETS", default="models,data,config").split(",")
        if name.strip()
    ]
    print("Creating buckets...")
    for name in buckets:
        ensure_bucket(client, name)
    print("Buckets ready")

    runtime_type = os.environ.get("RUNTIME_TYPE", "")
    print(f"Runtime type: {runtime_type}")

    ovms_root = "/upload/models/ovms"
    if os.path.isdir(ovms_root):
        print("Checking / uploading OpenVINO model trees (ovms/<model>/1/)...")
        for name in sorted(os.listdir(ovms_root)):
            directory = os.path.join(ovms_root, name)
            if not os.path.isdir(directory) or name.endswith("-onnx"):
                continue
            if not os.path.isfile(os.path.join(directory, "1", f"{name}.xml")):
                continue
            key = f"ovms/{name}/1/{name}.xml"
            if not object_exists(client, "models", key):
                print(f"Uploading OpenVINO model: ovms/{name}/")
                upload_tree(client, directory + "/", "models", f"ovms/{name}")
            else:
                print(f"OpenVINO ovms/{name} already present, skipping")
        config_file = os.path.join(ovms_root, "config.json")
        if any(
            os.environ.get(name)
            for name in ("OVMS_CONFIG_NIREQ", "OVMS_CONFIG_PLUGIN_CONFIG", "OVMS_CONFIG_SHAPE")
        ):
            config_file = regen_ovms_config()
        if os.path.isfile(config_file):
            print("Uploading OpenVINO config.json (multi-model OVMS)...")
            upload_file(client, config_file, "models", "ovms/config.json")

    if runtime_type == "kserve":
        print("Checking / uploading Triton ONNX model trees (triton/<model>/1/model.onnx)...")
        triton_root = "/upload/models/triton"
        if os.path.isdir(triton_root):
            for name in sorted(os.listdir(triton_root)):
                directory = os.path.join(triton_root, name)
                onnx_path = os.path.join(directory, "1", "model.onnx")
                if not os.path.isdir(directory) or not os.path.isfile(onnx_path):
                    continue
                key = f"triton/{name}/1/model.onnx"
                if not object_exists(client, "models", key):
                    print(f"Uploading Triton ONNX model: triton/{name}/")
                    upload_tree(client, directory + "/", "models", f"triton/{name}")
                else:
                    print(f"Triton ONNX {name} already present, skipping")
        pbtxt = "/upload/triton-config/config.pbtxt"
        ppe_onnx = "/upload/models/triton/ppe/1/model.onnx"
        if os.path.isfile(pbtxt) and os.path.isfile(ppe_onnx):
            print("Uploading Triton config for triton/ppe/...")
            upload_file(client, pbtxt, "models", "triton/ppe/config.pbtxt")
    elif runtime_type == "openvino":
        print("Skipping Triton ONNX uploads (runtime is OpenVINO).")
    else:
        print(f"ERROR: Unknown RUNTIME_TYPE '{runtime_type}'. Expected 'openvino' or 'kserve'.")
        return 1

    print("Uploading raw .pt files (for reference / other runtimes)...")
    pt_root = "/upload/models-pt"
    if os.path.isdir(pt_root):
        for name in sorted(os.listdir(pt_root)):
            if not name.endswith(".pt"):
                continue
            path = os.path.join(pt_root, name)
            if not object_exists(client, "models", name):
                print(f"Uploading {name}")
                upload_file(client, path, "models", name)
            else:
                print(f"{name} already in bucket, skipping")

    print("Checking sample videos in data bucket...")
    for vid in ("cars.mp4", "combined-video-no-gap-rooftop.mp4", "bluejayclear.mp4"):
        local = f"/upload/data/{vid}"
        if not os.path.isfile(local):
            raise SystemExit(f"missing local video {local}")
        if not object_exists(client, "data", vid):
            print(f"Uploading video ({vid})...")
            upload_file(client, local, "data", vid)
            print(f"Uploaded {vid}")
        else:
            print(f"{vid} already in bucket, skipping")

    print("=== Data upload complete ===")
    print("")
    print("Files in object storage:")
    list_top(client, "models")
    list_top(client, "data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
