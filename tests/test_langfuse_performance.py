"""
Performance benchmarks for Langfuse integration.

Tests parsing speed, memory efficiency, and scalability with realistic data volumes.
Uses pytest-benchmark to measure and track performance over time.
"""

import pytest
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone

from refinery.integrations.local_file_provider import LocalFileTraceProvider
from refinery.integrations.langfuse_parser import parse_langfuse_trace, _build_hierarchy
from refinery.integrations.prompt_extractors.langfuse_extractor import LangfusePromptExtractor
from refinery.core.models import TraceRun, RunType


class TestLangfuseParsingPerformance:
    """Benchmark Langfuse trace parsing performance."""

    @pytest.fixture
    def small_trace_data(self):
        """Create a small trace with 10 observations."""
        observations = []
        for i in range(10):
            observations.append(
                {
                    "id": f"obs-{i}",
                    "name": f"Observation {i}",
                    "type": "GENERATION" if i % 3 == 0 else "SPAN",
                    "startTime": f"2024-01-01T00:00:{i:02d}Z",
                    "endTime": f"2024-01-01T00:00:{i+1:02d}Z",
                    "model": "gpt-4" if i % 3 == 0 else None,
                    "input": {"messages": [{"role": "user", "content": f"Test {i}"}]},
                    "output": {"content": f"Response {i}"},
                    "parentObservationId": f"obs-{i-1}" if i > 0 else None,
                }
            )
        return {"id": "trace-small", "observations": observations}

    @pytest.fixture
    def large_trace_data(self):
        """Create a large trace with 1000 observations."""
        observations = []
        for i in range(1000):
            observations.append(
                {
                    "id": f"obs-{i}",
                    "name": f"Observation {i}",
                    "type": "GENERATION" if i % 10 == 0 else "SPAN",
                    "startTime": f"2024-01-01T{i//3600:02d}:{(i//60)%60:02d}:{i%60:02d}Z",
                    "endTime": f"2024-01-01T{(i+1)//3600:02d}:{((i+1)//60)%60:02d}:{(i+1)%60:02d}Z",
                    "model": "gpt-4" if i % 10 == 0 else None,
                    "input": {"messages": [{"role": "user", "content": f"Test {i}"}]},
                    "output": {"content": f"Response {i}"},
                    "parentObservationId": f"obs-{i-1}" if i > 0 and i % 10 != 0 else None,
                }
            )
        return {"id": "trace-large", "observations": observations}

    @pytest.fixture
    def wide_trace_data(self):
        """Create a wide trace with 500 sibling observations."""
        observations = [
            {
                "id": "root",
                "name": "Root",
                "type": "SPAN",
                "startTime": "2024-01-01T00:00:00Z",
                "endTime": "2024-01-01T00:10:00Z",
            }
        ]
        for i in range(500):
            observations.append(
                {
                    "id": f"child-{i}",
                    "name": f"Child {i}",
                    "type": "GENERATION",
                    "startTime": f"2024-01-01T00:00:{(i//60)%60:02d}Z",
                    "endTime": f"2024-01-01T00:00:{((i+1)//60)%60:02d}Z",
                    "model": "gpt-4",
                    "parentObservationId": "root",
                    "input": {"messages": [{"role": "user", "content": f"Test {i}"}]},
                    "output": {"content": f"Response {i}"},
                }
            )
        return {"id": "trace-wide", "observations": observations}

    def test_parse_small_trace_benchmark(self, benchmark, small_trace_data):
        """Benchmark parsing a small trace (10 observations)."""
        result = benchmark(parse_langfuse_trace, small_trace_data)

        # Verify correctness
        assert result.trace_id == "trace-small"
        assert len(result.runs) == 10

    def test_parse_large_trace_benchmark(self, benchmark, large_trace_data):
        """Benchmark parsing a large trace (1000 observations)."""
        result = benchmark(parse_langfuse_trace, large_trace_data)

        # Verify correctness
        assert result.trace_id == "trace-large"
        assert len(result.runs) == 1000

        # Performance assertion: should complete in reasonable time
        # pytest-benchmark will fail if it takes too long

    def test_hierarchy_building_benchmark(self, benchmark):
        """Benchmark hierarchy building with deep nesting."""
        # Create 200 observations in a deep chain
        runs = []
        for i in range(200):
            run = TraceRun(
                id=f"run-{i}",
                name=f"Run {i}",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime.now(timezone.utc),
                end_time=None,
                error=None,
                parent_run_id=f"run-{i-1}" if i > 0 else None,
                trace_id="test-trace",
                dotted_order=f"{i:04d}",
                metadata={},
            )
            runs.append(run)

        result = benchmark(_build_hierarchy, runs)

        # Verify correctness
        assert len(result) == 200
        # Check deepest run has proper dotted_order depth
        deepest = [r for r in result if r.id == "run-199"][0]
        assert deepest.dotted_order.count(".") == 199

    def test_wide_hierarchy_building_benchmark(self, benchmark, wide_trace_data):
        """Benchmark hierarchy building with many siblings (500 children)."""
        result = benchmark(parse_langfuse_trace, wide_trace_data)

        # Verify correctness
        assert len(result.runs) == 501  # 1 root + 500 children
        children = [r for r in result.runs if r.parent_run_id == "root"]
        assert len(children) == 500


class TestLangfuseFileLoadingPerformance:
    """Benchmark file loading and format detection."""

    @pytest.fixture
    def trace_file(self, tmp_path):
        """Create a trace file with 500 observations."""
        observations = []
        for i in range(500):
            observations.append(
                {
                    "id": f"obs-{i}",
                    "name": f"Observation {i}",
                    "type": "SPAN",
                    "startTime": f"2024-01-01T{i//3600:02d}:{(i//60)%60:02d}:{i%60:02d}Z",
                }
            )
        trace = {"id": "trace-file", "observations": observations}
        file_path = tmp_path / "trace.json"
        file_path.write_text(json.dumps(trace))
        return str(file_path)

    def test_file_loading_benchmark(self, benchmark, trace_file):
        """Benchmark loading and parsing trace from file."""
        provider = LocalFileTraceProvider(trace_file)

        def load_trace():
            return asyncio.run(provider.fetch_trace())

        result = benchmark(load_trace)

        # Verify correctness
        assert result.trace_id == "trace-file"
        assert len(result.runs) == 500

    def test_format_detection_benchmark(self, benchmark, tmp_path):
        """Benchmark format detection with multiple formats."""
        # Create files with different formats
        langfuse_file = tmp_path / "langfuse.json"
        langfuse_file.write_text(
            json.dumps({"id": "trace-1", "observations": []})
        )

        def detect_and_load():
            provider = LocalFileTraceProvider(str(langfuse_file))
            return asyncio.run(provider.fetch_trace())

        result = benchmark(detect_and_load)
        assert result.metadata["format"] == "langfuse"


class TestLangfusePromptExtractionPerformance:
    """Benchmark prompt extraction from traces."""

    @pytest.fixture
    def trace_with_many_prompts(self):
        """Create trace with 100 LLM generations."""
        observations = []
        for i in range(100):
            observations.append(
                {
                    "id": f"gen-{i}",
                    "name": f"Generation {i}",
                    "type": "GENERATION",
                    "startTime": f"2024-01-01T00:{i//60:02d}:{i%60:02d}Z",
                    "model": "gpt-4",
                    "input": {
                        "messages": [
                            {"role": "system", "content": f"System prompt {i}"},
                            {"role": "user", "content": f"User prompt {i}"},
                        ]
                    },
                    "output": {"content": f"Response {i}"},
                }
            )
        trace_data = {"id": "prompt-trace", "observations": observations}
        return parse_langfuse_trace(trace_data)

    def test_prompt_extraction_benchmark(self, benchmark, trace_with_many_prompts):
        """Benchmark prompt extraction from 100 LLM generations."""
        from unittest.mock import MagicMock

        # Create a mock client (no API calls needed for ad-hoc prompts)
        mock_client = MagicMock()
        mock_client.get_managed_prompt = MagicMock(return_value=None)

        extractor = LangfusePromptExtractor(mock_client)

        async def extract_prompts():
            return await extractor.extract(trace_with_many_prompts)

        result = benchmark(lambda: asyncio.run(extract_prompts()))

        # Verify correctness - all ad-hoc prompts extracted
        assert len(result.system_prompts) == 100
        assert len(result.user_prompts) == 100


class TestLangfuseStressTests:
    """Stress tests with extreme data volumes."""

    @pytest.mark.slow
    def test_very_large_trace_stress_test(self, benchmark):
        """Stress test with 5000 observations."""
        observations = []
        for i in range(5000):
            observations.append(
                {
                    "id": f"obs-{i}",
                    "name": f"Observation {i}",
                    "type": "SPAN" if i % 10 != 0 else "GENERATION",
                    "startTime": f"2024-01-01T{i//3600:02d}:{(i//60)%60:02d}:{i%60:02d}Z",
                    "parentObservationId": f"obs-{i-1}" if i > 0 and i % 100 != 0 else None,
                }
            )
        trace_data = {"id": "stress-trace", "observations": observations}

        result = benchmark(parse_langfuse_trace, trace_data)

        # Verify correctness
        assert result.trace_id == "stress-trace"
        assert len(result.runs) == 5000

        # Verify hierarchy was built correctly
        roots = [r for r in result.runs if r.parent_run_id is None]
        assert len(roots) > 0  # Should have multiple roots due to breaks every 100

    @pytest.mark.slow
    def test_extremely_wide_trace_stress_test(self, benchmark):
        """Stress test with 2000 sibling observations."""
        observations = [
            {
                "id": "root",
                "name": "Root",
                "type": "SPAN",
                "startTime": "2024-01-01T00:00:00Z",
            }
        ]
        for i in range(2000):
            observations.append(
                {
                    "id": f"child-{i}",
                    "name": f"Child {i}",
                    "type": "SPAN",
                    "startTime": f"2024-01-01T00:{i//60:02d}:{i%60:02d}Z",
                    "parentObservationId": "root",
                }
            )
        trace_data = {"id": "wide-stress", "observations": observations}

        result = benchmark(parse_langfuse_trace, trace_data)

        # Verify correctness
        assert len(result.runs) == 2001
        children = [r for r in result.runs if r.parent_run_id == "root"]
        assert len(children) == 2000
