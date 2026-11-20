"""Weather-code labels and icons shared by forecast and current conditions."""

SNOW_CODES = frozenset({71, 73, 75, 77, 85, 86})

WEATHER_CODES = [
    (frozenset({0}), "Clear", "clear"),
    (frozenset({1}), "Mostly clear", "clear"),
    (frozenset({2}), "Partly cloudy", "partly"),
    (frozenset({3}), "Overcast", "cloud"),
    (frozenset({45, 48}), "Fog", "fog"),
    (frozenset({51, 53, 55, 56, 57}), "Drizzle", "rain"),
    (frozenset({61, 63, 65, 66, 67}), "Rain", "rain"),
    (frozenset({80, 81, 82}), "Showers", "rain"),
    (SNOW_CODES, "Snow", "snow"),
    (frozenset({95, 96, 99}), "Thunderstorm", "storm"),
]

CONDITION_ICONS = {
    "clear": "☼",
    "night": "◐",
    "partly": "🌤",
    "cloud": "☁",
    "rain": "🌧",
    "snow": "❄",
    "storm": "🌩",
    "fog": "🌫",
}

ART = {
    "clear": [
        r"             ",
        r"    \___/    ",
        r"  __/   \__  ",
        r"    \___/    ",
        r"    /   \    ",
    ],
    "night": [
        r"             ",
        r"    ,-,-.    ",
        r"   /.( +.\   ",
        r"   \ {. */   ",
        r"    `-`-'    ",
    ],
    "partly": [
        r"   \___/     ",
        r' __/ .--.    ',
        r"  .-(    ).  ",
        r" (___.__)__) ",
        r"             ",
    ],
    "cloud": [
        r"             ",
        r"     .--.    ",
        r"  .-(    ).  ",
        r" (___.__)__) ",
        r"             ",
    ],
    "rain": [
        r"     .--.    ",
        r"  .-(    ).  ",
        r" (___.__)__) ",
        r"    ' ' ' '  ",
        r"   ' ' ' '   ",
    ],
    "snow": [
        r"     .--.    ",
        r"  .-(    ).  ",
        r" (___.__)__) ",
        r"   *  *  *   ",
        r"  *  *  *    ",
    ],
    "storm": [
        r"     .--.    ",
        r"  .-(    ).  ",
        r" (___.__)__) ",
        r"    /_  /_   ",
        r"     /   /   ",
    ],
    "fog": [
        r"             ",
        r" _ - _ - _ - ",
        r"  _ - _ - _  ",
        r" _ - _ - _ - ",
        r"             ",
    ],
}

BAR_LEVELS = "▁▂▃▄▅▆▇█"


def describe(code: int) -> tuple[str, str]:
    for codes, label, art in WEATHER_CODES:
        if code in codes:
            return label, art
    return "Unknown", "cloud"
