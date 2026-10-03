"""Verify-only: run a command, SIGKILL it after the Nth line containing a marker."""
import os, signal, subprocess, sys
n, marker, cmd = int(sys.argv[1]), sys.argv[2], sys.argv[3:]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
seen = 0
for line in p.stdout:
    if "INFO" not in line:
        print(line, end="", flush=True)
    if marker in line:
        seen += 1
        if seen >= n:
            os.killpg(p.pid, signal.SIGKILL)
            print("KILLED", flush=True)
            break
print("rc", p.wait())
