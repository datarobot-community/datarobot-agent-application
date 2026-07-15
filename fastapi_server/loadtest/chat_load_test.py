# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
E2E load test for the AGUI Chat endpoint (POST /api/v1/chat).

Each simulated user is identified by a distinct X-User-Email header.
The server auto-provisions a separate app user per email address, so no
DataRobot API keys are needed.  Run this script directly:

    uv run python loadtest/chat_load_test.py --users 20 --messages-per-user 3

or via Taskfile:

    task fastapi_server:test-load -- --users 20 --messages-per-user 3

Prerequisites:
  1. Start the server WITHOUT a DataRobot API key (email auth must win):
       task fastapi_server:dev          # sets TEST_USER_EMAIL, not TEST_USER_API_KEY
       # Recommended: SESSION_HTTPS_ONLY=false so cookies work over plain HTTP
  2. If ENABLE_DRAGENT_SERVER=true the downstream agent on :8842 must be running too.
"""

import argparse
import asyncio
import csv
import json
import re
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import httpx_sse

# ──────────────────────────────────────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────────────────────────────────────

OUTCOME_FINISHED = "finished"
OUTCOME_ERROR = "error"
OUTCOME_INCOMPLETE = "incomplete"
OUTCOME_HTTP_ERROR = "http_error"
OUTCOME_EXCEPTION = "exception"
OUTCOME_TIMEOUT = "timeout"


@dataclass
class RequestResult:
    user_email: str
    thread_id: str
    run_id: str
    message_index: int  # 0-based within the user's conversation
    outcome: str
    total_duration_s: float
    ttft_s: float | None = None  # time-to-first-token
    error_detail: str | None = None
    http_status: int | None = None


@dataclass
class LoadTestResults:
    results: list[RequestResult] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def parse_duration(value: str) -> float:
    """Convert a duration string to seconds.

    Accepts plain numbers ("5"), seconds ("5s", "5.5s"), and milliseconds
    ("500ms").  Raises ValueError on unrecognised patterns.
    """
    value = value.strip()
    if re.fullmatch(r"[\d.]+", value):
        return float(value)
    m_ms = re.fullmatch(r"([\d.]+)ms", value)
    if m_ms:
        return float(m_ms.group(1)) / 1000.0
    m_s = re.fullmatch(r"([\d.]+)s", value)
    if m_s:
        return float(m_s.group(1))
    raise ValueError(
        f"Unrecognised duration {value!r}.  "
        "Use a bare number (seconds), e.g. '5', '5s', '500ms'."
    )


def build_payload(thread_id: str, prompt: str) -> dict[str, Any]:
    """Build a camelCase RunAgentInput dict for a single user message."""
    return {
        "threadId": thread_id,
        "runId": str(uuid.uuid4()),
        "state": "",
        "messages": [
            {
                "id": str(uuid.uuid4()),
                "role": "user",
                "content": prompt,
                "name": "user",
            }
        ],
        "tools": [],
        "context": [],
        "forwardedProps": "",
    }


def percentile(data: list[float], pct: float) -> float:
    """Return the *pct*-th percentile of *data* (0–100).  data must be sorted."""
    if not data:
        return float("nan")
    k = (len(data) - 1) * pct / 100.0
    lo = int(k)
    hi = lo + 1
    if hi >= len(data):
        return data[lo]
    return data[lo] + (k - lo) * (data[hi] - data[lo])


# ──────────────────────────────────────────────────────────────────────────────
# Core request
# ──────────────────────────────────────────────────────────────────────────────


async def send_message(
    client: httpx.AsyncClient,
    base_url: str,
    payload: dict[str, Any],
    timeout_s: float,
    user_email: str,
    message_index: int,
) -> RequestResult:
    """
    POST /api/v1/chat and consume the SSE stream to completion.

    Returns a RequestResult describing the outcome and timings.  Never raises
    — all exceptions are caught and recorded in the result.
    """
    thread_id: str = payload["threadId"]
    run_id: str = payload["runId"]
    url = f"{base_url.rstrip('/')}/api/v1/chat"

    t_start = time.perf_counter()
    ttft: float | None = None

    try:
        async with httpx_sse.aconnect_sse(
            client,
            "POST",
            url,
            json=payload,
            timeout=timeout_s,
        ) as event_source:
            http_status = event_source.response.status_code
            if http_status >= 400:
                body = await event_source.response.aread()
                return RequestResult(
                    user_email=user_email,
                    thread_id=thread_id,
                    run_id=run_id,
                    message_index=message_index,
                    outcome=OUTCOME_HTTP_ERROR,
                    total_duration_s=time.perf_counter() - t_start,
                    http_status=http_status,
                    error_detail=body.decode(errors="replace")[:200],
                )

            outcome = OUTCOME_INCOMPLETE  # fallback if stream closes without terminal

            async for sse in event_source.aiter_sse():
                if not sse.data:
                    continue
                try:
                    event = json.loads(sse.data)
                except json.JSONDecodeError:
                    continue

                event_type: str = event.get("type", "")

                # Track time-to-first-token
                if ttft is None and event_type == "TEXT_MESSAGE_CONTENT":
                    ttft = time.perf_counter() - t_start

                # Terminal events
                if event_type == "RUN_FINISHED":
                    outcome = OUTCOME_FINISHED
                    break
                if event_type == "RUN_ERROR":
                    outcome = OUTCOME_ERROR
                    msg = event.get("message") or ""
                    return RequestResult(
                        user_email=user_email,
                        thread_id=thread_id,
                        run_id=run_id,
                        message_index=message_index,
                        outcome=outcome,
                        total_duration_s=time.perf_counter() - t_start,
                        ttft_s=ttft,
                        http_status=http_status,
                        error_detail=str(msg)[:200],
                    )

            return RequestResult(
                user_email=user_email,
                thread_id=thread_id,
                run_id=run_id,
                message_index=message_index,
                outcome=outcome,
                total_duration_s=time.perf_counter() - t_start,
                ttft_s=ttft,
                http_status=http_status,
            )

    except httpx.TimeoutException as exc:
        return RequestResult(
            user_email=user_email,
            thread_id=thread_id,
            run_id=run_id,
            message_index=message_index,
            outcome=OUTCOME_TIMEOUT,
            total_duration_s=time.perf_counter() - t_start,
            error_detail=str(exc)[:200],
        )
    except Exception as exc:  # noqa: BLE001
        return RequestResult(
            user_email=user_email,
            thread_id=thread_id,
            run_id=run_id,
            message_index=message_index,
            outcome=OUTCOME_EXCEPTION,
            total_duration_s=time.perf_counter() - t_start,
            error_detail=str(exc)[:200],
        )


# ──────────────────────────────────────────────────────────────────────────────
# Per-user simulation
# ──────────────────────────────────────────────────────────────────────────────


async def simulate_user(
    user_index: int,
    base_url: str,
    email_prefix: str,
    messages_per_user: int,
    prompt: str,
    ramp_up_s: float,
    think_time_s: float,
    timeout_s: float,
    total_users: int,
) -> list[RequestResult]:
    """Simulate a single user: ramp-up delay → N sequential messages on one thread."""
    # Stagger start: spread user_index linearly across the ramp-up window
    if ramp_up_s > 0 and total_users > 1:
        delay = ramp_up_s * user_index / (total_users - 1)
        await asyncio.sleep(delay)

    email = f"{email_prefix}-{user_index}@load.test"
    thread_id = str(uuid.uuid4())
    results: list[RequestResult] = []

    # One AsyncClient per user so each has its own cookie jar (session reuse).
    # Deliberately omit X-DATAROBOT-API-KEY so the email auth path wins.
    async with httpx.AsyncClient(
        headers={
            "X-User-Email": email,
            "Accept": "text/event-stream",
        },
        follow_redirects=True,
    ) as client:
        for msg_idx in range(messages_per_user):
            # Include message index in prompt so consecutive messages differ
            full_prompt = (
                prompt
                if messages_per_user == 1
                else f"{prompt} [message {msg_idx + 1}/{messages_per_user}]"
            )
            payload = build_payload(thread_id, full_prompt)
            result = await send_message(
                client=client,
                base_url=base_url,
                payload=payload,
                timeout_s=timeout_s,
                user_email=email,
                message_index=msg_idx,
            )
            results.append(result)

            if msg_idx < messages_per_user - 1 and think_time_s > 0:
                await asyncio.sleep(think_time_s)

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Reporting
# ──────────────────────────────────────────────────────────────────────────────


def _fmt(seconds: float | None) -> str:
    if seconds is None or seconds != seconds:  # None or NaN
        return "  n/a"
    return f"{seconds * 1000:7.0f}ms"


def print_summary(all_results: list[RequestResult], wall_s: float) -> None:
    total = len(all_results)
    successes = sum(1 for r in all_results if r.outcome == OUTCOME_FINISHED)
    failures = total - successes

    print()
    print("━" * 60)
    print("  LOAD TEST SUMMARY")
    print("━" * 60)
    print(f"  Total requests   : {total}")
    print(f"  Finished (OK)    : {successes}")
    print(f"  Failed           : {failures}")
    print(f"  Wall-clock time  : {wall_s:.1f}s")
    if wall_s > 0:
        print(f"  Throughput       : {total / wall_s:.2f} req/s")

    # Outcome breakdown
    outcomes: dict[str, int] = {}
    for r in all_results:
        outcomes[r.outcome] = outcomes.get(r.outcome, 0) + 1
    if outcomes:
        print()
        print("  Outcomes:")
        for outcome, count in sorted(outcomes.items()):
            print(f"    {outcome:<16} {count:>5}")

    # Latency stats — total duration
    durations = sorted(r.total_duration_s for r in all_results)
    ttfts = sorted(r.ttft_s for r in all_results if r.ttft_s is not None)

    print()
    print(
        f"  {'Metric':<22}  {'min':>7}  {'p50':>7}  {'p90':>7}  {'p99':>7}  {'max':>7}  {'mean':>7}"
    )
    print(
        f"  {'-' * 22}  {'-' * 7}  {'-' * 7}  {'-' * 7}  {'-' * 7}  {'-' * 7}  {'-' * 7}"
    )

    def row(label: str, data: list[float]) -> None:
        if not data:
            print(f"  {label:<22}  {'n/a':>7}")
            return
        print(
            f"  {label:<22}"
            f"  {_fmt(data[0])}"
            f"  {_fmt(percentile(data, 50))}"
            f"  {_fmt(percentile(data, 90))}"
            f"  {_fmt(percentile(data, 99))}"
            f"  {_fmt(data[-1])}"
            f"  {_fmt(statistics.mean(data))}"
        )

    row("Total duration (all)", durations)
    finished = sorted(
        r.total_duration_s for r in all_results if r.outcome == OUTCOME_FINISHED
    )
    row("Total duration (OK)", finished)
    row("Time-to-first-token", ttfts)

    # Error samples
    errors = [r for r in all_results if r.error_detail]
    if errors:
        print()
        print("  Error samples (first 5):")
        for r in errors[:5]:
            print(
                f"    [{r.outcome}] {r.user_email} msg#{r.message_index}: {r.error_detail}"
            )

    print("━" * 60)


def write_csv(path: str, all_results: list[RequestResult]) -> None:
    fields = [
        "user_email",
        "thread_id",
        "run_id",
        "message_index",
        "outcome",
        "total_duration_s",
        "ttft_s",
        "http_status",
        "error_detail",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in all_results:
            writer.writerow(
                {
                    "user_email": r.user_email,
                    "thread_id": r.thread_id,
                    "run_id": r.run_id,
                    "message_index": r.message_index,
                    "outcome": r.outcome,
                    "total_duration_s": f"{r.total_duration_s:.4f}",
                    "ttft_s": f"{r.ttft_s:.4f}" if r.ttft_s is not None else "",
                    "http_status": r.http_status if r.http_status is not None else "",
                    "error_detail": r.error_detail or "",
                }
            )
    print(f"\n  CSV written to: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────────────────


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chat_load_test",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8080",
        help="Base URL of the running fastapi_server (default: %(default)s)",
    )
    parser.add_argument(
        "--users",
        "-u",
        type=int,
        default=10,
        metavar="N",
        help="Number of concurrent simulated users (default: %(default)s)",
    )
    parser.add_argument(
        "--messages-per-user",
        "-m",
        type=int,
        default=1,
        metavar="N",
        help="Sequential messages each user sends on their thread (default: %(default)s)",
    )
    parser.add_argument(
        "--ramp-up",
        default="0",
        metavar="DURATION",
        help=(
            "Stagger user starts over this window, e.g. '5s', '500ms' "
            "(default: 0 — all start simultaneously)"
        ),
    )
    parser.add_argument(
        "--think-time",
        default="0",
        metavar="DURATION",
        help=("Delay between a user's sequential messages, e.g. '2s' (default: 0)"),
    )
    parser.add_argument(
        "--prompt",
        default="Hello, how are you?",
        help="Message content sent by each user (default: %(default)r)",
    )
    parser.add_argument(
        "--email-prefix",
        default="loadtest-user",
        help=(
            "Email address prefix; each user gets <prefix>-<N>@load.test "
            "(default: %(default)r)"
        ),
    )
    parser.add_argument(
        "--timeout",
        default="600s",
        metavar="DURATION",
        help="Per-request stream timeout (default: %(default)s)",
    )
    parser.add_argument(
        "--csv",
        default=None,
        metavar="PATH",
        help="Write per-request results to a CSV file at PATH",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    ramp_up_s = parse_duration(args.ramp_up)
    think_time_s = parse_duration(args.think_time)
    timeout_s = parse_duration(args.timeout)

    print()
    print("━" * 60)
    print("  AGUI Chat Load Test")
    print("━" * 60)
    print(f"  Base URL         : {args.base_url}")
    print(f"  Users            : {args.users}")
    print(f"  Messages/user    : {args.messages_per_user}")
    print(f"  Total requests   : {args.users * args.messages_per_user}")
    print(f"  Ramp-up          : {ramp_up_s}s")
    print(f"  Think time       : {think_time_s}s")
    print(f"  Per-req timeout  : {timeout_s}s")
    print(f"  Email prefix     : {args.email_prefix}-<N>@load.test")
    print(f"  Prompt           : {args.prompt[:60]!r}")
    print("━" * 60)
    print()

    wall_start = time.perf_counter()

    tasks = [
        simulate_user(
            user_index=i,
            base_url=args.base_url,
            email_prefix=args.email_prefix,
            messages_per_user=args.messages_per_user,
            prompt=args.prompt,
            ramp_up_s=ramp_up_s,
            think_time_s=think_time_s,
            timeout_s=timeout_s,
            total_users=args.users,
        )
        for i in range(args.users)
    ]

    per_user: list[list[RequestResult]] = await asyncio.gather(*tasks)
    wall_s = time.perf_counter() - wall_start

    all_results: list[RequestResult] = [r for user in per_user for r in user]

    print_summary(all_results, wall_s)

    if args.csv:
        write_csv(args.csv, all_results)

    failures = sum(1 for r in all_results if r.outcome != OUTCOME_FINISHED)
    return 1 if failures else 0


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        exit_code = asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\nAborted by user.", file=sys.stderr)
        sys.exit(1)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
