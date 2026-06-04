# nim-code telemetry — PostHog Cloud

nim-code can send three lightweight events to a [PostHog](https://posthog.com) project so you can see install / first-run counts on a dashboard. **Zero deploy** — PostHog Cloud is hosted; you only need a free account.

## What is sent

| Event | When |
|---|---|
| `nimcode_install_ok`  | end of a successful `./install.sh` |
| `nimcode_install_fail` | when `./install.sh` exits non-zero |
| `nimcode_first_run`   | the first `nimcode` launch on a given install |

Payload per event:

```json
{
  "api_key": "phc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "event":    "nimcode_install_ok",
  "distinct_id": "<random uuid, generated client-side, stored at ~/.config/nim-code/install_id>",
  "properties": { "version": "0.1.0", "os": "linux", "arch": "x86_64" }
}
```

**Not sent:** API key, hostname, username, file paths, IP (PostHog Cloud captures it but you can disable IP collection in project settings — recommended).

Users opt out via:

```bash
export NIMCODE_NO_TELEMETRY=1            # session
echo 'export NIMCODE_NO_TELEMETRY=1' >> ~/.bashrc   # permanent
touch ~/.config/nim-code/no-telemetry     # alternative: marker file
```

Maintainers can disable entirely by leaving `POSTHOG_API_KEY` empty in `install.sh`.

## Setup (one-time, ~3 minutes)

1. Sign up at [posthog.com](https://posthog.com) — free tier is 1M events/month, more than you'll ever hit.
2. Create a project. Copy the **Project API Key** (starts with `phc_...`).
3. *(Recommended)* Project Settings → "Anonymize IPs" → on.
4. In `install.sh`, set:

   ```bash
   POSTHOG_API_KEY="phc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```

   And confirm the host (`POSTHOG_HOST`). Defaults to `https://us.i.posthog.com`. If your PostHog Cloud project is in the EU region, change to `https://eu.i.posthog.com`.

5. Commit the change. Done — installs in the wild will populate your PostHog dashboard.

## View counts

In PostHog UI:
- **Activity** tab — raw event stream
- **Insights → Trends** — chart of `nimcode_install_ok` over time
- **Insights → Funnels** — `install_ok` → `first_run` to see how many installers actually launched `nimcode`

Or query via API:

```bash
curl -G "https://us.i.posthog.com/api/projects/<PROJECT_ID>/events/" \
  -H "Authorization: Bearer <PERSONAL_API_KEY>" \
  --data-urlencode "event=nimcode_install_ok"
```

## Self-hosting (later, optional)

PostHog is open source: <https://github.com/PostHog/posthog>. If you outgrow the cloud free tier or want to own the data, the wire format is identical — change `POSTHOG_HOST` in `install.sh` to your self-hosted URL.

## Removing telemetry entirely

If you don't want any telemetry:

1. Delete this `telemetry/` directory.
2. In `install.sh` leave `POSTHOG_API_KEY=""` (empty → no ping is sent).

That's it — the rest of the code already short-circuits cleanly on an empty key.
