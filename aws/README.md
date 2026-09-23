# AWS deployment (executed)

This folder documents how AI Confessor was actually deployed to AWS. The app
is live on an EC2 instance, not just scripted.

## What is actually running

- EC2 `t3.medium` in `us-east-1`, Ubuntu 24.04.
- Docker Compose on the host: `backend` (FastAPI on :8000) + `frontend`
  (nginx serving the built React app, proxying `/api` and `/ws` to the backend).
- Free public HTTPS via a Cloudflare quick tunnel pointed at the frontend.
  HTTPS matters: browsers only grant microphone access on secure origins.
- The Claude API key lives server-side only, in the backend `.env`
  (`chmod 600`). It is never in frontend code, never in Git.
- Live URL: https://passed-tampa-single-efforts.trycloudflare.com
  (quick-tunnel URLs change on redeploy; a custom domain + named tunnel would
  be the production step).

## How it was deployed

`deploy-ec2.sh` is the original script: it provisions an EC2 instance over
SSH, installs Docker, copies the project with `scp`, and runs
`docker compose up`. It documents the intended approach (security group
`ai-confessor-sg` with ports 22/3000/8000, 30 GB disk, `t3.medium` default).

The actual live deployment used EC2 user-data automation instead of the
SSH/`scp` path (no SSH access was available from the build environment):
the instance boots, installs Docker, starts the compose stack, launches the
Cloudflare tunnel, and publishes the tunnel URL through the frontend
container so it can be looked up with a single curl. The result is the same
stack the script describes: the same two containers, the same `.env`-driven
config, the same Vosk model volume.

## Verified on the live instance

- Page loads over HTTPS with no interstitial.
- Header shows `claude-sonnet-4-6` connected (not mock mode).
- Live chat test: the AI replied "PONG" exactly to a one-word instruction,
  proving a live Claude connection rather than canned replies.

## Production hardening (not done)

- Replace the quick tunnel with a named Cloudflare tunnel on a custom domain
  so the URL survives redeploys.
- Move the API key to AWS Secrets Manager / SSM Parameter Store (server-side
  only; never baked into images or user-data).
- Tighten the security group: drop public SSH (port 22) and the direct
  backend port (8000); keep only what the tunnel needs.
- Multi-instance scale-out would need shared session state (sessions are
  currently in-memory per worker; add Redis) plus a load balancer.
