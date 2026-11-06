---
tags: [proyecto/klaus-predictions-local, tipo/guia, prediccion/fuentes]
---

# 📚 Guía de Estilo de Documentación

Este documento define el estándar de formato para toda la documentación del proyecto **Klaus-predictions-local** a partir de septiembre 2026.

## 🎯 Estructura de README.md

### Portada
```markdown
# 🔮 Nombre del Proyecto

> **Tagline en negrita.** Contexto adicional.

[![Badge1](url)](url) [![Badge2](url)](url)

---
```

### Sección: "¿Qué hago? ¿Cómo lo hago? ¿Y para qué lo hago?"
```markdown
## 🤔 ¿Qué hago? ¿Cómo lo hago? ¿Y para qué lo hago?

**¿Qué hago:** [Descripción del proyecto]
**¿Cómo lo hago:** [Técnica/Arquitectura]
**¿Para qué lo hago:** [Problema que resuelve]

---
```

### Arquitectura con Flowchart
```markdown
## 🏗️ Arquitectura

\`\`\`mermaid
graph TD
    INPUT["📡 Input"] --> PROCESS["🔄 Proceso"]
    PROCESS --> OUTPUT["📊 Output"]
\`\`\`

**Stack:**
- Componente 1: tech
- Componente 2: tech

---
```

### Instalación rápida
```markdown
## 🚀 Instalación rápida

### Requisitos
- Python 3.11+
- [Requisito especial]

### Pasos

\`\`\`bash
git clone <repo>
cd project
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
\`\`\`

---
```

### Uso
```markdown
## 🎯 Uso

### Modo API

| Endpoint | Descripción |
|---|---|
| GET /health | Estado |
| POST /predict | Predicción |

### Línea de comandos

\`\`\`bash
python -m engine.cli predict --query "pregunta"
\`\`\`

### Dashboard

\`\`\`bash
cd ui && npm install && npm run dev
\`\`\`

---
```

### Configuración
```markdown
## ⚙️ Configuración

| Variable | Defecto | Descripción |
|---|---|---|
| `LLM_MODEL` | `mistral:7b` | Modelo |
| `API_PORT` | `8000` | Puerto |

---
```

### Documentación
```markdown
## 📚 Documentación

| Doc | Contenido |
|---|---|
| [🏗️ Arquitectura](docs/ARCH.md) | Diseño técnico |
| [🛠️ Configuración](docs/CONFIG.md) | Env vars |
| [💻 Hardware](docs/HW.md) | Rendimiento |

---
```

### Contribuir
```markdown
## 🤝 Contribuir

1. Fork
2. Rama: `git checkout -b GH-{N}-desc`
3. Commit: `git commit -m "GH-{N}: desc"`
4. Push y PR

---

## 📄 Licencia

[MIT](LICENSE) — Libre para uso comercial.
```

## 🎨 Emojis estándar

| Sección | Emoji |
|---|---|
| Título | 🔮 (específico proyecto) |
| ¿Qué? | 🤔 |
| Arquitectura | 🏗️ |
| Instalación | 🚀 |
| Uso | 🎯 |
| Configuración | ⚙️ |
| Documentación | 📚 |
| Tests | 🧪 |
| Contribuir | 🤝 |
| Licencia | 📄 |

## ✅ Checklist de calidad

- [ ] Portada: `# 🎯 Nombre` + tagline + badges
- [ ] Sección "¿Qué? ¿Cómo? ¿Para qué?"
- [ ] Separadores `---` entre secciones
- [ ] Arquitectura con Flowchart Mermaid
- [ ] Instalación con requisitos y pasos
- [ ] Uso con ejemplos (API + CLI + UI)
- [ ] Configuración en tabla
- [ ] Documentación: tabla con links
- [ ] Contribuir: pasos claros
- [ ] Licencia MIT con enlace
- [ ] Emojis contextuales y consistentes
- [ ] Párrafos cortos (máx 4 líneas)
- [ ] Código en ```bash``` con comentarios

## 📝 Ver README.md como referencia aplicada.
