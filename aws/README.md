# AWS deployment (prepared, NOT executed)

`deploy-ec2.sh` provisions one EC2 instance (Ubuntu 24.04, default `t3.medium`),
installs Docker, copies the project, and runs `docker compose up -d --build`.

## Why EC2 + docker-compose

For a demo / small-scale deployment this is the simplest path that reuses the
exact same containers as local dev — no image registry or orchestrator needed.
Estimated cost: ~$30/mo for a t3.medium on-demand (less with spot/savings plan).

## Before running

1. `aws configure` with credentials that can create EC2 + security groups.
2. Create an EC2 key pair in your target region.
3. Copy `.env.example` → `.env` and set `OPENAI_API_KEY` (or leave empty for MOCK).
4. Review the script — **it has never been run** and provisions real resources.

## What it does

- Creates security group `ai-confessor-sg` (ports 22, 3000, 8000 open).
- Launches the instance with a 30 GB disk, tagged `ai-confessor`.
- Installs `docker.io` + compose plugin via SSH.
- `scp`s backend/, frontend/, docker-compose.yml, .env and starts everything.
- Prints the public URL and the terminate command for teardown.

## Production hardening (not included)

- Put the instance behind an ALB + ACM certificate for HTTPS (browsers require
  HTTPS for microphone access on non-localhost origins).
- Move `OPENAI_API_KEY` to AWS Secrets Manager / SSM Parameter Store.
- Use an ECR-hosted image + ECS Fargate if you need multi-instance scale-out
  (sessions are currently in-memory per worker — add Redis for that).
