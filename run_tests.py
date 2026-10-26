#!/usr/bin/env python3

import re
import subprocess
import sys
import threading
import time
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print(
            f"Usage: {Path(sys.argv[0]).name} <jar-path> <server-directory>",
            file=sys.stderr,
        )
        return 2

    jar = Path(sys.argv[1]).resolve()
    server_dir = Path(sys.argv[2]).resolve()

    if not jar.is_file():
        print(f"ERROR: JAR not found: {jar}", file=sys.stderr)
        return 2

    if not server_dir.is_dir():
        print(f"ERROR: Server directory not found: {server_dir}", file=sys.stderr)
        return 2

    started_at = time.monotonic()

    def log_timing(message: str) -> None:
        elapsed = time.monotonic() - started_at
        print(f"[timing +{elapsed:.2f}s] {message}", flush=True)

    state = {
        "summary_seen": False,
        "tests_passed": False,
        "tests_failed": False,
        "failure_message": None,
    }
    state_lock = threading.Lock()

    # Recognize common test-framework summary and failure output.
    summary_patterns = (
        re.compile(r"\b(\d+)\s*/\s*(\d+)\s+tests?\s+passed\b", re.I),
        re.compile(r"\b(\d+)\s+tests?\s+passed\b", re.I),
        re.compile(r"\bAll\s+tests?\s+passed\b", re.I),
    )
    failure_patterns = (
        re.compile(r"\btests?\s+failed\b", re.I),
        re.compile(r"\btest\s+failures?\s*:", re.I),
        re.compile(r"\bFAILED\b"),
        re.compile(r"\bAssertionError\b"),
        re.compile(r"\bException in thread\b"),
    )

    def monitor_output(stream) -> None:
        try:
            for line in stream:
                print(line, end="", flush=True)
                stripped = line.strip()

                with state_lock:
                    for pattern in summary_patterns:
                        match = pattern.search(stripped)
                        if match:
                            state["summary_seen"] = True

                            if len(match.groups()) == 2:
                                passed = int(match.group(1))
                                total = int(match.group(2))
                                state["tests_passed"] = (
                                    total > 0 and passed == total
                                )
                                state["tests_failed"] = passed < total
                            elif len(match.groups()) == 1:
                                state["tests_passed"] = True
                            else:
                                state["tests_passed"] = True

                            if state["tests_passed"]:
                                log_timing("Test summary received")
                            else:
                                state["failure_message"] = stripped
                            break

                    if any(pattern.search(stripped) for pattern in failure_patterns):
                        # A failure-like line is not always a test failure, so
                        # only use it as a failure signal if no passing summary
                        # has already been observed.
                        if not state["tests_passed"]:
                            state["tests_failed"] = True
                            if state["failure_message"] is None:
                                state["failure_message"] = stripped
        except (OSError, ValueError) as exc:
            print(f"WARNING: Output reader stopped: {exc}", file=sys.stderr)

    log_timing("Starting Java process")

    try:
        process = subprocess.Popen(
            [
                "java",
                "-XX:TieredStopAtLevel=1",
                "-jar",
                str(jar),
            ],
            cwd=server_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        print(f"ERROR: Could not start Java: {exc}", file=sys.stderr)
        return 2

    log_timing("Java process launched")

    reader = threading.Thread(
        target=monitor_output,
        args=(process.stdout,),
        name="java-output-reader",
        daemon=True,
    )
    reader.start()

    exit_code = 1

    try:
        while process.poll() is None:
            with state_lock:
                summary_seen = state["summary_seen"]
                tests_passed = state["tests_passed"]
                tests_failed = state["tests_failed"]
                failure_message = state["failure_message"]

            if tests_failed:
                log_timing("Test failure detected")
                if failure_message:
                    print(f"Test failure: {failure_message}", file=sys.stderr)
                break

            if summary_seen and tests_passed:
                log_timing("All tests passed")
                exit_code = 0
                break

            time.sleep(0.1)

        # If Java exited before the summary was processed, allow the reader
        # to consume any remaining output before deciding the result.
        if process.poll() is not None:
            reader.join(timeout=1)

            with state_lock:
                summary_seen = state["summary_seen"]
                tests_passed = state["tests_passed"]
                tests_failed = state["tests_failed"]
                failure_message = state["failure_message"]

            if summary_seen and tests_passed and not tests_failed:
                exit_code = 0
            else:
                exit_code = process.returncode or 1
                if failure_message:
                    print(f"Test failure: {failure_message}", file=sys.stderr)
                elif not summary_seen:
                    print(
                        "ERROR: Java exited without a recognized test summary.",
                        file=sys.stderr,
                    )

    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        exit_code = 130

    finally:
        # Stop the server immediately after the test summary. The server may
        # run shutdown hooks but remain alive because of non-daemon threads.
        if process.poll() is None:
            log_timing("Sending terminate to server")
            try:
                process.terminate()
            except ProcessLookupError:
                pass

            try:
                process.wait(timeout=1)
                log_timing("Server exited after terminate")
            except subprocess.TimeoutExpired:
                log_timing("Server still running; sending kill")
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                process.wait()
                log_timing("Server exited after kill")

        # Wait for the reader to see EOF before closing the stream.
        reader.join(timeout=2)
        log_timing("Output reader joined")

        if process.stdout is not None and not process.stdout.closed:
            process.stdout.close()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
