"""Tests for TraceSourceFactory."""

import pytest
from unittest.mock import patch, Mock
from pathlib import Path
from refinery.core.trace_source_factory import TraceSourceFactory


class TestCreateFromProvider:
    """Test explicit provider creation."""

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langsmith")
    def test_create_langsmith(self, mock_create):
        """Test creating LangSmith provider."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        result = TraceSourceFactory.create_from_provider("langsmith", {"api_key": "test"})

        assert result == mock_provider
        mock_create.assert_called_once_with({"api_key": "test"})

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langfuse")
    def test_create_langfuse(self, mock_create):
        """Test creating Langfuse provider."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        result = TraceSourceFactory.create_from_provider("langfuse", {"public_key": "pk"})

        assert result == mock_provider
        mock_create.assert_called_once_with({"public_key": "pk"})

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_local_file")
    def test_create_otlp(self, mock_create):
        """Test creating OTLP provider."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        result = TraceSourceFactory.create_from_provider("otlp", {"file_path": "/tmp/trace.json"})

        assert result == mock_provider
        mock_create.assert_called_once_with({"file_path": "/tmp/trace.json"})

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_local_file")
    def test_create_local_file(self, mock_create):
        """Test creating local-file provider."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        result = TraceSourceFactory.create_from_provider("local-file", {"file_path": "/tmp/trace.json"})

        assert result == mock_provider
        mock_create.assert_called_once_with({"file_path": "/tmp/trace.json"})

    def test_case_insensitive_provider(self):
        """Test provider names are case insensitive."""
        with patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langsmith") as mock:
            mock.return_value = Mock()
            TraceSourceFactory.create_from_provider("LANGSMITH", {})
            mock.assert_called_once()

    def test_invalid_provider_raises_error(self):
        """Test invalid provider name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider: invalid"):
            TraceSourceFactory.create_from_provider("invalid", {})

    def test_empty_config_accepted(self):
        """Test empty config is accepted."""
        with patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langsmith") as mock:
            mock.return_value = Mock()
            TraceSourceFactory.create_from_provider("langsmith")
            mock.assert_called_once_with({})


class TestCreateFromConfig:
    """Test auto-detection from config."""

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langfuse")
    def test_explicit_provider_field(self, mock_create):
        """Test explicit 'provider' field in config."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        config = {"provider": "langfuse", "public_key": "pk"}
        result = TraceSourceFactory.create_from_config(config)

        assert result == mock_provider
        mock_create.assert_called_once_with(config)

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langfuse")
    def test_autodetect_langfuse_public_key(self, mock_create):
        """Test auto-detection of Langfuse from LANGFUSE_PUBLIC_KEY."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        config = {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"}
        result = TraceSourceFactory.create_from_config(config)

        assert result == mock_provider
        mock_create.assert_called_once_with(config)

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langfuse")
    def test_autodetect_langfuse_lowercase(self, mock_create):
        """Test auto-detection of Langfuse from lowercase keys."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        config = {"public_key": "pk", "secret_key": "sk"}
        result = TraceSourceFactory.create_from_config(config)

        assert result == mock_provider

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langsmith")
    def test_autodetect_langsmith_api_key(self, mock_create):
        """Test auto-detection of LangSmith from LANGCHAIN_API_KEY."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        config = {"LANGCHAIN_API_KEY": "key"}
        result = TraceSourceFactory.create_from_config(config)

        assert result == mock_provider

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langsmith")
    def test_autodetect_langsmith_lowercase(self, mock_create):
        """Test auto-detection of LangSmith from lowercase keys."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        config = {"api_key": "key"}
        result = TraceSourceFactory.create_from_config(config)

        assert result == mock_provider

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_local_file")
    def test_autodetect_local_file(self, mock_create):
        """Test auto-detection of local file from file_path."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        config = {"file_path": "/tmp/trace.json"}
        result = TraceSourceFactory.create_from_config(config)

        assert result == mock_provider

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_local_file")
    def test_autodetect_trace_file(self, mock_create):
        """Test auto-detection of local file from trace_file."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        config = {"trace_file": "/tmp/trace.json"}
        result = TraceSourceFactory.create_from_config(config)

        assert result == mock_provider

    def test_no_matching_keys_raises_error(self):
        """Test empty or unrecognized config raises ValueError."""
        with pytest.raises(ValueError, match="Cannot auto-detect provider"):
            TraceSourceFactory.create_from_config({"unknown_key": "value"})


class TestCreateForCLI:
    """Test CLI-specific creation patterns."""

    @patch("refinery.core.trace_source_factory.TraceSourceFactory.create_from_provider")
    def test_explicit_provider(self, mock_create):
        """Test explicit provider specified."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        result = TraceSourceFactory.create_for_cli(provider="langfuse", trace_id="abc123")

        assert result == mock_provider
        mock_create.assert_called_once_with("langfuse", {
            "trace_id": "abc123",
            "file_path": None,
        })

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_local_file")
    def test_autodetect_from_file_path(self, mock_create):
        """Test auto-detection from file path."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        result = TraceSourceFactory.create_for_cli(file_path="/tmp/trace.json")

        assert result == mock_provider
        mock_create.assert_called_once_with({"file_path": "/tmp/trace.json"})

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langsmith")
    def test_default_to_langsmith_with_trace_id(self, mock_create):
        """Test defaulting to LangSmith when trace_id provided."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        result = TraceSourceFactory.create_for_cli(trace_id="abc123")

        assert result == mock_provider
        mock_create.assert_called_once_with({"trace_id": "abc123"})

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langsmith")
    def test_default_to_langsmith_no_args(self, mock_create):
        """Test defaulting to LangSmith when no args provided."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        result = TraceSourceFactory.create_for_cli()

        assert result == mock_provider
        mock_create.assert_called_once_with({})

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_local_file")
    def test_file_path_takes_precedence(self, mock_create):
        """Test file_path takes precedence over trace_id when both provided."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        result = TraceSourceFactory.create_for_cli(
            file_path="/tmp/trace.json",
            trace_id="abc123"
        )

        assert result == mock_provider
        # Should use file path, not trace_id
        mock_create.assert_called_once_with({"file_path": "/tmp/trace.json"})


class TestProviderCreationHelpers:
    """Test individual provider creation helper methods."""

    @patch("refinery.integrations.langsmith_client_simple.SimpleLangSmithClient")
    def test_create_langsmith_with_credentials(self, mock_client_class):
        """Test LangSmith creation with credentials."""
        mock_instance = Mock()
        mock_client_class.return_value = mock_instance

        result = TraceSourceFactory._create_langsmith({})

        assert result == mock_instance
        mock_client_class.assert_called_once_with()

    @patch("refinery.integrations.langsmith_client_simple.SimpleLangSmithClient")
    def test_create_langsmith_with_env_vars(self, mock_client_class):
        """Test LangSmith creation with environment variable keys."""
        mock_instance = Mock()
        mock_client_class.return_value = mock_instance

        result = TraceSourceFactory._create_langsmith({})

        assert result == mock_instance
        mock_client_class.assert_called_once_with()

    @patch("refinery.integrations.langsmith_client_simple.SimpleLangSmithClient")
    def test_create_langsmith_empty_config(self, mock_client_class):
        """Test LangSmith creation with empty config (uses env vars)."""
        mock_instance = Mock()
        mock_client_class.return_value = mock_instance

        result = TraceSourceFactory._create_langsmith({})

        assert result == mock_instance
        mock_client_class.assert_called_once_with()

    @patch("refinery.integrations.langfuse_client.LangfuseClient")
    def test_create_langfuse_with_credentials(self, mock_client_class):
        """Test Langfuse creation with credentials."""
        from refinery.utils.config import config

        mock_instance = Mock()
        mock_client_class.return_value = mock_instance

        with patch.object(config, 'langfuse_public_key', 'pk-test'), \
             patch.object(config, 'langfuse_secret_key', 'sk-test'):
            result = TraceSourceFactory._create_langfuse({})

            assert result == mock_instance
            mock_client_class.assert_called_once_with()

    @patch("refinery.integrations.langfuse_client.LangfuseClient")
    def test_create_langfuse_with_env_vars(self, mock_client_class):
        """Test Langfuse creation with environment variable keys."""
        from refinery.utils.config import config

        mock_instance = Mock()
        mock_client_class.return_value = mock_instance

        with patch.object(config, 'langfuse_public_key', 'pk-test'), \
             patch.object(config, 'langfuse_secret_key', 'sk-test'):
            result = TraceSourceFactory._create_langfuse({})

            assert result == mock_instance
            mock_client_class.assert_called_once_with()

    def test_create_langfuse_missing_credentials(self):
        """Test Langfuse creation without required credentials raises error."""
        from refinery.utils.config import config

        with patch.object(config, 'langfuse_public_key', None), \
             patch.object(config, 'langfuse_secret_key', None):
            with pytest.raises(ValueError, match="Langfuse requires public_key and secret_key"):
                TraceSourceFactory._create_langfuse({})

    def test_create_langfuse_missing_secret_key(self):
        """Test Langfuse creation with only public_key raises error."""
        from refinery.utils.config import config

        with patch.object(config, 'langfuse_public_key', 'pk-test'), \
             patch.object(config, 'langfuse_secret_key', None):
            with pytest.raises(ValueError, match="Langfuse requires public_key and secret_key"):
                TraceSourceFactory._create_langfuse({})

    @patch("refinery.integrations.local_file_provider.LocalFileTraceProvider")
    def test_create_local_file_with_path(self, mock_provider_class):
        """Test local file provider creation with file path."""
        mock_instance = Mock()
        mock_provider_class.return_value = mock_instance

        # Mock Path.exists()
        with patch("refinery.core.trace_source_factory.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path.__str__ = Mock(return_value="/tmp/trace.json")
            mock_path_class.return_value = mock_path

            config = {"file_path": "/tmp/trace.json"}
            result = TraceSourceFactory._create_local_file(config)

            assert result == mock_instance
            mock_provider_class.assert_called_once_with(file_path="/tmp/trace.json")

    @patch("refinery.integrations.local_file_provider.LocalFileTraceProvider")
    def test_create_local_file_with_trace_file(self, mock_provider_class):
        """Test local file provider creation with trace_file key."""
        mock_instance = Mock()
        mock_provider_class.return_value = mock_instance

        with patch("refinery.core.trace_source_factory.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path.__str__ = Mock(return_value="/tmp/trace.json")
            mock_path_class.return_value = mock_path

            config = {"trace_file": "/tmp/trace.json"}
            result = TraceSourceFactory._create_local_file(config)

            assert result == mock_instance

    def test_create_local_file_missing_path(self):
        """Test local file provider without file_path raises error."""
        with pytest.raises(ValueError, match="Local file provider requires 'file_path'"):
            TraceSourceFactory._create_local_file({})

    def test_create_local_file_nonexistent(self):
        """Test local file provider with non-existent file raises error."""
        with patch("refinery.core.trace_source_factory.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_path_class.return_value = mock_path

            config = {"file_path": "/nonexistent/trace.json"}
            with pytest.raises(ValueError, match="Trace file not found"):
                TraceSourceFactory._create_local_file(config)


class TestBackwardCompatibility:
    """Test backward compatibility with existing workflows."""

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langsmith")
    def test_no_provider_defaults_to_langsmith(self, mock_create):
        """Test that omitting provider defaults to LangSmith."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        # CLI usage without provider
        result = TraceSourceFactory.create_for_cli()

        assert result == mock_provider
        mock_create.assert_called_once()

    @patch("refinery.core.trace_source_factory.TraceSourceFactory._create_langsmith")
    def test_trace_id_only_uses_langsmith(self, mock_create):
        """Test that providing only trace_id uses LangSmith."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider

        result = TraceSourceFactory.create_for_cli(trace_id="abc123")

        assert result == mock_provider
        mock_create.assert_called_once_with({"trace_id": "abc123"})
