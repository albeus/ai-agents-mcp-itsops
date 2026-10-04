import json
import logging
import subprocess
import time
from pathlib import Path
import os

from mcp.server.mcpserver import MCPServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = MCPServer("ITS Operations")

RUNBOOK_ROOT = Path.home() / "agent-lab" / "readable"
MAX_OUTPUT_LENGTH = 2000


@mcp.tool()
def search_runbooks(query: str) -> str:
    """Search approved Markdown runbooks for a text query."""
    matches = []

    for note in RUNBOOK_ROOT.rglob("*.md"):
        try:
            for line_number, line in enumerate(
                note.read_text(errors="replace").splitlines(),
                start=1,
            ):
                if query.lower() in line.lower():
                    relative_path = note.relative_to(RUNBOOK_ROOT)
                    matches.append(f"{relative_path}:{line_number}: {line}")

                    if len(matches) >= 20:
                        return "\n".join(matches)
        except OSError as exc:
            logger.warning("Could not read %s: %s", note, exc)

    return "\n".join(matches) if matches else "No matching runbooks found."


def _run_readonly_command(args: list[str]) -> str:
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return "Command timed out after 10 seconds."
    except OSError as exc:
        return f"Could not execute command: {exc}"

    output = result.stdout or result.stderr

    if len(output) > MAX_OUTPUT_LENGTH:
        return output[:MAX_OUTPUT_LENGTH] + f"\n[Output truncated at {MAX_OUTPUT_LENGTH} characters]"

    return output.strip()


@mcp.tool()
def host_health(host: str = "local") -> str:
    """Return read-only disk, memory, and failed-systemd-unit status for the local lab host."""
    if host != "local":
        return "Error: this lab server supports only host='local'."

    disk = _run_readonly_command(["df", "-h", "/"])
    memory = _run_readonly_command(["free", "-h"])
    failed_units = _run_readonly_command(
        ["systemctl", "--failed", "--no-legend", "--plain"]
    )

    return (
        f"Host: {host}\n\n"
        f"Disk:\n{disk}\n\n"
        f"Memory:\n{memory}\n\n"
        f"Failed systemd units:\n{failed_units or 'None'}"
    )


CLUSTERS = {
    "rke-lab": {
        "kubeconfig": Path.home() / "kubeconfigs" / "rke_cluster.yml",
        "context": "rke-lab",
        "namespaces": {"default", "monitoring", "lab"},
    },
    "kind-lab": {
        "kubeconfig": Path.home() / ".kube" / "config",
        "context": "kind-lab",
        "namespaces": {"default", "monitoring"},
    },
}

@mcp.tool()
def k8s_pod_status(
    cluster: str = "rke-lab",
    namespace: str = "default",
) -> str:
    """Return a bounded pod-status summary from an approved cluster and namespace."""
    config = CLUSTERS.get(cluster)

    if config is None:
        return f"Error: cluster must be one of: {', '.join(sorted(CLUSTERS))}"

    if namespace not in config["namespaces"]:
        allowed = ", ".join(sorted(config["namespaces"]))
        return f"Error: namespace must be one of: {allowed}"

    args = [
        "kubectl",
        "--kubeconfig",
        str(config["kubeconfig"]),
        "--context",
        config["context"],
        "get",
        "pods",
        "--namespace",
        namespace,
        "--output",
        "json",
    ]

    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return "kubectl timed out after 10 seconds."
    except OSError as exc:
        return f"Could not execute kubectl: {exc}"

    if result.returncode != 0:
        return f"kubectl failed: {result.stderr.strip()}"

    try:
        pods = json.loads(result.stdout)["items"]
    except (json.JSONDecodeError, KeyError):
        return "Error: kubectl returned an unexpected JSON response."

    lines = [
        f"Namespace: {namespace}",
        "NAME\tREADY\tSTATUS\tRESTARTS\tAGE",
    ]

    for pod in pods[:50]:
        name = pod["metadata"]["name"]
        phase = pod.get("status", {}).get("phase", "Unknown")
        statuses = pod.get("status", {}).get("containerStatuses", [])

        ready = sum(status.get("ready", False) for status in statuses)
        total = len(statuses)
        restarts = sum(status.get("restartCount", 0) for status in statuses)
        age = pod["metadata"].get("creationTimestamp", "unknown")

        lines.append(f"{name}\t{ready}/{total}\t{phase}\t{restarts}\t{age}")

    if len(pods) > 50:
        lines.append(f"... {len(pods) - 50} additional pods omitted")

    return "\n".join(lines)


@mcp.tool()
def slow_probe(seconds: int = 10) -> str:
    """Deliberately slow lab-only probe for timeout and tracing tests."""
    if seconds < 0 or seconds > 10:
        return "Error: seconds must be between 0 and 10."

    time.sleep(seconds)
    return f"Completed after {seconds} seconds."


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=os.environ.get("MCP_HOST", "127.0.0.1"),
            port=int(os.environ.get("MCP_PORT", "8000")),
            stateless_http=True,
            json_response=True,
        )
    else:
        mcp.run()
