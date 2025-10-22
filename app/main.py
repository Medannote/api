from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import images, signaux, text, batch

app = FastAPI(
    title="API Médicale Unifiée",
    description="API regroupant images, signaux, textes médicaux et traitement par lots",
    version="1.1.0"
)

# Configuration CORS pour permettre les requêtes depuis Django
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, remplacer par l'URL spécifique de Django
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(images, prefix="/images", tags=["Images"])
app.include_router(signaux, prefix="/signaux", tags=["Signaux"])
app.include_router(text, prefix="/text", tags=["Text"])
app.include_router(batch, prefix="/batch", tags=["Batch Processing"])