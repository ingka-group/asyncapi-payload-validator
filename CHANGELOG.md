# Changelog

All notable changes to the AsyncAPI Payload Validator project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-19

### Added
- Initial release of AsyncAPI Payload Validator
- Comprehensive JSON Schema validation against AsyncAPI specifications
- Support for AsyncAPI 2.x and 3.x specifications
- Type checking with lenient coercion for common patterns
- Required field validation
- String constraint validation (minLength, maxLength, pattern)
- Numeric constraint validation (minimum, maximum, multipleOf)
- Enum validation with numeric coercion
- Composition rules support (oneOf, anyOf, allOf)
- Additional properties handling
- HTML report generation with Jinja2 templates
- Command-line interface (`asyncapi-validate`)
- Python library API for programmatic usage
- Message ID selection for multi-message specs
- Detailed error reporting with line numbers and source context
- Exit codes for CI/CD integration

### Features
- **CLI Tool**: `asyncapi-validate payload.json spec.yaml [--html-report report.html] [--message-id MessageId]`
- **HTML Reports**: Beautiful, detailed validation reports with syntax highlighting
- **Lenient Type Coercion**: Accepts string numbers ("42" → integer), string booleans ("true" → boolean)
- **$ref Resolution**: Handles JSON Pointer references within AsyncAPI documents
- **Wildcard Properties**: Respects `additionalProperties` for dynamic keys
- **oneOf Refinement**: Smart required field handling for variant schemas

### Technical Details
- Python 3.8+ support
- Dependencies: PyYAML>=6.0, Jinja2>=3.1.2
- Package structure follows Python best practices
- Comprehensive test suite with pytest
- Type hints throughout codebase
- Black code formatting
- PEP 517/518 compliant build system

### Documentation
- Complete README with usage examples
- Quick publish guide for PyPI
- AsyncAPI contribution guide
- API documentation in code
- CI/CD integration examples (GitHub Actions, GitLab CI)

---

## Future Releases

### [Unreleased]

Ideas for future versions:
- [ ] JSON Schema Draft 2020-12 support
- [ ] Schema registry integration (Confluent, Azure Schema Registry)
- [ ] Batch validation for multiple payloads
- [ ] JUnit XML output for test frameworks
- [ ] JSON output format for programmatic parsing
- [ ] Webhook endpoint validation
- [ ] Performance benchmarks and optimization
- [ ] VS Code extension
- [ ] Docker image for containerized usage

---

## Version History

| Version | Date       | Highlights                          |
|---------|------------|-------------------------------------|
| 1.0.0   | 2026-02-19 | Initial release with full features |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to this project.

## License

This project is licensed under the MIT License - see [LICENCE.md](LICENCE.md) for details.
