import sys
from fastapi import FastAPI
import uvicorn

port = int(sys.argv[1])
app = FastAPI()

@app.get("/")
@app.post("/")
def root():
    return {"service": f"mock backend on port {port}", "status": "ok"}

@app.get("/{path:path}")
@app.post("/{path:path}")
def catch_all(path: str):
    return {"service": f"mock backend on port {port}", "path": f"/{path}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)