"""Terminate a private command process group, including orphan descendants."""
import os
import signal
import time
import psutil


def stop_group(group,grace=.25):
    try:os.killpg(group,signal.SIGTERM)
    except ProcessLookupError:return
    time.sleep(grace)
    # The leader can be gone while a grandchild remains in the private group.
    try:os.killpg(group,signal.SIGKILL)
    except ProcessLookupError:return
    deadline=time.monotonic()+1
    while True:
        running=[]
        for p in psutil.process_iter(['pid','status']):
            try:
                if p.info['status']!=psutil.STATUS_ZOMBIE and os.getpgid(p.pid)==group:running.append(p.pid)
            except (ProcessLookupError,PermissionError,psutil.NoSuchProcess):continue
        if not running:return
        if time.monotonic()>=deadline:raise RuntimeError('Process group still running after SIGKILL: '+str(running))
        time.sleep(.02)
