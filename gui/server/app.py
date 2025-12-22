from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import devices, system, agent, control, tasks, recordings

app = FastAPI(title="Open-AutoGLM GUI", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    """Clean up any leftover scrcpy connections on startup."""
    try:
        from phone_agent.adb.scrcpy_capture import cleanup_all_scrcpy
        cleanup_all_scrcpy()
    except Exception as e:
        print(f"[App] Error cleaning up scrcpy on startup: {e}", flush=True)

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up scrcpy connections on shutdown."""
    try:
        from phone_agent.adb.scrcpy_capture import cleanup_all_scrcpy
        cleanup_all_scrcpy()
    except Exception as e:
        print(f"[App] Error cleaning up scrcpy on shutdown: {e}", flush=True)

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow ALL origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(devices.router, prefix="/api/devices", tags=["Devices"])
app.include_router(agent.router, prefix="/api/agent", tags=["Agent"])
app.include_router(control.router, prefix="/api/control", tags=["Control"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(recordings.router, prefix="/api/recordings", tags=["Recordings"])

@app.get("/")
async def root():
    print("Root endpoint hit!")
    return {"message": "Open-AutoGLM GUI Backend is running"}
