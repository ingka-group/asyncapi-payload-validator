# CI/CD Integration

Use the AsyncAPI Payload Validator in your CI/CD pipelines to catch schema violations before deployment.

## GitHub Actions

```yaml
name: Validate AsyncAPI Payloads

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install validator
        run: pip install asyncapi-payload-validator
      
      - name: Validate payload
        run: |
          asyncapi-validate \
            tests/fixtures/payload.json \
            asyncapi-spec.yaml \
            --html-report validation-report.html
      
      - name: Upload report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: validation-report
          path: validation-report.html
```

## GitLab CI

```yaml
validate-payloads:
  image: python:3.11
  script:
    - pip install asyncapi-payload-validator
    - asyncapi-validate payload.json asyncapi.yaml --html-report report.html
  artifacts:
    when: always
    paths:
      - report.html
```

## Exit Codes

The CLI uses standard exit codes for CI/CD integration:

| Code | Meaning |
|------|---------|
| `0` | Validation **passed** — no violations |
| `1` | Validation **failed** — violations found |
| `2` | Error — invalid arguments, file not found, etc. |
| `130` | Cancelled by user (Ctrl+C) |

A non-zero exit code will fail the pipeline step automatically.
