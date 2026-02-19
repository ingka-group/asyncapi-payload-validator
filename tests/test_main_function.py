"""
Copyright (c) 2026 Ingka Holding B.V.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

"""Tests for main() CLI function edge cases and HTML report generation."""

import sys
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestMainFunctionEdgeCases:
    """Test main() function with various argument combinations."""
    
    def test_main_with_html_report(self, tmp_path):
        """Test main() with --html-report flag."""
        payload = tmp_path / "payload.json"
        payload.write_text('{"id": 123, "name": "test"}')
        
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
            name:
              type: string
          required: [id, name]
''')
        
        report = tmp_path / "report.html"
        
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', ['validator', str(payload), str(spec), '--html-report', str(report)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            assert report.exists()
            content = report.read_text()
            assert 'AsyncAPI' in content or 'Validation' in content
    
    def test_main_with_message_id(self, tmp_path):
        """Test main() with --message-id flag."""
        payload = tmp_path / "payload.json"
        payload.write_text('{"userId": "12345"}')
        
        spec = tmp_path / "spec.yaml"
        spec.write_text('''
asyncapi: 2.0.0
components:
  messages:
    UserCreated:
      payload:
        type: object
        properties:
          userId:
            type: string
        required: [userId]
    UserDeleted:
      payload:
        type: object
        properties:
          userId:
            type: string
''')
        
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', ['validator', str(payload), str(spec), '--message-id', 'UserCreated']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
    
    def test_main_with_jinja2_rendering(self, tmp_path):
        """Test main() with --render-jinja2 and --jinja2-context flags."""
        template = tmp_path / "template.json"
        template.write_text('{"userId": "{{user_id}}", "name": "{{user_name}}"}')
        
        context = tmp_path / "context.json"
        context.write_text('{"user_id": "12345", "user_name": "John"}')
        
        spec = tmp_path / "spec.yaml"
        spec.write_text('''
asyncapi: 2.0.0
channels:
  test:
    publish:
      message:
        payload:
          type: object
          properties:
            userId:
              type: string
            name:
              type: string
''')
        
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', [
            'validator', str(template), str(spec),
            '--render-jinja2',
            '--jinja2-context', str(context)
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
    
    def test_main_with_jinja2_no_context(self, tmp_path):
        """Test main() with --render-jinja2 but no context (structural validation)."""
        template = tmp_path / "template.json"
        template.write_text('{"userId": "{{user_id}}", "requiredField": "value"}')
        
        spec = tmp_path / "spec.yaml"
        spec.write_text('''
asyncapi: 2.0.0
channels:
  test:
    publish:
      message:
        payload:
          type: object
          properties:
            userId:
              type: string
            requiredField:
              type: string
          required: [requiredField]
''')
        
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', [
            'validator', str(template), str(spec),
            '--render-jinja2'
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # Should pass structural validation
            assert exc_info.value.code == 0
    
    def test_main_invalid_jinja2_context_file(self, tmp_path):
        """Test main() with invalid --jinja2-context file."""
        template = tmp_path / "template.json"
        template.write_text('{"userId": "{{user_id}}"}')
        
        spec = tmp_path / "spec.yaml"
        spec.write_text('asyncapi: 2.0.0')
        
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', [
            'validator', str(template), str(spec),
            '--render-jinja2',
            '--jinja2-context', 'nonexistent.json'
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
    
    def test_main_missing_html_report_path(self, tmp_path):
        """Test main() with --html-report but no path."""
        payload = tmp_path / "payload.json"
        payload.write_text('{}')
        
        spec = tmp_path / "spec.yaml"
        spec.write_text('asyncapi: 2.0.0')
        
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', ['validator', str(payload), str(spec), '--html-report']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
    
    def test_main_missing_message_id_value(self, tmp_path):
        """Test main() with --message-id but no value."""
        payload = tmp_path / "payload.json"
        payload.write_text('{}')
        
        spec = tmp_path / "spec.yaml"
        spec.write_text('asyncapi: 2.0.0')
        
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', ['validator', str(payload), str(spec), '--message-id']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
    
    def test_main_wrong_number_of_arguments(self):
        """Test main() with wrong number of arguments."""
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', ['validator', 'only-one-arg']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
    
    def test_main_with_violations_generates_detailed_report(self, tmp_path):
        """Test main() generates detailed HTML report with violations."""
        payload = tmp_path / "payload.json"
        payload.write_text('{"extra": "field", "name": "ab"}')  # Too short, extra field, missing required
        
        spec = tmp_path / "spec.yaml"
        spec.write_text('''
asyncapi: 2.0.0
info:
  title: Test API
  version: 1.0.0
channels:
  test:
    publish:
      message:
        payload:
          type: object
          properties:
            name:
              type: string
              minLength: 5
            id:
              type: integer
          required: [id, name]
''')
        
        report = tmp_path / "report.html"
        
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', ['validator', str(payload), str(spec), '--html-report', str(report)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1  # Should fail due to violations
            assert report.exists()
            content = report.read_text()
            # Check report contains violation details
            assert 'extra' in content or 'Extra' in content
    
    def test_main_with_json_spec_file(self, tmp_path):
        """Test main() with JSON specification file instead of YAML."""
        payload = tmp_path / "payload.json"
        payload.write_text('{"id": 123}')
        
        spec = tmp_path / "spec.json"
        spec.write_text(json.dumps({
            "asyncapi": "2.0.0",
            "channels": {
                "test": {
                    "publish": {
                        "message": {
                            "payload": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"}
                                }
                            }
                        }
                    }
                }
            }
        }))
        
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', ['validator', str(payload), str(spec)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
    
    def test_main_jinja2_template_with_complex_variables(self, tmp_path):
        """Test main() with Jinja2 template containing complex object variables."""
        template = tmp_path / "template.json"
        template.write_text('{"user": {{user_obj}}, "tags": {{tag_list}}}')
        
        context = tmp_path / "context.json"
        context.write_text(json.dumps({
            "user_obj": {"id": 1, "name": "John"},
            "tag_list": ["tag1", "tag2", "tag3"]
        }))
        
        spec = tmp_path / "spec.yaml"
        spec.write_text('''
asyncapi: 2.0.0
channels:
  test:
    publish:
      message:
        payload:
          type: object
          properties:
            user:
              type: object
              properties:
                id:
                  type: integer
                name:
                  type: string
            tags:
              type: array
              items:
                type: string
''')
        
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', [
            'validator', str(template), str(spec),
            '--render-jinja2',
            '--jinja2-context', str(context)
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
    
    def test_main_invalid_json_template_structure(self, tmp_path):
        """Test main() with structurally invalid JSON template."""
        template = tmp_path / "template.json"
        template.write_text('{"unclosed": {{var}')  # Invalid JSON structure
        
        spec = tmp_path / "spec.yaml"
        spec.write_text('asyncapi: 2.0.0')
        
        from asyncapi_payload_validator.validator import main
        with patch.object(sys, 'argv', [
            'validator', str(template), str(spec),
            '--render-jinja2'
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
