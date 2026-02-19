"""
Copyright (c) 2026 Ingka Holding B.V.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

"""Tests for CLI entry point."""

import sys
import pytest
from unittest.mock import patch, MagicMock
from asyncapi_payload_validator.cli import cli


class TestCLI:
    """Test cases for CLI wrapper function."""
    
    def test_cli_calls_main(self, tmp_path):
        """Test that cli() calls main() successfully."""
        # Create minimal test files
        payload = tmp_path / "payload.json"
        payload.write_text('{"id": 123}')
        
        spec = tmp_path / "spec.yaml"
        spec.write_text('''
asyncapi: 2.0.0
info:
  title: Test
  version: 1.0.0
channels:
  test:
    publish:
      message:
        payload:
          type: object
          properties:
            id:
              type: integer
          required: [id]
''')
        
        # Mock sys.argv to pass correct arguments
        with patch.object(sys, 'argv', ['cli', str(payload), str(spec)]):
            with pytest.raises(SystemExit) as exc_info:
                cli()
            assert exc_info.value.code == 0
    
    def test_cli_keyboard_interrupt(self):
        """Test that KeyboardInterrupt is handled gracefully."""
        with patch('asyncapi_payload_validator.cli.main', side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc_info:
                cli()
            assert exc_info.value.code == 130
    
    def test_cli_exception_handling(self):
        """Test that general exceptions are caught and reported."""
        with patch('asyncapi_payload_validator.cli.main', side_effect=RuntimeError("Test error")):
            with pytest.raises(SystemExit) as exc_info:
                cli()
            assert exc_info.value.code == 2
    
    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows-specific test")
    def test_cli_windows_encoding(self):
        """Test that Windows encoding is configured correctly."""
        import io
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        try:
            with patch('asyncapi_payload_validator.cli.main', side_effect=KeyboardInterrupt):
                with pytest.raises(SystemExit):
                    cli()
                
                # Verify stdout/stderr are TextIOWrapper with UTF-8
                assert isinstance(sys.stdout, io.TextIOWrapper)
                assert isinstance(sys.stderr, io.TextIOWrapper)
                assert sys.stdout.encoding == 'utf-8'
                assert sys.stderr.encoding == 'utf-8'
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
