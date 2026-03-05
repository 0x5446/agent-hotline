"""TTY input injection for macOS Terminal.app via AppleScript."""

import os
import stat
import subprocess

# Single-key replies that should NOT have a newline appended
SINGLE_KEYS = {"y", "n", "a", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0"}


def validate_tty(tty_path: str) -> str | None:
    """Check TTY exists and is owned by current user. Returns error message or None."""
    if not os.path.exists(tty_path):
        return f"TTY {tty_path} does not exist (terminal closed?)"
    try:
        st = os.stat(tty_path)
    except OSError as e:
        return f"Cannot stat {tty_path}: {e}"
    if not stat.S_ISCHR(st.st_mode):
        return f"{tty_path} is not a character device"
    if st.st_uid != os.getuid():
        return f"{tty_path} is not owned by current user"
    return None


def _escape_for_applescript(text: str) -> str:
    """Escape text for use in AppleScript string literals."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def inject(tty_path: str, text: str, enter: bool | None = None):
    """Inject text into a terminal by finding the window with the given TTY
    and sending keystrokes via AppleScript.

    Args:
        tty_path: TTY device path, e.g. /dev/ttys004
        text: Text to inject
        enter: Whether to press Return after. None = auto-detect
    """
    error = validate_tty(tty_path)
    if error:
        raise RuntimeError(error)

    if enter is None:
        enter = text.strip().lower() not in SINGLE_KEYS

    escaped_text = _escape_for_applescript(text)
    escaped_tty = _escape_for_applescript(tty_path)

    # AppleScript: find the Terminal.app window/tab with this TTY,
    # bring it to front, select the tab, then send keystrokes.
    enter_line = 'keystroke return' if enter else ''
    script = f'''
tell application "Terminal"
    repeat with w in windows
        repeat with t in tabs of w
            if tty of t is "{escaped_tty}" then
                set frontmost of w to true
                set selected tab of w to t
                delay 0.3
                tell application "System Events"
                    tell process "Terminal"
                        keystroke "{escaped_text}"
                        {enter_line}
                    end tell
                end tell
                return "ok"
            end if
        end repeat
    end repeat
    return "tty_not_found"
end tell
'''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=10,
    )
    output = result.stdout.strip()
    if result.returncode != 0:
        raise RuntimeError(
            f"AppleScript failed: {result.stderr.strip()}"
        )
    if output == "tty_not_found":
        raise RuntimeError(
            f"No Terminal.app tab found with TTY {tty_path}"
        )
