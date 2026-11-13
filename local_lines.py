"""Slower regional trains along five of the HSR corridors: the stops of the regional-express
tier that runs beside (or partly on) each high-speed line and feeds it. Used by make_local.py.

Lists are in route order (lon, lat, WGS84). European coordinates come from the Trainline EU
stations dataset (github.com/trainline-eu/stations, ODbL); stations shared with the HSR line
reuse stations.py. Amtrak Cascades stations were entered by hand (within a few hundred metres).

The chains combine several services where no single train runs end to end:
  cascadia  Amtrak Cascades, Vancouver BC – Eugene (Surrey/Richmond bus stops left out)
  de        RE Berlin – Lutherstadt Wittenberg; RE/S-Bahn Wittenberg – Bitterfeld – Leipzig;
            RE Leipzig – Naumburg – Weimar – Erfurt; Franken-Thüringen-Express Erfurt – Coburg
            – Bamberg – Nürnberg; München-Nürnberg-Express Nürnberg – Ingolstadt – München
  es        Cercanías/Media Distancia Madrid – Guadalajara – Sigüenza – Arcos de Jalón;
            Media Distancia Arcos – Calatayud – Zaragoza – Monzón – Lleida;
            Rodalies R14/R15 Lleida – Reus – Tarragona; R14/R15 and R2 Sud Tarragona – Barcelona
  it        Regionale Veloce Torino – Novara – Milano; Milano – Piacenza – Parma – Bologna;
            Bologna – Prato – Firenze; Firenze – Arezzo – Chiusi – Orvieto – Roma ("linea lenta");
            Roma – Latina – Formia – Napoli
  fr        TER Paris – Sens – Dijon; TER Dijon – Chalon – Mâcon – Lyon;
            TER Lyon – Valence – Avignon – Marseille (Rhône valley line)
"""
from stations import CORRIDORS

_HSR = {s[0]: (s[1], s[2]) for c in CORRIDORS for s in c["stations"]}


def _hsr(name, label=None):
    lon, lat = _HSR[name]
    return (label or name, lon, lat)


LOCAL = {
    "cascadia": dict(name="Amtrak Cascades", stations=[
        _hsr("Vancouver BC"),
        _hsr("Bellingham"),
        ("Mount Vernon",      -122.3343, 48.4196),
        ("Stanwood",          -122.3497, 48.2416),
        _hsr("Everett"),
        ("Edmonds",           -122.3842, 47.8111),
        _hsr("Seattle"),
        ("Tukwila",           -122.2405, 47.4610),
        ("Tacoma Dome",       -122.4273, 47.2412),
        _hsr("Olympia/Lacey"),
        ("Centralia",         -122.9534, 46.7173),
        ("Kelso-Longview",    -122.9132, 46.1428),
        ("Vancouver WA",      -122.6862, 45.6290),
        _hsr("Portland"),
        ("Oregon City",       -122.6062, 45.3549),
        _hsr("Salem"),
        ("Albany",            -123.1035, 44.6301),
        _hsr("Eugene"),
    ]),
    "de": dict(name="RE", stations=[
        _hsr("Berlin Hbf"),
        _hsr("Berlin Südkreuz"),
        ("Ludwigsfelde",          13.2673, 52.2981),
        ("Trebbin",               13.2304, 52.2179),
        ("Luckenwalde",           13.1604, 52.0906),
        ("Jüterbog",              13.0544, 51.9975),
        ("Lutherstadt Wittenberg", 12.6620, 51.8675),
        ("Bitterfeld",            12.3167, 51.6231),
        ("Delitzsch",             12.3457, 51.5245),
        _hsr("Leipzig Hbf"),
        ("Weißenfels",            11.9708, 51.2048),
        ("Naumburg",              11.7970, 51.1631),
        ("Bad Kösen",             11.7181, 51.1304),
        ("Apolda",                11.5261, 51.0309),
        ("Weimar",                11.3265, 50.9915),
        _hsr("Erfurt Hbf"),
        ("Coburg",                10.9574, 50.2631),
        ("Lichtenfels",           11.0597, 50.1467),
        _hsr("Bamberg"),
        ("Forchheim",             11.0699, 49.7171),
        _hsr("Erlangen"),
        ("Fürth",                 10.9900, 49.4697),
        _hsr("Nürnberg Hbf"),
        ("Allersberg",            11.2126, 49.2621),
        ("Kinding",               11.3775, 48.9927),
        ("Ingolstadt Nord",       11.4329, 48.7731),
        _hsr("Ingolstadt Hbf"),
        ("Rohrbach (Ilm)",        11.5732, 48.6059),
        ("Pfaffenhofen (Ilm)",    11.5119, 48.5224),
        ("Petershausen",          11.4703, 48.4135),
        _hsr("München Hbf"),
    ]),
    "es": dict(name="Media Distancia / Rodalies", stations=[
        ("Madrid Chamartín",      -3.6824, 40.4722),
        ("Alcalá de Henares",     -3.3662, 40.4891),
        ("Guadalajara",           -3.1602, 40.6324),
        ("Jadraque",              -2.9361, 40.9303),
        ("Sigüenza",              -2.6464, 41.0713),
        ("Arcos de Jalón",        -2.2777, 41.2160),
        ("Ariza",                 -2.0597, 41.3095),
        ("Ateca",                 -1.7856, 41.3246),
        ("Calatayud",             -1.6385, 41.3463),
        ("Épila",                 -1.3013, 41.6090),
        _hsr("Zaragoza Delicias"),
        ("Tardienta",             -0.5381, 41.9758),
        ("Sariñena",              -0.1724, 41.8170),
        ("Monzón-Río Cinca",       0.1970, 41.9139),
        ("Binéfar",                0.2913, 41.8496),
        _hsr("Lleida Pirineus"),
        ("Les Borges Blanques",    0.8780, 41.5215),
        ("L'Espluga de Francolí",  1.1034, 41.4006),
        ("Montblanc",              1.1654, 41.3766),
        ("Reus",                   1.1002, 41.1606),
        ("Tarragona",              1.2434, 41.1189),
        ("Sant Vicenç de Calders", 1.5242, 41.1861),
        ("Vilanova i la Geltrú",   1.7312, 41.2201),
        ("Sitges",                 1.8096, 41.2392),
        _hsr("Barcelona Sants"),
    ]),
    "it": dict(name="Regionale Veloce", stations=[
        _hsr("Torino Porta Nuova"),
        ("Chivasso",               7.8897, 45.1935),
        ("Santhià",                8.1802, 45.3637),
        ("Vercelli",               8.4165, 45.3301),
        ("Novara",                 8.6251, 45.4513),
        ("Magenta",                8.8807, 45.4682),
        _hsr("Milano Centrale"),
        ("Lodi",                   9.4975, 45.3091),
        ("Codogno",                9.7015, 45.1549),
        ("Piacenza",               9.7064, 45.0521),
        ("Fidenza",               10.0634, 44.8678),
        ("Parma",                 10.3286, 44.8102),
        ("Reggio Emilia",         10.6430, 44.6977),
        ("Modena",                10.9299, 44.6546),
        _hsr("Bologna Centrale"),
        ("Vernio",                11.1524, 44.0436),
        ("Prato",                 11.1093, 43.8791),
        _hsr("Firenze S.M.N."),
        ("Figline Valdarno",      11.4736, 43.6218),
        ("Montevarchi",           11.5642, 43.5254),
        ("Arezzo",                11.8754, 43.4611),
        ("Castiglion Fiorentino", 11.9145, 43.3410),
        ("Camucia-Cortona",       11.9709, 43.2617),
        ("Terontola",             12.0079, 43.2104),
        ("Chiusi",                11.9579, 43.0025),
        ("Orvieto",               12.1268, 42.7239),
        ("Orte",                  12.4091, 42.4376),
        _hsr("Roma Termini"),
        ("Latina",                12.9463, 41.5382),
        ("Fondi",                 13.4249, 41.3376),
        ("Formia",                13.6062, 41.2588),
        ("Minturno",              13.7209, 41.2576),
        _hsr("Napoli Centrale"),
    ]),
    "fr": dict(name="TER", stations=[
        _hsr("Paris Gare de Lyon"),
        ("Melun",                  2.6554, 48.5277),
        ("Montereau",              2.9430, 48.3799),
        ("Sens",                   3.2678, 48.1979),
        ("Laroche-Migennes",       3.5132, 47.9610),
        ("Tonnerre",               3.9736, 47.8594),
        ("Montbard",               4.3362, 47.6187),
        ("Dijon",                  5.0272, 47.3234),
        ("Beaune",                 4.8484, 47.0231),
        ("Chalon-sur-Saône",       4.8435, 46.7816),
        ("Tournus",                4.9066, 46.5667),
        ("Mâcon",                  4.8249, 46.3026),
        ("Villefranche-sur-Saône", 4.7208, 45.9845),
        _hsr("Lyon Part-Dieu"),
        ("Vienne",                 4.8742, 45.5212),
        ("St-Rambert-d'Albon",     4.8108, 45.2978),
        ("Tain-l'Hermitage",       4.8400, 45.0722),
        ("Valence",                4.8933, 44.9280),
        ("Montélimar",             4.7500, 44.5667),
        ("Pierrelatte",            4.7038, 44.3747),
        ("Orange",                 4.8196, 44.1373),
        ("Avignon Centre",         4.8053, 43.9419),
        ("Arles",                  4.6320, 43.6849),
        ("Miramas",                5.0003, 43.5807),
        _hsr("Marseille St-Charles"),
    ]),
}
