# ai-agents-mcp-itsops

A small, local Model Context Protocol (MCP) server for learning MCP server design, tool discovery, tool execution and operational security boundaries.

> **Part of the [AI Agents Lab](https://github.com/albeus/ai-agents-lab).** This is a learning project, not a production service. Read the [Safety notice](#safety-notice) before pointing it at any real infrastructure.

## What this demonstrates

The server exposes a deliberately narrow set of read-only-style operations tools to an MCP-compatible client:

- `search_runbooks(query)` searches an approved local folder of Markdown runbooks.
- `host_health(host)` returns selected health information for the local host: disk, memory and failed systemd units. The `host` argument defaults to `"local"`; other hosts are rejected.
- `k8s_pod_status(cluster, namespace)` returns a pod-status summary for approved clusters and namespaces, limited to the first 50 pods.
- `slow_probe(seconds)` is a deliberately slow, lab-only tool for timeout and tracing tests. It defaults to 10 seconds and accepts values between 0 and 10 inclusive.

The operations tools are intentionally restricted. They demonstrate exposing specific capabilities rather than general shell, filesystem, SSH or Kubernetes access. `slow_probe` is a test fixture, not an operations capability.

## Safety notice

- The server process runs with the permissions of the local user and any kubeconfig you configure. Use a lab cluster and a least-privilege, read-only identity.
- Use only non-sensitive runbooks and data. Do not point it at production clusters or confidential documents.
- There is no authentication or per-user authorisation. Do not expose it to an untrusted network.
- HTTP defaults to `127.0.0.1`. Setting `MCP_HOST=0.0.0.0` exposes the listener on all IPv4 interfaces; check your firewall before doing this for the container-based gateway lab.
- Tool results can enter a model's context when the client passes them to a model. Inspector can exercise tools without a model.
- A client timeout does not establish that server-side work has stopped. Use `slow_probe` only in the lab.

## Concepts explored

- MCP server and client interaction.
- Tool discovery through `tools/list` and invocation through `tools/call`.
- Typed tool arguments, with schemas generated from Python function signatures.
- Stdio for local, client-managed processes and Streamable HTTP for the gateway lab.
- Safe subprocess invocation using argument lists rather than shell strings.
- Allowlists for clusters and namespaces.
- Output limits to reduce how much data enters an agent's context.
- Logging to standard error while reserving standard output for stdio MCP messages.

## Requirements

- Python 3.12 or later.
- [uv](https://docs.astral.sh/uv/).
- Node.js 20 or later, for MCP Inspector.
- Linux diagnostic commands (`df`, `free` and `systemctl`) for `host_health`. Environments without systemd may return an error for the systemd check.
- `kubectl` and a valid local kubeconfig, only if you use the Kubernetes tool.

Use the project's dependency configuration and lockfile to reproduce the SDK environment. MCP client and server versions matter; do not assume that any Inspector or SDK release will work with every protocol revision.

## Installation

```bash
git clone https://github.com/albeus/ai-agents-mcp-itsops.git
cd ai-agents-mcp-itsops
uv sync
```

Run all commands below from this repository's root. The standard invocation is:

```bash
uv run python -m mcp_itsops.server
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

### Transport settings

The entry point selects the transport through environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MCP_TRANSPORT` | `stdio` | Set to `streamable-http` to enable HTTP. |
| `MCP_HOST` | `127.0.0.1` | HTTP bind address; not used in stdio mode. |
| `MCP_PORT` | `8000` | HTTP port; not used in stdio mode. |

HTTP mode uses `stateless_http=True` and `json_response=True`. The lab endpoint is `/mcp`.

Use only the documented transport values. The current entry point falls back to stdio for values other than `streamable-http`, so a typo can make an intended HTTP server wait on stdin instead.

## Running the server

### Stdio (default)

```bash
uv run python -m mcp_itsops.server
```

The server appears idle. That is expected: a stdio MCP server waits for JSON-RPC requests on standard input. It is not an interactive chat prompt. Stop it with `Ctrl+C`.

Normally, a stdio client such as Inspector launches its own server process; do not start a separate process first.

### Streamable HTTP (local testing)

```bash
MCP_TRANSPORT=streamable-http \
MCP_HOST=127.0.0.1 \
MCP_PORT=8000 \
uv run python -m mcp_itsops.server
```

Keep this terminal running. Connect an HTTP-capable client to [the local MCP endpoint](http://127.0.0.1:8000/mcp).

### Streamable HTTP (LiteLLM container)

In the gateway lab, the LiteLLM container reaches the host through `host.docker.internal`. Start the server with an explicitly wider bind:

```bash
MCP_TRANSPORT=streamable-http \
MCP_HOST=0.0.0.0 \
MCP_PORT=8000 \
uv run python -m mcp_itsops.server
```

This is not loopback-only and does not add authentication. Restrict access with the host firewall and stop the server when you finish. See the [LiteLLM gateway lab](https://github.com/albeus/ai-agents-litellm-gateway) for the corresponding gateway configuration and its recorded limitations.

## Testing with MCP Inspector

### Stdio workflow

Inspector launches the server as a child process. Explicitly select stdio so a previously exported HTTP setting cannot change the transport:

```bash
MCP_TRANSPORT=stdio \
npx @modelcontextprotocol/inspector \
  uv run python -m mcp_itsops.server
```

Open the local URL Inspector prints, select the stdio connection if needed, and connect. Use the **Tools** tab to discover and call tools.

### HTTP workflow

Start the server in HTTP mode in one terminal using the local-testing command above. In another terminal, start Inspector without a child-process command:

```bash
npx @modelcontextprotocol/inspector
```

Open the URL Inspector prints. Select **Streamable HTTP**, enter `http://127.0.0.1:8000/mcp` as the server URL and connect. Use the proxy connection mode if Inspector offers a choice; direct browser connections may require additional CORS configuration.

Do not use the stdio launch command to connect to an HTTP server. In HTTP mode the server is started independently, and Inspector connects to its URL.

### Tool checks

1. Run **List Tools** and check names, descriptions and input schemas. The current source includes four tools, including the lab-only `slow_probe`.
2. Call `search_runbooks` with `{"query": "systemctl"}`.
3. Call `host_health` with `{}` to use the default local host.
4. If you have configured a lab cluster, call `k8s_pod_status` with `{"cluster": "rke-lab", "namespace": "default"}`.
5. Optionally call `slow_probe` with `{"seconds": 1}`. Reserve longer delays for the timeout/tracing exercise.

Inspector discovery and tool calls do not require Ollama or another model. Kubernetes is needed only for the Kubernetes check.

## Stdio safety rule

In the stdio transport, standard output is reserved for MCP JSON-RPC messages. Do not use `print()` for diagnostics, because ordinary text can corrupt the protocol stream. Use Python logging instead:

```python
logger.info(
    "Reading pod status: cluster=%s namespace=%s",
    cluster,
    namespace,
)
```

The default logging handler writes to standard error, which leaves standard output free for MCP communication. Keep this convention in both transport modes so switching back to stdio remains safe.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Inspector's stdio connection hangs | Ensure `MCP_TRANSPORT=stdio`; an HTTP listener does not answer stdin requests. |
| HTTP connection refused | Ensure the server is running in HTTP mode and that the URL's host and port match its bind settings. |
| HTTP 404 | Check that the URL includes `/mcp`. |
| Address already in use | Stop the previous HTTP server or choose another `MCP_PORT`, then update the client URL. |
| Inspector fails while another client works | Compare client/server SDK and protocol versions; transport selection alone does not guarantee protocol compatibility. |
| LiteLLM cannot reach the server | Check the bind address, `host.docker.internal` mapping, container networking and firewall. |
| `No module named mcp_itsops` | Run `uv sync` and invoke the module from the repository root; check the project's package configuration if it still fails. |

A bare browser visit or GET to `/mcp` is not a substitute for a complete MCP client test.

## Security decisions

- No arbitrary shell-command tool and no `shell=True` subprocess calls.
- No arbitrary hostnames, SSH targets or kubeconfig paths.
- Explicit cluster and namespace allowlists.
- Fixed `kubectl` argument structure.
- Command timeouts.
- Diagnostic command output truncated to 2,000 characters; runbook search limited to 20 matches; pod summaries limited to 50 pods. These are partial limits, not a universal response-size cap.
- Expected command and validation errors returned as tool results.

These controls reduce broad infrastructure access. They have not been independently reviewed or validated by an automated test suite.

## Current limitations

This local learning server does not yet provide:

- Authentication or per-user authorisation.
- Gateway enforcement within the server itself.
- Audit logging suitable for production.
- Workload identity or isolated Kubernetes credentials.
- Container sandboxing or network egress restrictions.
- Automated tests.
- A uniform output-size limit or structured error handling across all tools.

For a remotely exposed service, transport alone is not a security boundary. Authenticated access, authorisation, audit logs and network controls would need to be designed and tested separately.

## Learning outcomes

- Explain the difference between an MCP client, server, host and tool.
- Inspect tool schemas and raw JSON-RPC messages.
- Explain why stdio servers must not write diagnostics to standard output.
- Recognise why arbitrary infrastructure identifiers should not become unrestricted tool inputs.
- Compare a client-launched stdio server with an independently started HTTP server.
- Distinguish a client timeout from evidence of server-side cancellation.

## Relationship to the rest of the lab

This project publishes tools for MCP clients. It differs from [`ai-agents-miniagent`](https://github.com/albeus/ai-agents-miniagent), which owns its own agent loop and runs its tools locally; `miniagent` is not currently an MCP client.

The LiteLLM lab uses this server over Streamable HTTP. Its recorded success was tool discovery with the gateway master key; per-team MCP authorisation was not established.

The trace-probe lab uses the server directly for MCP calls, including `slow_probe`. It does not prove end-to-end tracing through LiteLLM's MCP gateway.

See the [lab index](https://github.com/albeus/ai-agents-lab) for the suggested reading order.

## Licence

Released under the [MIT Licence](LICENSE). This is a learning lab, provided as is, without warranty.
