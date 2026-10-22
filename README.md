# Skript Minestom Tests

A GitHub Action for running Skript runtime tests on Minestom using the published Skript-Minestom runtime and a lightweight test framework.

## Features

- Runs Skript test scripts on Minestom.
- Supports configurable test script directories.
- Downloads the runtime test framework automatically.
- Installs Skript-Reflect, required by the framework.
- Supports configurable runtime versions and timeouts.
- Stops execution if the runtime exceeds the configured timeout.

## Usage

Create a workflow at `.github/workflows/tests.yml`:

```yaml
name: Skript Tests

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Run Skript tests
        uses: devdinc/skript-minestom-test-action
        with:
          test_script_directory: tests
```

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `test_script_directory` | Yes | — | Directory containing Skript test scripts, relative to the calling repository's root or an absolute path. |
| `version` | No | `1.0.0-alpha.49` | Published Skript-Minestom Maven version to download. |
| `timeout` | No | `45s` | Maximum runtime duration, such as `30s`, `1m`, or `5m`. |

## Test Directory

By default, place your tests in a `tests/` directory at the root of your repository:

```text
your-repository/
├── .github/
│   └── workflows/
│       └── tests.yml
└── tests/
    ├── assertions.sk
    └── runtime.sk
```

Configure another directory using the `test_script_directory` input:

```yaml
- name: Run tests
  uses: devdinc/skript-minestom-test-action
  with:
    test_script_directory: skript-tests
```

The action copies the contents of the configured directory into the runtime's Skript scripts directory under `tests/`, preserving nested directories.

**Note:** The test directory is read from the repository running the workflow, not automatically from the action's repository.

## Test Framework

The action downloads the runtime test framework from the `devdinc/skripts` repository and installs it alongside the test scripts. The framework provides test registration, assertions, failure reporting, test filtering, and autorun controls.

Example:

```skript
devdinc test "assert true passes":
    assert true: {_value} is not set

devdinc test "assert false passes":
    assert false: {_value} is set

devdinc test "all tests are registered":
    set {_tests::*} to all tests
    assert true: size of {_tests::*} > 0
```

### Assertions

Supported assertion forms include:

```skript
assert true: <condition>
assert false: <condition>
assert <condition> to fail
```

The framework also supports non-halting assertions and failure effects.

- `without halting assert ...` records a failure and continues execution.
- `fail test` records a test failure and halts by default.
- `without halting fail test` records a failure and continues execution.

A test that records a failure is counted as failed by the runner, even if the test continues and later assertions pass.

## Dependencies

The action automatically downloads:

- Skript-Minestom from the configured Maven version.
- Skript-Reflect `2.6.3`.
- The runtime test framework from the `devdinc/skripts` repository.

It also configures Java 25 using `actions/setup-java@v4`.

## Timeout

The default timeout is 45 seconds. Override it when tests need more time:

```yaml
- name: Run tests
  uses: devdinc/skripts/minestom@main
  with:
    test_script_directory: tests
    timeout: 2m
```

## Troubleshooting

### Test directory not found

Ensure `test_script_directory` points to a directory in the calling repository and that the workflow checks out the repository first.

### Tests fail to parse

Verify that your test syntax is supported by the framework and by the installed Skript-Minestom runtime. Features unavailable in the runtime, such as unsupported world fixtures, cannot be tested by simply declaring them in a test script.

### Tests time out

Increase the `timeout` input if runtime startup or test execution takes longer than the configured duration.

### Tests report failures

Review the runtime output for `TEST FAILURE` messages. The framework records failed assertions and explicit test failures, and the runner reports the number of successful and failed tests.

Add the license applicable to your project here.
