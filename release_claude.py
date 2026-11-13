"""Build the Claude Directory package; optionally publish its dedicated branch."""
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
    parser = argparse.ArgumentParser(description=__doc__)
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
