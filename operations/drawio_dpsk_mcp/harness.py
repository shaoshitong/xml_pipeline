"""Launch a headless DPSK session with only its case and verifier bridge mounted."""

from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "dpsk_skills/drawio-reconstruction"


def run(runtime, credentials, profile, case, output, prompt, *, socket_dir=None, timeout=1200):
    output.mkdir(parents=True, exist_ok=True)
    home = output / "home"
    profile_home = home / ".dsh/profiles/headless"
    if not profile_home.exists():
        shutil.copytree(profile, profile_home)
    skills = case / ".agents/skills"
    skills.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL, skills / SKILL.name, dirs_exist_ok=True)
    command = [
        "bwrap", "--unshare-all", "--share-net", "--new-session", "--die-with-parent", "--clearenv",
        "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--ro-bind", str(runtime), "/runtime", "--ro-bind", str(credentials), "/account.yml",
        "--ro-bind", str(HERE / "headless.yml"), "/integration/headless.yml",
        "--bind", str(case), "/case",
        "--bind", str(home), "/session", "--setenv", "HOME", "/session",
        "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "LANG", "C.UTF-8",
        "--setenv", "DSH_HOME", "/session/.dsh", "--setenv", "DSH_PERMISSION_MODE", "workspace-write",
        "--setenv", "DSH_TELEMETRY_DISABLED", "1", "--chdir", "/case",
    ]
    for name in ("resolv.conf", "hosts", "nsswitch.conf", "ssl/certs"):
        path = f"/etc/{name}"
        command.extend(("--ro-bind", path, path))
    patches = ["--patch", "/integration/headless.yml"]
    if socket_dir:
        command.extend(("--ro-bind", str(socket_dir), "/verifier",
                        "--ro-bind", str(HERE / "mcp.yml"), "/integration/mcp.yml",
                        "--ro-bind", str(HERE / "mcp_bridge.py"), "/integration/mcp_bridge.py"))
        patches.extend(("--patch", "/integration/mcp.yml"))
    command.extend(("--", "/usr/bin/node", "/runtime/node_modules/@deepseek-ai/dsh/lib/bin.js",
                    "--profile", "headless", *patches, "--json", prompt))
    with (output / "events.jsonl").open("xb") as events, (output / "stderr.log").open("xb") as errors:
        return subprocess.run(command, stdin=subprocess.DEVNULL, stdout=events, stderr=errors,
                              timeout=timeout, check=False).returncode
