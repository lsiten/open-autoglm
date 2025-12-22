import uvicorn
import os
import sys
import subprocess
import argparse
import shutil
import platform

def check_and_install_scrcpy():
    """Check if scrcpy is installed, and try to install it if not available."""
    # Check if scrcpy is already available
    if shutil.which("scrcpy"):
        try:
            result = subprocess.run(
                ["scrcpy", "--version"],
                capture_output=True,
                timeout=2
            )
            if result.returncode == 0:
                version = result.stdout.decode('utf-8', errors='ignore').strip().split('\n')[0]
                print(f"[Scrcpy] ✓ scrcpy 已安装: {version}")
                return True
        except Exception:
            pass
    
    # scrcpy not found, try to install
    print("[Scrcpy] ⚠ 未找到 scrcpy 工具，正在尝试自动安装...")
    
    system = platform.system().lower()
    install_success = False
    
    if system == "darwin":  # macOS
        if shutil.which("brew"):
            print("[Scrcpy] 使用 Homebrew 安装 scrcpy...")
            try:
                # Check if already installed via brew
                result = subprocess.run(
                    ["brew", "list", "scrcpy"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    print("[Scrcpy] ✓ scrcpy 已通过 Homebrew 安装")
                    install_success = True
                else:
                    # Try to install
                    print("[Scrcpy] 正在安装 scrcpy（这可能需要几分钟）...")
                    result = subprocess.run(
                        ["brew", "install", "scrcpy"],
                        capture_output=False,  # Show progress
                        timeout=600  # 10 minutes timeout
                    )
                    if result.returncode == 0:
                        # Verify installation
                        if shutil.which("scrcpy"):
                            install_success = True
                            print("[Scrcpy] ✓ scrcpy 安装成功")
                        else:
                            # Try to add brew prefix to PATH
                            brew_prefix_result = subprocess.run(
                                ["brew", "--prefix"],
                                capture_output=True,
                                timeout=5
                            )
                            if brew_prefix_result.returncode == 0:
                                brew_prefix = brew_prefix_result.stdout.decode('utf-8').strip()
                                brew_bin = os.path.join(brew_prefix, "bin")
                                if os.path.exists(os.path.join(brew_bin, "scrcpy")):
                                    os.environ["PATH"] = f"{brew_bin}:{os.environ.get('PATH', '')}"
                                    if shutil.which("scrcpy"):
                                        install_success = True
                                        print("[Scrcpy] ✓ scrcpy 安装成功")
            except subprocess.TimeoutExpired:
                print("[Scrcpy] ⚠ 安装超时，请手动安装: brew install scrcpy")
            except Exception as e:
                print(f"[Scrcpy] ⚠ 安装失败: {e}")
                print("[Scrcpy] 请手动安装: brew install scrcpy")
        else:
            print("[Scrcpy] ⚠ 未找到 Homebrew，请手动安装 scrcpy:")
            print("[Scrcpy]   brew install scrcpy")
            print("[Scrcpy]   或访问: https://github.com/Genymobile/scrcpy/releases")
    
    elif system == "linux":
        # Try different package managers
        if shutil.which("apt-get"):
            print("[Scrcpy] 使用 apt 安装 scrcpy...")
            try:
                result = subprocess.run(
                    ["sudo", "apt-get", "update", "-qq"],
                    capture_output=True,
                    timeout=60
                )
                result = subprocess.run(
                    ["sudo", "apt-get", "install", "-y", "scrcpy"],
                    capture_output=True,
                    timeout=300
                )
                if result.returncode == 0 and shutil.which("scrcpy"):
                    install_success = True
                    print("[Scrcpy] ✓ scrcpy 安装成功")
            except Exception as e:
                print(f"[Scrcpy] ⚠ 安装失败: {e}")
                print("[Scrcpy] 请手动安装: sudo apt-get install scrcpy")
        elif shutil.which("dnf"):
            print("[Scrcpy] 使用 dnf 安装 scrcpy...")
            try:
                result = subprocess.run(
                    ["sudo", "dnf", "install", "-y", "scrcpy"],
                    capture_output=True,
                    timeout=300
                )
                if result.returncode == 0 and shutil.which("scrcpy"):
                    install_success = True
                    print("[Scrcpy] ✓ scrcpy 安装成功")
            except Exception as e:
                print(f"[Scrcpy] ⚠ 安装失败: {e}")
                print("[Scrcpy] 请手动安装: sudo dnf install scrcpy")
        elif shutil.which("yum"):
            print("[Scrcpy] 使用 yum 安装 scrcpy...")
            try:
                result = subprocess.run(
                    ["sudo", "yum", "install", "-y", "scrcpy"],
                    capture_output=True,
                    timeout=300
                )
                if result.returncode == 0 and shutil.which("scrcpy"):
                    install_success = True
                    print("[Scrcpy] ✓ scrcpy 安装成功")
            except Exception as e:
                print(f"[Scrcpy] ⚠ 安装失败: {e}")
                print("[Scrcpy] 请手动安装: sudo yum install scrcpy")
        else:
            print("[Scrcpy] ⚠ 未找到支持的包管理器，请手动安装 scrcpy")
            print("[Scrcpy]   访问: https://github.com/Genymobile/scrcpy/releases")
    else:
        print(f"[Scrcpy] ⚠ 不支持的操作系统: {system}")
        print("[Scrcpy] 请手动安装 scrcpy:")
        print("[Scrcpy]   访问: https://github.com/Genymobile/scrcpy/releases")
    
    if not install_success:
        print("[Scrcpy] ⚠ scrcpy 安装失败或需要手动安装（可选，不影响启动）")
        print("[Scrcpy]   系统将使用 ADB 截图方法（性能略低）")
        print("[Scrcpy]   如需使用 scrcpy 提升性能，请手动安装")
    else:
        # Verify one more time
        if shutil.which("scrcpy"):
            try:
                result = subprocess.run(
                    ["scrcpy", "--version"],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    version = result.stdout.decode('utf-8', errors='ignore').strip().split('\n')[0]
                    print(f"[Scrcpy] ✓ scrcpy 工具已就绪: {version}")
                    return True
            except Exception:
                pass
    
    return False

def run_backend(reload=False, use_https=False):
    # Use uvicorn's default logging - don't modify it to avoid breaking subprocess logging
    # For filtering stream/latest logs, we'll use a simpler approach: just accept the logs
    # or use uvicorn's access_log parameter if needed
    if use_https:
        print("Starting Backend on https://0.0.0.0:8000...")
        uvicorn.run(
            "gui.server.app:app", 
            host="0.0.0.0", 
            port=8000, 
            reload=reload,
            ssl_keyfile="certs/key.pem",
            ssl_certfile="certs/cert.pem"
        )
    else:
        print("Starting Backend on http://127.0.0.1:8000...")
        uvicorn.run(
            "gui.server.app:app", 
            host="127.0.0.1", 
            port=8000, 
            reload=reload
        )

def run_frontend(use_https=False):
    print("Starting Frontend...")
    web_dir = os.path.join(os.getcwd(), "gui", "web")
    cmd = ["npm", "run", "dev", "--", "--host"]
    env = os.environ.copy()
    if use_https:
        # Pass a custom mode or env var if needed, 
        # but usually we configure vite via vite.config.ts.
        # However, passing an env var is cleaner.
        env["VITE_HTTPS"] = "true"
        print("Frontend will start with HTTPS enabled")
    else:
        env.pop("VITE_HTTPS", None)
        
    subprocess.Popen(cmd, cwd=web_dir, env=env)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-only", action="store_true", help="Run only backend")
    parser.add_argument("--dev", action="store_true", help="Run with reload")
    parser.add_argument("--https", action="store_true", help="Run with HTTPS")
    parser.add_argument("--skip-scrcpy-check", action="store_true", help="Skip scrcpy installation check")
    args = parser.parse_args()

    # Check and install scrcpy if needed (before starting services)
    if not args.skip_scrcpy_check:
        check_and_install_scrcpy()

    if not args.backend_only:
        run_frontend(use_https=args.https)
    
    # Backend must run in main thread for reload to work
    run_backend(reload=args.dev, use_https=args.https)
