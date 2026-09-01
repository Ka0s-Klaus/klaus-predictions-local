# Guía de contribución

Gracias por dedicar tiempo a este proyecto. Estas son las reglas del juego.

## Antes de empezar

1. Lee el [Código de Conducta](CODE_OF_CONDUCT.md). Participar implica aceptarlo.
2. Busca en [issues](https://github.com/Ka0s-Klaus/klaus-predictions-local/issues) si
   ya existe algo sobre lo que quieres trabajar.
3. Para cambios grandes, abre primero una
   [Discussion](https://github.com/Ka0s-Klaus/klaus-predictions-local/discussions)
   o un issue. Evita escribir 2.000 líneas que luego haya que descartar.

## Flujo de trabajo

```bash
# 1. Fork y clona
gh repo fork Ka0s-Klaus/klaus-predictions-local --clone

# 2. Rama desde main
git switch -c feat/mi-cambio

# 3. Commits siguiendo Conventional Commits
git commit -m "feat: añade soporte para X"

# 4. Push y PR
git push -u origin feat/mi-cambio
gh pr create --fill
```

`main` está protegida: no se puede hacer push directo. Todo entra por Pull Request
con al menos una aprobación y el CI en verde.

## Convención de ramas

| Prefijo     | Uso                                    |
| ----------- | -------------------------------------- |
| `feat/`     | Nueva funcionalidad                    |
| `fix/`      | Corrección de bug                      |
| `docs/`     | Solo documentación                     |
| `refactor/` | Cambio interno sin alterar el contrato |
| `test/`     | Añadir o corregir tests                |
| `chore/`    | Tooling, dependencias, CI              |

## Conventional Commits

El historial y el changelog dependen de esto. Formato:

```
<tipo>(<ámbito opcional>): <descripción en imperativo>
```

Tipos válidos: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`,
`ci`, `chore`, `revert`.

Un cambio incompatible lleva `!` antes de los dos puntos (`feat!: ...`) o un pie
`BREAKING CHANGE:`.

## Pull Requests

- Un PR resuelve **una** cosa. Si estás tocando tres temas, son tres PRs.
- Rellena la plantilla. Enlaza el issue con `Closes #123`.
- Los merges son **squash**: el título del PR se convierte en el mensaje del commit,
  así que escríbelo en formato Conventional Commit.
- Mantén el PR actualizado con `main` si hay conflictos.
- Los borradores (`draft`) son bienvenidos para pedir feedback temprano.

## Revisión

- Revisa el código, no a la persona.
- Quien revisa propone; quien mantiene decide.
- Un PR sin actividad durante 30 días se marca como `stale` y se cierra a los 7 días.

## Reportar bugs

Usa la [plantilla de bug](https://github.com/Ka0s-Klaus/klaus-predictions-local/issues/new?template=bug_report.yml).
Incluye siempre pasos de reproducción, comportamiento esperado y comportamiento real.

Si el fallo es de **seguridad**, no abras un issue: sigue [SECURITY.md](SECURITY.md).

## Licencia

Al contribuir, aceptas que tu aportación se publique bajo la licencia
[MIT](LICENSE) del proyecto.
