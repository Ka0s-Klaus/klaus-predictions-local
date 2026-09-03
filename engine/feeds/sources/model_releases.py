"""Model Releases — newly released AI models across all providers."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class ModelReleases(FeedSource):
    """Monitorea lanzamientos de nuevos modelos de IA."""

    name: ClassVar[str] = "Model-Releases"
    domain: ClassVar[str] = "technology"
    event_type: ClassVar[str] = "model_release"
    # Usar modelos recientemente modificados en Hugging Face
    endpoint: ClassVar[str] = "https://huggingface.co/api/models?sort=modified&limit=50"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Parsea lanzamientos recientes de modelos."""
        events = []

        # La API devuelve un array o un objeto con modelos
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

            # Información del modelo
            updated_at = model.get("updated_at")
            created_at = model.get("created_at")
            timestamp = updated_at or created_at

            # Preferir modelos recientemente creados (verdaderos lanzamientos)
            # pero también incluir los modificados
            is_new = False
            if created_at and updated_at:
                # Si fue creado en los últimos 7 días, es probable que sea un lanzamiento
                from datetime import UTC, datetime, timedelta

                try:
                    created = parse_timestamp(created_at)
                    now = datetime.now(UTC)
                    if created and (now - created) < timedelta(days=7):
                        is_new = True
                except Exception:
                    pass

            # Descargas y likes
            downloads = model.get("downloads", 0)
            if not isinstance(downloads, (int, float)):
                downloads = 0

            likes = model.get("likes", 0)
            if not isinstance(likes, (int, float)):
                likes = 0

            # Descripción
            tags = model.get("tags", [])
            if isinstance(tags, list):
                tags_str = ", ".join(tags[:3])
            else:
                tags_str = ""

            description = model.get("description", "").strip()
            if not description:
                description = f"Tags: {tags_str}" if tags_str else "New AI model release"

            # URL del modelo
            url = f"https://huggingface.co/{model_id}"

            # Salience basada en descargas y recencia
            # 0.65 base + bonus si es nuevo
            salience = clamp(0.65 + min(downloads / 1000000.0 * 0.25, 0.25))
            if is_new:
                salience = clamp(salience + 0.1)

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=model_id,
                    description=description,
                    url=url,
                    magnitude=float(downloads),
                    salience=salience,
                    event_time=parse_timestamp(timestamp),
                    external_id=f"{model_id}_{updated_at or created_at}",
                    raw={
                        "model_id": model_id,
                        "downloads": int(downloads),
                        "likes": int(likes),
                        "is_new": is_new,
                        "tags": tags[:5] if isinstance(tags, list) else [],
                    },
                )
            )

        return events
