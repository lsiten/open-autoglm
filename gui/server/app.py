from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import devices, system, agent, control, tasks

app = FastAPI(title="Open-AutoGLM GUI", version="1.0.0")

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

@app.get("/")
async def root():
    print("Root endpoint hit!")
    return {"message": "Open-AutoGLM GUI Backend is running"}
