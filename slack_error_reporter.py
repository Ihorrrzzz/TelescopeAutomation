"""Centralized Slack error reporter — posts unhandled errors to #bug-hunters.

Canonical module (AA-241). Home: github.com/YozmaTech-dev/error-reporter.
Copied as-is into every YozmaTech automation repo — do not edit per-repo
copies; fix in the home repo and re-sync.

Usage:
    from slack_error_reporter import report_error
    try:
        main()
    except Exception as err:
        report_error(system="<repo-folder-name>", error=err, source="run.py main()")
        raise

Contract:
- Token resolution: ERROR_SLACK_BOT_TOKEN first (the shared "AI Automation
  Errors" bot, already a member of #bug-hunters), then SLACK_BOT_TOKEN
  (the repo's own bot). Missing both => silent no-op.
- NEVER raises into the host app; every failure path returns False.
- Network call is bounded by a 5 s timeout.
- No secrets / PII in the payload: exception first line + stack trace only.
- Report only unhandled/terminal errors — never validation errors, 4xx
  responses, or errors that a retry already recovered from.
"""

import json
import os
import traceback
import urllib.request
from datetime import datetime, timezone

SLACK_CHANNEL_ID = "C0BL8330ABV"  # #bug-hunters — always the ID, never the name
OWNER_SLACK_ID = "U0B4U0WCG0K"
_API_URL = "https://slack.com/api/chat.postMessage"
_TIMEOUT_S = 5
_MAX_TRACE_CHARS = 1800


def report_error(system, error, source="", runtime="python"):
    """Post one unhandled-error report to #bug-hunters. Never raises.

    system  -- repo folder name (e.g. "techmap-signal")
    error   -- the exception instance
    source  -- where it escaped (e.g. "run.py main()", "agents/cv_screener")
    runtime -- "python" unless the caller is something more specific
    Returns True only if Slack accepted the message.
    """
    try:
        token = (
            os.environ.get("ERROR_SLACK_BOT_TOKEN") or os.environ.get("SLACK_BOT_TOKEN") or ""
        ).strip()
        if not token:
            return False

        message = str(error).strip()
        head = message.splitlines()[0] if message else ""
        cls = error.__class__.__name__
        first_line = f"{cls}: {head}" if head else cls
        trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        if len(trace) > _MAX_TRACE_CHARS:
            trace = "…" + trace[-_MAX_TRACE_CHARS:]
        trace = trace.replace("```", "'''")
        when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        src = source or "unknown"
        context_line = f"AA-241 error-report • sys={system} • rt={runtime} • src={src}"

        payload = {
            "channel": SLACK_CHANNEL_ID,
            "unfurl_links": False,
            "unfurl_media": False,
            "text": f":red_circle: {system}: {first_line}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":red_circle: *{system}* — unhandled error <@{OWNER_SLACK_ID}>",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Runtime:*\n{runtime}"},
                        {"type": "mrkdwn", "text": f"*Source:*\n{src}"},
                        {"type": "mrkdwn", "text": f"*When (UTC):*\n{when}"},
                        {"type": "mrkdwn", "text": f"*Error:*\n{first_line[:250]}"},
                    ],
                },
                {"type": "section", "text": {"type": "mrkdwn", "text": f"```{trace}```"}},
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": context_line}],
                },
            ],
        }

        req = urllib.request.Request(
            _API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
        return bool(body.get("ok"))
    except Exception:
        # Deliberately blind: reporting must never crash the host app.
        return False
