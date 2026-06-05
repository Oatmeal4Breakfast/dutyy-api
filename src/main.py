from fastapi import FastAPI

app = FastAPI(title="dutyy-api")


@app.get("/")
async def root():
    return {"message": "hello world"}
