# Skript Minestom Tests

A GitHub Action for running Skript runtime tests on Minestom. It supports downloading a published Skript-Minestom JAR or building the runtime from source before running tests.

## Features

- Runs Skript test scripts on Minestom.
- Supports downloading a published runtime or building from a Git repository.
- Supports selecting a published version or source Git reference.
- Downloads the runtime test framework automatically.
- Installs Skript-Reflect, required by the framework.
- Supports configurable test script directories and runtime timeouts.
- Stops execution if the runtime exceeds the configured timeout.
- Uses Java 25.

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
        uses: devdinc/skript-minestom-test-action@main
        with:
          test_script_directory: tests
```

By default, the action downloads the latest published version available in the configured Maven snapshot repository.

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `mode` | No | `download` | Runtime source: `download` or `build`. |
| `version` | No | `latest` | Published Skript-Minestom version to download. Used only in `download` mode. |
| `repository` | No | `https://github.com/hapily04/skript-minestom.git` | Git repository to clone in `build` mode. |
| `ref` | No | — | Branch, tag, or commit to build. Used only in `build` mode. |
| `test_script_directory` | Yes | — | Directory containing Skript test scripts, relative to the calling repository's root. |
| `timeout` | No | `45s` | Maximum runtime duration, such as `30s`, `1m`, or `5m`. |

## Runtime Modes

### Download a published runtime

This is the default mode. The action downloads a published JAR from the configured Maven snapshot repository.

```yaml
- name: Run Skript tests
  uses: devdinc/skript-minestom-test-action
  with:
    mode: download
    version: latest
    test_script_directory: tests
```

To use a specific published version, replace `latest` with the desired version:

```yaml
- name: Run Skript tests
  uses: devdinc/skript-minestom-test-action@main
  with:
    mode: download
    version: 1.0.0-alpha.49
    test_script_directory: tests
```

The `latest` version is resolved from Maven metadata. It reflects the latest version published in that repository, which may differ from the newest version in the source repository.

### Build from source

Use `build` mode to clone the Skript-Minestom source repository and build its runnable Shadow JAR.

```yaml
- name: Run Skript tests
  uses: devdinc/skript-minestom-test-action@main
  with:
    mode: build
    test_script_directory: tests
```

To build a specific branch, tag, or commit:

```yaml
- name: Run Skript tests
  uses: devdinc/skript-minestom-test-action@main
  with:
    mode: build
    repository: https://github.com/hapily04/skript-minestom.git
    ref: main
    test_script_directory: tests
```

The action runs the Gradle task `:minestom:shadowJar` and uses the resulting runnable JAR to execute the tests. The source repository must be buildable in the GitHub Actions environment, including successful resolution of its dependencies.

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
  uses: devdinc/skript-minestom-test-action@main
  with:
    test_script_directory: skript-tests
```

The action copies the contents of the configured directory into the runtime's Skript scripts directory under `tests/`, preserving nested directories.

**Note:** The test directory is read from the repository running the workflow, not automatically from the action's repository. Ensure the workflow checks out the calling repository before running the action.

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

The framework also supports non-halting assertions and failure effects:

- `without halting assert ...` records a failure and continues execution.
- `fail test` records a test failure and halts by default.
- `without halting fail test` records a failure and continues execution.

A test that records a failure is counted as failed by the runner, even if the test continues and later assertions pass.

## Dependencies

The action automatically downloads or prepares the following:

- **Skript-Minestom:** downloaded from the configured Maven repository in `download` mode, or built from source in `build` mode.
- **Skript-Reflect 2.6.3:** downloaded and installed as an addon.
- **Runtime test framework:** downloaded from the `devdinc/skripts` repository.

The action configures Java 25 using `actions/setup-java@v4`.

## Timeout

The default timeout is 45 seconds. Override it when runtime startup or test execution needs more time:

```yaml
- name: Run tests
  uses: devdinc/skript-minestom-test-action@main
  with:
    test_script_directory: tests
    timeout: 2m
```

The timeout applies to the runtime test runner. If it is exceeded, the action terminates the process and fails the step.

## Troubleshooting

### Test directory not found

Ensure `test_script_directory` points to a directory in the calling repository and that the workflow checks out the repository first.

### Build fails in `build` mode

The source build requires Gradle and all runtime dependencies to resolve successfully. A repository outage, TLS handshake failure, or unavailable snapshot dependency can prevent the Shadow JAR from being produced.

Check the Gradle output for the dependency and repository that failed to resolve.

### Tests fail to parse

Verify that your test syntax is supported by the framework and by the installed Skript-Minestom runtime. Features unavailable in the runtime, such as unsupported world fixtures, cannot be tested by simply declaring them in a test script.

### Tests time out

Increase the `timeout` input if runtime startup or test execution takes longer than the configured duration.

### Tests report failures

Review the runtime output for `TEST FAILURE` messages. The framework records failed assertions and explicit test failures, and the runner reports the number of successful and failed tests.
