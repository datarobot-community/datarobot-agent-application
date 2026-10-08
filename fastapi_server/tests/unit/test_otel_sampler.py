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
"""Custom-application tracer sampling: record even when ingress sends unsampled parents."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, use_span

from app.telemetry.otel import otel


def test_configure_tracing_records_unsampled_remote_parent() -> None:
    previous_provider = trace.get_tracer_provider()
    otel._tracer_provider = None
    try:
        provider = otel.configure_tracing()
        tracer = provider.get_tracer("test-otel-sampler")
        parent_ctx = SpanContext(
            trace_id=0x5DE827FA7B49B748492899B545DDCACD,
            span_id=0x2320F93B33591443,
            is_remote=True,
            trace_flags=TraceFlags(0x00),
        )
        with use_span(NonRecordingSpan(parent_ctx), end_on_exit=True):
            with tracer.start_as_current_span("POST /api/v1/chat") as span:
                assert span.is_recording()
                assert span.get_span_context().trace_flags.sampled
    finally:
        otel._tracer_provider = None
        trace.set_tracer_provider(previous_provider)
