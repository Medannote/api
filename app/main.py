from fastapi import FastAPI
from app.routers import images, signaux, text

app = FastAPI(
    title="API Médicale Unifiée",
    description="API regroupant images, signaux et textes médicaux",
    version="1.0.0"
)

app.include_router(images , prefix="/images", tags=["Images"])
app.include_router(signaux, prefix="/signaux", tags=["Signaux"])
app.include_router(text, prefix="/text", tags=["Text"])