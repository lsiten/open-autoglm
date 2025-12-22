import uvicorn
import os
import sys
import subprocess
import argparse

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
    args = parser.parse_args()

    if not args.backend_only:
        run_frontend(use_https=args.https)
    
    # Backend must run in main thread for reload to work
    run_backend(reload=args.dev, use_https=args.https)
