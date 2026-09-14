"""
Shared gas station registry.

Single source of truth for the station-name -> Tankerkönig UUID mapping, used
by extract.py and record_prices.py. Previously duplicated (and, in one copy,
corrupted) across multiple scripts.
"""

STATIONS = {
    "Tanke_Lud": "916d61b6-7279-4d63-a754-ae160f8cdee2",
    "Tanke_Steinf": "291fafe3-dbfb-4452-8c68-aa6a7540ce98",
    "Wentorf_Hem": "e1a15081-2543-9107-e040-0b0a3dfe563c",
    "MrWash": "21d8e11f-5712-4d00-81aa-100887b65699",
    "EDEKA_Wentorf": "2f432c0c-9052-466d-9030-c78ab8c4149d",
    "München": "fb79c457-543a-4ff6-ba70-cd270ac2110a",
    "Orlen_Wentorf": "005056ba-7cb6-1ed2-bceb-bbb7e74e0d4e",
}
