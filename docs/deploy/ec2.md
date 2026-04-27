# Deploy PowerClaw On EC2

This guide installs PowerClaw as a private, loopback-bound service on an EC2
instance. Expose it only after authentication, persistence, and terminal policy
are configured.

## Instance Baseline

- Ubuntu 24.04 LTS or Amazon Linux 2023
- `t3.small` or larger
- Encrypted EBS volume
- Security group with no public PowerClaw port
- SSH locked to your IP, or AWS SSM Session Manager
- Optional domain name for HTTPS through Nginx and Let's Encrypt

## Install

You can install from git or from a tarball built on your Mac.

### Option A: Git install

```bash
sudo POWERCLAW_REPO_URL=https://github.com/YOUR_ORG/YOUR_REPO.git \
  POWERCLAW_REF=main \
  bash scripts/install-ec2.sh
```

### Option B: Package on Mac, upload to EC2

On your Mac:

```bash
bash scripts/package-ec2.sh
scp dist/powerclaw-ec2-0.1.0.tar.gz ec2-user@YOUR_EC2_HOST:/tmp/
```

On EC2:

```bash
mkdir -p /tmp/powerclaw-install
tar -xzf /tmp/powerclaw-ec2-0.1.0.tar.gz -C /tmp/powerclaw-install
cd /tmp/powerclaw-install
sudo bash scripts/install-ec2.sh
```

The script creates:

- `/opt/powerclaw` for application code
- `/var/lib/powerclaw/workspace` for the agent workspace
- `/var/lib/powerclaw/state.db` for SQLite transcripts
- `/var/lib/powerclaw/cache` and `/var/lib/powerclaw/uv-cache` for service-safe caches
- `/etc/powerclaw/powerclaw.env` for secrets/config
- `powerclaw.service` as a systemd service

## Configure

Edit the environment file:

```bash
sudo editor /etc/powerclaw/powerclaw.env
sudo chmod 600 /etc/powerclaw/powerclaw.env
```

Required values:

```bash
OPENAI_API_KEY=...
POWERCLAW_AUTH_TOKEN=<long random token>
```

Generate a token:

```bash
openssl rand -hex 32
```

Keep the default bind address unless you have a reverse proxy or tunnel with its
own access control:

```bash
POWERCLAW_SERVER_HOST=127.0.0.1
POWERCLAW_SERVER_PORT=8765
```

For durable sessions, approvals, observability, and transcript memory, keep the
SQLite backends enabled:

```bash
POWERCLAW_TRANSCRIPT_BACKEND=sqlite
POWERCLAW_RETRIEVAL_BACKEND=sqlite
POWERCLAW_SESSION_BACKEND=sqlite
POWERCLAW_PERMISSIONS_BACKEND=sqlite
POWERCLAW_OBSERVABILITY_BACKEND=sqlite
POWERCLAW_STATE_DB_PATH=/var/lib/powerclaw/state.db
```

## Start

```bash
sudo systemctl start powerclaw
sudo systemctl status powerclaw
```

Health check from the instance:

```bash
curl -H "Authorization: Bearer $POWERCLAW_AUTH_TOKEN" \
  http://127.0.0.1:8765/health
```

Submit a turn:

```bash
curl -X POST http://127.0.0.1:8765/v1/turn \
  -H "Authorization: Bearer $POWERCLAW_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Summarize the current workspace."}'
```

Search transcript memory:

```bash
curl -H "Authorization: Bearer $POWERCLAW_AUTH_TOKEN" \
  "http://127.0.0.1:8765/v1/memory/search?q=workspace&limit=5"
```

Open the local dashboard through an SSH or SSM tunnel:

```bash
ssh -L 8765:127.0.0.1:8765 ec2-user@YOUR_EC2_HOST
open http://127.0.0.1:8765/dashboard
```

The dashboard shows recent sessions, runtime events, metrics, pending approvals,
and a turn composer. If `POWERCLAW_AUTH_TOKEN` is set, paste the token into the
dashboard token field before using API-backed controls.

## Approvals

When the terminal tool is enabled, commands that are not already approved create
a pending permission request instead of running:

```bash
curl -H "Authorization: Bearer $POWERCLAW_AUTH_TOKEN" \
  "http://127.0.0.1:8765/v1/approvals?status=pending"
```

Approve an exact request:

```bash
curl -X POST http://127.0.0.1:8765/v1/approvals/REQUEST_ID/approve \
  -H "Authorization: Bearer $POWERCLAW_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"note":"approved for this session"}'
```

The CLI can operate on the same SQLite approval store:

```bash
POWERCLAW_PERMISSIONS_BACKEND=sqlite \
POWERCLAW_STATE_DB_PATH=/var/lib/powerclaw/state.db \
/usr/local/bin/uv --directory /opt/powerclaw run powerclaw approvals list --status pending
```

## Remote Access

Preferred options:

- AWS SSM port forwarding
- Tailscale
- Cloudflare Tunnel with access policy
- ALB with HTTPS and authentication

Avoid opening `8765` directly to the internet.

## Reverse Proxy And TLS

Run the hardening script after the base service works locally:

```bash
sudo POWERCLAW_DOMAIN=agent.example.com \
  POWERCLAW_TLS_EMAIL=you@example.com \
  bash /opt/powerclaw/scripts/harden-ec2.sh
```

The script installs and configures:

- Nginx reverse proxy to `127.0.0.1:8765`
- Let's Encrypt TLS when `POWERCLAW_DOMAIN` and `POWERCLAW_TLS_EMAIL` are set
- Security headers at the proxy
- Daily SQLite backups through a systemd timer
- UFW rules only when UFW is already active

For private-only deployments, omit the domain and keep access through SSM,
Tailscale, or SSH port forwarding.

## Terminal Tool Policy

The terminal tool is disabled by default:

```bash
POWERCLAW_ENABLE_TERMINAL=false
```

If enabled, PowerClaw still denies every command unless the exact command string
appears in:

```bash
POWERCLAW_TERMINAL_ALLOWED_COMMANDS=python3 -m pytest -q
```

If a command is not preconfigured, the runtime creates an approval request. Use
the dashboard or approvals API to approve the exact command for the session.
Use this for tightly scoped operational tasks, not broad shell access.

For isolated throwaway VMs where the operator explicitly wants full machine
control, trusted terminal mode removes per-command approvals:

```bash
POWERCLAW_TERMINAL_TRUSTED=true
```

This also enables the terminal tool. Do not use trusted terminal mode on shared
hosts or systems with sensitive credentials.

## Flagship Workflow

The repo-operator workflow exercises the complete runtime surface: workspace
inspection, skills, approvals, observability, memory, and EC2 deployment
preparation.

```bash
/usr/local/bin/uv --directory /opt/powerclaw run powerclaw workflow repo-operator \
  --objective "Inspect this repo and prepare the next EC2-ready release step"
```

HTTP:

```bash
curl -X POST http://127.0.0.1:8765/v1/workflows/repo-operator \
  -H "Authorization: Bearer $POWERCLAW_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"objective":"Inspect this repo and prepare the next EC2-ready release step"}'
```

## Operations

Restart after config changes:

```bash
sudo systemctl restart powerclaw
```

View logs:

```bash
journalctl -u powerclaw -f
```

View recent runtime events:

```bash
curl -H "Authorization: Bearer $POWERCLAW_AUTH_TOKEN" \
  "http://127.0.0.1:8765/v1/events?limit=25"
```

View metrics:

```bash
curl -H "Authorization: Bearer $POWERCLAW_AUTH_TOKEN" \
  http://127.0.0.1:8765/v1/metrics
```

Check backups:

```bash
systemctl list-timers powerclaw-backup.timer
sudo ls -lh /var/backups/powerclaw
```

Update:

```bash
cd /opt/powerclaw
sudo -u powerclaw git pull --ff-only
sudo -u powerclaw /usr/local/bin/uv sync
sudo systemctl restart powerclaw
```
