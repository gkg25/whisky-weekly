from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from src.mailer import send_email


def _get_required_creds() -> Optional[tuple[str, str, str]]:
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("RECIPIENT_EMAIL")
    if not (sender and password and recipient):
        print("[notifier] GMAIL_ADDRESS / GMAIL_APP_PASSWORD / RECIPIENT_EMAIL のいずれかが未設定。通知できません。", file=sys.stderr)
        return None
    return sender, password, recipient


def _gh_context() -> dict:
    return {
        "repo": os.environ.get("GITHUB_REPOSITORY", "(local)"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "(local)"),
        "workflow": os.environ.get("GITHUB_WORKFLOW", "Whisky Weekly"),
        "server": os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
        "sha": os.environ.get("GITHUB_SHA", "")[:7],
        "ref": os.environ.get("GITHUB_REF_NAME", ""),
    }


def _tail_log(log_path: Optional[Path], n: int = 60) -> str:
    if not log_path or not log_path.exists():
        return ""
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()[-n:]
        return "\n--- ログ末尾（最後の{0}行）---\n{1}\n".format(n, "\n".join(lines))
    except Exception as e:
        return f"\n(ログ読み取り失敗: {e})\n"


def notify_failure(log_path: Optional[Path] = None) -> int:
    creds = _get_required_creds()
    if not creds:
        return 1
    sender, password, recipient = creds
    ctx = _gh_context()
    run_url = (
        f"{ctx['server']}/{ctx['repo']}/actions/runs/{ctx['run_id']}"
        if ctx["run_id"] != "(local)"
        else "(local run, no URL)"
    )

    body = (
        "Whisky Weekly のワークフローが失敗しました。\n\n"
        f"  ワークフロー: {ctx['workflow']}\n"
        f"  リポジトリ:   {ctx['repo']}\n"
        f"  Run ID:      {ctx['run_id']}\n"
        f"  Run URL:     {run_url}\n"
        f"  ブランチ:     {ctx['ref']} ({ctx['sha']})\n\n"
        "対応:\n"
        "  1. 上記 Run URL を開き、失敗ステップのログを確認\n"
        "  2. 必要なら画面右上「Re-run jobs」で再実行\n"
        f"  3. Secrets確認: {ctx['server']}/{ctx['repo']}/settings/secrets/actions\n"
        f"{_tail_log(log_path)}"
        "\n(このメールは GitHub Actions の `if: failure()` ステップから自動送信)\n"
    )

    send_email(
        sender=sender,
        password=password,
        recipients=recipient,
        subject=f"[Whisky Weekly] ❌ ワークフロー失敗 - Run #{ctx['run_id']}",
        body_text=body,
    )
    print("[notifier] failure notification sent", file=sys.stderr)
    return 0


def notify_heartbeat_missing(days: int) -> int:
    creds = _get_required_creds()
    if not creds:
        return 1
    sender, password, recipient = creds
    ctx = _gh_context()
    actions_url = f"{ctx['server']}/{ctx['repo']}/actions"

    body = (
        "Whisky Weekly の死活監視からの警告です。\n\n"
        f"直近 {days} 日間、weekly ワークフローの **成功実行が1件もありません**。\n"
        "通常は毎週月曜 朝7時(JST) に配信される newsletter が、止まっている可能性があります。\n\n"
        "確認手順:\n"
        f"  1. {actions_url} を開く\n"
        "  2. 「Whisky Weekly」ワークフローの Runs 一覧をチェック\n"
        "  3. 失敗していれば原因を特定、無ければ手動で 'Run workflow' から実行\n\n"
        "考えられる原因:\n"
        "  - GitHub Actions の scheduled workflow がスキップされた（高負荷時の仕様）\n"
        "  - リポジトリが60日間活動停止 → schedule 自動無効化\n"
        "  - workflow ファイルがデフォルトブランチに無い\n"
        "  - Secrets（GEMINI_API_KEY / GMAIL_APP_PASSWORD 等）の失効・タイポ\n\n"
        "(このメールは check.yml ワークフローから毎週火曜朝に自動チェック・送信)\n"
    )

    send_email(
        sender=sender,
        password=password,
        recipients=recipient,
        subject="[Whisky Weekly] ⚠ 配信が止まっている可能性",
        body_text=body,
    )
    print("[notifier] heartbeat alert sent", file=sys.stderr)
    return 0


def main():
    parser = argparse.ArgumentParser(description="ワークフロー失敗 / 死活監視 通知")
    parser.add_argument("--mode", choices=["failure", "heartbeat"], required=True)
    parser.add_argument("--log", default=None, help="failure モードで添付するログファイル")
    parser.add_argument("--days", type=int, default=8, help="heartbeat モードで '直近何日に成功なし' か")
    args = parser.parse_args()

    load_dotenv()

    if args.mode == "failure":
        return notify_failure(Path(args.log) if args.log else None)
    return notify_heartbeat_missing(args.days)


if __name__ == "__main__":
    sys.exit(main() or 0)
