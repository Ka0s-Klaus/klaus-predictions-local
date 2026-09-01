#!/usr/bin/env python3
"""Benchmark de latencia extremo a extremo de predicciones.

Uso:
  python scripts/benchmark_latency.py
  python scripts/benchmark_latency.py --output results.json --runs 3

Necesita la API en localhost:8088. Requiere Ollama con mistral:7b-instruct-q4_K_M
levantado, pero captura tanto latencia de LLM como fallidos con graceful degradation.
"""

import json
import sys
import time
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Error: requiere httpx. Instala: pip install httpx")
    sys.exit(1)

QUERIES = [
    {"query": "Current global anomalies?", "horizon": "24h"},
    {"query": "Earthquake activity in Asia", "horizon": "7d"},
    {"query": "Geopolitical tensions emerging", "horizon": "30d"},
    {"query": "Financial market volatility", "horizon": "24h"},
    {"query": "Climate and weather events", "horizon": "7d"},
]

AGENTS = [
    "Strategist",
    "Economist",
    "Skeptic",
    "Naturalist",
    "Tech Analyst",
    "Climate Expert",
    "Geopolitical Analyst",
]


def predict(client: httpx.Client, query: str, horizon: str) -> dict:
    """Una predicción, midiendo el tiempo total."""
    start = time.perf_counter()
    try:
        resp = client.post(
            "http://localhost:8088/predict",
            json={"query": query, "horizon": horizon},
            timeout=600.0,  # 10 minutos, porque 7B es lento
        )
        resp.raise_for_status()
        elapsed = time.perf_counter() - start
        body = resp.json()
        return {
            "query": query,
            "horizon": horizon,
            "elapsed_seconds": round(elapsed, 2),
            "status": "ok",
            "confidence": body.get("confidence"),
            "prediction": body.get("prediction"),
            "agents_voted": len(body.get("agent_votes", {})),
        }
    except httpx.HTTPStatusError as e:
        elapsed = time.perf_counter() - start
        return {
            "query": query,
            "horizon": horizon,
            "elapsed_seconds": round(elapsed, 2),
            "status": f"error_{e.response.status_code}",
            "detail": e.response.text[:200],
        }
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {
            "query": query,
            "horizon": horizon,
            "elapsed_seconds": round(elapsed, 2),
            "status": "error",
            "detail": str(e)[:200],
        }


def main():
    parser = ArgumentParser(
        description="Benchmark de latencia del API de Pythia"
    )
    parser.add_argument(
        "--output",
        default="benchmark_results.json",
        help="Fichero JSON donde guardar resultados (default: benchmark_results.json)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Cuántas veces repetir cada query (default: 1)",
    )
    parser.add_argument(
        "--api",
        default="localhost:8088",
        help="Dirección del API (default: localhost:8088)",
    )
    args = parser.parse_args()

    print(f"Benchmark de latencia de {args.api}")
    print(f"Queries: {len(QUERIES)}, repeticiones: {args.runs}")
    print(f"Total: {len(QUERIES) * args.runs} predicciones")
    print()

    results = {
        "timestamp": datetime.now().isoformat(),
        "api": args.api,
        "queries": len(QUERIES),
        "runs_per_query": args.runs,
        "predictions": [],
        "summary": {},
    }

    with httpx.Client() as client:
        for run in range(args.runs):
            for q in QUERIES:
                print(f"  Run {run + 1}/{args.runs}: {q['query'][:40]}...", end=" ", flush=True)
                result = predict(client, q["query"], q["horizon"])
                results["predictions"].append(result)
                status_icon = "✓" if result["status"] == "ok" else "✗"
                print(f"{status_icon} {result['elapsed_seconds']}s")

    # Estadísticas
    ok_results = [r for r in results["predictions"] if r["status"] == "ok"]
    if ok_results:
        times = [r["elapsed_seconds"] for r in ok_results]
        times.sort()
        results["summary"] = {
            "successful": len(ok_results),
            "failed": len(results["predictions"]) - len(ok_results),
            "min_seconds": times[0],
            "max_seconds": times[-1],
            "avg_seconds": round(sum(times) / len(times), 2),
            "median_seconds": times[len(times) // 2],
            "p95_seconds": times[int(len(times) * 0.95)] if len(times) > 1 else times[0],
        }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(results, indent=2))

    print()
    print("=" * 60)
    if ok_results:
        s = results["summary"]
        print(f"Exitosas: {s['successful']}/{len(results['predictions'])}")
        min_s, avg_s = s["min_seconds"], s["avg_seconds"]
        max_s, p95_s = s["max_seconds"], s["p95_seconds"]
        print(f"Latencia: min={min_s}s, avg={avg_s}s, max={max_s}s, p95={p95_s}s")
    else:
        print("Ninguna predicción completó. Primeros errores:")
        for r in results["predictions"][:3]:
            query_short = r["query"][:30]
            status = r["status"]
            detail = r.get("detail", "")
            print(f"  {query_short}... → {status}: {detail}")
    print(f"Guardados en: {output_path}")


if __name__ == "__main__":
    main()
