import re
import subprocess
import sys
import threading
import time
from pathlib import Path

started_at = time.monotonic()


def log_timing(message):
    elapsed = time.monotonic() - started_at
    print(f"[timing +{elapsed:.2f}s] {message}", flush=True)


jar = Path(sys.argv[1])
server_dir = Path(sys.argv[2])

summary_pattern = re.compile(
    r"(\d+)\s*/\s*(\d+)\s+tests passed\.",
    re.IGNORECASE,
)
no_tests_pattern = re.compile(r"No tests found\.", re.IGNORECASE)

failure_patterns = [
    re.compile(r"failed to install", re.IGNORECASE),
    re.compile(r"installation failed", re.IGNORECASE),
]

summary = None
install_failed = False
no_tests = False
output_lock = threading.Lock()


def monitor_output(process):
    global summary, install_failed, no_tests

    for raw_line in process.stdout:
        line = raw_line.rstrip()
        print(line, flush=True)

        with output_lock:
            match = summary_pattern.search(line)
            if match:
                summary = (int(match.group(1)), int(match.group(2)))
                log_timing("Test summary received")

            if no_tests_pattern.search(line):
                no_tests = True

            if any(pattern.search(line) for pattern in failure_patterns):
                install_failed = True


log_timing("Starting Java process")
process = subprocess.Popen(
    ["java", "-XX:TieredStopAtLevel=1", "-jar", str(jar)],
    cwd=server_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
)
log_timing("Java process launched")

reader = threading.Thread(
    target=monitor_output,
    args=(process,),
    daemon=True,
)
reader.start()

try:
    deadline = time.monotonic() + 600

    while time.monotonic() < deadline:
        with output_lock:
            current_summary = summary
            current_install_failed = install_failed
            current_no_tests = no_tests

        if current_install_failed:
            raise RuntimeError("Package reported an installation failure.")

        if current_no_tests:
            raise RuntimeError("The runtime test framework found no tests.")

        if current_summary is not None:
            passed, total = current_summary
            if total == 0:
                raise RuntimeError("No tests were executed.")
            if passed != total:
                raise RuntimeError(
                    f"Runtime tests failed: {passed}/{total} passed."
                )
            log_timing("All tests passed")
            print(f"All runtime tests passed: {passed}/{total}.")
            break

        if process.poll() is not None:
            reader.join(timeout=2)

            with output_lock:
                current_summary = summary

            if current_summary is None:
                raise RuntimeError(
                    f"Server exited with code {process.returncode} "
                    "before a test summary."
                )
            break

        time.sleep(0.1)
    else:
        raise TimeoutError("Timed out waiting for runtime test results.")

finally:
    if process.poll() is None:
        log_timing("Waiting up to 2s for natural server shutdown")
        try:
            process.wait(timeout=2)
            log_timing("Server exited naturally")
        except subprocess.TimeoutExpired:
            log_timing("Server still running; sending terminate")
            process.terminate()
            try:
                process.wait(timeout=2)
                log_timing("Server exited after terminate")
            except subprocess.TimeoutExpired:
                log_timing("Server still running; sending kill")
                process.kill()
                process.wait()
                log_timing("Server exited after kill")

    if process.stdout:
        process.stdout.close()

    reader.join(timeout=2)
    log_timing("Output reader joined")

with output_lock:
    final_summary = summary
    final_no_tests = no_tests
    final_install_failed = install_failed

if final_summary is None:
    raise SystemExit("No runtime test summary was detected.")

passed, total = final_summary
if (
    total == 0
    or passed != total
    or final_no_tests
    or final_install_failed
):
    raise SystemExit(1)
