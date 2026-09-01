# klaus-predictions-local

> Motor de predicciones que se ejecuta íntegramente en local, sin dependencia de servicios externos.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Ka0s-Klaus/klaus-predictions-local/actions/workflows/ci.yml/badge.svg)](https://github.com/Ka0s-Klaus/klaus-predictions-local/actions/workflows/ci.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

## Estado

🚧 **Fase inicial.** El repositorio está creado y gobernado, pero el stack técnico
(lenguaje, framework, modelos) aún no está definido. Este README se sustituirá en
cuanto se fije el alcance.

## Qué es

`klaus-predictions-local` nace para cubrir la ejecución de predicciones en el propio
equipo del usuario: los datos no salen de la máquina, no hay llamadas a APIs de
terceros y el coste marginal por inferencia es cero.

Objetivos de diseño:

- **Local-first** — todo el ciclo (datos, modelo, inferencia) corre en local.
- **Sin lock-in** — agnóstico del proveedor de modelos.
- **Reproducible** — misma entrada, misma salida, misma versión.
- **Open source** — licencia MIT, contribuciones abiertas.

## Instalación

Pendiente de definir el stack.

```bash
git clone https://github.com/Ka0s-Klaus/klaus-predictions-local.git
cd klaus-predictions-local
```

## Uso

Pendiente.

## Contribuir

Las contribuciones son bienvenidas. Lee [CONTRIBUTING.md](CONTRIBUTING.md) antes de
abrir un PR y respeta el [Código de Conducta](CODE_OF_CONDUCT.md).

- 🐛 [Reportar un bug](https://github.com/Ka0s-Klaus/klaus-predictions-local/issues/new?template=bug_report.yml)
- 💡 [Proponer una funcionalidad](https://github.com/Ka0s-Klaus/klaus-predictions-local/issues/new?template=feature_request.yml)
- 💬 [Discussions](https://github.com/Ka0s-Klaus/klaus-predictions-local/discussions)

## Seguridad

Para reportar vulnerabilidades, consulta [SECURITY.md](SECURITY.md). **No abras un
issue público** para fallos de seguridad.

## Licencia

Distribuido bajo licencia [MIT](LICENSE). © 2026 Ka0s-Klaus.
