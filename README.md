# modernDash

A modular terminal dashboard (rich + textual).

## Install
    python install.py                # sets up the `modernDash` command (+ asks about startup)
    python install.py --startup      # ...and run at login
    python install.py --no-venv      # use the current Python instead of a private .venv

## Commands
    modernDash run                    start the dashboard (any key quits)
    modernDash layout                 mouse layout editor (also: modernDash config layout)
    modernDash config <tool> <value>  e.g. config name Atlas / config list / config --help
    modernDash modules                list modules and their sizes
    modernDash startup enable [login|shell] | disable | status
    modernDash uninstall [--purge]

## Layout
    main.py         generic host: reads the config, loads modules/, draws them
    modules/*.py    one file per panel (see modules/_template.py)
    dashlib/        shared library (config, weather service, fonts, grid drawing)
    startup.json    your settings; `layout` lists each module's row/col/rows/cols
    dbfonts/        put your font JSON files here (e.g. Georgia11.json)

Layout editor: drag to move, drag the corner mark to resize, right-click cycles
sizes, ctrl+s saves. A running dashboard reloads the saved layout by itself.
