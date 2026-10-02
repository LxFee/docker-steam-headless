#!/usr/bin/env bash

# Source from start-desktop.sh as the desktop user, after X and D-Bus are ready.
configure_input_method() {
    [[ "${ENABLE_FCITX5:-false}" == "true" ]] || return 0
    command -v fcitx5 >/dev/null 2>&1 || return 0

    # Respect explicit selections of another input method (including empty values).
    if [[ "${GTK_IM_MODULE-fcitx}" != "fcitx" ||
          "${QT_IM_MODULE-fcitx}" != "fcitx" ||
          "${XMODIFIERS-@im=fcitx}" != "@im=fcitx" ]]; then
        echo "**** Keeping user-selected input method; skipping Fcitx5 ****"
        return 0
    fi
    export GTK_IM_MODULE=fcitx
    export QT_IM_MODULE=fcitx
    export XMODIFIERS=@im=fcitx

    # Keep this outside the rsync home template. Existing settings and symlinks,
    # including dangling symlinks, must never be overwritten on container updates.
    local config_dir="${XDG_CONFIG_HOME:?}/fcitx5"
    local profile="${config_dir}/profile"
    if [[ ! -e "${config_dir}" && ! -L "${config_dir}" ]]; then
        if mkdir -p "${config_dir}"; then
            ( set -o noclobber; cat > "${profile}" <<'EOF'
[Groups/0]
Name=Default
Default Layout=us
DefaultIM=pinyin

[Groups/0/Items/0]
Name=keyboard-us
Layout=

[Groups/0/Items/1]
Name=pinyin
Layout=

[GroupOrder]
0=Default
EOF
            ) || echo "WARNING: Could not create default Fcitx5 profile"
        else
            echo "WARNING: Could not create Fcitx5 configuration directory"
        fi
    fi

    # Use the same DISPLAY, session bus and runtime directory as Xfce.
    # Do not replace an instance already started by the user.
    if ! pgrep -u "$(id -u)" -x fcitx5 >/dev/null; then
        fcitx5 -d || echo "WARNING: Could not start Fcitx5; see desktop logs"
    fi
}

configure_input_method
