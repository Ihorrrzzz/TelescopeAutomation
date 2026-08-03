"""Centralized Slack error reporter — posts unhandled errors to #bug-hunters.

Canonical module (AA-241). Copied as-is into every YozmaTech automation repo.
Do not edit per-repo copies; fix here and re-sync.

Usage:
    from slack_error_reporter import report_error
    try:
        main()
    except Exception as err:
        report_error(system="<repo-folder-name>", error=err, source="run.py main()")
        raise

Contract:
- Token comes from the SLACK_BOT_TOKEN env var. Missing token => silent no-op.
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
        token = (os.environ.get("SLACK_BOT_TOKEN") or "").strip()
        if not token:
            return False

        first_line = (str(error).strip().splitlines() or [error.__class__.__name__])[0]
        first_line = "%s: %s" % (error.__class__.__name__, first_line) if str(error).strip() else error.__class__.__name__
        trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        if len(trace) > _MAX_TRACE_CHARS:
            trace = "…" + trace[-_MAX_TRACE_CHARS:]
        trace = trace.replace("```", "'''")
        when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        payload = {
            "channel": SLACK_CHANNEL_ID,
            "unfurl_links": False,
            "unfurl_media": False,
            "text": ":red_circle: %s: %s" % (system, first_line),
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn",
                 "text": ":red_circle: *%s* — unhandled error <@%s>" % (system, OWNER_SLACK_ID)}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": "*Runtime:*\n%s" % runtime},
                    {"type": "mrkdwn", "text": "*Source:*\n%s" % (source or "unknown")},
                    {"type": "mrkdwn", "text": "*When (UTC):*\n%s" % when},
                    {"type": "mrkdwn", "text": "*Error:*\n%s" % first_line[:250]},
                ]},
                {"type": "section", "text": {"type": "mrkdwn", "text": "```%s```" % trace}},
                {"type": "context", "elements": [{"type": "mrkdwn",
                 "text": "AA-241 error-report • sys=%s • rt=%s • src=%s" % (system, runtime, source or "unknown")}]},
            ],
        }

        req = urllib.request.Request(
            _API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer %s" % token,
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
        return bool(body.get("ok"))
    except Exception:
        return False  # reporting must never crash the host app
