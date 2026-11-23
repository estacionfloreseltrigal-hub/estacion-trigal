#!/bin/bash
# Estación Trigal: sube las fotos nuevas a Google Drive y libera la microSD.
# - copy: sube solo lo que falte (si no hay internet, falla y se intenta en la próxima hora).
# - move --min-age 30d: las fotos de más de 30 días se suben (si faltaban) y se borran de la Pi.
ORIGEN=/home/trigal/fotos
DESTINO=drive:EstacionTrigal/fotos
OPCIONES=(--exclude "*.tmp" --transfers 2 --retries 3 --low-level-retries 10 --log-level INFO)

rclone copy "$ORIGEN" "$DESTINO" "${OPCIONES[@]}" || exit 1
rclone move "$ORIGEN" "$DESTINO" "${OPCIONES[@]}" --min-age 30d --delete-empty-src-dirs
