"""Build the Claude Directory package; optionally publish its dedicated branch.

Dokumentasi pengembang; tidak disertakan dalam paket Claude Directory.

## Struktur

| File | Dipakai oleh |
|---|---|
| `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.mcp.json` | Claude (directory, Cowork, Claude Code) |
| `plugin.json`, `mcp.json` | Format [Agent Plugins](https://agent-plugins.org/) (ChatGPT/Codex dan aplikasi lain) |
| `gemini-extension.json` | Gemini CLI |
| `skills/` | Semua aplikasi di atas |

## Pengujian paket

Uji tanpa OAuth, model, atau jaringan:

```sh
python3 -m unittest discover -s tests/Unit -p 'test_*.py'
```

## Rilis Claude Directory

Claude Directory membaca branch `claude-directory`, dengan plugin path tetap di root. Branch `main` menyimpan source bersama untuk semua host dan tes pengembangan. Pemeriksaan Directory menolak file kode seperti tes Python untuk organisasi yang belum Verified, meskipun file tersebut tidak dijalankan plugin.

Siapkan folder keluaran kosong di luar repository, lalu jalankan:

```sh
python3 release_claude.py /tmp/kedeka-claude-2.2.4
```

Exporter menyertakan manifest Claude, ikon, `.mcp.json`, README, LICENSE, dan Markdown skill. Tes, script rilis, marketplace, serta manifest host lain tidak masuk paket. Perintah juga menjalankan `claude plugin validate`.

URL kebijakan privasi disimpan pada listing Claude Directory: `https://kedeka.com/privacy-policy`. Jangan menambahkan `privacyPolicyUrl` ke `.claude-plugin/plugin.json` karena field itu menimbulkan warning schema Claude Code. URL tetap tersedia di README dan manifest host lain.

Setelah tes lulus dan perubahan source di-commit, terbitkan paket memakai folder keluaran baru:

```sh
python3 release_claude.py /tmp/kedeka-claude-2.2.4-release --publish
```

Perintah ini mendorong commit baru ke branch `claude-directory` tanpa mengganti checkout `main` atau melakukan force-push. Setiap perubahan skill harus dirilis ulang lewat perintah tersebut. Di portal submission, gunakan **Settings → Tracked branch or tag: `claude-directory`**, lalu **Check for new commits**. Lolos validasi lokal belum menjamin lolos policy review atau publikasi oleh Anthropic.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
BRANCH = "claude-directory"
STATIC_FILES = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/icon.png",
    ".mcp.json",
    "README.md",
    "LICENSE",
)


def git(*args, **kwargs):
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], text=True, **kwargs
    ).strip()


def build(source, output):
    """Export only Claude metadata, the remote connector, and Markdown skills."""
    source = source.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty")
    files = [Path(name) for name in STATIC_FILES]
    files += sorted(path.relative_to(source) for path in (source / "skills").rglob("*.md"))
    for relative in files:
        path = source / relative
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise ValueError(f"Symlinks are not allowed: {relative}")
        data = path.read_bytes()
        if relative.suffix == ".png":
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError(f"Invalid PNG: {relative}")
        else:
            data.decode("utf-8")
            if data.startswith(b"#!") or b"\x00" in data:
                raise ValueError(f"Executable or non-text content: {relative}")
            if relative.suffix == ".json":
                json.loads(data)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return files


def publish(output, files):
    """Push a normal fast-forward release without changing the source checkout."""
    if git("status", "--porcelain"):
        raise ValueError("Commit source changes before publishing")
    source_commit = git("rev-parse", "HEAD")
    ref = f"refs/heads/{BRANCH}"
    parent = git("ls-remote", "origin", ref).split()
    if parent:
        git("fetch", "origin", ref)
        parent = ["-p", git("rev-parse", "FETCH_HEAD")]
    # Retain source ancestry so GitHub can compare this release to versions
    # previously submitted from main, while the release tree stays filtered.
    parent += ["-p", source_commit]
    with tempfile.TemporaryDirectory(prefix="kedeka-claude-index-") as directory:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(directory) / "index")}
        git("read-tree", "--empty", env=env)
        for relative in files:
            blob = git("hash-object", "-w", str(output / relative))
            git("update-index", "--add", "--cacheinfo", "100644", blob,
                relative.as_posix(), env=env)
        tree = git("write-tree", env=env)
    version = json.loads((output / ".claude-plugin/plugin.json").read_text())["version"]
    commit = git("commit-tree", tree, *parent, "-m",
                 f"build: release claude plugin {version}\n\nSource: {source_commit}")
    subprocess.run(["git", "-C", str(ROOT), "push", "origin", f"{commit}:{ref}"], check=True)
    return commit


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, help="An empty output directory outside the repository")
    parser.add_argument("--publish", action="store_true", help=f"Push origin/{BRANCH}")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error("Output must be outside the source repository")
    files = build(ROOT, output)
    subprocess.run(["claude", "plugin", "validate", str(output)], check=True)
    print(f"Exported {len(files)} files to {output}")
    if args.publish:
        print(f"Published {publish(output, files)} to {BRANCH}")


if __name__ == "__main__":
    main()
