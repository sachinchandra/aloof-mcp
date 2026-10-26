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

OAuth scopes: `paas:read` (look only: `inspect`, `list`), `paas:write` (everything except `destroy_app` and `restore`), `paas:admin` (all). `paas` means `paas:admin`. The Authorize page shows which one your assistant asked for, and the server and API both enforce it. A bearer API key has full access. Deploy tokens made with `create_deploy_token` can't destroy unless `allow_destroy=true`.

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
| `ALOOF_MCP_TOOLS` | (none) | `legacy` also lists the pre-0.3 tool names (see below). |

## Tools

<!-- tools:start -->
25 tools:

| Tool | What it does |
|---|---|
| `inspect` | Read-only look at one app. |
| `list` | Read-only lists. |
| `signup` | Create an account and return an API key (pk_...). |
| `deploy_app` | Deploy (or redeploy) a backend app from `image` (e.g. |
| `deploy_template` | Deploy a one-click template (id from list(kind='templates')) as app `name`. |
| `scale_app` | Scale an app. |
| `set_env` | Set environment variables (triggers rolling restart). |
| `rollback_app` | Roll back to an earlier release (default: the previous one). |
| `set_self_heal` | Self-healing deploys (default on): for ~5 minutes after a deploy the new release's 5xx rate and p95 latency are compared with the previous release; if clearly worse it is rolled back automatically with the reason recorded. |
| `exec_command` | Run a shell command in a running instance of the app (like `fly ssh console -C`). |
| `destroy_app` | Permanently delete an app and stop its instances. |
| `add_domain` | Attach a custom domain to an app. |
| `verify_domain` | Check a custom domain's DNS now (TXT ownership + CNAME/A/AAAA routing) and return its status and what is missing. |
| `remove_domain` | Remove a custom domain from an app (its certificate stops being renewed). |
| `create_volume` | Create a persistent volume in `region` (default nbg1). |
| `attach_volume` | Mount a volume into an app at `path` (rolling redeploy). |
| `detach_volume` | Unmount a volume from an app (data is kept). |
| `create_postgres` | Create a managed Postgres 16 database (plans: pg-dev $2.99/mo, pg-basic $9.99, pg-standard $28.99, pg-perf $60.99; daily backups, 7 kept) in `region` (default nbg1; must match the app's region). |
| `attach_postgres` | Connect an app to a database over a private network and inject its connection URL as env `var` (rolling redeploy). |
| `backup` | Take a backup now. |
| `restore` | Destructive: overwrite data from a backup; confirm with the user first. |
| `add_log_drain` | Forward the app's logs to https:// (JSON array POST) or syslog+tls://host:port / syslog+tcp:// / syslog+udp:// (RFC 5424). |
| `add_credential` | Save private source credentials, for all apps or one `app`; encrypted at rest. |
| `create_deploy_token` | Create a CI deploy token scoped to one app (or the whole account if app is empty). |
| `join_gpu_waitlist` | GPUs (L4, RTX 4090, L40, A100 80GB, H100) are coming soon. |
<!-- tools:end -->

## Legacy tool names (before 0.3)

Version 0.3 merged 42 tools into 25: reads are `inspect` (one app) and `list` (account-wide); everything that changes something is still its own tool. The old names keep working when called, but are only listed with `ALOOF_MCP_TOOLS=legacy` (hosted server: `https://mcp.aloof.si/mcp?tools=legacy` or header `X-Aloof-Tools: legacy`).

| Old tool | Use instead |
|---|---|
| `list_plans` | `list(kind='plans')` |
| `get_status` | `inspect(what='status')` |
| `list_apps` | `list(kind='apps')` |
| `get_logs` | `inspect(what='logs')` |
| `set_autoscale` | `scale_app(autoscale={...})` |
| `get_usage` | `list(kind='usage')` |
| `list_templates` | `list(kind='templates')` |
| `list_volumes` | `list(kind='volumes')` |
| `list_domains` | `list(kind='domains')` |
| `list_releases` | `inspect(what='releases')` |
| `diagnose_app` | `inspect(what='diagnose')` |
| `list_regions` | `list(kind='regions')` |
| `list_postgres` | `list(kind='postgres')` |
| `backup_postgres` | `backup(kind='postgres')` |
| `snapshot_volume` | `backup(kind='volume')` |
| `restore_volume` | `restore(kind='snapshot')` |
| `list_offsite_backups` | `list(kind='backups')` |
| `restore_offsite_backup` | `restore(kind='offsite_pg'/'offsite_vol')` |
| `registry_login` | `add_credential(kind='registry')` |
| `add_git_credential` | `add_credential(kind='git_ssh'/'git_token')` |
| `deploy_with_config` | `deploy_app(config=...)` |
| `app_status` | `inspect(what='details')` |


## Connecting a custom domain

Ask your assistant to run `add_domain` (app name + domain). It returns the DNS records to create at your registrar:

| Record | Name | Value | When |
|---|---|---|---|
| TXT | `_aloof-challenge.<domain>` | `aloof-verify=<token>` | always (proves ownership) |
| CNAME | `api.example.com` | `<app>.aloof.si` | subdomains |
| A + AAAA | `example.com` | the edge IPv4 and IPv6 in the response | root (apex) domains. ALIAS/ANAME/CNAME flattening to `<app>.aloof.si` also works |

On Cloudflare, set the routing records to **DNS only** (grey cloud). Aloof re-checks DNS every few minutes, so a pending domain verifies by itself;
`verify_domain` checks immediately, `list_domains` shows each domain's status (`pending`, `verified`, or `dns_error` if DNS later broke; it is never removed automatically) and
`remove_domain` removes it. Limits per account: Free 1, Hobby 3, Pro 10 domains; unverified claims are released after 7 days. Once `example.com` is verified, `www.example.com`
redirects to it (308) if it points at Aloof too. Per-registrar steps (Cloudflare, GoDaddy, Namecheap, Route 53): https://www.aloof.si/docs/domains

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
