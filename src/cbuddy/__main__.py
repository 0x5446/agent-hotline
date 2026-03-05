"""CBuddy CLI."""

import argparse
import json
import logging
import sys
from pathlib import Path


def cmd_serve(_args):
    import uvicorn
    from .config import Config
    from .server import app, init, start_ws_client

    cfg = Config.load()
    init(cfg)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    start_ws_client(cfg)
    print(f"CBuddy serving on http://localhost:{cfg.port}")
    print(f"  Feishu {cfg.feishu_receive_id_type}: {cfg.feishu_receive_id}")
    print(f"  Hook: POST http://localhost:{cfg.port}/hook")
    uvicorn.run(app, host="127.0.0.1", port=cfg.port, log_level="warning")


def cmd_install_hooks(_args):
    from .config import Config

    cfg = Config.load()
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        print(f"Error: {settings_path} not found")
        sys.exit(1)

    settings = json.loads(settings_path.read_text())
    url = f"http://localhost:{cfg.port}/hook"

    tty = 'TTY=$(tty 2>/dev/null || ps -o tty= -p $PPID 2>/dev/null | tr -d " " | sed "s|^|/dev/|")'
    cwd = "CWD=$(pwd)"

    def hook_cmd(hook_type, extra=""):
        return (
            f'{tty}; {cwd}; '
            f'afplay /System/Library/Sounds/{"Hero" if hook_type == "stop" else "Ping"}.aiff & '
            f'curl -s -X POST {url} '
            f'-H "Content-Type: application/json" '
            f"""-d '{{"type":"{hook_type}","tty":"'"'"'"$TTY"'"'"'","cwd":"'"'"'"$CWD"'"'"'"{extra}}}' """
            f'>/dev/null 2>&1'
        )

    settings["hooks"] = {
        "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": hook_cmd("stop")}]}],
        "Notification": [{"matcher": "", "hooks": [{"type": "command", "command": hook_cmd("notification", ',"matcher":"\'"\'"\'$CLAUDE_NOTIFICATION_TYPE\'"\'"\'"')}]}],
    }

    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    print(f"Hooks installed to {settings_path}")
    print("Restart Claude Code sessions to activate.")


def cmd_test_inject(args):
    from .tty import inject, validate_tty

    error = validate_tty(args.tty)
    if error:
        print(f"Error: {error}")
        sys.exit(1)

    inject(args.tty, args.text, enter=not args.no_enter)
    suffix = " (no enter)" if args.no_enter else " + Enter"
    print(f"Injected '{args.text}'{suffix} -> {args.tty}")


def main():
    parser = argparse.ArgumentParser(prog="cbuddy", description="Drive your terminal Claude Code from Feishu")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("serve", help="Start CBuddy server")
    sub.add_parser("install-hooks", help="Install Claude Code hooks")

    p = sub.add_parser("test-inject", help="Test terminal injection")
    p.add_argument("tty", help="TTY path, e.g. /dev/ttys003")
    p.add_argument("text", help="Text to inject")
    p.add_argument("--no-enter", action="store_true", help="Don't press Enter")

    args = parser.parse_args()
    cmds = {"serve": cmd_serve, "install-hooks": cmd_install_hooks, "test-inject": cmd_test_inject}
    fn = cmds.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
