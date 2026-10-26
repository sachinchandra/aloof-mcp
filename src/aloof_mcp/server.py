"""Aloof MCP server (stdio). A thin client for the public Aloof REST API (https://api.aloof.si).

Auth: set ALOOF_API_KEY (a pk_... key from https://www.aloof.si/dashboard), or pass api_key to a tool.
For a hosted server with OAuth instead of a key, connect your MCP client to https://mcp.aloof.si/mcp."""
import os, httpx
from mcp.server.fastmcp import FastMCP
API = os.environ.get("ALOOF_API_URL", "https://api.aloof.si").rstrip("/")
BRAND = "Aloof"
mcp = FastMCP(BRAND, instructions=(
  f"{BRAND} hosts backend web apps, APIs and workers cheaply for anyone worldwide, billed per second in USD "
  "(Stripe: cards, Apple/Google Pay; tax handled at checkout). Compute runs in Nuremberg, Germany on Hetzner (backups in Helsinki), so be "
  "honest about latency: ~10-40 ms within Europe, ~90-110 ms from US East, more from Asia. GPUs are coming soon: GPU plans "
  "can't be deployed yet; offer join_gpu_waitlist instead. Deploy from a Docker image or a git repo with a Dockerfile. "
  "Flow: list_plans -> (signup if no key) -> deploy_app -> get_status until running -> share url."))
def _h(k):
    k = k or os.environ.get("ALOOF_API_KEY")
    return {"Authorization": f"Bearer {k}"} if k else {}
from mcp.server.fastmcp.exceptions import ToolError
def _err(code, body):
    d = body.get("detail", body) if isinstance(body, dict) else body
    return f"Aloof API error {code}: {d if isinstance(d, str) else __import__('json').dumps(d)}"
def _r(method, path, key=None, **kw):
    r = httpx.request(method, API+path, headers=_h(key), timeout=60, **kw)
    try: body = r.json()
    except Exception: body = r.text
    if r.status_code >= 400: raise ToolError(_err(r.status_code, body))   # MCP result isError:true
    return body
@mcp.tool()
def list_plans() -> dict:
    """Aloof pricing (USD excl. tax): shared/performance CPU plans billed per second, volume $/GB-month,
    egress $/GB, workspace tiers (Free $0, Hobby $5, Pro $20/workspace, each with that much usage included), regions
    (Nuremberg, Germany; backups in Helsinki) and provider availability. CPU from $1.99/mo (shared-1x-256mb), perf-1x-2gb $24/mo;
    volumes $0.22/GB-mo; egress $0.06/GB. GPUs: coming soon (see the `gpu` field; use join_gpu_waitlist).
    Free tier: 3 apps, shared-1x-256mb/512mb only, 1 instance, sleeps after 5 min idle, hard-capped at $1/month
    (apps pause, never billed).
    Recommend shared-1x-* for small APIs, perf-* for steady CPU load."""
    return {"plans": _r("GET","/v1/plans"), "providers": _r("GET","/v1/providers")}
@mcp.tool()
def signup(email: str) -> dict:
    """Create an account and return an API key (pk_...). Store it; pass as api_key to other tools."""
    return _r("POST","/v1/signup", json={"email": email})
@mcp.tool()
def deploy_app(name: str, image: str = "", git_url: str = "", git_ref: str = "", plan: str = "",
               port: int = 8080, env: dict[str,str] | None = None, instances: int = 1, region: str = "", api_key: str = "") -> dict:
    """Deploy (or redeploy) a backend app. Give either `image` (e.g. 'nginx:alpine') or `git_url` of a repo
    containing a Dockerfile. `port` is the port the app listens on (PORT env is also set). `plan` from list_plans
    (shared-* or perf-*; gpu-* only once GPUs launch); leave it empty to get the largest plan your tier allows (Free: shared-1x-512mb). `region` from list_regions (live only; default nbg1; fixed once created). Returns app record with public url; poll get_status until status=='running'."""
    src = {"image": image} if image else {"git": git_url, **({"ref": git_ref} if git_ref else {})}
    return _r("POST","/v1/apps", api_key, json={"name":name,"source":src,**({"plan":plan} if plan else {}),"port":port,"env":env or {},"instances":instances, **({"region": region} if region else {})})
@mcp.tool()
def get_status(name: str, api_key: str = "") -> dict:
    """Get status (queued/building/starting/running/failed), instances, url and errors for an app."""
    return _r("GET",f"/v1/apps/{name}", api_key)
@mcp.tool()
def list_apps(api_key: str = "") -> list | dict:
    """List your apps."""
    return _r("GET","/v1/apps", api_key)
@mcp.tool()
def get_logs(name: str, tail: int = 100, api_key: str = "") -> str:
    """Platform events plus recent stdout/stderr of each instance."""
    r = httpx.get(f"{API}/v1/apps/{name}/logs", params={"tail":tail}, headers=_h(api_key), timeout=60)
    if r.status_code >= 400:
        try: body = r.json()
        except Exception: body = r.text
        raise ToolError(_err(r.status_code, body))
    return r.text
@mcp.tool()
def scale_app(name: str, instances: int, api_key: str = "") -> dict:
    """Scale an app to N instances (0 stops it). Traffic is round-robined."""
    return _r("POST",f"/v1/apps/{name}/scale", api_key, json={"instances":instances})
@mcp.tool()
def set_env(name: str, env: dict[str, str], api_key: str = "") -> dict:
    """Set environment variables (triggers rolling restart)."""
    return _r("POST",f"/v1/apps/{name}/env", api_key, json={"env":env})
@mcp.tool()
def destroy_app(name: str, with_volumes: bool = False, api_key: str = "") -> dict:
    """Permanently delete an app and stop its instances. Volumes and Postgres databases its template created are deleted too;
    volumes you attached yourself are detached and kept unless with_volumes=True. The result lists deleted and kept resources."""
    return _r("DELETE",f"/v1/apps/{name}" + ("?with_volumes=true" if with_volumes else ""), api_key)
@mcp.tool()
def get_usage(api_key: str = "") -> dict:
    """Usage hours and USD cost so far, plus remaining credit (credit_usd)."""
    return _r("GET","/v1/usage", api_key)
@mcp.tool()
def create_volume(name: str, size_gb: int = 1, region: str = "", api_key: str = "") -> dict:
    """Create a persistent volume in `region` (default nbg1). Attach it to an app in the same region with attach_volume; data survives redeploys."""
    return _r("POST","/v1/volumes", api_key, json={"name": name, "size_gb": size_gb, **({"region": region} if region else {})})
@mcp.tool()
def list_volumes(api_key: str = "") -> list | dict:
    """List volumes and which app/path each is attached to."""
    return _r("GET","/v1/volumes", api_key)
@mcp.tool()
def attach_volume(app: str, volume: str, path: str = "/data", api_key: str = "") -> dict:
    """Mount a volume into an app at `path` (rolling redeploy)."""
    return _r("POST",f"/v1/apps/{app}/volumes", api_key, json={"volume": volume, "path": path})
@mcp.tool()
def detach_volume(app: str, volume: str, api_key: str = "") -> dict:
    """Unmount a volume from an app (data is kept)."""
    return _r("DELETE",f"/v1/apps/{app}/volumes/{volume}", api_key)
@mcp.tool()
def set_autoscale(name: str, min_instances: int = 0, max_instances: int = 3, target_concurrency: int = 10,
                  cpu_percent: float | None = None, idle_seconds: int = 60, api_key: str = "") -> dict:
    """Enable autoscaling on in-flight requests per instance (and optionally CPU %). min_instances=0 enables
    scale-to-zero after idle_seconds with automatic cold start on the next request."""
    return _r("PUT",f"/v1/apps/{name}/autoscale", api_key, json={"min": min_instances, "max": max_instances,
              "target_concurrency": target_concurrency, "cpu_percent": cpu_percent, "idle_seconds": idle_seconds})
@mcp.tool()
def add_domain(name: str, domain: str, api_key: str = "") -> dict:
    """Attach a custom domain to an app. Returns the DNS records to create at the registrar: a TXT ownership record plus either a CNAME (subdomains) or A + AAAA records
    (root/apex domains; ALIAS/ANAME/CNAME flattening also works). Aloof re-checks DNS automatically every few minutes, and the HTTPS certificate is issued after it verifies.
    Limits per account: Free 1, Hobby 3, Pro 10 domains. Unverified claims are released after 7 days."""
    return _r("POST",f"/v1/apps/{name}/domains", api_key, json={"domain": domain})
@mcp.tool()
def list_domains(name: str = "", api_key: str = "") -> dict:
    """List custom domains with status (pending, verified, dns_error), last check time, the DNS records still needed, and the plan's domain limit.
    Pass `name` for one app, or leave it empty for every domain on the account."""
    r = _r("GET", f"/v1/apps/{name}/domains" if name else "/v1/domains", api_key)
    return {"domains": r} if isinstance(r, list) else r
@mcp.tool()
def verify_domain(name: str, domain: str, api_key: str = "") -> dict:
    """Check a custom domain's DNS now (TXT ownership + CNAME/A/AAAA routing) and return its status and what is missing. Rate limited; Aloof also re-checks automatically."""
    return _r("POST",f"/v1/apps/{name}/domains/{domain}/verify", api_key)
@mcp.tool()
def remove_domain(name: str, domain: str, api_key: str = "") -> dict:
    """Remove a custom domain from an app (its certificate stops being renewed). Your DNS records are untouched."""
    return _r("DELETE",f"/v1/apps/{name}/domains/{domain}", api_key)
@mcp.tool()
def join_gpu_waitlist(email: str, gpu: str = "", note: str = "") -> dict:
    """GPUs (L4, RTX 4090, L40, A100 80GB, H100) are coming soon. Add an email to the waitlist; optional `gpu` plan id
    (e.g. 'gpu-h100') and a short note on the workload."""
    return _r("POST", "/v1/waitlist", json={"email": email, **({"gpu": gpu} if gpu else {}), **({"note": note} if note else {})})
@mcp.tool()
def list_releases(name: str, api_key: str = "") -> list | dict:
    """Release history of an app (every deploy, config change and rollback is a numbered release; status active/superseded/failed)."""
    return _r("GET", f"/v1/apps/{name}/releases", api_key)
@mcp.tool()
def rollback_app(name: str, version: int | None = None, api_key: str = "") -> dict:
    """Roll back to an earlier release (default: the previous one). Zero downtime, no rebuild. Poll get_status."""
    return _r("POST", f"/v1/apps/{name}/rollback", api_key, json={"version": version})
@mcp.tool()
def create_postgres(name: str, plan: str = "pg-dev", region: str = "", api_key: str = "") -> dict:
    """Create a managed Postgres 16 database (plans: pg-dev $2.99/mo, pg-basic $9.99, pg-standard $28.99, pg-perf $60.99; daily
    backups, 7 kept) in `region` (default nbg1; must match the app's region). Then attach_postgres to inject DATABASE_URL into an app."""
    return _r("POST", "/v1/pg", api_key, json={"name": name, "plan": plan, **({"region": region} if region else {})})
@mcp.tool()
def list_postgres(api_key: str = "") -> list | dict:
    """List managed Postgres databases, status, attached apps and backups."""
    return _r("GET", "/v1/pg", api_key)
@mcp.tool()
def attach_postgres(name: str, app: str, var: str = "DATABASE_URL", api_key: str = "") -> dict:
    """Connect an app to a database over a private network and inject its connection URL as env `var` (rolling redeploy)."""
    return _r("POST", f"/v1/pg/{name}/attach", api_key, json={"app": app, "var": var})
@mcp.tool()
def backup_postgres(name: str, api_key: str = "") -> dict:
    """Take an on-demand pg_dump backup now (daily backups happen automatically)."""
    return _r("POST", f"/v1/pg/{name}/backups", api_key)
@mcp.tool()
def snapshot_volume(volume: str, api_key: str = "") -> dict:
    """Snapshot a volume (tar.gz, 10 kept). Restore with restore_volume."""
    return _r("POST", f"/v1/volumes/{volume}/snapshots", api_key)
@mcp.tool()
def restore_volume(volume: str, snapshot_id: str, api_key: str = "") -> dict:
    """Restore a volume from a snapshot. The attached app is stopped during the restore and restarted after. Destructive: confirm with the user first."""
    return _r("POST", f"/v1/volumes/{volume}/restore", api_key, json={"snapshot_id": snapshot_id})
@mcp.tool()
def exec_command(name: str, command: str, api_key: str = "") -> dict:
    """Run a shell command in a running instance of the app (like `fly ssh console -C`). Audited. Returns exit_code and output."""
    return _r("POST", f"/v1/apps/{name}/exec", api_key, json={"command": command})
@mcp.tool()
def add_log_drain(name: str, url: str, api_key: str = "") -> dict:
    """Forward the app's logs to https:// (JSON array POST) or syslog+tls://host:port / syslog+tcp:// / syslog+udp:// (RFC 5424)."""
    return _r("POST", f"/v1/apps/{name}/drains", api_key, json={"url": url})
@mcp.tool()
def list_offsite_backups(kind: str, name: str, api_key: str = "") -> list | dict:
    """List encrypted off-site (S3) backups. kind='pg' (database name) or 'vol' (volume name). Daily 7, weekly 4, monthly 3 kept."""
    return _r("GET", f"/v1/{'pg' if kind == 'pg' else 'volumes'}/{name}/offsite", api_key)
@mcp.tool()
def restore_offsite_backup(kind: str, name: str, backup_id: str, api_key: str = "") -> dict:
    """Restore a database (kind='pg') or volume (kind='vol') from an off-site backup. Destructive: confirm with the user first."""
    return _r("POST", f"/v1/{'pg' if kind == 'pg' else 'volumes'}/{name}/offsite-restore", api_key, json={"backup_id": backup_id})
@mcp.tool()
def registry_login(server: str, username: str, password: str, app: str = "", api_key: str = "") -> dict:
    """Save private registry credentials (docker.io, ghcr.io, ECR, GCR/Artifact Registry, any v2 registry) for all apps, or one app. Encrypted at rest."""
    return _r("POST", "/v1/registry", api_key, json={"server": server, "username": username, "password": password, "app": app or None})
@mcp.tool()
def add_git_credential(host: str, kind: str = "ssh", token: str = "", app: str = "", api_key: str = "") -> dict:
    """Private git access. kind='ssh' generates a deploy key and returns the public key to add to the repo; kind='token' stores an HTTPS token."""
    return _r("POST", "/v1/git/credentials", api_key, json={"host": host, "kind": kind, "token": token or None, "app": app or None})
@mcp.tool()
def deploy_with_config(name: str, config: dict, image: str = "", git_url: str = "", git_ref: str = "", api_key: str = "") -> dict:
    """Deploy using an aloof.toml (fly.toml-style) config parsed to a dict: processes, release_command, mounts, cron, checks, vm size."""
    return _r("POST", f"/v1/apps/{name}/deploy", api_key, json={"config": config, "image": image or None, "git": git_url or None, "ref": git_ref or None})
@mcp.tool()
def app_status(name: str, api_key: str = "") -> dict:
    """Detailed status: release, process groups (web/worker) and their instances, cron jobs, previews, private hostname."""
    return _r("GET", f"/v1/apps/{name}/status", api_key)
@mcp.tool()
def create_deploy_token(app: str = "", expires_in: str = "90d", api_key: str = "") -> dict:
    """Create a CI deploy token scoped to one app (or the whole account if app is empty). Shown once."""
    return _r("POST", "/v1/tokens", api_key, json={"app": app or None, "expires_in": expires_in})
@mcp.tool()
def list_templates() -> dict:
    """One-click templates (Uptime Kuma, n8n, Umami, ...): id, description, required env vars, volumes, Postgres needs, default plan."""
    return _r("GET", "/v1/templates")
@mcp.tool()
def deploy_template(template: str, name: str, env: dict[str,str] | None = None, plan: str = "", api_key: str = "") -> dict:
    """Deploy a one-click template (id from list_templates) as app `name`. Creates the volumes and managed Postgres it needs,
    generates its secrets (returned once in generated_secrets), and starts the deploy. Pass required env vars in `env`."""
    import re as _re, urllib.parse as _up
    if not _re.fullmatch(r"[a-z0-9][a-z0-9-]{1,38}[a-z0-9]", template or ""): return {"error": "unknown template id; use list_templates"}
    return _r("POST", f"/v1/templates/{_up.quote(template, safe='')}/deploy", api_key, json={"name": name, "env": env or {}, **({"plan": plan} if plan else {})})
@mcp.tool()
def list_regions() -> dict:
    """Regions with status (live | coming_soon) computed from healthy nodes, aliases, and region pricing for live regions.
    Only live regions accept deploy_app/create_volume/create_postgres. Free tier is EU-only."""
    return _r("GET", "/v1/regions")
@mcp.tool()
def diagnose_app(name: str, api_key: str = "") -> dict:
    """Read-only: why is my app broken? Returns recent error log lines, failed health checks, recent deploys, rollbacks and restarts,
    instance states and exit codes, and likely causes (OOM/exit 137, crash loop, bad release after a deploy, port mismatch or failing
    health check, suspended for $0 balance, scaled to zero) each with a suggested fix. Changes nothing; secrets and env values are redacted."""
    return _r("GET", f"/v1/apps/{name}/diagnose", api_key)
@mcp.tool()
def set_self_heal(name: str, enabled: bool, api_key: str = "") -> dict:
    """Self-healing deploys (default on): for ~5 minutes after a deploy the new release's 5xx rate and p95 latency are compared with
    the previous release; if clearly worse it is rolled back automatically with the reason recorded. Turn it off/on per app."""
    return _r("PUT", f"/v1/apps/{name}/self-heal", api_key, json={"enabled": enabled})
def main():
    """Run the Aloof MCP server over stdio."""
    mcp.run("stdio")

if __name__ == "__main__":
    main()
