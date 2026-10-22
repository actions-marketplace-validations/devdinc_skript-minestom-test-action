import re
import subprocess
import sys
import threading
import time
from pathlib import Path

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

log_path = server_dir / "server.log"
summary = None
install_failed = False
no_tests = False
output_lines = []
stop_requested = False


def monitor_output(process):
    global summary, install_failed, no_tests

    for raw_line in process.stdout:
        line = raw_line.rstrip()
        print(line, flush=True)
        output_lines.append(line)

        match = summary_pattern.search(line)
        if match:
            summary = (int(match.group(1)), int(match.group(2)))

        if no_tests_pattern.search(line):
            no_tests = True

        if any(pattern.search(line) for pattern in failure_patterns):
            install_failed = True


process = subprocess.Popen(
    ["java", "-jar", str(jar)],
    cwd=server_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
)

reader = threading.Thread(target=monitor_output, args=(process,), daemon=True)
reader.start()

try:
    deadline = time.time() + 600

    while time.time() < deadline:
        if install_failed:
            raise RuntimeError("Pacskage reported an installation failure.")

        if no_tests:
            raise RuntimeError("The runtime test framework found no tests.")

        if summary is not None:
            passed, total = summary
            if total == 0:
                raise RuntimeError("No tests were executed.")
            if passed != total:
                raise RuntimeError(f"Runtime tests failed: {passed}/{total} passed.")
            print(f"All runtime tests passed: {passed}/{total}.")
            break

        if process.poll() is not None:
            reader.join(timeout=2)
            if summary is None:
                raise RuntimeError(
                    f"Server exited with code {process.returncode} before a test summary."
                )
            break

        time.sleep(0.25)
    else:
        raise TimeoutError("Timed out waiting for runtime test results.")

finally:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    reader.join(timeout=2)

if summary is None:
    raise SystemExit("No runtime test summary was detected.")

passed, total = summary
if total == 0 or passed != total or no_tests or install_failed:
    raise SystemExit(1)
