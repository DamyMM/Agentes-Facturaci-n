#!/usr/bin/env bash
# Baja y sube la carpeta de datos compartidos entre las tareas programadas.
# Es un worktree de la rama `cola` del repo (un archivo JSON por pedido; en prueba, también el Odoo simulado).
#
#   eval "$(scripts/cola.sh bajar)"     # deja exportado HG_DATOS_DIR
#   scripts/cola.sh subir "Transporte: HG-20261124-0007 borrador_creado"
#
# Variables: HG_DATOS_DIR (por defecto ../hg-cola), HG_COLA_RAMA (por defecto cola).
set -euo pipefail
RAMA="${HG_COLA_RAMA:-cola}"
DIR="${HG_DATOS_DIR:-$(cd "$(git rev-parse --show-toplevel)/.." && pwd)/hg-cola}"

case "${1:-}" in
  bajar)
    if [ -d "$DIR/.git" ] || [ -f "$DIR/.git" ]; then
      git -C "$DIR" pull --rebase --quiet origin "$RAMA" >&2 || true
    elif git fetch --quiet origin "$RAMA" 2>/dev/null; then
      git worktree add --quiet -B "$RAMA" "$DIR" "origin/$RAMA" >&2
    else
      # Primera vez: rama huérfana, sin el código.
      git worktree add --quiet --detach "$DIR" >&2
      git -C "$DIR" checkout --quiet --orphan "$RAMA"
      git -C "$DIR" rm -rfq . >/dev/null
      printf '# Cola de pedidos de facturación\n\nDatos que se pasan las tareas programadas. No editar a mano.\n' > "$DIR/README.md"
      printf 'bitacora/\n' > "$DIR/.gitignore"
      git -C "$DIR" add -A && git -C "$DIR" commit --quiet -m "Inicio de la cola de pedidos"
    fi
    echo "export HG_DATOS_DIR='$DIR'"
    ;;
  subir)
    MSG="${2:?Indicá el mensaje del commit}"
    cd "$DIR"
    git add -A
    git diff --cached --quiet && { echo "Nada para subir." >&2; exit 0; }
    git commit --quiet -m "$MSG"
    for espera in 2 4 8 16; do
      git push --quiet -u origin "$RAMA" 2>/dev/null && exit 0
      sleep "$espera"
      git pull --rebase --quiet origin "$RAMA" || { git rebase --abort 2>/dev/null; echo "Conflicto al integrar la cola." >&2; exit 1; }
    done
    echo "No se pudo subir la cola después de 4 intentos." >&2
    exit 1
    ;;
  *)
    echo "Uso: scripts/cola.sh bajar | subir \"mensaje\"" >&2
    exit 2
    ;;
esac
