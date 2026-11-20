# Dashboard

A full-screen terminal weather dashboard built with [Rich](https://github.com/Textualize/rich). It displays:

- The current weather, forecast, temperature, and rain probability
- An animated ASCII aquarium
- A configurable greeting and block font
- The current time and weather update status
- A clock and 7-day forecast

Weather data is provided by [Open-Meteo](https://open-meteo.com/) and does not require an API key.

## Requirements

- Python 3.10 or newer
- Rich

Install Rich:

```powershell
python -m pip install rich
```

## Run the dashboard

From the project directory:

```powershell
python startup.py
```

Press any key to exit full-screen mode.

## Configuration

Configuration is stored in `startup.json`. It is created automatically when you use a configuration command. Unlisted settings fall back to the defaults in `startup.py`.

View the effective configuration:

```powershell
python startup.py config list
```

View or change one setting:

```powershell
python startup.py config get appearance.font_file
python startup.py config font BlurVision9.json
python startup.py config padding 5
python startup.py config welcome_summary true
```

Open the mouse-driven layout editor:

```powershell
python startup.py config layout
```

Click the `[-]` and `[+]` controls to adjust a module's relative row or column
size, then choose **Save** (or press `S`). Press `Q` or choose **Cancel** to
discard changes. Layout sizes are stored under `layout.modules` in
`startup.json`.

Each dashboard panel is implemented in its own file under [`modules/`](./modules).
The module owns its rendering and any panel-specific state; `startup.py` handles
configuration, weather updates, and composing the modules into the dashboard.
Modules receive the shared frame data through `modules/context.py`.

You can use friendly setting names or dotted keys:

```powershell
python startup.py config name "Alex"
python startup.py config location "Seattle, WA"
python startup.py config latitude 47.6062
python startup.py config longitude -122.3321
python startup.py config auto_location false
python startup.py config frame_seconds 0.5
python startup.py config refresh_seconds 120
python startup.py config retry_seconds 60
python startup.py config wave "~"
```

Show all available configuration commands:

```powershell
python startup.py config help
```

Remove `startup.json` and restore all default settings:

```powershell
python startup.py config reset
```

## Appearance settings

| Friendly name | Dotted key | Example |
|---|---|---|
| `font` / `font_file` | `appearance.font_file` | `BlurVision9.json` |
| `font_gap` | `appearance.custom_font_gap` | `1` |
| `padding` | `appearance.padding` | `3` |
| `frame_seconds` | `appearance.frame_seconds` | `0.25` |
| `welcome_summary` | `appearance.show_welcome_summary` | `true` |

Dashboard module sizes are relative weights, bounded from 1 to 12:

| Module | Layout key |
|---|---|
| Location and status | `layout.modules.status_bar` |
| Clock | `layout.modules.clock` |
| Welcome banner | `layout.modules.welcome` |
| Aquarium | `layout.modules.aquarium` |
| 7-day forecast | `layout.modules.forecast` |
| Current conditions | `layout.modules.current` |
| Update footer | `layout.modules.footer` |

Each module has `row` and `column` weights. Column weights resize neighboring
dashboard regions; row weights resize vertically stacked modules.

List installed font JSON files:

```powershell
python startup.py config fonts
```

Set the built-in font instead of a custom font:

```powershell
python startup.py config font default
```

## Location and weather settings

| Friendly name | Dotted key | Example |
|---|---|---|
| `location` | `location.name` | `New York City, NY` |
| `latitude` | `location.latitude` | `40.7128` |
| `longitude` | `location.longitude` | `-74.0060` |
| `auto_location` | `location.auto_from_ip` | `true` |
| `refresh_seconds` | `weather.refresh_seconds` | `120` |
| `retry_seconds` | `weather.retry_seconds` | `60` |
| `rain_min_chance` | `weather.rain_min_chance` | `30` |
| `rain_min_amount` | `weather.rain_min_amount` | `0.01` |
| `rain_full` | `weather.rain_full` | `0.25` |

Location detection uses the public `ip-api.com` service. Set `auto_location` to `false` to use the configured latitude and longitude instead.

## Aquarium settings

Change the character used for the aquarium wave:

```powershell
python startup.py config wave "~"
```

## Create a custom font

Create a blank text file using this structure:

```text
[FONT NAME]
[LETTER HEIGHT]
A...
...
Z
a...
...
z
,
.
!
?
-
```

The first line is the font name, and the second line is the height of each glyph in rows. Include a glyph for every letter and supported punctuation character listed above.

Convert the source file to JSON:

```powershell
python fonttojson.py "C:\path\to\MyFont.txt"
```

The converter creates a JSON file in the current directory using the format `<font name><height>.json`, for example `MyFont11.json`.

Move or copy the generated JSON file into `dbfonts/`, then select it:

```powershell
python startup.py config font MyFont11.json
python startup.py config font_gap 0
```

The dashboard looks for custom fonts in the project directory, in `dbfonts/`, and relative to the project directory. Font names are resolved case-sensitively by the operating system.

The JSON format contains each supported character as an array of text rows. Existing files in `dbfonts/` can be used as examples:

- `dbfonts/BlurVision9.json`
- `dbfonts/Georgia11.json`
- `dbfonts/SmallASCII10.json`

The [patorjk Text to ASCII Art generator](https://patorjk.com/software/taag/#p=display&f=Isometric1&t=Hello&x=none&v=4&h=4&w=80&we=false) can be used to generate compatible ASCII glyph layouts.

## Configuration file

You can edit `startup.json` directly. For example:

```json
{
  "name": "Alex",
  "location": {
    "name": "Seattle, WA",
    "latitude": 47.6062,
    "longitude": -122.3321,
    "auto_from_ip": false
  },
  "appearance": {
    "padding": 3,
    "frame_seconds": 0.25,
    "show_welcome_summary": true,
    "font_file": "dbfonts/BlurVision9.json",
    "custom_font_gap": 0
  }
}
```

The file is merged with `DEFAULT_CONFIG`, so it does not need to contain every setting.
