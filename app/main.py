from fastapi import FastAPI
from api.endpoints import router as api_router

main_app = FastAPI(title="Deduplication Service")

main_app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:main_app", host="0.0.0.0", port=8000, reload=True)
