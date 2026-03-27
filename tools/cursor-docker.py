#!/usr/bin/env python3
"""
cursor-docker: Run Cursor AI agent in a Docker container.

This tool manages a Docker-based Cursor AI environment, automatically
fetching the latest version and building the container as needed.
"""

import argparse
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

VERSION = "1.0.0"
CURSOR_INSTALL = "https://cursor.com/install"

DEFAULT_DOCKER_ARGS = ""

DOCKERFILE = """
FROM debian:trixie AS cursor

ARG CURSOR_VERSION
ARG USER_UID=1000
ARG USER_GID=1000
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    ca-certificates \
    sudo

# wtf cursor, piping to bash install script??
RUN curl https://cursor.com/install -fsS | bash
RUN mv /root/.local/share/cursor-agent /usr/local/share/cursor-agent && \
    ln -s /usr/local/share/cursor-agent/versions/$CURSOR_VERSION/cursor-agent /usr/local/bin/cursor-agent

RUN if ! getent group $USER_GID > /dev/null 2>&1; then groupadd -g $USER_GID cursor; fi
RUN useradd -u $USER_UID -g $USER_GID -m -d /workspace cursor
RUN usermod -aG sudo cursor
RUN echo "cursor ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

VOLUME /workspace
WORKDIR /workspace
USER cursor

CMD ["cursor"]
"""

def get_cursor_version() -> str:
    """Fetch the latest Cursor version from the install page."""
    with urlopen(CURSOR_INSTALL) as response:
        content = response.read().decode("utf-8")
    match = re.search(r"https://downloads\.cursor\.com/lab/([^/\"]+)", content)
    if not match:
        raise RuntimeError("Could not find Cursor version in install page")
    return match.group(1)


def docker_image_exists(image: str) -> bool:
    """Check if a Docker image exists locally."""
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
    )
    return result.returncode == 0


def setup_cursor_dirs() -> tuple[Path, Path]:
    """Create cursor-home and cursor-docker directories, write Dockerfile and docker-args if needed."""
    home = Path.home()
    cursor_home = home / ".config" / "cursor-docker" / "cursor-home"
    cursor_docker = home / ".config" / "cursor-docker" / "cursor-docker"

    cursor_home.mkdir(parents=True, exist_ok=True)
    cursor_docker.mkdir(parents=True, exist_ok=True)

    dockerfile = cursor_docker / "Dockerfile"
    if not dockerfile.exists():
        dockerfile.write_text(DOCKERFILE.lstrip())

    docker_args_file = cursor_docker / "docker-args"
    if not docker_args_file.exists():
        docker_args_file.write_text(DEFAULT_DOCKER_ARGS)

    return cursor_home, cursor_docker


def read_docker_args(cursor_docker: Path) -> list[str]:
    """Read additional docker arguments from docker-args file."""
    docker_args_file = cursor_docker / "docker-args"
    if not docker_args_file.exists():
        return []

    content = docker_args_file.read_text()
    # Filter out comments and empty lines, then parse with shlex
    lines = []
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(line)

    if not lines:
        return []

    # Join lines and parse as shell arguments
    return shlex.split(" ".join(lines))


def get_user_ids() -> tuple[int, int]:
    """Get the current user's UID and primary GID."""
    uid = os.getuid()
    gid = os.getgid()
    return uid, gid


def build_docker_image(version: str, dockerfile_path: Path) -> None:
    """Build the Cursor Docker image."""
    uid, gid = get_user_ids()
    print(f"Docker image 'cursor' not found. Building version {version}...")
    print(f"Using UID={uid}, GID={gid}")
    subprocess.run(
        [
            "docker", "buildx", "build",
            "--build-arg", f"CURSOR_VERSION={version}",
            "--build-arg", f"USER_UID={uid}",
            "--build-arg", f"USER_GID={gid}",
            "--tag", f"cursor:{version}",
            str(dockerfile_path),
        ],
        check=True,
    )


def get_config_dir() -> Path:
    """Return the configuration directory path."""
    return Path.home() / ".config" / "cursor-docker"


def cmd_run(args: argparse.Namespace) -> None:
    """Run the Cursor container."""
    cursor_home, cursor_docker = setup_cursor_dirs()

    version = get_cursor_version()
    image = f"cursor:{version}"

    if args.rebuild or not docker_image_exists(image):
        build_docker_image(version, cursor_docker)

    extra_args = read_docker_args(cursor_docker)

    docker_cmd = [
        "docker", "run", "-it", "--rm",
        "-v", f"{cursor_home}:/workspace",
        *extra_args,
        image,
        "/bin/bash",
    ]

    os.execvp("docker", docker_cmd)


def cmd_config(args: argparse.Namespace) -> None:
    """Show configuration information."""
    config_dir = get_config_dir()
    uid, gid = get_user_ids()
    print(f"Configuration directory: {config_dir}")
    print(f"  Dockerfile:   {config_dir / 'cursor-docker' / 'Dockerfile'}")
    print(f"  Docker args:  {config_dir / 'cursor-docker' / 'docker-args'}")
    print(f"  Cursor home:  {config_dir / 'cursor-home'}")
    print(f"User IDs (used when building image):")
    print(f"  UID: {uid}")
    print(f"  GID: {gid}")


def cmd_version(args: argparse.Namespace) -> None:
    """Show version information."""
    print(f"cursor-docker version {VERSION}")
    try:
        cursor_version = get_cursor_version()
        print(f"Latest Cursor version: {cursor_version}")
    except Exception as e:
        print(f"Could not fetch Cursor version: {e}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="cursor-docker",
        description="Run Cursor AI agent in a Docker container.",
        epilog=f"Configuration is stored in: {get_config_dir()}",
    )
    parser.add_argument(
        "-V", "--version",
        action="store_true",
        help="show version information and exit",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # run command (default)
    run_parser = subparsers.add_parser(
        "run",
        help="start the Cursor container (default)",
        description="Start the Cursor AI container. Builds the image if needed.",
    )
    run_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="force rebuild the Docker image even if it exists",
    )

    # config command
    subparsers.add_parser(
        "config",
        help="show configuration paths",
        description="Display the paths to configuration files.",
    )

    # version command
    subparsers.add_parser(
        "version",
        help="show version information",
        description="Display cursor-docker and Cursor versions.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.version:
        cmd_version(args)
        return

    if args.command is None or args.command == "run":
        # Default to run if no command specified
        if not hasattr(args, "rebuild"):
            args.rebuild = False
        cmd_run(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command == "version":
        cmd_version(args)


if __name__ == "__main__":
    main()