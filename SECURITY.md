# Security Policy

## Supported Scope

This repository is a defensive, receive-only early-warning sensor stack. Security reports should focus on software vulnerabilities, unsafe defaults, credential handling, tamper logging, deployment scripts, and supply-chain risks.

## Reporting a Vulnerability

Please do not open a public issue for exploitable vulnerabilities.

Email: security@fratresx.ai

Include:

- Affected file, command, or deployment path
- Reproduction steps
- Expected impact
- Suggested fix, if known

We aim to acknowledge reports within 7 days.

## Secrets

Never commit production HMAC keys, mesh signing keys, RunPod credentials, SSH private keys, Wi-Fi passwords, or deployment tokens. Use environment variables or local-only secret stores.
