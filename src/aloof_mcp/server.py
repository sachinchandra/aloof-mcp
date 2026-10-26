"""Aloof MCP server (stdio). A thin client for the public Aloof REST API (https://api.aloof.si).

Auth: set ALOOF_API_KEY (a pk_... key from https://www.aloof.si/dashboard), or pass api_key to a tool.
For a hosted server with OAuth instead of a key, connect your MCP client to https://mcp.aloof.si/mcp."""
import os, httpx
from mcp.server.fastmcp import FastMCP
API = os.environ.get("ALOOF_API_URL", "https://api.aloof.si").rstrip("/")
BRAND = "Aloof"
class _MCP(FastMCP):
    """Hides the pre-v2 tool names from tools/list unless ALOOF_MCP_TOOLS=legacy. Calls to them always work."""
    async def list_tools(self):
        ts = await super().list_tools()
        return ts if os.environ.get("ALOOF_MCP_TOOLS", "").lower() == "legacy" else [t for t in ts if t.name not in LEGACY]
mcp = _MCP(BRAND, instructions=(
  f"{BRAND} hosts backend web apps, APIs and workers cheaply for anyone worldwide, billed per second in USD "
  "(Stripe: cards, Apple/Google Pay; tax handled at checkout). Compute runs in Nuremberg, Germany on Hetzner (backups in Helsinki), so be "
  "honest about latency: ~10-40 ms within Europe, ~90-110 ms from US East, more from Asia. GPUs are coming soon: GPU plans "
  "can't be deployed yet; offer join_gpu_waitlist instead. Deploy from a Docker image or a git repo with a Dockerfile. "
  "Flow: list(kind='plans') -> (signup if no key) -> deploy_app(wait=true) -> share url. Reads are inspect (one app) and list (account); inspect(what='diagnose') explains failures."))
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
# ---- tool surface (v2: 25 tools). Reads are grouped into `inspect` (one app) and `list` (account-wide); everything that
# changes something stays its own explicit tool, and destroy_app / restore stay standalone so they're easy to gate.
# Old tool names still work when called and are listed only on opt-in (?tools=legacy, header X-Aloof-Tools: legacy,
# or ALOOF_MCP_TOOLS=legacy for stdio). LEGACY maps each old name to its replacement.
import re as _re, urllib.parse as _up
INSPECT = ("status", "details", "logs", "diagnose", "releases", "metrics", "events", "domains")
LISTS = ("apps", "domains", "volumes", "snapshots", "postgres", "backups", "templates", "plans", "regions", "usage")
def _q(s): return _up.quote(str(s), safe="")
def _text(path, key, **params):
    r = httpx.get(API + path, params=params, headers=_h(key), timeout=60)
    if r.status_code >= 400:
        try: body = r.json()
        except Exception: body = r.text
        raise ToolError(_err(r.status_code, body))
    return r.text
@mcp.tool(name="inspect")
def inspect_(name: str, what: str = "status", tail: int = 100, after: int = 0, api_key: str = "") -> dict:
    """Read-only look at one app. what=status (default: state, url, instances, plus requested_release, serving_release, health of the
    serving release, mismatch and a plain warning when a newer deploy failed) | details (process groups, cron, previews, private hostname)
    | logs (platform events plus recent stdout/stderr; `tail` lines) | diagnose (why is it broken: recent errors, failed health checks,
    deploys, rollbacks, restarts, exit codes and likely causes with fixes; secrets redacted) | releases (numbered release history,
    active/superseded/failed, self-heal rollbacks) | metrics (requests, in-flight, CPU %) | events (platform events after event id `after`)
    | domains (this app's custom domains and DNS still needed). Changes nothing."""
    n = _q(name)
    if what == "status": return _r("GET", f"/v1/apps/{n}", api_key)
    if what == "details": return _r("GET", f"/v1/apps/{n}/status", api_key)
    if what == "logs": return {"name": name, "logs": _text(f"/v1/apps/{n}/logs", api_key, tail=tail)}
    if what == "diagnose": return _r("GET", f"/v1/apps/{n}/diagnose", api_key)
    if what == "releases": return {"name": name, "releases": _r("GET", f"/v1/apps/{n}/releases", api_key)}
    if what == "metrics": return _r("GET", f"/v1/apps/{n}/metrics", api_key)
    if what == "events": return {"name": name, "events": _r("GET", f"/v1/apps/{n}/events", api_key, params={"after": after})}
    if what == "domains": return {"name": name, "domains": _r("GET", f"/v1/apps/{n}/domains", api_key)}
    raise ToolError(f"unknown what='{what}'; use one of: {', '.join(INSPECT)}")
@mcp.tool(name="list")
def list_(kind: str = "apps", name: str = "", source: str = "", api_key: str = "") -> dict:
    """Read-only lists. kind=apps | domains (all custom domains with status and DNS still needed; `name` = one app) | volumes (and where
    each is mounted) | snapshots (of volume `name`) | postgres (databases, attached apps, backups) | backups (encrypted off-site backups
    of `name`; source='pg' for a database or 'vol' for a volume; daily 7, weekly 4, monthly 3 kept) | templates (one-click apps: Uptime
    Kuma, n8n, Umami, ...) | plans (pricing in USD: CPU plans billed per second from $1.99/mo, volumes $0.22/GB-mo, egress $0.06/GB, tiers
    Free/Hobby $5/Pro $20, providers; Free tier: 3 apps, sleeps after 5 min idle, hard-capped at $1/month) | regions (live/coming_soon,
    pricing; Nuremberg, Germany, backups in Helsinki) | usage (hours and USD cost so far, remaining credit_usd)."""
    if kind == "apps": return {"apps": _r("GET", "/v1/apps", api_key)}
    if kind == "domains":
        r = _r("GET", f"/v1/apps/{_q(name)}/domains" if name else "/v1/domains", api_key); return {"domains": r} if isinstance(r, list) else r
    if kind == "volumes": return {"volumes": _r("GET", "/v1/volumes", api_key)}
    if kind == "snapshots":
        if not name: raise ToolError("kind='snapshots' needs name=<volume>")
        return {"volume": name, "snapshots": _r("GET", f"/v1/volumes/{_q(name)}/snapshots", api_key)}
    if kind == "postgres": return {"postgres": _r("GET", "/v1/pg", api_key)}
    if kind == "backups":
        if not name or source not in ("pg", "vol"): raise ToolError("kind='backups' needs name=<database or volume> and source='pg' or 'vol'")
        return {"name": name, "backups": _r("GET", f"/v1/{'pg' if source == 'pg' else 'volumes'}/{_q(name)}/offsite", api_key)}
    if kind == "templates": return _r("GET", "/v1/templates")
    if kind == "plans": return {"plans": _r("GET", "/v1/plans"), "providers": _r("GET", "/v1/providers")}
    if kind == "regions": return _r("GET", "/v1/regions")
    if kind == "usage": return _r("GET", "/v1/usage", api_key)
    raise ToolError(f"unknown kind='{kind}'; use one of: {', '.join(LISTS)}")
@mcp.tool()
def signup(email: str) -> dict:
    """Create an account and return an API key (pk_...). Store it; pass as api_key to other tools."""
    return _r("POST", "/v1/signup", json={"email": email})
@mcp.tool()
def deploy_app(name: str, image: str = "", git_url: str = "", git_ref: str = "", plan: str = "",
               port: int = 8080, env: dict[str,str] | None = None, instances: int = 1, region: str = "", config: dict | None = None,
               wait: bool = False, timeout_s: int = 600, api_key: str = "") -> dict:
    """Deploy (or redeploy) a backend app from `image` (e.g. 'nginx:alpine') or `git_url` of a repo with a Dockerfile. `port` is the port
    the app listens on (PORT env is also set). `plan` from list(kind='plans'); empty = the largest plan your tier allows. `region` from
    list(kind='regions') (default nbg1; fixed once created). `config` = an aloof.toml (fly.toml-style) parsed to a dict (processes,
    release_command, mounts, cron, checks, vm size); when given, plan/port/env/instances come from it. wait=true blocks until this deploy
    finishes (up to timeout_s) and returns ok, requested_release, serving_release, health, mismatch and warning; ok is false when the new
    release failed, even if an older release is still serving. Without wait, poll inspect(what='status')."""
    before = _latest_version(name, api_key) if wait else None
    if config is not None:
        r = _r("POST", f"/v1/apps/{_q(name)}/deploy", api_key, json={"config": config, "image": image or None, "git": git_url or None, "ref": git_ref or None})
    else:
        src = {"image": image} if image else {"git": git_url, **({"ref": git_ref} if git_ref else {})}
        r = _r("POST", "/v1/apps", api_key, json={"name": name, "source": src, **({"plan": plan} if plan else {}), "port": port, "env": env or {},
                                                   "instances": instances, **({"region": region} if region else {})})
    return _wait_release(name, before, timeout_s, api_key, r) if wait else r
def _latest_version(name, key):
    try: return ((_r("GET", f"/v1/apps/{_q(name)}", key).get("requested_release") or {}).get("version")) or 0
    except ToolError: return 0
def _wait_release(name, before, timeout_s, key, first=None):
    """Poll until a release newer than `before` is active or failed. Success only if that release is the one serving."""
    import time as _t
    end = _t.time() + max(10, min(int(timeout_s or 600), 1800)); st = {}
    while _t.time() < end:
        st = _r("GET", f"/v1/apps/{_q(name)}", key); rq = st.get("requested_release") or {}
        if (rq.get("version") or 0) > (before or 0) and rq.get("status") in ("active", "failed"): break
        _t.sleep(3)
    else:
        return {"ok": False, "result": "timeout", "warning": f"still deploying after {timeout_s}s; check inspect(what='status') or inspect(what='diagnose')",
                **{k: st.get(k) for k in ("requested_release", "serving_release", "health", "mismatch")}, "url": st.get("url")}
    ok = bool(st.get("deploy_ok"))
    return {"ok": ok, "result": "live" if ok else "failed", "warning": st.get("warning"), "error": (st.get("requested_release") or {}).get("error"),
            **{k: st.get(k) for k in ("requested_release", "serving_release", "health", "mismatch")}, "url": st.get("url"), "status": st.get("status")}
@mcp.tool()
def deploy_template(template: str, name: str, env: dict[str,str] | None = None, plan: str = "", api_key: str = "") -> dict:
    """Deploy a one-click template (id from list(kind='templates')) as app `name`. Creates the volumes and managed Postgres it needs,
    generates its secrets (returned once in generated_secrets), and starts the deploy. Pass required env vars in `env`."""
    if not _re.fullmatch(r"[a-z0-9][a-z0-9-]{1,38}[a-z0-9]", template or ""): return {"error": "unknown template id; use list(kind='templates')"}
    return _r("POST", f"/v1/templates/{_q(template)}/deploy", api_key, json={"name": name, "env": env or {}, **({"plan": plan} if plan else {})})
@mcp.tool()
def scale_app(name: str, instances: int | None = None, autoscale: dict | None = None, api_key: str = "") -> dict:
    """Scale an app. instances=N sets a fixed count (0 stops it; traffic is round-robined). autoscale={min, max, target_concurrency,
    cpu_percent, idle_seconds} turns on autoscaling on in-flight requests per instance (min=0 = scale-to-zero after idle_seconds with
    automatic cold start); autoscale={} turns autoscaling off."""
    if autoscale is not None:
        if not autoscale: return _r("DELETE", f"/v1/apps/{_q(name)}/autoscale", api_key)
        a = {"min": 0, "max": 3, "target_concurrency": 10, "cpu_percent": None, "idle_seconds": 60, **autoscale}
        return _r("PUT", f"/v1/apps/{_q(name)}/autoscale", api_key, json=a)
    if instances is None: raise ToolError("give instances=N or autoscale={...}")
    return _r("POST", f"/v1/apps/{_q(name)}/scale", api_key, json={"instances": instances})
@mcp.tool()
def set_env(name: str, env: dict[str, str], api_key: str = "") -> dict:
    """Set environment variables (triggers rolling restart)."""
    return _r("POST", f"/v1/apps/{_q(name)}/env", api_key, json={"env": env})
@mcp.tool()
def rollback_app(name: str, version: int | None = None, api_key: str = "") -> dict:
    """Roll back to an earlier release (default: the previous one). Zero downtime, no rebuild. Check with inspect(what='status')."""
    return _r("POST", f"/v1/apps/{_q(name)}/rollback", api_key, json={"version": version})
@mcp.tool()
def set_self_heal(name: str, enabled: bool, api_key: str = "") -> dict:
    """Self-healing deploys (default on): for ~5 minutes after a deploy the new release's 5xx rate and p95 latency are compared with
    the previous release; if clearly worse it is rolled back automatically with the reason recorded. Turn it off/on per app."""
    return _r("PUT", f"/v1/apps/{_q(name)}/self-heal", api_key, json={"enabled": enabled})
@mcp.tool()
def exec_command(name: str, command: str, api_key: str = "") -> dict:
    """Run a shell command in a running instance of the app (like `fly ssh console -C`). Audited. Returns exit_code and output."""
    return _r("POST", f"/v1/apps/{_q(name)}/exec", api_key, json={"command": command})
@mcp.tool()
def destroy_app(name: str, with_volumes: bool = False, api_key: str = "") -> dict:
    """Permanently delete an app and stop its instances. Volumes and Postgres databases its template created are deleted too;
    volumes you attached yourself are detached and kept unless with_volumes=True. The result lists deleted and kept resources."""
    return _r("DELETE", f"/v1/apps/{_q(name)}" + ("?with_volumes=true" if with_volumes else ""), api_key)
@mcp.tool()
def add_domain(name: str, domain: str, api_key: str = "") -> dict:
    """Attach a custom domain to an app. Returns the DNS records to create at the registrar: a TXT ownership record plus either a CNAME (subdomains) or A + AAAA records
    (root/apex domains; ALIAS/ANAME/CNAME flattening also works). Aloof re-checks DNS automatically every few minutes, and the HTTPS certificate is issued after it verifies.
    Limits per account: Free 1, Hobby 3, Pro 10 domains. Unverified claims are released after 7 days."""
    return _r("POST", f"/v1/apps/{_q(name)}/domains", api_key, json={"domain": domain})
@mcp.tool()
def verify_domain(name: str, domain: str, api_key: str = "") -> dict:
    """Check a custom domain's DNS now (TXT ownership + CNAME/A/AAAA routing) and return its status and what is missing. Rate limited; Aloof also re-checks automatically."""
    return _r("POST", f"/v1/apps/{_q(name)}/domains/{_q(domain)}/verify", api_key)
@mcp.tool()
def remove_domain(name: str, domain: str, api_key: str = "") -> dict:
    """Remove a custom domain from an app (its certificate stops being renewed). Your DNS records are untouched."""
    return _r("DELETE", f"/v1/apps/{_q(name)}/domains/{_q(domain)}", api_key)
@mcp.tool()
def create_volume(name: str, size_gb: int = 1, region: str = "", api_key: str = "") -> dict:
    """Create a persistent volume in `region` (default nbg1). Attach it to an app in the same region with attach_volume; data survives redeploys."""
    return _r("POST", "/v1/volumes", api_key, json={"name": name, "size_gb": size_gb, **({"region": region} if region else {})})
@mcp.tool()
def attach_volume(app: str, volume: str, path: str = "/data", api_key: str = "") -> dict:
    """Mount a volume into an app at `path` (rolling redeploy)."""
    return _r("POST", f"/v1/apps/{_q(app)}/volumes", api_key, json={"volume": volume, "path": path})
@mcp.tool()
def detach_volume(app: str, volume: str, api_key: str = "") -> dict:
    """Unmount a volume from an app (data is kept)."""
    return _r("DELETE", f"/v1/apps/{_q(app)}/volumes/{_q(volume)}", api_key)
@mcp.tool()
def create_postgres(name: str, plan: str = "pg-dev", region: str = "", api_key: str = "") -> dict:
    """Create a managed Postgres 16 database (plans: pg-dev $2.99/mo, pg-basic $9.99, pg-standard $28.99, pg-perf $60.99; daily
    backups, 7 kept) in `region` (default nbg1; must match the app's region). Then attach_postgres to inject DATABASE_URL into an app."""
    return _r("POST", "/v1/pg", api_key, json={"name": name, "plan": plan, **({"region": region} if region else {})})
@mcp.tool()
def attach_postgres(name: str, app: str, var: str = "DATABASE_URL", api_key: str = "") -> dict:
    """Connect an app to a database over a private network and inject its connection URL as env `var` (rolling redeploy)."""
    return _r("POST", f"/v1/pg/{_q(name)}/attach", api_key, json={"app": app, "var": var})
@mcp.tool()
def backup(kind: str, name: str, api_key: str = "") -> dict:
    """Take a backup now. kind='postgres' = on-demand pg_dump of database `name` (daily backups also happen automatically);
    kind='volume' = snapshot of volume `name` (tar.gz, 10 kept). See them with list(kind='postgres') / list(kind='snapshots')."""
    if kind == "postgres": return _r("POST", f"/v1/pg/{_q(name)}/backups", api_key)
    if kind == "volume": return _r("POST", f"/v1/volumes/{_q(name)}/snapshots", api_key)
    raise ToolError("kind must be 'postgres' or 'volume'")
@mcp.tool()
def restore(kind: str, name: str, backup_id: str, api_key: str = "") -> dict:
    """Destructive: overwrite data from a backup; confirm with the user first. kind='snapshot' restores volume `name` from snapshot
    `backup_id` (the attached app is stopped during the restore and restarted after); kind='offsite_pg' / 'offsite_vol' restores a
    database / volume from an encrypted off-site backup (ids from list(kind='backups'))."""
    if kind == "snapshot": return _r("POST", f"/v1/volumes/{_q(name)}/restore", api_key, json={"snapshot_id": backup_id})
    if kind in ("offsite_pg", "offsite_vol"):
        return _r("POST", f"/v1/{'pg' if kind == 'offsite_pg' else 'volumes'}/{_q(name)}/offsite-restore", api_key, json={"backup_id": backup_id})
    raise ToolError("kind must be 'snapshot', 'offsite_pg' or 'offsite_vol'")
@mcp.tool()
def add_log_drain(name: str, url: str, api_key: str = "") -> dict:
    """Forward the app's logs to https:// (JSON array POST) or syslog+tls://host:port / syslog+tcp:// / syslog+udp:// (RFC 5424)."""
    return _r("POST", f"/v1/apps/{_q(name)}/drains", api_key, json={"url": url})
@mcp.tool()
def add_credential(kind: str, host: str, username: str = "", secret: str = "", app: str = "", api_key: str = "") -> dict:
    """Save private source credentials, for all apps or one `app`; encrypted at rest. kind='registry': container registry login
    (docker.io, ghcr.io, ECR, GCR/Artifact Registry, any v2 registry) with username + secret (password/token). kind='git_ssh': generates
    a deploy key for git `host` and returns the public key to add to the repo. kind='git_token': stores an HTTPS token (`secret`) for `host`."""
    if kind == "registry": return _r("POST", "/v1/registry", api_key, json={"server": host, "username": username, "password": secret, "app": app or None})
    if kind in ("git_ssh", "git_token"):
        return _r("POST", "/v1/git/credentials", api_key, json={"host": host, "kind": kind[4:], "token": secret or None, "app": app or None})
    raise ToolError("kind must be 'registry', 'git_ssh' or 'git_token'")
@mcp.tool()
def create_deploy_token(app: str = "", expires_in: str = "90d", allow_destroy: bool = False, api_key: str = "") -> dict:
    """Create a CI deploy token scoped to one app (or the whole account if app is empty). Shown once. By default it can deploy, scale and
    change config but can't destroy apps, delete volumes/databases or restore backups; allow_destroy=true lifts that (full-access callers only)."""
    return _r("POST", "/v1/tokens", api_key, json={"app": app or None, "expires_in": expires_in, "can_destroy": bool(allow_destroy)})
@mcp.tool()
def join_gpu_waitlist(email: str, gpu: str = "", note: str = "") -> dict:
    """GPUs (L4, RTX 4090, L40, A100 80GB, H100) are coming soon. Add an email to the waitlist; optional `gpu` plan id
    (e.g. 'gpu-h100') and a short note on the workload."""
    return _r("POST", "/v1/waitlist", json={"email": email, **({"gpu": gpu} if gpu else {}), **({"note": note} if note else {})})
# ---- legacy names (pre-v2). Hidden from tools/list unless opted in; always callable so old clients keep working. ----
LEGACY = {}
def _legacy(new):
    def deco(f):
        LEGACY[f.__name__] = new; mcp.add_tool(f, description=f"(legacy) use {new}. " + " ".join((f.__doc__ or "").split())); return f
    return deco
@_legacy("list(kind='plans')")
def list_plans() -> dict:
    """Pricing, tiers, regions and providers."""
    return list_(kind="plans")
@_legacy("inspect(what='status')")
def get_status(name: str, api_key: str = "") -> dict:
    """App status, url, instances, releases."""
    return inspect_(name, "status", api_key=api_key)
@_legacy("list(kind='apps')")
def list_apps(api_key: str = "") -> list | dict:
    """Your apps."""
    return _r("GET", "/v1/apps", api_key)
@_legacy("inspect(what='logs')")
def get_logs(name: str, tail: int = 100, api_key: str = "") -> str:
    """Events plus recent stdout/stderr."""
    return _text(f"/v1/apps/{_q(name)}/logs", api_key, tail=tail)
@_legacy("scale_app(autoscale={...})")
def set_autoscale(name: str, min_instances: int = 0, max_instances: int = 3, target_concurrency: int = 10,
                  cpu_percent: float | None = None, idle_seconds: int = 60, api_key: str = "") -> dict:
    """Enable autoscaling."""
    return scale_app(name, autoscale={"min": min_instances, "max": max_instances, "target_concurrency": target_concurrency,
                                      "cpu_percent": cpu_percent, "idle_seconds": idle_seconds}, api_key=api_key)
@_legacy("list(kind='usage')")
def get_usage(api_key: str = "") -> dict:
    """Usage and credit."""
    return list_(kind="usage", api_key=api_key)
@_legacy("list(kind='templates')")
def list_templates() -> dict:
    """One-click templates."""
    return list_(kind="templates")
@_legacy("list(kind='volumes')")
def list_volumes(api_key: str = "") -> list | dict:
    """Volumes."""
    return _r("GET", "/v1/volumes", api_key)
@_legacy("list(kind='domains')")
def list_domains(name: str = "", api_key: str = "") -> dict:
    """Custom domains."""
    return list_(kind="domains", name=name, api_key=api_key)
@_legacy("inspect(what='releases')")
def list_releases(name: str, api_key: str = "") -> list | dict:
    """Release history."""
    return _r("GET", f"/v1/apps/{_q(name)}/releases", api_key)
@_legacy("inspect(what='diagnose')")
def diagnose_app(name: str, api_key: str = "") -> dict:
    """Why is my app broken."""
    return inspect_(name, "diagnose", api_key=api_key)
@_legacy("list(kind='regions')")
def list_regions() -> dict:
    """Regions."""
    return list_(kind="regions")
@_legacy("list(kind='postgres')")
def list_postgres(api_key: str = "") -> list | dict:
    """Databases."""
    return _r("GET", "/v1/pg", api_key)
@_legacy("backup(kind='postgres')")
def backup_postgres(name: str, api_key: str = "") -> dict:
    """pg_dump now."""
    return backup("postgres", name, api_key)
@_legacy("backup(kind='volume')")
def snapshot_volume(volume: str, api_key: str = "") -> dict:
    """Snapshot a volume."""
    return backup("volume", volume, api_key)
@_legacy("restore(kind='snapshot')")
def restore_volume(volume: str, snapshot_id: str, api_key: str = "") -> dict:
    """Destructive: restore a volume snapshot; confirm with the user first."""
    return restore("snapshot", volume, snapshot_id, api_key)
@_legacy("list(kind='backups')")
def list_offsite_backups(kind: str, name: str, api_key: str = "") -> list | dict:
    """Off-site backups (kind pg|vol)."""
    return _r("GET", f"/v1/{'pg' if kind == 'pg' else 'volumes'}/{_q(name)}/offsite", api_key)
@_legacy("restore(kind='offsite_pg'|'offsite_vol')")
def restore_offsite_backup(kind: str, name: str, backup_id: str, api_key: str = "") -> dict:
    """Destructive: restore from an off-site backup; confirm with the user first."""
    return restore("offsite_pg" if kind == "pg" else "offsite_vol", name, backup_id, api_key)
@_legacy("add_credential(kind='registry')")
def registry_login(server: str, username: str, password: str, app: str = "", api_key: str = "") -> dict:
    """Registry credentials."""
    return add_credential("registry", server, username, password, app, api_key)
@_legacy("add_credential(kind='git_ssh'|'git_token')")
def add_git_credential(host: str, kind: str = "ssh", token: str = "", app: str = "", api_key: str = "") -> dict:
    """Git credentials."""
    return add_credential("git_token" if kind == "token" else "git_ssh", host, "", token, app, api_key)
@_legacy("deploy_app(config=...)")
def deploy_with_config(name: str, config: dict, image: str = "", git_url: str = "", git_ref: str = "", api_key: str = "") -> dict:
    """Deploy from an aloof.toml dict."""
    return deploy_app(name, image=image, git_url=git_url, git_ref=git_ref, config=config, api_key=api_key)
@_legacy("inspect(what='details')")
def app_status(name: str, api_key: str = "") -> dict:
    """Process groups, cron, previews."""
    return inspect_(name, "details", api_key=api_key)
def main():
    """Run the Aloof MCP server over stdio."""
    mcp.run("stdio")

if __name__ == "__main__":
    main()
