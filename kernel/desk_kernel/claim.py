from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

WatchKind = Literal["bbox", "point"]
HostRegion = Literal["us", "nl"]


@dataclass(frozen=True)
class ClaimClass:
    """One honest claim. One desk. Not a layer picker."""

    id: str
    product_name: str
    tagline: str
    artifact_type: str
    delta_artifact_type: str
    event_name: str
    key_prefix: str
    invoice_prefix: str
    canonical_host: str
    canonical_origin: str
    desk_mail: str
    demo_email: str
    demo_password: str
    cookie_name: str
    ops_cookie_name: str
    signature_header: str
    mint_header: str
    ops_header: str
    user_agent: str
    watch_kind: WatchKind
    default_layers: tuple[str, ...]
    match_layers: tuple[str, ...]
    cheap_sku: str | None
    brief_sku: str
    extra_skus: tuple[str, ...] = ()
    #: Named ATLAS situation.brief preset. When set, the engine sends `preset`
    #: and does not also send `layers`, so the desk's scope sentence is the answer.
    brief_preset: str | None = None
    hub_cogs: dict[str, float] = field(default_factory=dict)
    overage: dict[str, float] = field(default_factory=dict)
    schedules: tuple[str, ...] = ("15m", "30m", "60m")
    default_schedule: str = "60m"
    max_span_ew: float = 40.0
    max_span_ns: float = 30.0
    geography_note: str = ""
    badges: tuple[str, ...] = ()
    legal_strip: str = ""
    limitations: tuple[str, ...] = ()
    not_list: tuple[str, ...] = ()
    cite_header: str = ""
    cite_author: str = ""
    cite_creator: str = ""
    cite_subject: str = ""
    cite_footer: str = "Monitoring aid only. Quiet is not proof of safety."
    readme_title: str = "CITE PACK"
    items_heading: str = "LIVE items on this run"
    count_field: str = "live_count"
    verified_key: str = "desk_verified"
    sample_watch_name: str = "Sample watch"
    sample_timezone: str = "UTC"
    default_bbox: tuple[float, float, float, float] | None = None  # W S E N
    default_point: tuple[float, float] | None = None  # lat, lon
    default_policy: str = "on_match"
    powered_by: str = "AIMarket ATLAS / GAIA / Hub"
    operates_satellites: bool = False
    locales: tuple[str, ...] = ("en",)
    default_locale: str = "en"
    host_region: HostRegion = "us"
    placement_note: str = ""

    @property
    def anon_mail_domain(self) -> str:
        """Where a prepaid key's placeholder seat lives. Never a deliverable mailbox."""
        return f"anon.{self.canonical_host}"

    def sku_cogs(self, skus: list[str]) -> float:
        return round(sum(self.hub_cogs.get(sku, 0.0) for sku in skus), 4)

    def all_skus(self) -> list[dict[str, float | str]]:
        ids = [s for s in (self.cheap_sku, self.brief_sku, *self.extra_skus) if s]
        return [{"id": sku, "list_usd": self.hub_cogs.get(sku, 0.0)} for sku in ids]


EMBERLINE = ClaimClass(
    id="emberline",
    product_name="Emberline Fire Evidence Desk",
    tagline="Citeable LIVE thermal detections. Not a perimeter.",
    artifact_type="emberline.evidence_brief@v1",
    delta_artifact_type="emberline.run_delta@v1",
    event_name="emberline.alert",
    key_prefix="emb_",
    invoice_prefix="EL",
    canonical_host="emberlinedesk.com",
    canonical_origin="https://emberlinedesk.com",
    desk_mail="desk@emberlinedesk.com",
    demo_email="owner@emberlinedesk.com",
    demo_password="emberline-demo",
    cookie_name="emberline_session",
    ops_cookie_name="emberline_ops",
    signature_header="X-Emberline-Signature",
    mint_header="X-Emberline-Mint",
    ops_header="X-Emberline-Ops",
    user_agent="emberline-desk/0.1 (+https://emberlinedesk.com)",
    watch_kind="bbox",
    default_layers=("fire", "weather"),
    match_layers=("fire",),
    cheap_sku="atlas.watchbox.check@v1",
    brief_sku="atlas.fire.weather@v1",
    extra_skus=("atlas.smoke.operations@v1",),
    hub_cogs={
        "atlas.watchbox.check@v1": 0.02,
        "atlas.fire.weather@v1": 0.08,
        "atlas.smoke.operations@v1": 0.12,
    },
    overage={
        "atlas.watchbox.check@v1": 0.04,
        "atlas.fire.weather@v1": 0.12,
        "atlas.smoke.operations@v1": 0.16,
    },
    badges=("NOT A PERIMETER", "NOT A FORECAST", "NOT AN EVACUATION ORDER"),
    legal_strip=(
        "Monitoring aid only. Not a perimeter, forecast, risk rating, evacuation order, "
        "or insurance product. Do not treat a quiet run as proof of safety."
    ),
    limitations=(
        "Emberline is a monitoring aid. It is not an emergency service, evacuation authority, or insurer.",
        "Absence of an alert is not a safety guarantee. Satellite revisit, cloud cover, and sensor gaps exist.",
        "Detections are thermal anomalies. Emberline does not invent fire perimeters, forecasts, or risk scores.",
        "HMS smoke, if requested, is a qualitative North America polygon — not measured PM2.5 and not a fire perimeter.",
        "Powered by AIMarket ATLAS/GAIA. Emberline does not operate satellites.",
    ),
    not_list=("fire perimeter", "forecast", "evacuation authority", "insurer", "risk score"),
    cite_header="EMBERLINE  |  EVIDENCE CITE PACK  |  NOT A PERIMETER / FORECAST / EVACUATION ORDER",
    cite_author="Emberline Fire Evidence Desk",
    cite_creator="emberline.cite_pack@v1",
    cite_subject="Monitoring aid. Not a perimeter, forecast, or evacuation order.",
    readme_title="EMBERLINE CITE PACK",
    items_heading="LIVE detections on this run",
    count_field="live_fire_detection_count",
    verified_key="emberline_verified",
    sample_watch_name="CA Transmission Corridor",
    sample_timezone="America/Los_Angeles",
    default_bbox=(-125.0, 32.0, -114.0, 42.0),
    default_policy="always_brief",
    locales=("en", "es", "fr"),
    default_locale="en",
    host_region="us",
    placement_note=(
        "USA host. FIRMS/HMS and CAL-FIRE-shaped operators are North American; "
        "EFFIS readers still hit the same origin. Do not put Emberline in NL just for GDPR theatre — "
        "the evidence is US-weighted and the desk is already live on the US box."
    ),
)

TIDELINE = ClaimClass(
    id="tideline",
    product_name="Tideline Flood Evidence Desk",
    tagline="Warning product and in-situ gauge, two lists. Not a flood model.",
    artifact_type="tideline.evidence_brief@v1",
    delta_artifact_type="tideline.run_delta@v1",
    event_name="tideline.alert",
    key_prefix="tdl_",
    invoice_prefix="TL",
    canonical_host="tidelinedesk.com",
    canonical_origin="https://tidelinedesk.com",
    desk_mail="desk@tidelinedesk.com",
    demo_email="owner@tidelinedesk.com",
    demo_password="tideline-demo",
    cookie_name="tideline_session",
    ops_cookie_name="tideline_ops",
    signature_header="X-Tideline-Signature",
    mint_header="X-Tideline-Mint",
    ops_header="X-Tideline-Ops",
    user_agent="tideline-desk/0.1 (+https://tidelinedesk.com)",
    watch_kind="bbox",
    default_layers=("flood", "river"),
    match_layers=("flood",),
    cheap_sku="atlas.watchbox.check@v1",
    brief_sku="atlas.situation.brief@v1",
    extra_skus=("gaia.river.read@v1", "gaia.flood.read@v1"),
    hub_cogs={
        "atlas.watchbox.check@v1": 0.02,
        "atlas.situation.brief@v1": 0.06,
        "gaia.river.read@v1": 0.001,
        "gaia.flood.read@v1": 0.002,
        "gaia.water_quality.read@v1": 0.002,
        "gaia.reservoir.read@v1": 0.001,
    },
    overage={
        "atlas.watchbox.check@v1": 0.04,
        "atlas.situation.brief@v1": 0.10,
    },
    badges=(
        "NOT A FLOOD MODEL",
        "WARNING IS NOT A GAUGE",
        "NOT AN EVACUATION ORDER",
        "NOT A RISK SCORE",
    ),
    legal_strip=(
        "Monitoring aid only. A CAP or agency warning is not an in-situ stage. "
        "A river gauge is not a flood warning. Empty LIVE is not all-clear. "
        "Not a flood model, parametric quote, or 911 feed."
    ),
    limitations=(
        "Tideline keeps warning products and in-situ gauges in separate lists. It will not merge them into one flood-risk number.",
        "US NWS CAP flood, EA England flood warnings, and continental gauges are licensed geographies — not a global flood index.",
        "Empty warning feed means the warning product is empty, not that the basin is safe.",
        "Water-quality and reservoir modes are extra lists, never a substitute for a warning or a stage.",
        "Powered by AIMarket ATLAS/GAIA. Tideline does not operate gauges or issue warnings.",
    ),
    not_list=("flood model", "Floodbase index", "evacuation authority", "insurer", "risk score", "all-clear"),
    cite_header="TIDELINE  |  EVIDENCE CITE PACK  |  WARNING ≠ GAUGE / NOT A FLOOD MODEL",
    cite_author="Tideline Flood Evidence Desk",
    cite_creator="tideline.cite_pack@v1",
    cite_subject="Monitoring aid. Warning product and gauge kept separate.",
    readme_title="TIDELINE CITE PACK",
    items_heading="LIVE warning products and gauges on this run",
    count_field="live_warning_count",
    sample_watch_name="Thames to Estuary",
    sample_timezone="Europe/London",
    default_bbox=(-1.2, 51.2, 0.6, 51.7),
    geography_note="Licensed warning/gauge geographies only (US CAP, England EA, Rhine/NL, FR/AT gauges). Not a global flood index.",
    locales=("en", "nl", "fr", "de"),
    default_locale="en",
    host_region="nl",
    placement_note=(
        "Netherlands host. RWS, Rhine, Hub'Eau, eHYD, and EA are EEA evidence; "
        "US CAP still works from AMS. GDPR stays in the Union. Not a US fire box."
    ),
)

SOLRECORD = ClaimClass(
    id="solrecord",
    product_name="Solrecord PV Evidence Desk",
    tagline="Retrospective irradiance record. Not a yield forecast.",
    artifact_type="solrecord.evidence_brief@v1",
    delta_artifact_type="solrecord.run_delta@v1",
    event_name="solrecord.alert",
    key_prefix="sol_",
    invoice_prefix="SR",
    canonical_host="solrecorddesk.com",
    canonical_origin="https://solrecorddesk.com",
    desk_mail="desk@solrecorddesk.com",
    demo_email="owner@solrecorddesk.com",
    demo_password="solrecord-demo",
    cookie_name="solrecord_session",
    ops_cookie_name="solrecord_ops",
    signature_header="X-Solrecord-Signature",
    mint_header="X-Solrecord-Mint",
    ops_header="X-Solrecord-Ops",
    user_agent="solrecord-desk/0.1 (+https://solrecorddesk.com)",
    watch_kind="point",
    default_layers=("solar", "atmosphere"),
    match_layers=("solar",),
    cheap_sku=None,
    brief_sku="atlas.pv.irradiance.record@v1",
    hub_cogs={"atlas.pv.irradiance.record@v1": 0.15},
    overage={"atlas.pv.irradiance.record@v1": 0.20},
    schedules=("12h", "1d"),
    default_schedule="1d",
    badges=(
        "NOT A YIELD FORECAST",
        "NOT A PYRANOMETER",
        "NOT P50/P90",
        "NOT A SOILING MODEL",
    ),
    legal_strip=(
        "Retrospective record of fact for one plant coordinate. NASA POWER cell + CAMS aerosol. "
        "Not a pyranometer, not a yield forecast, not a bankable energy assessment."
    ),
    limitations=(
        "NASA POWER daily irradiation is satellite-derived and published with a multi-day lag. Retrospective, not a nowcast.",
        "Values describe the POWER source grid cell nearest the coordinate — not a pyranometer on the plant.",
        "Aerosol and dust are CAMS-derived modelled composition, not a measured soiling rate on the modules.",
        "No P50/P90 and no uncertainty band is supplied.",
        "Powered by AIMarket ATLAS/GAIA. Solrecord does not operate satellites.",
    ),
    not_list=("yield forecast", "pyranometer", "P50/P90", "soiling-loss model", "insurer"),
    cite_header="SOLRECORD  |  EVIDENCE CITE PACK  |  NOT A YIELD FORECAST / NOT A PYRANOMETER",
    cite_author="Solrecord PV Evidence Desk",
    cite_creator="solrecord.cite_pack@v1",
    cite_subject="Retrospective irradiance record. Not a yield forecast.",
    cite_footer="Record of fact. Quiet is not a performance guarantee.",
    readme_title="SOLRECORD CITE PACK",
    items_heading="Irradiance record for this plant",
    count_field="live_record_count",
    sample_watch_name="Mojave plant pin",
    sample_timezone="America/Los_Angeles",
    default_point=(35.0, -117.5),
    default_policy="always_brief",
    locales=("en", "es", "de"),
    default_locale="en",
    host_region="us",
    placement_note=(
        "USA host. NASA POWER is published in the US; utility-scale pins for US plants "
        "are the lead buyer. CAMS is European, but the SKU is ATLAS. DACH plants still use this origin."
    ),
)

SEAMARK = ClaimClass(
    id="seamark",
    product_name="Seamark Nordic Maritime Desk",
    tagline="Finnish and Norwegian AIS, kept separate. Not global AIS.",
    artifact_type="seamark.evidence_brief@v1",
    delta_artifact_type="seamark.run_delta@v1",
    event_name="seamark.alert",
    key_prefix="smk_",
    invoice_prefix="SM",
    canonical_host="seamarkdesk.com",
    canonical_origin="https://seamarkdesk.com",
    desk_mail="desk@seamarkdesk.com",
    demo_email="owner@seamarkdesk.com",
    demo_password="seamark-demo",
    cookie_name="seamark_session",
    ops_cookie_name="seamark_ops",
    signature_header="X-Seamark-Signature",
    mint_header="X-Seamark-Mint",
    ops_header="X-Seamark-Ops",
    user_agent="seamark-desk/0.1 (+https://seamarkdesk.com)",
    watch_kind="bbox",
    default_layers=("ais", "marine"),
    match_layers=("ais",),
    cheap_sku="atlas.watchbox.check@v1",
    brief_sku="gaia.ais.public.read@v1",
    extra_skus=("gaia.marine.read@v1",),
    hub_cogs={
        "atlas.watchbox.check@v1": 0.02,
        "gaia.ais.public.read@v1": 0.002,
        "gaia.marine.read@v1": 0.002,
    },
    overage={"atlas.watchbox.check@v1": 0.04, "gaia.ais.public.read@v1": 0.01},
    max_span_ew=20.0,
    max_span_ns=15.0,
    geography_note=(
        "Fintraffic Digitraffic CC BY 4.0 (Finnish waters) and Kystverket/BarentsWatch NLOD 2.0 "
        "(Norwegian waters). Each reading carries its own attribution. Not own-edge AIS, not GFW."
    ),
    badges=(
        "NOT GLOBAL AIS",
        "FINLAND ≠ NORWAY",
        "NOT COLLISION AVOIDANCE",
        "NOT OWN-EDGE AIS",
    ),
    legal_strip=(
        "Monitoring aid only. Finnish AIS and Norwegian AIS are separate licensed feeds. "
        "Not global AIS, not GFW, not a collision-avoidance or VTS replacement."
    ),
    limitations=(
        "Seamark will not merge Fintraffic and Kystverket into one Europe blob.",
        "Coverage is Finnish waters and/or Norwegian waters as licensed — not the North Sea as a whole, not global AIS.",
        "Public AIS ≠ own-edge gaia.ais.read@v1.",
        "A disappeared vessel may be a coverage gap, not that the ship left.",
        "Powered by AIMarket ATLAS/GAIA. Seamark does not operate receivers.",
    ),
    not_list=("global AIS", "GFW", "collision avoidance", "VTS", "own-edge AIS"),
    cite_header="SEAMARK  |  EVIDENCE CITE PACK  |  NOT GLOBAL AIS / FI ≠ NO",
    cite_author="Seamark Nordic Maritime Desk",
    cite_creator="seamark.cite_pack@v1",
    cite_subject="Nordic public AIS. Not global tracking.",
    readme_title="SEAMARK CITE PACK",
    items_heading="LIVE vessels on this run",
    count_field="live_vessel_count",
    sample_watch_name="Helsinki approaches",
    sample_timezone="Europe/Helsinki",
    default_bbox=(24.4, 59.8, 25.4, 60.4),
    locales=("en", "fi", "nb"),
    default_locale="en",
    host_region="nl",
    placement_note=(
        "Netherlands host. Fintraffic and Kystverket are EEA feeds; AIS positions are closer "
        "to AMS than to the US. Swedish UI is omitted on purpose — licensed waters are FI and NO, not Sweden."
    ),
)

PLINTH = ClaimClass(
    id="plinth",
    product_name="Plinth Site Evidence Desk",
    tagline="Named-site nowcast. Weather, air, water — separate lists. Not a BMS.",
    artifact_type="plinth.evidence_brief@v1",
    delta_artifact_type="plinth.run_delta@v1",
    event_name="plinth.alert",
    key_prefix="pln_",
    invoice_prefix="PL",
    canonical_host="plinthdesk.com",
    canonical_origin="https://plinthdesk.com",
    desk_mail="desk@plinthdesk.com",
    demo_email="owner@plinthdesk.com",
    demo_password="plinth-demo",
    cookie_name="plinth_session",
    ops_cookie_name="plinth_ops",
    signature_header="X-Plinth-Signature",
    mint_header="X-Plinth-Mint",
    ops_header="X-Plinth-Ops",
    user_agent="plinth-desk/0.1 (+https://plinthdesk.com)",
    watch_kind="bbox",
    default_layers=("weather", "air", "flood", "river", "alerts", "grid", "lightning"),
    match_layers=("flood", "alerts", "air"),
    cheap_sku="atlas.watchbox.check@v1",
    brief_sku="atlas.situation.brief@v1",
    brief_preset="campus",
    hub_cogs={
        "atlas.watchbox.check@v1": 0.02,
        "atlas.situation.brief@v1": 0.06,
    },
    overage={
        "atlas.watchbox.check@v1": 0.04,
        "atlas.situation.brief@v1": 0.10,
    },
    max_span_ew=1.0,
    max_span_ns=1.0,
    geography_note=(
        "A named building, campus, or colo bbox. Public-sensor nowcast only — "
        "not a building-management system, not a 50-year siting index."
    ),
    badges=(
        "NOT A BMS",
        "NOT A SITING INDEX",
        "WEATHER ≠ AIR ≠ WATER",
        "NOT AN INSURER",
    ),
    legal_strip=(
        "Monitoring aid only. Weather, air, flood warnings and river gauges stay in "
        "separate lists. Not a BMS, First Street clone, fire perimeter, flood model, or insurer. "
        "Empty LIVE is not all-clear."
    ),
    limitations=(
        "Plinth watches one named site. It does not operate the building.",
        "Weather is a public nowcast, not a roof station unless a LIVE pin is in the box.",
        "Air is a public network reading, not indoor IAQ.",
        "Flood warnings and river gauges, if present, stay in two lists — never a campus risk score.",
        "Not a 50-year siting index, not a fire perimeter, not an insurer.",
        "Powered by AIMarket ATLAS/GAIA. Plinth does not operate sensors.",
    ),
    not_list=("BMS", "First Street index", "fire perimeter", "flood model", "insurer", "all-clear", "campus risk score"),
    cite_header="PLINTH  |  SITE EVIDENCE CITE PACK  |  NOT A BMS / NOT A SITING INDEX",
    cite_author="Plinth Site Evidence Desk",
    cite_creator="plinth.cite_pack@v1",
    cite_subject="Named-site nowcast. Weather, air, and water kept separate.",
    readme_title="PLINTH CITE PACK",
    items_heading="LIVE readings on this site",
    count_field="live_site_count",
    sample_watch_name="Ashburn colo campus",
    sample_timezone="America/New_York",
    default_bbox=(-77.52, 39.00, -77.38, 39.08),
    default_policy="always_brief",
    locales=("en", "es", "de"),
    default_locale="en",
    host_region="us",
    placement_note=(
        "USA host. Colo and campus buyers are US-weighted (Ashburn, Northern Virginia, "
        "university EHS). DACH and LatAm sites still use this origin. Not a Rhine flood box."
    ),
)

CLAIMS: dict[str, ClaimClass] = {
    EMBERLINE.id: EMBERLINE,
    TIDELINE.id: TIDELINE,
    SOLRECORD.id: SOLRECORD,
    SEAMARK.id: SEAMARK,
    PLINTH.id: PLINTH,
}


def get_claim(desk_id: str) -> ClaimClass:
    try:
        return CLAIMS[desk_id]
    except KeyError as exc:
        raise KeyError(f"unknown desk {desk_id!r}") from exc
