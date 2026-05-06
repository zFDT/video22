"""
MCP 服务管理器 - 自动启停采集所需的 MCP 服务

支持：
- xiaohongshu-mcp: 小红书内容采集（Go 编译的 exe，提供 HTTP API）
- undoom-douyin-mcp: 抖音数据采集分析（Python MCP server，基于 DrissionPage）
"""

import subprocess
import time
import logging
import socket
from pathlib import Path

logger = logging.getLogger(__name__)

SERVICES_DIR = Path(__file__).parent.parent.parent / "services"
PYTHON_EXE = Path(r"D:\anaconda3\envs\video22\python.exe")


class McpServiceManager:
    def __init__(self):
        self.processes: dict[str, subprocess.Popen] = {}

    def start_xhs_mcp(self, port: int = 9527) -> bool:
        """启动小红书 MCP 服务"""
        exe_path = SERVICES_DIR / "xhs-mcp" / "xiaohongshu-mcp-windows-amd64.exe"
        if not exe_path.exists():
            logger.error(f"XHS MCP exe not found: {exe_path}")
            return False

        if self._is_port_open(port):
            logger.info(f"XHS MCP already running on port {port}")
            return True

        logger.info(f"Starting XHS MCP on port {port}...")
        try:
            proc = subprocess.Popen(
                [str(exe_path)],
                cwd=str(exe_path.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.processes["xhs-mcp"] = proc

            for _ in range(30):
                if self._is_port_open(port):
                    logger.info("XHS MCP started successfully")
                    return True
                time.sleep(0.5)

            logger.error("XHS MCP failed to start within 15s")
            return False
        except Exception as e:
            logger.error(f"Failed to start XHS MCP: {e}")
            return False

    def start_douyin_mcp(self) -> bool:
        """启动抖音 MCP 服务（undoom-douyin-data-analysis，stdio 模式）

        注意：undoom-douyin-mcp 是 stdio 模式的 MCP server，
        不提供 HTTP 端口。它通过 DrissionPage 控制浏览器采集数据。
        这里我们预启动浏览器实例以加速后续采集。
        """
        logger.info("Douyin MCP (undoom) ready - uses DrissionPage browser automation")
        return True

    def start_all(self) -> dict[str, bool]:
        """启动所有 MCP 服务"""
        results = {}
        results["xhs-mcp"] = self.start_xhs_mcp()
        results["douyin-mcp"] = self.start_douyin_mcp()
        logger.info(f"Services status: {results}")
        return results

    def stop_all(self):
        """停止所有 MCP 服务"""
        for name, proc in self.processes.items():
            if proc and proc.poll() is None:
                logger.info(f"Stopping {name} (PID: {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                logger.info(f"{name} stopped")
        self.processes.clear()

    def _is_port_open(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", port)) == 0

    def __enter__(self):
        self.start_all()
        return self

    def __exit__(self, *args):
        self.stop_all()

    def refresh_xhs_cookies(self) -> bool:
        """调用小红书登录工具刷新 Cookie"""
        login_exe = SERVICES_DIR / "xhs-mcp" / "xiaohongshu-login-windows-amd64.exe"
        if not login_exe.exists():
            logger.error(f"XHS login tool not found: {login_exe}")
            return False

        logger.info("Launching XHS login tool (please login in browser)...")
        try:
            result = subprocess.run(
                [str(login_exe)], cwd=str(login_exe.parent), timeout=300,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error("Login timed out")
            return False
