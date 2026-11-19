# Security model and limitations

- Host scanner is read-only and uses fixed command arguments; no arbitrary shell command is accepted from chat.
- The chat model is advisory and is not given OS execution tools.
- Remediation approval endpoint records consent but does not run changes.
- MongoDB is published only on 127.0.0.1 by default; change networking deliberately if remote access is required.
- `.env` is ignored by Git; never commit credentials.
- Rate limiting is applied to API routes with a MongoDB minute bucket.
- For production: enable TLS/reverse proxy, MongoDB authentication and least-privilege users, network segmentation, backups, alerting, secret management, and audit retention.
- Local host scans are not comprehensive vulnerability assessments. They do not establish exploitability or absence of compromise.
