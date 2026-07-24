from fastapi import FastAPI

from roster import router as roster_router
from routes import router
from upload import router as upload_router


app = FastAPI()
app.include_router(router)
app.include_router(upload_router)
app.include_router(roster_router)


@app.get("/")
def read_root():
    return {"message": "Hello from med-roster!"}
