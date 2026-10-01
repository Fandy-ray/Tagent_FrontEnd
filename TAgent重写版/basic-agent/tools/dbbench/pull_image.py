"""经本机代理从 Docker Hub 下载 linux/arm64 镜像，打成 OCI 布局 tar 交给 docker load。

Docker Desktop 自带的拉取代理在这台机器上连不上任何仓库（EOF）；本机代理 17897 能通但时好时坏，
所以所有请求都交给 curl：自动重试、断点续传。用法：python pull_image.py postgres:16-alpine out.tar
"""
import hashlib, json, os, subprocess, sys, tarfile, tempfile

PROXY = "http://127.0.0.1:17897"
ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])


def curl(url, out, headers=(), resume=False, attempts=6):
    """headers 可以是函数：每次重试现取（令牌约 5 分钟过期，大层在慢网上下不完一轮）。"""
    base = ["curl", "-sS", "-L", "--fail", "-x", PROXY, "--connect-timeout", "10",
            "--speed-limit", "2000", "--speed-time", "60", "-o", out]
    if resume:
        base += ["-C", "-"]
    for attempt in range(attempts):
        if attempt:
            import time
            time.sleep(min(10, 2 * attempt))  # 代理抽风时别连环猛打
        cmd = list(base)
        for header in (headers() if callable(headers) else headers):
            cmd += ["-H", header]
        if subprocess.run(cmd + [url]).returncode == 0:
            return
        size = os.path.getsize(out) if os.path.exists(out) else 0
        print(f"  curl retry {attempt + 1} (have {size / 1e6:.1f} MB): {url[:90]}", flush=True)
    raise SystemExit(f"download failed: {url}")


def main(ref, out):
    name, tag = ref.split(":")
    repo = name if "/" in name else f"library/{name}"
    # 固定工作目录：断了重跑能接着下，不从头来
    work = os.path.join(os.path.dirname(os.path.abspath(out)), "work-" + name.split("/")[-1])
    os.makedirs(work, exist_ok=True)
    tok = os.path.join(work, "token.json")

    def fresh_auth():
        # Docker Hub 的令牌约 5 分钟过期；慢网下一层要下好几分钟，所以每层前都换一个
        curl(f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull", tok, attempts=30)
        return f"Authorization: Bearer {json.load(open(tok))['token']}"

    auth = fresh_auth()
    base = f"https://registry-1.docker.io/v2/{repo}"

    def manifest(reference):
        path = os.path.join(work, "manifest.json")
        curl(f"{base}/manifests/{reference}", path, [auth, f"Accept: {ACCEPT}"])
        raw = open(path, "rb").read()
        return raw, json.loads(raw)

    raw, doc = manifest(tag)
    if "manifests" in doc:
        pick = next(m for m in doc["manifests"]
                    if m.get("platform", {}).get("os") == "linux" and m["platform"].get("architecture") == "arm64")
        raw, doc = manifest(pick["digest"])
    manifest_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    media_type = doc.get("mediaType") or "application/vnd.oci.image.manifest.v1+json"

    files = {manifest_digest: None}
    for blob in [doc["config"]] + doc["layers"]:
        path = os.path.join(work, blob["digest"].split(":")[1])
        if os.path.exists(path) and "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest() == blob["digest"]:
            files[blob["digest"]] = path
            print(f"  {blob['digest'][:19]} already downloaded", flush=True)
            continue
        curl(f"{base}/blobs/{blob['digest']}", path, lambda: [fresh_auth()], resume=True, attempts=60)
        got = "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()
        assert got == blob["digest"], f"digest mismatch {blob['digest']}"
        files[blob["digest"]] = path
        print(f"  {blob['digest'][:19]} {os.path.getsize(path) / 1e6:.1f} MB ok", flush=True)

    index = {"schemaVersion": 2, "manifests": [{
        "mediaType": media_type, "digest": manifest_digest, "size": len(raw),
        "annotations": {"io.containerd.image.name": f"docker.io/{repo}:{tag}", "org.opencontainers.image.ref.name": tag},
    }]}
    with tarfile.open(out, "w") as tar:
        def add_bytes(path, data):
            import io
            info = tarfile.TarInfo(path); info.size = len(data); tar.addfile(info, io.BytesIO(data))
        add_bytes("oci-layout", b'{"imageLayoutVersion": "1.0.0"}')
        add_bytes("index.json", json.dumps(index).encode())
        add_bytes(f"blobs/sha256/{manifest_digest.split(':')[1]}", raw)
        for digest, path in files.items():
            if path:
                tar.add(path, arcname=f"blobs/sha256/{digest.split(':')[1]}")
    print(f"{ref} -> {out} ({os.path.getsize(out) / 1e6:.1f} MB)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
