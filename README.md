# Aloof MCP server

[Aloof](https://www.aloof.si) hosts backend web apps, APIs, workers and managed Postgres, billed per second in USD. This
[Model Context Protocol](https://modelcontextprotocol.io) server lets an AI assistant deploy and operate them for you:
create apps from a Docker image or a git repo, watch status and logs, scale, set env vars, attach Postgres, roll back.

It is a thin client for the public Aloof REST API (`https://api.aloof.si`). It holds no state and ships no platform internals.

## Option 1: hosted server (recommended)

Point any MCP client that supports remote servers at:

```
https://mcp.aloof.si/mcp
```

Transport: streamable HTTP. Auth: OAuth 2.1 with PKCE (dynamic client registration and Client ID Metadata Documents are
supported); you log in to Aloof in the browser. An API key also works as a bearer token: `Authorization: Bearer pk_...`.

- **Claude** (claude.ai / Desktop): Settings → Connectors → Add custom connector → `https://mcp.aloof.si/mcp`.
- **Claude Code**: `claude mcp add --transport http aloof https://mcp.aloof.si/mcp`
- **Cursor**: `~/.cursor/mcp.json`:
  ```json
  { "mcpServers": { "aloof": { "url": "https://mcp.aloof.si/mcp" } } }
  ```

## Option 2: run locally over stdio

Requires Python 3.10+. Get an API key (`pk_...`) from the [dashboard](https://www.aloof.si/dashboard), or let the
assistant call the `signup` tool.

```bash
pip install git+https://github.com/sachinchandra/aloof-mcp      # or: git clone ... && pip install .
ALOOF_API_KEY=pk_... aloof-mcp                            # speaks MCP on stdin/stdout
```

With [uv](https://docs.astral.sh/uv/) and no install step: `uvx --from git+https://github.com/sachinchandra/aloof-mcp aloof-mcp`.

**Claude Desktop** (`claude_desktop_config.json`) / **Cursor** (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "aloof": {
      "command": "aloof-mcp",
      "env": { "ALOOF_API_KEY": "pk_..." }
    }
  }
}
```

**Claude Code**: `claude mcp add aloof -e ALOOF_API_KEY=pk_... -- aloof-mcp`

Environment:

| Variable | Default | Purpose |
|---|---|---|
| `ALOOF_API_KEY` | (none) | Your `pk_...` key. Tools also accept an `api_key` argument. |
| `ALOOF_API_URL` | `https://api.aloof.si` | API base URL. |

## Tools

<!-- tools:start -->
34 tools:

| Tool | What it does |
|---|---|
| `list_plans` | Aloof pricing (USD excl. |
| `signup` | Create an account and return an API key (pk_...). |
| `deploy_app` | Deploy (or redeploy) a backend app. |
| `get_status` | Get status (queued/building/starting/running/failed), instances, url and errors for an app. |
| `list_apps` | List your apps. |
| `get_logs` | Platform events plus recent stdout/stderr of each instance. |
| `scale_app` | Scale an app to N instances (0 stops it). |
| `set_env` | Set environment variables (triggers rolling restart). |
| `destroy_app` | Permanently delete an app and stop its instances. |
| `get_usage` | Usage hours and USD cost so far, plus remaining credit (credit_usd). |
| `create_volume` | Create a persistent volume. |
| `list_volumes` | List volumes and which app/path each is attached to. |
| `attach_volume` | Mount a volume into an app at `path` (rolling redeploy). |
| `detach_volume` | Unmount a volume from an app (data is kept). |
| `set_autoscale` | Enable autoscaling on in-flight requests per instance (and optionally CPU %). |
| `add_domain` | Attach a custom domain (CNAME it to <app>.<platform domain>). |
| `join_gpu_waitlist` | GPUs (L4, RTX 4090, L40, A100 80GB, H100) are coming soon. |
| `list_releases` | Release history of an app (every deploy, config change and rollback is a numbered release; status active/superseded/failed). |
| `rollback_app` | Roll back to an earlier release (default: the previous one). |
| `create_postgres` | Create a managed Postgres 16 database (plans: pg-dev $2.99/mo, pg-basic $9.99, pg-standard $28.99, pg-perf $60.99; daily backups, 7 kept). |
| `list_postgres` | List managed Postgres databases, status, attached apps and backups. |
| `attach_postgres` | Connect an app to a database over a private network and inject its connection URL as env `var` (rolling redeploy). |
| `backup_postgres` | Take an on-demand pg_dump backup now (daily backups happen automatically). |
| `snapshot_volume` | Snapshot a volume (tar.gz, 10 kept). |
| `restore_volume` | Restore a volume from a snapshot. |
| `exec_command` | Run a shell command in a running instance of the app (like `fly ssh console -C`). |
| `add_log_drain` | Forward the app's logs to https:// (JSON array POST) or syslog+tls://host:port / syslog+tcp:// / syslog+udp:// (RFC 5424). |
| `list_offsite_backups` | List encrypted off-site (S3) backups. |
| `restore_offsite_backup` | Restore a database (kind='pg') or volume (kind='vol') from an off-site backup. |
| `registry_login` | Save private registry credentials (docker.io, ghcr.io, ECR, GCR/Artifact Registry, any v2 registry) for all apps, or one app. |
| `add_git_credential` | Private git access. |
| `deploy_with_config` | Deploy using an aloof.toml (fly.toml-style) config parsed to a dict: processes, release_command, mounts, cron, checks, vm size. |
| `app_status` | Detailed status: release, process groups (web/worker) and their instances, cron jobs, previews, private hostname. |
| `create_deploy_token` | Create a CI deploy token scoped to one app (or the whole account if app is empty). |
<!-- tools:end -->

Destructive tools (`destroy_app`, `delete_postgres`, `restore_postgres`, ...) act immediately; keep your client's
"ask before running tools" setting on if you want a human in the loop.

## Development

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e . pytest
pytest                       # starts the server over stdio and lists the tools
python scripts/gen_tools.py  # refresh the tool table above after changing tools
```

Docs for the platform and API: <https://api.aloof.si/llms.txt>.

## License

MIT, see [LICENSE](LICENSE).
