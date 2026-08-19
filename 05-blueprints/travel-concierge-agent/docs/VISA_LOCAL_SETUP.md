# Visa Local Setup

Setup guide for Visa iframe integration (required for real Visa API testing).

## Why This Setup?

Visa iframe requires:
- Custom domain (not `localhost`) due to CSP
- HTTPS connection
- Hosts file entry for `vcas.local.com`

## Quick Setup

```bash
./scripts/setup-visa-local.sh
```

This script:
- Stops running servers
- Adds `vcas.local.com` to `/etc/hosts`
- Verifies DNS resolution
- Creates Python virtual environment
- Installs dependencies
- Checks AWS credentials

## Manual Setup

### 1. Add Hosts Entry

```bash
# macOS/Linux
echo "127.0.0.1 vcas.local.com" | sudo tee -a /etc/hosts

# Windows (as Administrator)
Add-Content C:\Windows\System32\drivers\etc\hosts "127.0.0.1 vcas.local.com"
```

### 2. Flush DNS

```bash
# macOS
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder

# Linux
sudo systemd-resolve --flush-caches

# Windows
ipconfig /flushdns
```

### 4. Configure AWS

Ensure `~/.aws/credentials` exists with default profile:
```ini
[default]
aws_access_key_id = YOUR_KEY
aws_secret_access_key = YOUR_SECRET
region = us-east-1
```

## Running

Follow stes in the [local visa server.](../concierge_agent/local-visa-server/README.md)