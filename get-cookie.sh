#!/usr/bin/env bash
set -euo pipefail

TARGET_HOST="${TARGET_HOST:-www.apple.com}"
URL="${URL:-https://www.apple.com/}"
SLEEP_BEFORE_COPY="${SLEEP_BEFORE_COPY:-2}"

# 1) Bases posibles (paquetes nativos / Flatpak / Snap)
CANDIDATES=(
  "$HOME/.mozilla/firefox"
  "$HOME/.var/app/org.mozilla.firefox/.mozilla/firefox"
  "$HOME/snap/firefox/common/.mozilla/firefox"
)

# 2) Si el usuario fuerza el perfil por ruta completa, úsalo
if [[ -n "${PROFILE_DIR:-}" ]]; then
  FF_BASE="$(dirname "$PROFILE_DIR")"
  DB_SRC="$PROFILE_DIR/cookies.sqlite"
else
  FF_BASE=""
  PROFILES_INI=""
  for b in "${CANDIDATES[@]}"; do
    if [[ -f "$b/profiles.ini" ]]; then
      FF_BASE="$b"; PROFILES_INI="$b/profiles.ini"; break
    fi
  done
  if [[ -z "$FF_BASE" ]]; then
    echo "No encontré profiles.ini en instalaciones conocidas de Firefox." >&2
    exit 1
  fi

  # 3) Parsear profiles.ini: priorizar [Profile*] con Default=1
  #    Si no hay, buscar Name=default-release; si tampoco, tomar el más reciente que exista.
  readarray -t SECTION_LINES < <(awk '
    BEGIN{sec=""}
    /^\[Profile/ {sec=$0; next}
    /^Path=|^Default=|^IsRelative=|^Name=/ {print sec"|"$0}
  ' "$PROFILES_INI")

  best_path=""
  best_isrel=""
  default_path=""
  default_isrel=""
  release_path=""
  release_isrel=""
  declare -A secPath secIsRel secName secDefault

  current=""
  while IFS= read -r line; do
    :
  done <<< ""

  # Cargar mapas
  for l in "${SECTION_LINES[@]}"; do
    sec="${l%%|*}"; kv="${l#*|}"
    k="${kv%%=*}"; v="${kv#*=}"
    case "$k" in
      Path) secPath["$sec"]="$v" ;;
      IsRelative) secIsRel["$sec"]="$v" ;;
      Name) secName["$sec"]="$v" ;;
      Default) secDefault["$sec"]="$v" ;;
    esac
  done

  # Buscar Default=1
  for s in "${!secPath[@]}"; do
    if [[ "${secDefault[$s]:-0}" == "1" ]]; then
      default_path="${secPath[$s]}"; default_isrel="${secIsRel[$s]:-1}"
      break
    fi
  done

  # Si no hay Default=1, probar Name=default-release
  if [[ -z "${default_path}" ]]; then
    for s in "${!secPath[@]}"; do
      if [[ "${secName[$s]:-}" == "default-release" ]]; then
        release_path="${secPath[$s]}"; release_isrel="${secIsRel[$s]:-1}"
        break
      fi
    done
  fi

  # Resolver ruta final
  if [[ -n "${default_path}" ]]; then
    if [[ "${default_isrel}" == "1" ]]; then PROFILE_DIR="$FF_BASE/$default_path"; else PROFILE_DIR="$default_path"; fi
  elif [[ -n "${release_path}" ]]; then
    if [[ "${release_isrel}" == "1" ]]; then PROFILE_DIR="$FF_BASE/$release_path"; else PROFILE_DIR="$release_path"; fi
  else
    # Último recurso: elegir el directorio de perfil más recientemente modificado
    PROFILE_DIR="$(ls -1dt "$FF_BASE"/*.* | head -n1)"
  fi

  DB_SRC="$PROFILE_DIR/cookies.sqlite"
fi

if [[ ! -f "$DB_SRC" ]]; then
  echo "No existe cookies.sqlite en: $DB_SRC" >&2
  echo "Perfil detectado: $PROFILE_DIR" >&2
  echo
  echo "Perfíles disponibles (por si querés forzar uno):"
  ls -1d "$FF_BASE"/*.* 2>/dev/null || true
  echo
  echo "Podés reintentar forzando: PROFILE_DIR='/ruta/al/perfil' bash get-cookie.sh"
  exit 1
fi

# (Opcional) abrir URL en el perfil real:
# /usr/bin/firefox -P "$(basename "$PROFILE_DIR")" "$URL" >/dev/null 2>&1 &

# Copiar DB para evitar lock
TMPDIR="$(mktemp -d /tmp/apple-cookies.XXXXXX)"
trap 'rm -rf "$TMPDIR"' EXIT
sleep "$SLEEP_BEFORE_COPY" || true
cp -f "$DB_SRC" "$TMPDIR/cookies.sqlite" || true
[[ -f "$PROFILE_DIR/cookies.sqlite-wal" ]] && cp -f "$PROFILE_DIR/cookies.sqlite-wal" "$TMPDIR/"
[[ -f "$PROFILE_DIR/cookies.sqlite-shm" ]] && cp -f "$PROFILE_DIR/cookies.sqlite-shm" "$TMPDIR/"
DB="$TMPDIR/cookies.sqlite"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "Falta sqlite3 (instalalo con tu gestor de paquetes)" >&2
  exit 2
fi

# Consultas
READABLE_QUERY="
SELECT name, value, host, path, expiry, isSecure, isHttpOnly
FROM moz_cookies
WHERE host LIKE '%apple.com%';"

HEADER_QUERY="
SELECT name, value
FROM moz_cookies
WHERE (host = '$TARGET_HOST' OR host = 'apple.com' OR host LIKE '%.apple.com')
  AND (expiry = 0 OR expiry IS NULL OR expiry > strftime('%s','now'));"

echo "=== Perfil: $PROFILE_DIR ==="
echo "=== Cookies apple.com (legible) ==="
sqlite3 -readonly "$DB" -separator $'\t' "$READABLE_QUERY" | awk -F'\t' '
function epoch_to_date(e) {
  if (e ~ /^[0-9]+$/ && e > 0) { cmd="date -d @" e " +\"%Y-%m-%d %H:%M:%S %Z\""; cmd|getline d; close(cmd); return d }
  return "session"
}
{
  printf("%s=%s\n  Domain: %s\n  Path: %s\n  Expires: %s\n  Secure: %s  HttpOnly: %s\n\n",
         $1,$2,$3,$4,epoch_to_date($5),($6==1?"yes":"no"),($7==1?"yes":"no"))
}'

COOKIE_HEADER=$(sqlite3 -readonly "$DB" -separator $'\t' "$HEADER_QUERY" \
  | awk -F'\t' '{ printf("%s=%s; ", $1,$2) } END { print "" }')

echo "=== Cookie: header para https://$TARGET_HOST/ ==="
if [[ -n "$COOKIE_HEADER" ]]; then
  echo "Cookie: $COOKIE_HEADER"
else
  echo "(no se encontraron cookies aplicables)"
fi
