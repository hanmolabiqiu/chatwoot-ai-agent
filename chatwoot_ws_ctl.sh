#!/bin/sh
# Chatwoot WebSocket Agent Control Script
# Usage: ./chatwoot_ws_ctl.sh {start|stop|restart|status|logs}

SCRIPT_DIR="/app/working/workspaces/wordpress/skills/wordpress-cli"
PIDFILE="/var/run/chatwoot_ws_agent.pid"
LOGFILE="/var/log/chatwoot_ws_agent.log"
COMMAND="python3 $SCRIPT_DIR/chatwoot_ws_agent.py"

# Helper: check if PID is actually our agent (avoids PID reuse race)
_pid_is_ours() {
    pid="$1"
    [ -z "$pid" ] && return 1
    # Check PID exists AND its cmdline matches
    if kill -0 "$pid" 2>/dev/null; then
        cmdline=$(cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' ')
        case "$cmdline" in
            *chatwoot_ws_agent.py*) return 0 ;;
        esac
    fi
    return 1
}

case "$1" in
  start)
    if [ -f "$PIDFILE" ] && _pid_is_ours $(cat "$PIDFILE"); then
      echo "Agent already running (PID $(cat $PIDFILE))"
      exit 1
    fi
    cd "$SCRIPT_DIR"
    python3 -c "
import subprocess, os
p = subprocess.Popen(['python3', '$SCRIPT_DIR/chatwoot_ws_agent.py'],
    stdout=open('$LOGFILE','a'), stderr=subprocess.STDOUT,
    cwd='$SCRIPT_DIR', preexec_fn=os.setsid)
print(p.pid)
" > "$PIDFILE"
    echo "Agent started (PID $(cat $PIDFILE))"
    ;;
  stop)
    if [ -f "$PIDFILE" ]; then
      PID=$(cat "$PIDFILE")      
      if _pid_is_ours "$PID"; then
        kill "$PID" 2>/dev/null
        sleep 2
        kill -9 "$PID" 2>/dev/null
      fi
      rm -f "$PIDFILE"
      echo "Agent stopped"
    else
      echo "No PID file found"
      pkill -f "chatwoot_ws_agent.py" 2>/dev/null && echo "Killed all chatwoot_ws_agent processes" || echo "No processes found"
    fi
    ;;
  restart)
    $0 stop
    sleep 1
    $0 start
    ;;
  status)
    if [ -f "$PIDFILE" ] && _pid_is_ours $(cat "$PIDFILE"); then
      echo "Agent running (PID $(cat $PIDFILE))"
    else
      if pgrep -f "chatwoot_ws_agent.py" >/dev/null 2>&1; then
        echo "Agent running (no PID file)"
        pgrep -f "chatwoot_ws_agent.py"
      else
        echo "Agent not running"
      fi
    fi
    ;;
  logs)
    tail -30 "$LOGFILE"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
