"""Papers with Code — research papers with implementations."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class PapersWithCode(FeedSource):
    """Monitorea papers recientes con código en Papers with Code."""

    name: ClassVar[str] = "PapersWithCode"
    domain: ClassVar[str] = "research"
    event_type: ClassVar[str] = "paper_with_implementation"
    endpoint: ClassVar[str] = "https://paperswithcode.com/api/papers/?ordering=-published&limit=20"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Parsea papers de la API de Papers with Code."""
        events = []

        # La API devuelve {'results': [...], 'count': N, 'next': '...'}
        if isinstance(payload, dict):
            results = payload.get("results", [])
        elif isinstance(payload, list):
            results = payload
        else:
            return []

        for paper in results:
            if not isinstance(paper, dict):
                continue

            paper_url = paper.get("url", "").strip()
            if not paper_url:
                continue

            title = paper.get("title", "").strip()
            if not title:
                continue

            # Información adicional
            abstract = paper.get("abstract", "").strip() or ""
            published = paper.get("published", "")

            # Contar repositorios asociados (proxy de calidad)
            github_urls = paper.get("github_urls", [])
            if not isinstance(github_urls, list):
                github_urls = []

            repo_count = len(github_urls)

            # Salience basada en número de implementaciones
            # 0.75 base + un poco de bonus por repositorios
            salience = clamp(0.75 + min(repo_count / 10.0 * 0.15, 0.15))

            # Descripción
            description = abstract[:500] if abstract else f"With {repo_count} implementation(s)"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=description,
                    url=paper_url,
                    magnitude=float(repo_count),
                    salience=salience,
                    event_time=parse_timestamp(published),
                    external_id=paper_url,
                    raw={
                        "url": paper_url,
                        "repo_count": repo_count,
                        "published": published,
                    },
                )
            )

        return events
