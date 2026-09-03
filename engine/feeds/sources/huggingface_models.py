"""Hugging Face — trending and newly released ML models."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class HuggingFaceModels(FeedSource):
    """Monitorea lanzamientos y modelos trending en Hugging Face."""

    name: ClassVar[str] = "HuggingFace-Models"
    domain: ClassVar[str] = "technology"
    event_type: ClassVar[str] = "model_release"
    endpoint: ClassVar[str] = "https://huggingface.co/api/models?sort=trending&limit=20"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Parsea modelos trending de la API de Hugging Face."""
        events = []

        # La API devuelve un array directamente o un objeto con modelos
        if isinstance(payload, dict):
            models = payload.get("models", [])
        elif isinstance(payload, list):
            models = payload
        else:
            return []

        for model in models:
            if not isinstance(model, dict):
                continue

            model_id = model.get("id", "").strip()
            if not model_id:
                continue

            # Extrae información del modelo
            downloads = model.get("downloads", 0)
            if not isinstance(downloads, (int, float)):
                downloads = 0

            likes = model.get("likes", 0)
            if not isinstance(likes, (int, float)):
                likes = 0

            updated_at = model.get("updated_at")
            created_at = model.get("created_at")
            timestamp = updated_at or created_at

            # Descripción corta
            tags = model.get("tags", [])
            if isinstance(tags, list):
                tags_str = ", ".join(tags[:3])
            else:
                tags_str = ""

            description = model.get("description", "").strip()
            if not description:
                description = f"Tags: {tags_str}" if tags_str else "New model on Hugging Face"

            # Salience basada en descargas
            # 0.6 base + 0.3 basado en descargas (normalizado a 1M)
            salience = clamp(0.6 + min(downloads / 1000000.0 * 0.3, 0.3))

            # URL del modelo
            url = f"https://huggingface.co/{model_id}"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{model_id}",
                    description=description,
                    url=url,
                    magnitude=float(downloads),
                    salience=salience,
                    event_time=parse_timestamp(timestamp),
                    external_id=model_id,
                    raw={
                        "model_id": model_id,
                        "downloads": int(downloads),
                        "likes": int(likes),
                        "tags": tags[:5] if isinstance(tags, list) else [],
                    },
                )
            )

        return events
