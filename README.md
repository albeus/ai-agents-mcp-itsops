# ai-agents-mcp-itsops

A small, local Model Context Protocol (MCP) server for learning MCP server design, tool discovery, tool execution and operational security boundaries.

> **Part of the [AI Agents Lab](https://github.com/albeus/ai-agents-lab).** This is a learning project, not a production service. Read the [Safety notice](#safety-notice) before pointing it at any real infrastructure.

## What this demonstrates

The server exposes a deliberately narrow set of read-only-style operations tools to an MCP-compatible client:

- `search_runbooks(query)` searches an approved local folder of Markdown runbooks.
- `host_health(host)` returns selected health information for the local host: disk, memory and failed systemd units. The `host` argument defaults to the local host.
- `k8s_pod_status(cluster, namespace)` returns a bounded pod-status summary for approved clusters and namespaces.

The tools are intentionally restricted. They show that an MCP server should expose a specific capability rather than general shell, filesystem, SSH or Kubernetes access.

## Safety notice

- The server process runs with the permissions of the local user and any kubeconfig you configure. Use a lab cluster and a least-privilege, read-only identity.
- Use only non-sensitive runbooks and data. Do not point it at production clusters or confidential documents.
- There is no authentication or per-user authorisation. Do not expose it to an untrusted network.
- Tool output is returned to a model, so anything the tools can read may end up in a model's context.

## Concepts explored

- MCP server and client interaction.
- Tool discovery through `tools/list` and invocation through `tools/call`.
- Typed tool arguments, with schemas generated from Python function signatures.
- Stdio as an MCP transport.
- Safe subprocess invocation using argument lists rather than shell strings.
- Allowlists for clusters and namespaces.
- Bounded output, to avoid flooding an agent's context window.
- Logging to standard error while reserving standard output for MCP messages.

## Requirements

- Python 3.12 or later.
- [uv](https://docs.astral.sh/uv/).
- Node.js 20 or later, for MCP Inspector.
- `kubectl` and a valid local kubeconfig, only if you use the Kubernetes tool.

## Installation

```bash
git clone https://github.com/albeus/ai-agents-mcp-itsops.git
cd ai-agents-mcp-itsops
uv venv
source .venv/bin/activate
uv sync
```

## Configuration

The server uses a server-side mapping of approved logical cluster names to kubeconfig files, Kubernetes contexts and allowed namespaces. Edit the mapping in the source to match your lab. Example:

```python
CLUSTERS = {
    "rke-lab": {
        "kubeconfig": Path.home() / "kubeconfigs" / "rke_cluster.yml",
        "context": "rke-lab",
        "namespaces": {"default", "monitoring", "lab"},
    },
}
```

The server, not the client, owns these boundaries. Do not expose arbitrary kubeconfig paths, contexts, namespaces, shell commands or SSH targets as unrestricted tool inputs.

For runbook search, create the folder and add a sample file:

```bash
mkdir -p ~/agent-lab/readable

printf '%s\n' \
  '# SSH Runbook' \
  'Check failed units with systemctl --failed.' \
  > ~/agent-lab/readable/ssh.md
```

## Running the server

From the project root:

```bash
uv run python src/mcp_itsops/server.py
```

The server appears idle. That is expected: a stdio MCP server waits for JSON-RPC requests on standard input. Stop it with `Ctrl+C`.

## Testing with MCP Inspector

Inspector launches the server as a child process:

```bash
npx @modelcontextprotocol/inspector \
  uv --directory . run python src/mcp_itsops/server.py
```

Open the local URL that Inspector prints, connect, and use the **Tools** tab.

1. Run **List Tools**.
2. Confirm each tool has the expected name, description and input schema.
3. Call `search_runbooks`:

   ```json
   { "query": "systemctl" }
   ```

4. Call `host_health` with its default argument:

   ```json
   {}
   ```

5. Call `k8s_pod_status` with an approved cluster and namespace:

   ```json
   { "cluster": "rke-lab", "namespace": "default" }
   ```

## Stdio safety rule

In the stdio transport, standard output is reserved for MCP JSON-RPC messages. Do not use `print()` for diagnostics, because ordinary text can corrupt the protocol stream. Use Python logging instead:

```python
logger.info(
    "Reading pod status: cluster=%s namespace=%s",
    cluster,
    namespace,
)
```

The default logging handler writes to standard error, which leaves standard output free for MCP communication.

## Security decisions

- No arbitrary shell-command tool and no `shell=True` subprocess calls.
- No arbitrary hostnames, SSH targets or kubeconfig paths.
- Explicit cluster and namespace allowlists.
- Fixed `kubectl` argument structure.
- Command timeouts.
- Trimmed and bounded tool output.
- Errors returned as tool results rather than uncaught exceptions.

These controls reduce the chance that an unsafe model decision, prompt injection or malformed client input becomes broad infrastructure access. They have not been independently reviewed or tested with an automated suite.

## Transport

This README documents the **stdio** transport, which is what the steps above use. The [LiteLLM gateway lab](https://github.com/albeus/ai-agents-litellm-gateway) registered this server over HTTP, so check the current code for how that mode is started and secured. It is not covered here.

<!-- TODO before publishing: confirm the HTTP start command in the code and either document it here or remove this note. -->

## Current limitations

This local learning server does not yet provide:

- Authentication or per-user authorisation.
- Gateway enforcement.
- Audit logging suitable for production.
- Workload identity or isolated Kubernetes credentials.
- Container sandboxing or network egress restrictions.
- Automated tests.

For production, the same narrow tool surface would need Streamable HTTP behind authenticated access, authorisation policies, structured audit logs, network controls and a gateway.

## Learning outcomes

- Explain the difference between an MCP client, server, host and tool.
- Inspect MCP tool schemas and raw JSON-RPC messages.
- Explain why stdio servers must not write logs to standard output.
- Recognise why arbitrary infrastructure identifiers should not become unrestricted tool inputs.
- Compare stdio for local development with Streamable HTTP for controlled remote deployment.

## Relationship to the rest of the lab

This project is an MCP server that publishes tools for any MCP client. It is a different thing from [`ai-agents-miniagent`](https://github.com/albeus/ai-agents-miniagent), which owns its own agent loop and runs its tools locally; `miniagent` is not currently an MCP client.

See the [lab index](https://github.com/albeus/ai-agents-lab) for the suggested reading order.

## Licence

Released under the [MIT Licence](LICENSE). This is a learning lab, provided as is, without warranty.
