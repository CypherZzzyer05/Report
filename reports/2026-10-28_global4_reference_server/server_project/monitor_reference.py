"""Read this single reference job's manifest and native log without taking locks."""
import argparse
from collections import deque
from datetime import datetime
import json
from pathlib import Path
import time


def show_status(root):
    """Print one file-based snapshot and return the manifest state, if present."""
    root = Path(root)
    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] 参考任务：{root}")
    manifest_path = root / "data/manifest.json"
    state = None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("未发现 manifest 状态记录；无法据此判断求解器是否运行。")
    except json.JSONDecodeError:
        print("manifest 暂不可读，可能正在更新；本次未取得状态。")
    else:
        samples = manifest.get("samples", [])
        if samples:
            state = samples[0].get("state")
            print(f"清单状态：{state or '未记录'}（来自 data/manifest.json）")
        else:
            print("manifest 已存在，但未发现单样本状态记录。")

    logs = list((root / "data/projects").glob("*.log"))
    try:
        latest = max(logs, key=lambda path: path.stat().st_mtime) if logs else None
        if latest is None:
            print("未发现原生日志；仅检查本任务的 data/projects 目录。")
        else:
            age = time.time() - latest.stat().st_mtime
            print(f"最新原生日志：{latest.name}；日志年龄：{age:.0f} 秒")
            with latest.open("r", encoding="utf-8", errors="replace") as stream:
                lines = deque(stream, maxlen=8)
            if lines:
                for line in lines:
                    print(line.rstrip())
            else:
                print("日志文件尚无内容。")
    except FileNotFoundError:
        print("原生日志本次读取时已不存在；未取得日志内容。")
    print("以上为文件记录，不认证 Python worker 或原生求解器进程存活。", flush=True)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="只显示一次状态")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                        help="参考项目目录，默认使用本脚本所在目录")
    args = parser.parse_args(argv)
    try:
        while True:
            state = show_status(args.root.resolve())
            if state in ("success", "failed"):
                print(f"manifest 记录终态 {state}，监视结束；该状态不认证进程存活。")
                return
            if args.once:
                return
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n监视已退出；未向计算进程发送停止命令。")


if __name__ == "__main__":
    main()
