import uvicorn

from src.config import get_config

if __name__ == "__main__":
    config = get_config()
    uvicorn.run(
        "src.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        reload_dirs=["src"] if config.reload else None,
    )
