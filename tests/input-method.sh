#!/usr/bin/env bash
# No container or display needed: mock the daemon and process lookup.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

run_case() (
    export XDG_CONFIG_HOME="$work/$1/config with spaces"
    export ENABLE_FCITX5=true DISPLAY=:55 DBUS_SESSION_BUS_ADDRESS=unix:path=test
    export XDG_RUNTIME_DIR="$work/runtime"
    unset GTK_IM_MODULE QT_IM_MODULE XMODIFIERS
    mkdir -p "$XDG_CONFIG_HOME"
    launches=0
    fcitx5() {
        [[ "$1" == -d && "$DISPLAY" == :55 && "$DBUS_SESSION_BUS_ADDRESS" == unix:path=test ]]
        [[ "$GTK_IM_MODULE" == fcitx && "$QT_IM_MODULE" == fcitx && "$XMODIFIERS" == @im=fcitx ]]
        launches=$((launches + 1))
    }
    pgrep() { return 1; }
    case "$1" in
        fresh) ;;
        existing)
            mkdir -p "$XDG_CONFIG_HOME/fcitx5"
            printf 'custom profile\n' > "$XDG_CONFIG_HOME/fcitx5/profile"
            cp "$XDG_CONFIG_HOME/fcitx5/profile" "$work/original"
            ;;
        existing-directory) mkdir -p "$XDG_CONFIG_HOME/fcitx5" ;;
        dangling-directory) ln -s "$work/missing-directory" "$XDG_CONFIG_HOME/fcitx5" ;;
        dangling-profile)
            mkdir -p "$XDG_CONFIG_HOME/fcitx5"
            ln -s "$work/missing-profile" "$XDG_CONFIG_HOME/fcitx5/profile"
            ;;
        disabled) export ENABLE_FCITX5=false ;;
        arch-default) unset ENABLE_FCITX5 ;;
        other-im) export GTK_IM_MODULE=ibus ;;
        empty-im) export QT_IM_MODULE='' ;;
        running) pgrep() { return 0; } ;;
        failure) fcitx5() { launches=$((launches + 1)); return 1; } ;;
        missing)
            # Called indirectly by the sourced setup script.
            # shellcheck disable=SC2317
            command() {
                if [[ "$*" == '-v fcitx5' ]]; then return 1; fi
                builtin command "$@"
            }
            ;;
    esac
    source "$repo/overlay/usr/bin/configure-input-method.sh"
    case "$1" in
        fresh)
            grep -q '^DefaultIM=pinyin$' "$XDG_CONFIG_HOME/fcitx5/profile"
            grep -q '^Name=keyboard-us$' "$XDG_CONFIG_HOME/fcitx5/profile"
            cp "$XDG_CONFIG_HOME/fcitx5/profile" "$work/fresh-original"
            configure_input_method
            cmp "$work/fresh-original" "$XDG_CONFIG_HOME/fcitx5/profile"
            [[ "$launches" == 2 ]]
            ;;
        existing) cmp "$work/original" "$XDG_CONFIG_HOME/fcitx5/profile"; [[ "$launches" == 1 ]] ;;
        existing-directory) [[ ! -e "$XDG_CONFIG_HOME/fcitx5/profile" && "$launches" == 1 ]] ;;
        dangling-directory) [[ -L "$XDG_CONFIG_HOME/fcitx5" && ! -e "$work/missing-directory" && "$launches" == 1 ]] ;;
        dangling-profile) [[ -L "$XDG_CONFIG_HOME/fcitx5/profile" && ! -e "$work/missing-profile" && "$launches" == 1 ]] ;;
        disabled|arch-default|other-im|empty-im|missing)
            [[ ! -e "$XDG_CONFIG_HOME/fcitx5" && "$launches" == 0 ]]
            ;;
        running) [[ "$launches" == 0 ]] ;;
        failure) [[ "$launches" == 1 ]] ;;
    esac
    printf 'PASS: %s\n' "$1"
)

for case_name in fresh existing existing-directory dangling-directory dangling-profile disabled arch-default other-im empty-im running failure missing; do
    run_case "$case_name"
done
