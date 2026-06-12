import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from ppt_agent.state import State


PPT_MASTER_ROOT = Path(__file__).resolve().parents[2] / "ppt_creator"


def _make_project_name(topic: str) -> str:
    """把 PPT 题目转成适合项目目录的英文名。"""
    if not topic:
        return f"ppt_project_{datetime.now():%Y%m%d_%H%M%S}"

    name = topic.lower()

    # 保留英文、数字、下划线；中文会被替换掉。
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")

    if not name:
        name = "ppt_project"

    return f"{name}_{datetime.now():%Y%m%d_%H%M%S}"


def create_p_node(state: State) -> dict:
    """调用 ppt-master 创建项目目录。"""
    ppt_brief = state.get("ppt_brief", {})
    topic = ppt_brief.get("topic", "")

    if not PPT_MASTER_ROOT.exists():
        return {
            "status": "failed",
            "error": f"缺少 ppt_creator 目录：{PPT_MASTER_ROOT}",
        }

    project_name = _make_project_name(topic)

    command = [
        sys.executable,
        "skills/ppt-master/scripts/project_manager.py",
        "init",
        project_name,
        "--format",
        "ppt169",
    ]

    try:
        result = subprocess.run(
            command,
            cwd=PPT_MASTER_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )

        projects_dir = PPT_MASTER_ROOT / "projects"

        matched_projects = sorted(
            projects_dir.glob(f"{project_name}*"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        if not matched_projects:
            return {
                "status": "failed",
                "error": "ppt-master 命令执行成功，但没有找到创建出的项目目录。",
            }

        project_path = str(matched_projects[0])

        return {
            "project_path": project_path,
            "status": "project_created",
            "assistant_reply": f"项目已创建：{project_path}",
        }

    except subprocess.CalledProcessError as exc:
        return {
            "status": "failed",
            "error": exc.stderr or exc.stdout or str(exc),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"项目创建失败：{exc}",
        }
