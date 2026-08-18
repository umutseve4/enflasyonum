"""FastAPI uygulama giriş noktası.

M1.1 kapsamı: yalnızca /health. Sonraki adımlar ROADMAP.md'de.
"""

from fastapi import FastAPI

from enflasyonum import __version__

app = FastAPI(
    title="Enflasyonumdan ne haber?",
    description="Kişisel enflasyon endeksi — kendi sepetinle TÜİK'i kıyasla.",
    version=__version__,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Canlılık kontrolü — deploy ve CI smoke testinin dayanak noktası."""
    return {"status": "ok", "version": __version__}
