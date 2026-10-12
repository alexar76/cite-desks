from __future__ import annotations

"""Translated limits — the geography note and the list of what each desk will not claim.

The English text is the ClaimClass itself (claim.py); this module carries every other locale a
desk supports. A desk or locale missing here falls back to English, which a test forbids for the
locales a desk declares.
"""

LIMITS: dict[str, dict[str, dict[str, object]]] = {'emberline': {'es': {'geography_note': '',
                      'limitations': ['Emberline es una ayuda de monitoreo. No es un servicio de emergencia, '
                                      'ni una autoridad de evacuación, ni una aseguradora.',
                                      'La ausencia de alerta no es una garantía de seguridad. Hay intervalos '
                                      'de revisita satelital, nubosidad y lagunas en los sensores.',
                                      'Las detecciones son anomalías térmicas. Emberline no inventa '
                                      'perímetros de incendio, pronósticos ni puntuaciones de riesgo.',
                                      'El humo HMS, si se solicita, es un polígono cualitativo de '
                                      'Norteamérica — no es PM2.5 medido ni un perímetro de incendio.',
                                      'Con AIMarket ATLAS/GAIA. Emberline no opera satélites.']},
               'fr': {'geography_note': '',
                      'limitations': ['Emberline est une aide de surveillance. Ce n’est ni un service '
                                      'd’urgence, ni une autorité d’évacuation, ni un assureur.',
                                      'L’absence d’alerte n’est pas une garantie de sécurité. Délais de '
                                      'revisite satellite, couverture nuageuse et lacunes de capteurs sont '
                                      'bien réels.',
                                      'Les détections sont des anomalies thermiques. Emberline n’invente ni '
                                      'périmètres de feu, ni prévisions, ni scores de risque.',
                                      'La fumée HMS, si elle est demandée, est un polygone qualitatif sur '
                                      'l’Amérique du Nord — ni du PM2.5 mesuré, ni un périmètre de feu.',
                                      'Propulsé par AIMarket ATLAS/GAIA. Emberline n’opère pas de '
                                      'satellites.']}},
 'plinth': {'de': {'geography_note': 'Eine benannte Gebäude-, Standort- oder Colo-Bbox. Nur Nowcast aus '
                                     'öffentlichen Sensoren — kein Gebäudemanagementsystem, kein '
                                     '50-Jahres-Standortindex.',
                   'limitations': ['Plinth überwacht einen benannten Standort. Es betreibt das Gebäude '
                                   'nicht.',
                                   'Wetter ist ein öffentliches Nowcast, keine Dachstation — außer ein '
                                   'LIVE-Pin liegt in der Bbox.',
                                   'Luft ist ein Messwert aus einem öffentlichen Netz, keine Innenraum-IAQ.',
                                   'Hochwasserwarnungen und Flusspegel bleiben, sofern vorhanden, in zwei '
                                   'Listen — nie ein Standort-Risikoscore.',
                                   'Kein 50-Jahres-Standortindex, kein Brandperimeter, kein Versicherer.',
                                   'Betrieben durch AIMarket ATLAS/GAIA. Plinth betreibt keine Sensoren.']},
            'es': {'geography_note': 'Un bbox de edificio, sede o colo nombrado. Solo nowcast de sensores '
                                     'públicos — no es un sistema de gestión de edificios ni un índice de '
                                     'emplazamiento a 50 años.',
                   'limitations': ['Plinth vigila un sitio nombrado. No opera el edificio.',
                                   'El tiempo es un nowcast público, no una estación en la azotea, salvo que '
                                   'haya un pin LIVE dentro del bbox.',
                                   'El aire es una lectura de red pública, no IAQ interior.',
                                   'Los avisos de inundación y los limnímetros, si los hay, se mantienen en '
                                   'dos listas — nunca un score de riesgo de sede.',
                                   'No es un índice de emplazamiento a 50 años, ni un perímetro de incendio, '
                                   'ni un asegurador.',
                                   'Con AIMarket ATLAS/GAIA. Plinth no opera sensores.']}},
 'seamark': {'fi': {'geography_note': 'Fintraffic Digitraffic CC BY 4.0 (Suomen vedet) ja '
                                      'Kystverket/BarentsWatch NLOD 2.0 (Norjan vedet). Jokaisella lukemalla '
                                      'on oma lähdemerkintänsä. Ei oman reunan AIS:ää, ei GFW:tä.',
                    'limitations': ['Seamark ei yhdistä Fintraffic- ja Kystverket-dataa yhdeksi '
                                    'Eurooppa-möykyksi.',
                                    'Kattavuus rajoittuu lisensoituihin Suomen ja/tai Norjan vesiin — ei '
                                    'koko Pohjanmerta, ei globaalia AIS:ää.',
                                    'Julkinen AIS ≠ oma reuna gaia.ais.read@v1.',
                                    'Aluksen katoaminen voi johtua katvealueesta, ei siitä, että alus lähti.',
                                    'Taustalla AIMarket ATLAS/GAIA. Seamark ei operoi vastaanottimia.']},
             'nb': {'geography_note': 'Fintraffic Digitraffic CC BY 4.0 (finske farvann) og '
                                      'Kystverket/BarentsWatch NLOD 2.0 (norske farvann). Hver avlesning har '
                                      'sin egen kildehenvisning. Ikke egen-edge AIS, ikke GFW.',
                    'limitations': ['Seamark slår ikke sammen Fintraffic og Kystverket til én Europa-klump.',
                                    'Dekningen er finske og/eller norske farvann slik de er lisensiert — '
                                    'ikke Nordsjøen som helhet, ikke global AIS.',
                                    'Offentlig AIS ≠ egen-edge gaia.ais.read@v1.',
                                    'Et forsvunnet fartøy kan skyldes et dekningshull, ikke at skipet har '
                                    'dratt.',
                                    'Drevet av AIMarket ATLAS/GAIA. Seamark driver ikke mottakere.']}},
 'smokeproof': {'es': {'geography_note': 'El humo NOAA/NESDIS HMS es solo de Norteamérica — nunca global. Un '
                                         'pin fuera del inventario HMS se rechaza, no se puntúa. El aire '
                                         'cercano es una lista aparte: malla Open-Meteo modelada en la misma '
                                         'coordenada (vía atlas.smoke.operations@v1), no una estación '
                                         'regulatoria in situ ni PM2.5 medido por HMS. Un upstream vacío o '
                                         'fallido se queda vacío — SIM nunca se presenta como LIVE.',
                       'limitations': ['El mismo núcleo que los desks hermanos: fijar un punto, ejecutar '
                                       'según un horario, archivar un cite pack. No hay un número único de '
                                       'riesgo.',
                                       'La pregunta es de contención binaria — ¿estaba este pin dentro del '
                                       'humo NOAA/NESDIS HMS? — más el aire cercano en una segunda lista.',
                                       'La geografía HMS es solo Norteamérica. No lea este desk como '
                                       'cobertura global de humo. Fuera del inventario el SKU rechaza.',
                                       'La densidad HMS es cualitativa y está limitada por nubes/imágenes. '
                                       'No es PM2.5 medido ni un perímetro de fuego.',
                                       'El aire cercano son datos de malla Open-Meteo modelados y '
                                       'colocalizados, de atlas.smoke.operations@v1 — no una estación '
                                       'regulatoria in situ, ni Sensor.Community, ni OpenAQ, salvo que un '
                                       'futuro SKU lo indique.',
                                       'Humo y aire se mantienen en listas separadas. La contención más el '
                                       'aire nunca se funde en una puntuación de riesgo de humo.',
                                       'Un LIVE vacío, un inventario HMS truncado o un fallo del upstream se '
                                       'quedan vacíos / fuera de línea. El desk no inventa lecturas. SIM '
                                       'nunca se presenta como LIVE.',
                                       'Fuera del humo no es all-clear. El silencio no es una garantía de '
                                       'salud ni de evacuación.',
                                       'Con AIMarket ATLAS/GAIA. Smokeproof no opera satélites.']},
                'fr': {'geography_note': 'La fumée NOAA/NESDIS HMS couvre uniquement l’Amérique du Nord — '
                                         'jamais le monde entier. Un pin hors de l’inventaire HMS est '
                                         'refusé, pas évalué. L’air voisin est une liste séparée : grille '
                                         'Open-Meteo modélisée à la même coordonnée (via '
                                         'atlas.smoke.operations@v1), pas une station réglementaire sur site '
                                         'ni du PM2.5 mesuré issu de HMS. Un amont vide ou en échec reste '
                                         'vide — SIM n’est jamais déguisé en LIVE.',
                       'limitations': ['Même noyau que les desks frères : épingler un point, exécuter selon '
                                       'une cadence, archiver un cite pack. Il n’y a pas de chiffre de '
                                       'risque unique.',
                                       'La question est un containment binaire — ce pin était-il dans la '
                                       'fumée NOAA/NESDIS HMS ? — plus l’air voisin, gardé dans une seconde '
                                       'liste.',
                                       'La géographie HMS se limite à l’Amérique du Nord. Ne lisez pas ce '
                                       'desk comme une couverture mondiale de la fumée. Hors inventaire, le '
                                       'SKU refuse.',
                                       'La densité HMS est qualitative et limitée par les nuages/l’imagerie. '
                                       'Ce n’est pas du PM2.5 mesuré ni un périmètre de feu.',
                                       'L’air voisin provient de données de grille Open-Meteo modélisées et '
                                       'colocalisées, via atlas.smoke.operations@v1 — pas une station '
                                       'réglementaire sur site, ni Sensor.Community, ni OpenAQ, sauf si un '
                                       'futur SKU le prévoit.',
                                       'Fumée et air restent des listes séparées. Containment plus air n’est '
                                       'jamais fusionné en un score de risque fumée.',
                                       'LIVE vide, inventaire HMS tronqué ou échec en amont reste vide / '
                                       'hors ligne. Le desk n’invente pas de relevés. SIM n’est jamais '
                                       'présenté comme LIVE.',
                                       'Hors fumée n’est pas un all-clear. Le silence n’est une garantie ni '
                                       'sanitaire ni d’évacuation.',
                                       'Propulsé par AIMarket ATLAS/GAIA. Smokeproof n’opère pas de '
                                       'satellites.']}},
 'solrecord': {'de': {'geography_note': '',
                      'limitations': ['Die tägliche Einstrahlung von NASA POWER ist satellitengestützt und '
                                      'erscheint mit mehrtägiger Verzögerung. Retrospektiv, kein Nowcast.',
                                      'Die Werte beschreiben die der Koordinate nächstgelegene '
                                      'POWER-Quellrasterzelle — kein Pyranometer an der Anlage.',
                                      'Aerosol und Staub sind von CAMS abgeleitete, modellierte '
                                      'Zusammensetzung — keine gemessene Verschmutzungsrate auf den Modulen.',
                                      'Es werden weder P50/P90 noch ein Unsicherheitsband geliefert.',
                                      'Betrieben durch AIMarket ATLAS/GAIA. Solrecord betreibt keine '
                                      'Satelliten.']},
               'es': {'geography_note': '',
                      'limitations': ['La irradiación diaria de NASA POWER se deriva de satélite y se '
                                      'publica con un retraso de varios días. Retrospectiva, no un nowcast.',
                                      'Los valores describen la celda de malla de origen POWER más cercana a '
                                      'la coordenada — no un piranómetro en la planta.',
                                      'El aerosol y el polvo son composición modelada derivada de CAMS, no '
                                      'una tasa de suciedad medida en los módulos.',
                                      'No se suministra P50/P90 ni banda de incertidumbre.',
                                      'Con AIMarket ATLAS/GAIA. Solrecord no opera satélites.']}},
 'tideline': {'de': {'geography_note': 'Nur lizenzierte Warn-/Pegelgebiete (US CAP, England EA, Rhein/NL, '
                                       'FR/AT-Pegel). Kein globaler Hochwasserindex.',
                     'limitations': ['Tideline führt Warnprodukte und in-situ-Pegel in getrennten Listen. Es '
                                     'vermischt sie nicht zu einer einzigen Hochwasserrisikozahl.',
                                     'Hochwassermeldungen von US NWS CAP, EA-Hochwasserwarnungen für England '
                                     'und kontinentale Pegel sind lizenzierte Gebiete — kein globaler '
                                     'Hochwasserindex.',
                                     'Ein leerer Warnfeed heißt, dass das Warnprodukt leer ist — nicht, dass '
                                     'das Einzugsgebiet sicher ist.',
                                     'Die Modi Wasserqualität und Talsperren sind zusätzliche Listen, nie '
                                     'Ersatz für eine Warnung oder einen Pegelstand.',
                                     'Betrieben durch AIMarket ATLAS/GAIA. Tideline betreibt keine Pegel und '
                                     'gibt keine Warnungen heraus.']},
              'fr': {'geography_note': 'Uniquement des géographies d’alertes/jauges sous licence (US CAP, EA '
                                       'Angleterre, Rhin/NL, jauges FR/AT). Pas un indice mondial des crues.',
                     'limitations': ['Tideline garde les produits d’alerte et les jauges in situ dans des '
                                     'listes séparées. Il ne les fusionne pas en un seul chiffre de risque '
                                     'inondation.',
                                     'Les alertes crue US NWS CAP, les alertes inondation EA (Angleterre) et '
                                     'les jauges continentales sont des géographies sous licence — pas un '
                                     'indice mondial des crues.',
                                     'Un flux d’alertes vide signifie que le produit d’alerte est vide, pas '
                                     'que le bassin est sûr.',
                                     'Les modes qualité de l’eau et réservoir sont des listes '
                                     'supplémentaires, jamais un substitut à une alerte ou à une cote.',
                                     'Propulsé par AIMarket ATLAS/GAIA. Tideline n’exploite pas de jauges et '
                                     'n’émet pas d’alertes.']},
              'nl': {'geography_note': 'Alleen gelicentieerde waarschuwings-/peilgebieden (US CAP, EA '
                                       'Engeland, Rijn/NL, FR/AT-peilschalen). Geen wereldwijde '
                                       'overstromingsindex.',
                     'limitations': ['Tideline houdt waarschuwingsproducten en in-situ peilschalen in aparte '
                                     'lijsten. Het voegt ze niet samen tot één overstromingsrisicocijfer.',
                                     'Overstromingsberichten van US NWS CAP, EA-overstromingswaarschuwingen '
                                     'voor Engeland en continentale peilschalen zijn gelicentieerde gebieden '
                                     '— geen wereldwijde overstromingsindex.',
                                     'Een lege waarschuwingsfeed betekent dat het waarschuwingsproduct leeg '
                                     'is, niet dat het stroomgebied veilig is.',
                                     'Waterkwaliteits- en reservoirmodi zijn extra lijsten, nooit een '
                                     'vervanging voor een waarschuwing of een peil.',
                                     'Aangedreven door AIMarket ATLAS/GAIA. Tideline beheert geen '
                                     'peilschalen en geeft geen waarschuwingen uit.']}}}

# The section heading, per locale (the English one is in LANDING_UI).
LIMITS_UI: dict[str, dict[str, str]] = {
    "es": {"limits_kicker": "Límites", "limits_h2": "Lo que este desk no afirma"},
    "fr": {"limits_kicker": "Limites", "limits_h2": "Ce que ce desk n’affirme pas"},
    "de": {"limits_kicker": "Grenzen", "limits_h2": "Was dieser Desk nicht behauptet"},
    "nl": {"limits_kicker": "Grenzen", "limits_h2": "Wat deze desk niet beweert"},
    "fi": {"limits_kicker": "Rajat", "limits_h2": "Mitä tämä desk ei väitä"},
    "nb": {"limits_kicker": "Grenser", "limits_h2": "Hva denne desken ikke påstår"},
}
