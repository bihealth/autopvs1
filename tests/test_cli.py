import io
from unittest.mock import patch

import pytest
from loguru import logger
from typer.testing import CliRunner

from src.cli import app

#: Create a test runner
runner = CliRunner()


@pytest.fixture
def loguru_capture():
    buffer = io.StringIO()
    # Add a sink that logs to a StringIO object
    logger_id = logger.add(buffer, format="{message}")

    yield buffer

    # Remove the sink after the test to clean up
    logger.remove(logger_id)


@pytest.fixture
def mock_auto_acmg_predict_success():
    """Fixture to mock AutoACMG predict method with a success response."""
    with patch("src.auto_acmg.AutoACMG.predict") as mock_predict:
        mock_predict.return_value = "Pathogenic"
        yield mock_predict


@pytest.fixture
def mock_auto_acmg_predict_failure():
    """Fixture to mock AutoPVS1 predict method with a failure response."""
    with patch("src.auto_acmg.AutoACMG.predict") as mock_predict:
        mock_predict.side_effect = Exception("An error occurred")
        yield mock_predict


def test_classify_command_success(mock_auto_acmg_predict_success, loguru_capture):
    """Test the 'classify' command with a mocked success response from AutoACMG.predict."""
    result = runner.invoke(app, ["NM_000038.3:c.797G>A", "--genome-release", "GRCh38"])
    log_output = loguru_capture.getvalue()
    assert result.exit_code == 0
    assert "" in log_output


def test_classify_command_failure(mock_auto_acmg_predict_failure, loguru_capture):
    """Test the 'classify' command with a mocked failure response from AutoACMG.predict."""
    result = runner.invoke(app, ["NM_000038.3:c.797G>A", "--genome-release", "GRCh38"])
    log_output = loguru_capture.getvalue()
    assert result.exit_code == 0
    assert "Error" in log_output


def test_classify_invalid_genome_release(loguru_capture):
    """Test the 'classify' command with an invalid genome release."""
    result = runner.invoke(app, ["NM_000038.3:c.797G>A", "--genome-release", "InvalidRelease"])
    log_output = loguru_capture.getvalue()
    assert result.exit_code == 0
    assert "Invalid genome release" in log_output
