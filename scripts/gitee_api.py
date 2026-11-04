"""Small Gitee API v5 executor; token comes from GITEE_TOKEN, never argv.

Verified API specification: https://gitee.com/api/v5/swagger_doc (5.4.93).
The documented PR operations use access_token in the query string.
GET fields become query parameters. Writes use JSON unless --body-format form.
This helper does not configure Gitee Go, infer permissions, or auto-paginate.
"""

import argparse
import json
import math
import os
from pathlib import Path
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


SENSITIVE_KEYS = {"access_token", "token", "refresh_token", "authorization",
                  "password", "client_secret", "secret"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def redact(value, token):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else redact(item, token)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, token) for item in value]
    if isinstance(value, str) and token:
        for secret in {token, quote(token, safe=""), quote_plus(token)}:
            value = value.replace(secret, "[REDACTED]")
    return value


def build_request(api_base, path, method, fields, token, body_format="json", allow_http=False):
    base = urlsplit(api_base)
    if base.scheme not in {"http", "https"} or not base.hostname:
        raise ValueError("api-base must be an absolute HTTP(S) URL")
    if base.scheme == "http" and not allow_http:
        raise ValueError("HTTP requires explicit --allow-http for a documented local/private endpoint")
    if base.username or base.password or base.query or base.fragment:
        raise ValueError("api-base must not contain credentials, query parameters or a fragment")
    decoded = unquote(path)
    if any(part in {".", ".."} for part in decoded.split("/")) or any(
            char in decoded for char in (":", "?", "#", "\\")):
        raise ValueError("path must be a relative API path without traversal or URL components")
    if not isinstance(fields, dict) or any(str(key).lower() in SENSITIVE_KEYS for key in fields):
        raise ValueError("body-file must contain an object without credential fields")
    query = {"access_token": token}
    headers = {"Accept": "application/json", "User-Agent": "review-workflow-tooling/1"}
    body = None
    if method == "GET":
        query.update(fields)
    elif body_format == "form":
        body = urlencode(fields, doseq=True).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    else:
        body = json.dumps(fields, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    url = api_base.rstrip("/") + "/" + path.lstrip("/") + "?" + urlencode(query, doseq=True)
    return Request(url, data=body, headers=headers, method=method)


def select_fields(payload, selected):
    if not selected:
        return payload
    if isinstance(payload, list):
        return [select_fields(item, selected) for item in payload]
    if isinstance(payload, dict):
        return {key: payload.get(key) for key in selected}
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="https://gitee.com/api/v5")
    parser.add_argument("--path", required=True)
    parser.add_argument("--method", choices=("GET", "POST", "PATCH", "PUT"), default="GET")
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--body-format", choices=("json", "form"), default="json")
    parser.add_argument("--select", help="Comma-separated top-level response keys")
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--allow-http", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print a redacted request; send nothing")
    args = parser.parse_args()
    token = os.environ.get("GITEE_TOKEN", "")
    if not token and not args.dry_run:
        print(json.dumps({"ok": False, "error": "GITEE_TOKEN is not configured"}))
        return 2
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        fields = json.loads(args.body_file.read_text(encoding="utf-8-sig")) if args.body_file else {}
        request = build_request(args.api_base, args.path, args.method, fields,
                                token or "DRY_RUN_TOKEN", args.body_format, args.allow_http)
        if args.dry_run:
            report = {"phase": "request_preview_only", "request_sent": False,
                      "credential_present": bool(token), "method": args.method,
                      "url": request.full_url, "body": fields}
            print(json.dumps(redact(report, token or "DRY_RUN_TOKEN"), ensure_ascii=True, indent=2))
            return 0
        context = ssl.create_default_context(cafile=str(args.ca_file) if args.ca_file else None)
        opener = build_opener(NoRedirect(), HTTPSHandler(context=context))
        with opener.open(request, timeout=args.timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            try:
                payload = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                payload = raw
            selected = args.select.split(",") if args.select else None
            report = {"ok": True, "http_status": response.status,
                      "data": select_fields(payload, selected)}
            print(json.dumps(redact(report, token), ensure_ascii=True, indent=2))
            return 0
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:3000]
        report = {"ok": False, "http_status": exc.code, "error": redact(detail, token)}
        print(json.dumps(report, ensure_ascii=True))
        return 1
    except (OSError, URLError, ValueError) as exc:
        report = {"ok": False, "error": redact(str(exc), token)}
        print(json.dumps(report, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
