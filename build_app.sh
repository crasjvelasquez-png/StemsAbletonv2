#!/usr/bin/env bash
set -euo pipefail

# Stable signing identity: macOS ties permissions (Accessibility etc.) to the
# app's signature. A fresh ad-hoc signature each build makes it forget them.
# A fixed local certificate keeps the signature the same across rebuilds.
IDENTITY="Stems Local Signing"

ensure_identity() {
    if security find-identity -p codesigning | grep -q "$IDENTITY"; then
        return
    fi
    echo "Creating local signing certificate '$IDENTITY' (one time)..."
    local tmp; tmp="$(mktemp -d)"
    cat > "$tmp/openssl.cnf" <<CNF
[req]
distinguished_name=dn
x509_extensions=ext
prompt=no
[dn]
CN=$IDENTITY
[ext]
basicConstraints=critical,CA:false
keyUsage=critical,digitalSignature
extendedKeyUsage=critical,codeSigning
CNF
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout "$tmp/key.pem" -out "$tmp/cert.pem" -config "$tmp/openssl.cnf" 2>/dev/null
    openssl pkcs12 -export -inkey "$tmp/key.pem" -in "$tmp/cert.pem" \
        -certpbe PBE-SHA1-3DES -keypbe PBE-SHA1-3DES -macalg sha1 \
        -out "$tmp/id.p12" -passout pass:stems 2>/dev/null
    security import "$tmp/id.p12" -k "$HOME/Library/Keychains/login.keychain-db" \
        -P stems -T /usr/bin/codesign >/dev/null
    rm -rf "$tmp"
}

python3 -m PyInstaller --noconfirm --clean "Stems.spec"

ensure_identity
if codesign --force --deep --sign "$IDENTITY" "dist/Stems.app" 2>/dev/null; then
    codesign --verify --deep "dist/Stems.app"
else
    # Stable signing failed: the old permission entry would be stale. Clear it
    # so macOS asks fresh instead of showing a dead checkbox.
    echo "Stable signing failed; using temporary signature and clearing old permissions."
    codesign --force --deep --sign - "dist/Stems.app"
    for service in Accessibility AppleEvents; do
        tccutil reset "$service" com.c4milo.stems >/dev/null 2>&1 || true
    done
fi

printf '\nBuilt app bundle: %s\n' "$(pwd)/dist/Stems.app"
