"""NEUTRIK cable-connector chooser.

Legal SKUs for the five cable-connector product lines in this folder.
Harness build instructions import this module, not the generator.

    import os
    import sys

    from harnice.lists import instances_list
    from harnice.utils import library_utils

    LIBRARY_REPO = "https://github.com/harnice/harnice-av-library"
    LIBRARY_SUBPATH = "neutrik"
    sys.path.append(
        os.path.join(library_utils.get_local_path(LIBRARY_REPO), LIBRARY_SUBPATH)
    )
    import neutrik

    for instance in instances_list.read():
        if instance.get("item_type") != "harness_connector":
            continue
        device_mpn = instance.get("device_side_connector_mpn") or ""
        if not device_mpn.upper().startswith("NC"):
            continue
        instances_list.modify(
            instance.get("instance_name"),
            {
                "mpn": neutrik.find_mating_connector(device_mpn),
                "lib_repo": LIBRARY_REPO,
                "lib_subpath": LIBRARY_SUBPATH,
            },
        )
"""

from __future__ import annotations

import re

LIBRARY_REPO = "https://github.com/harnice/harnice-av-library"
LIBRARY_SUBPATH = "neutrik"
MANUFACTURER = "Neutrik"

FAMILIES = ("XLR", "etherCON", "powerCON", "TRS", "speakON")

# ---------------------------------------------------------------------------
# Catalog tables — only commercially sold SKUs. Sources cited per series.
# ---------------------------------------------------------------------------
# XLR XX series: https://www.neutrik.com/media/19523/download/Assembly%20Instruction%20-%20XLR%20XX%20Series.pdf
XLR_XX_POLES = [3, 4, 5, 6, 7]
XLR_XX_FINISHES = {
    3: ["", "B", "BAG", "WT"],
    4: ["", "B", "BAG"],
    5: ["", "B", "BAG"],
    6: [""],
    7: [""],
}
XLR_XX_SOURCE = (
    "https://www.neutrik.com/media/19523/download/"
    "Assembly%20Instruction%20-%20XLR%20XX%20Series.pdf"
)

# etherCON: https://www.neutrik.com/media/10044/download/Drawing%20NE8MX6.pdf
ETHERCON_SOURCE = (
    "https://www.neutrik.com/media/10044/download/Drawing%20NE8MX6.pdf"
)
ETHERCON_CATALOG = (
    ("NE8MX", "", "carrier for pre-assembled RJ45 plugs", [4.5, 8.0], "CAT5e", []),
    ("NE8MX-B", "B", "carrier for pre-assembled RJ45 plugs", [4.5, 8.0], "CAT5e", []),
    (
        "NE8MC",
        "",
        "CAT5e cable connector with RJ45 plug",
        [5.0, 8.0],
        "CAT5e",
        ["RJ45 crimp tool"],
    ),
    (
        "NE8MC-B",
        "B",
        "CAT5e cable connector with RJ45 plug",
        [5.0, 8.0],
        "CAT5e",
        ["RJ45 crimp tool"],
    ),
    (
        "NE8MX6",
        "",
        "CAT6A self-termination cable connector, insulation diameter > 1.1 mm",
        [7.0, 9.5],
        "CAT6A",
        ["Cable stripping tool", "Flush cutter"],
    ),
    (
        "NE8MX6-B",
        "B",
        "CAT6A self-termination cable connector, insulation diameter > 1.1 mm",
        [7.0, 9.5],
        "CAT6A",
        ["Cable stripping tool", "Flush cutter"],
    ),
    (
        "NE8MX6-T",
        "",
        "CAT6A self-termination cable connector, insulation diameter <= 1.1 mm",
        [7.0, 9.5],
        "CAT6A",
        ["Cable stripping tool", "Flush cutter"],
    ),
)

# powerCON: https://www.neutrik.com/media/10093/download/Neutrik%20Product%20Guide%20-%2006%20powerCON%20and%20Circular%20Connectors%20PG%20EN%20202210-V25.pdf
POWERCON_SOURCE = (
    "https://www.neutrik.com/media/10093/download/"
    "Neutrik%20Product%20Guide%20-%2006%20powerCON%20and%20Circular%20"
    "Connectors%20PG%20EN%20202210-V25.pdf"
)
POWERCON_CATALOG = (
    (
        "NAC3FCA",
        "powerCON 20 A",
        "female",
        "blue",
        "power-in cable connector, quick lock with securing lever",
        [6.0, 15.0],
        False,
    ),
    (
        "NAC3FCB",
        "powerCON 20 A",
        "female",
        "grey",
        "power-out cable connector, quick lock with securing lever",
        [6.0, 15.0],
        False,
    ),
    (
        "NAC3FX-W",
        "powerCON TRUE1",
        "female",
        "black",
        "locking power-in cable connector, IP65",
        [6.0, 12.0],
        True,
    ),
    (
        "NAC3MX-W",
        "powerCON TRUE1",
        "male",
        "black",
        "locking power-out cable connector, IP65",
        [6.0, 12.0],
        True,
    ),
    (
        "NAC3FX-W-TOP",
        "powerCON TRUE1 TOP",
        "female",
        "black",
        "locking power-in cable connector, IP65",
        [6.0, 12.0],
        True,
    ),
    (
        "NAC3MX-W-TOP",
        "powerCON TRUE1 TOP",
        "male",
        "black",
        "locking power-out cable connector, IP65",
        [6.0, 12.0],
        True,
    ),
    (
        "NAC3FX-W-TOP-L",
        "powerCON TRUE1 TOP Large",
        "female",
        "black",
        "locking power-in cable connector for large cable, IP65",
        [10.0, 16.0],
        True,
    ),
    (
        "NAC3MX-W-TOP-L",
        "powerCON TRUE1 TOP Large",
        "male",
        "black",
        "locking power-out cable connector for large cable, IP65",
        [10.0, 16.0],
        True,
    ),
)

# TRS: https://media.djmania.net/manuales/pdf/Manual_Neutrik_NP3X.pdf
PHONE_SOURCE = "https://media.djmania.net/manuales/pdf/Manual_Neutrik_NP3X.pdf"

# speakON: https://www.neutrik.com/media/10094/download/03%20NEUTRIK%20PG%20E%20-%20speakON%20Connectors%20-%20202104-V21.pdf
SPEAKON_SOURCE = (
    "https://www.neutrik.com/media/10094/download/"
    "03%20NEUTRIK%20PG%20E%20-%20speakON%20Connectors%20-%20202104-V21.pdf"
)
SPEAKON_CATALOG = (
    (
        "NL2FX",
        "X",
        2,
        "female",
        "",
        "blue",
        "cable connector with chuck, intermates with 4 pole chassis on +1/-1",
        [6.0, 10.0],
        25.0,
        74.0,
        11.0,
        "plastic",
    ),
    (
        "NL4FX",
        "X",
        4,
        "female",
        "",
        "black",
        "cable connector with chuck",
        [7.0, 14.5],
        25.0,
        74.0,
        11.0,
        "plastic",
    ),
    (
        "NL4FX-2",
        "X",
        4,
        "female",
        "",
        "red",
        "cable connector with chuck and red bushing",
        [7.0, 14.5],
        25.0,
        74.0,
        11.0,
        "plastic",
    ),
    (
        "NL4FX-4",
        "X",
        4,
        "female",
        "",
        "yellow",
        "cable connector with chuck and yellow bushing",
        [7.0, 14.5],
        25.0,
        74.0,
        11.0,
        "plastic",
    ),
    (
        "NL4FX-5",
        "X",
        4,
        "female",
        "",
        "green",
        "cable connector with chuck and green bushing",
        [7.0, 14.5],
        25.0,
        74.0,
        11.0,
        "plastic",
    ),
    (
        "NL4FX-9",
        "X",
        4,
        "female",
        "",
        "white",
        "cable connector with chuck and white bushing",
        [7.0, 14.5],
        25.0,
        74.0,
        11.0,
        "plastic",
    ),
    (
        "NL4FC",
        "FC",
        4,
        "female",
        "",
        "black",
        "cable connector with latch lock",
        [8.0, 20.0],
        26.0,
        78.0,
        13.0,
        "plastic",
    ),
    (
        "NL8FC",
        "FC",
        8,
        "female",
        "",
        "black",
        "cable connector with latch lock",
        [8.0, 20.0],
        26.0,
        78.0,
        13.0,
        "plastic",
    ),
    (
        "NLT4FX",
        "STX",
        4,
        "female",
        "",
        "black",
        "female cable connector, metal housing, chuck and bushing",
        [8.0, 16.0],
        26.0,
        78.0,
        13.0,
        None,
    ),
    (
        "NLT4FX-BAG",
        "STX",
        4,
        "female",
        "BAG",
        "black",
        "female cable connector, metal housing, chuck and bushing",
        [8.0, 16.0],
        26.0,
        78.0,
        13.0,
        None,
    ),
    (
        "NLT4MX",
        "STX",
        4,
        "male",
        "",
        "black",
        "male cable connector, metal housing, chuck and bushing",
        [8.0, 16.0],
        26.0,
        78.0,
        13.0,
        None,
    ),
    (
        "NLT4MX-BAG",
        "STX",
        4,
        "male",
        "BAG",
        "black",
        "male cable connector, metal housing, chuck and bushing",
        [8.0, 16.0],
        26.0,
        78.0,
        13.0,
        None,
    ),
    (
        "NLT8FX",
        "STX",
        8,
        "female",
        "",
        "black",
        "female cable connector, metal housing, chuck and bushing",
        [8.0, 20.0],
        30.0,
        82.0,
        15.0,
        None,
    ),
    (
        "NLT8FX-BAG",
        "STX",
        8,
        "female",
        "BAG",
        "black",
        "female cable connector, metal housing, chuck and bushing",
        [8.0, 20.0],
        30.0,
        82.0,
        15.0,
        None,
    ),
    (
        "NLT8MX-BAG",
        "STX",
        8,
        "male",
        "BAG",
        "black",
        "male cable connector, metal housing, chuck and bushing",
        [8.0, 20.0],
        30.0,
        82.0,
        15.0,
        None,
    ),
)

HOUSING_NAMES = {
    "": "nickel",
    "B": "black chrome",
    "BAG": "black chrome",
    "WT": "white painted",
}
HOUSING_PALETTES = {
    "": "nickel",
    "B": "black_chrome",
    "BAG": "black_chrome",
    "WT": "white",
}

_FAMILY_ALIASES = {
    "XLR": "XLR",
    "ETHERCON": "etherCON",
    "ETHER": "etherCON",
    "RJ45": "etherCON",
    "POWERCON": "powerCON",
    "POWER": "powerCON",
    "TRUE1": "powerCON",
    "TRS": "TRS",
    "TS": "TRS",
    "PHONE": "TRS",
    "QUARTER": "TRS",
    "1/4": "TRS",
    "SPEAKON": "speakON",
    "SPEAK": "speakON",
}

_GENDER_ALIASES = {
    "M": "male",
    "MALE": "male",
    "PLUG": "male",
    "PIN": "male",
    "P": "male",
    "F": "female",
    "FEMALE": "female",
    "JACK": "female",
    "SOCKET": "female",
    "S": "female",
    "RECEPTACLE": "female",
}

_FINISH_ALIASES = {
    "": "",
    "NICKEL": "",
    "B": "B",
    "BLACK": "B",
    "BLACKCHROME": "B",
    "BAG": "BAG",
    "WT": "WT",
    "WHITE": "WT",
    "WHITEPAINTED": "WT",
}

_XLR_RE = re.compile(
    r"^NC(?P<poles>[3-7])(?P<gender>[FM])XX(?:-(?P<finish>B|BAG|WT))?$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Catalog iterator
# ---------------------------------------------------------------------------
def _xlr_configurations():
    for poles in XLR_XX_POLES:
        for gender, gender_code in (("female", "F"), ("male", "M")):
            for finish in XLR_XX_FINISHES[poles]:
                suffix = f"-{finish}" if finish else ""
                yield {
                    "mpn": f"NC{poles}{gender_code}XX{suffix}",
                    "family": "XLR",
                    "series": "XX",
                    "poles": poles,
                    "gender": gender,
                    "finish": finish,
                    "palette": HOUSING_PALETTES[finish],
                    "bushing": "black",
                    "housing_material": "zinc diecast (ZnAl4Cu1)",
                    "termination": "solder cup",
                    "cable_od_mm": [3.5, 8.0],
                    "contact_names": [str(i) for i in range(1, poles + 1)],
                    "tools": ["Soldering iron"],
                    "source": XLR_XX_SOURCE,
                }


def _ethercon_configurations():
    for mpn, finish, desc, cable_od, category, tools in ETHERCON_CATALOG:
        yield {
            "mpn": mpn,
            "family": "etherCON",
            "series": category,
            "poles": 8,
            "gender": "male",
            "finish": finish,
            "palette": HOUSING_PALETTES[finish],
            "bushing": "black",
            "housing_material": "zinc diecast (ZnAl4Cu1)",
            "termination": "RJ45",
            "cable_od_mm": cable_od,
            "contact_names": [str(i) for i in range(1, 9)],
            "tools": tools,
            "source": ETHERCON_SOURCE,
            "product_desc": desc,
        }


def _powercon_configurations():
    for mpn, series, gender, bushing, desc, cable_od, true1 in POWERCON_CATALOG:
        if true1:
            tools = ["T8 Torx driver", "13 mm wrench"]
        else:
            tools = ["3 mm flat-blade screwdriver"]
        yield {
            "mpn": mpn,
            "family": "powerCON",
            "series": series,
            "poles": 3,
            "gender": gender,
            "finish": "",
            "palette": "plastic",
            "bushing": bushing,
            "housing_material": "glass-reinforced polyamide",
            "termination": "screw terminal",
            "cable_od_mm": cable_od,
            "contact_names": ["L", "N", "PE"],
            "tools": tools,
            "source": POWERCON_SOURCE,
            "product_desc": desc,
            "true1": true1,
        }


def _phone_configurations():
    catalog = []
    for poles, poles_name in ((2, "mono (TS)"), (3, "stereo (TRS)")):
        finishes = ["", "B", "BAG"] + (["WT"] if poles == 2 else [])
        for finish in finishes:
            suffix = f"-{finish}" if finish else ""
            catalog.append(
                (
                    f"NP{poles}X{suffix}",
                    "PX",
                    poles,
                    finish,
                    f'1/4" phone plug, {poles_name}',
                    [4.0, 7.0],
                    14.5,
                    9.0,
                )
            )
        catalog.append(
            (
                f"NP{poles}XL",
                "jumboPLUG",
                poles,
                "",
                f'1/4" jumboPLUG for thick instrument and loudspeaker cable, {poles_name}',
                [4.0, 10.0],
                17.0,
                12.0,
            )
        )
    catalog.append(
        (
            "NP2X-AU-SILENT",
            "silentPLUG",
            2,
            "",
            '1/4" silentPLUG with muting switch, mono (TS)',
            [4.0, 7.0],
            14.5,
            9.0,
        )
    )
    for mpn, series, poles, finish, desc, cable_od, handle_dia, bushing_dia in catalog:
        if mpn.endswith("-AU-SILENT") or finish == "B":
            plating = "Au"
        else:
            plating = "Ni"
        yield {
            "mpn": mpn,
            "family": "TRS",
            "series": series,
            "poles": poles,
            "gender": "male",
            "finish": finish,
            "palette": HOUSING_PALETTES[finish],
            "bushing": "white" if finish == "WT" else "black",
            "housing_material": "zinc diecast (ZnAl4Cu1)",
            "termination": "solder cup",
            "cable_od_mm": cable_od,
            "contact_names": ["T", "R", "S"] if poles == 3 else ["T", "S"],
            "tools": ["Soldering iron"],
            "source": PHONE_SOURCE,
            "product_desc": desc,
            "plating_override": plating,
            "handle_dia": handle_dia,
            "bushing_dia": bushing_dia,
        }


def _speakon_configurations():
    for (
        mpn,
        series,
        poles,
        gender,
        finish,
        bushing,
        desc,
        cable_od,
        body_dia,
        total_length,
        bushing_dia,
        palette_override,
    ) in SPEAKON_CATALOG:
        contacts = []
        for pair in range(1, poles // 2 + 1):
            contacts.append(f"{pair}+")
            contacts.append(f"{pair}-")
        tools = (
            ["HTFAC hand tool"]
            if series == "FC"
            else ["2.5 mm flat-blade screwdriver"]
        )
        yield {
            "mpn": mpn,
            "family": "speakON",
            "series": series,
            "poles": poles,
            "gender": gender,
            "finish": finish,
            "palette": palette_override or HOUSING_PALETTES[finish],
            "bushing": bushing,
            "housing_material": "glass-reinforced polyamide"
            if palette_override == "plastic"
            else "zinc diecast (ZnAl4Cu1)",
            "termination": "screw terminal",
            "cable_od_mm": list(cable_od),
            "contact_names": contacts,
            "tools": tools,
            "source": SPEAKON_SOURCE,
            "product_desc": desc,
            "body_dia": body_dia,
            "total_length": total_length,
            "bushing_dia": bushing_dia,
        }


_BUILDERS = {
    "XLR": _xlr_configurations,
    "etherCON": _ethercon_configurations,
    "powerCON": _powercon_configurations,
    "TRS": _phone_configurations,
    "speakON": _speakon_configurations,
}


def iter_part_configurations(families=None):
    """Yield one catalog dict per legal SKU. No geometry."""
    for family, builder in _BUILDERS.items():
        if families and family not in families:
            continue
        yield from builder()


def make_part_number(cfg):
    return cfg["mpn"]


def official_pin(cfg):
    return cfg["mpn"]


def description_from_cfg(cfg):
    bits = [f"NEUTRIK {cfg['family'].upper()} CABLE CONNECTOR"]
    if cfg["family"] != "powerCON":
        bits.append(f"{cfg['poles']} POLE")
    bits.append(cfg["gender"].upper())
    bits.append(HOUSING_NAMES[cfg["finish"]].upper())
    return ", ".join(bits)


CATALOG_COLUMNS = (
    "library_pn",
    "official_pin",
    "family",
    "series",
    "poles",
    "gender",
    "finish",
    "bushing",
    "termination",
    "contacts",
    "cable_od_min_mm",
    "cable_od_max_mm",
    "housing_material",
    "datasheet",
    "product_desc",
)


def catalog_row(cfg):
    cable = cfg["cable_od_mm"]
    return {
        "library_pn": cfg["mpn"],
        "official_pin": cfg["mpn"],
        "family": cfg["family"],
        "series": cfg["series"],
        "poles": cfg["poles"],
        "gender": cfg["gender"],
        "finish": cfg["finish"] or "nickel",
        "bushing": cfg["bushing"],
        "termination": cfg["termination"],
        "contacts": " ".join(cfg["contact_names"]),
        "cable_od_min_mm": cable[0],
        "cable_od_max_mm": cable[1],
        "housing_material": cfg["housing_material"],
        "datasheet": cfg["source"],
        "product_desc": cfg.get("product_desc", ""),
    }


def _catalog_index():
    return {cfg["mpn"]: cfg for cfg in iter_part_configurations()}


CATALOG = _catalog_index()


# ---------------------------------------------------------------------------
# Chooser
# ---------------------------------------------------------------------------
def parse_neutrik(part_number):
    """Parse a Neutrik cable-connector PN sold in this library."""
    mpn = _normalize_pn(part_number)
    cfg = CATALOG.get(mpn)
    if cfg is None:
        raise ValueError(
            f"Could not parse {part_number!r} as a Neutrik cable connector "
            f"in this library. Legal PNs: {', '.join(list_parts())}."
        )
    return dict(cfg)


def choose_part(
    family=None,
    poles=None,
    gender=None,
    finish=None,
    series=None,
    bushing=None,
    mpn=None,
):
    """
    Choose a Neutrik cable connector that exists in this library.

    family:
      XLR, etherCON, powerCON, TRS, speakON (aliases: ether, phone, speak, …)
    poles:
      Contact count (3 for XLR3 / powerCON, 8 for etherCON, …)
    gender:
      male / female / M / F / plug / jack
    finish:
      nickel (default when omitted), B / black chrome, BAG, WT / white
    series:
      XX, CAT5e, CAT6A, powerCON TRUE1, PX, jumboPLUG, X, FC, STX, …
    bushing:
      speakON / powerCON bushing color (blue, grey, red, …)
    mpn:
      Vendor / library PN. When set, the other filters must match that SKU.

    Returns the library PN. Raises ValueError if zero or several SKUs match.
    """
    if mpn is not None:
        matches = [parse_neutrik(mpn)]
    else:
        matches = list(iter_part_configurations())
    if family is not None:
        family_name = _normalize_family(family)
        matches = [cfg for cfg in matches if cfg["family"] == family_name]
    if poles is not None:
        matches = [cfg for cfg in matches if cfg["poles"] == int(poles)]
    if gender is not None:
        sex = _normalize_gender(gender)
        matches = [cfg for cfg in matches if cfg["gender"] == sex]
    if finish is not None:
        code = _normalize_finish(finish)
        matches = [cfg for cfg in matches if cfg["finish"] == code]
    elif family is not None and _normalize_family(family) in {"XLR", "TRS", "speakON"}:
        matches = [cfg for cfg in matches if cfg["finish"] == ""]
    if series is not None:
        series_key = str(series).strip()
        matches = [
            cfg
            for cfg in matches
            if cfg["series"] == series_key
            or cfg["series"].lower() == series_key.lower()
        ]
    if bushing is not None:
        color = str(bushing).strip().lower()
        matches = [cfg for cfg in matches if cfg["bushing"] == color]
    return _require_unique(matches, locals())


def find_mating_connector(
    part_number,
    override_gender=None,
    override_finish=None,
):
    """
    Return the opposite-gender cable connector of the same series / finish
    when that mate is sold in this library.

    XLR XX: NC3FXX-B -> NC3MXX-B
    powerCON TRUE1: NAC3FX-W-TOP -> NAC3MX-W-TOP
    speakON STX: NLT4FX-BAG -> NLT4MX-BAG

    etherCON, TRS, classic powerCON, and speakON X/FC cable parts mate to
    chassis jacks that are not in this family — those raise ValueError.
    """
    parsed = parse_neutrik(part_number)
    gender = (
        _normalize_gender(override_gender)
        if override_gender is not None
        else _flip_gender(parsed["gender"])
    )
    finish = (
        _normalize_finish(override_finish)
        if override_finish is not None
        else parsed["finish"]
    )
    mate = _mate_mpn(parsed, gender, finish)
    if mate not in CATALOG:
        raise ValueError(
            f"No cable-side mate for {parsed['mpn']!r} in this library. "
            f"{parsed['family']} {parsed['gender']} typically mates to a "
            "chassis connector that is not catalogued here. "
            f"Legal PNs: {', '.join(list_parts(parsed['family']))}."
        )
    return mate


def compatible_mates(part_number):
    """Library PNs this cable connector can mate to, or empty if chassis-only."""
    try:
        return [find_mating_connector(part_number)]
    except ValueError:
        return []


def list_parts(family=None):
    """Library PNs, optionally filtered by family."""
    families = None
    if family is not None:
        families = [_normalize_family(family)]
    return [cfg["mpn"] for cfg in iter_part_configurations(families)]


def list_families():
    return list(FAMILIES)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _normalize_pn(part_number):
    text = str(part_number).strip().upper().replace(" ", "").replace("_", "-")
    if text in CATALOG:
        return text
    compact = text.replace("-", "")
    for mpn in CATALOG:
        if mpn.replace("-", "") == compact:
            return mpn
    match = _XLR_RE.match(text.replace("-", "", 1) if text.count("-") == 1 else text)
    if match:
        poles = match.group("poles")
        gender = match.group("gender").upper()
        finish = (match.group("finish") or "").upper()
        suffix = f"-{finish}" if finish else ""
        candidate = f"NC{poles}{gender}XX{suffix}"
        if candidate in CATALOG:
            return candidate
    return text


def _normalize_family(family):
    key = str(family).strip().upper().replace(" ", "").replace("-", "")
    if key not in _FAMILY_ALIASES:
        raise ValueError(
            f"Unknown family {family!r}. Expected one of: {', '.join(FAMILIES)}."
        )
    return _FAMILY_ALIASES[key]


def _normalize_gender(gender):
    key = str(gender).strip().upper().replace(" ", "").replace("-", "")
    if key not in _GENDER_ALIASES:
        raise ValueError(
            f"Unknown gender {gender!r}. Expected M/F, male/female, or plug/jack."
        )
    return _GENDER_ALIASES[key]


def _normalize_finish(finish):
    if finish is None:
        return ""
    key = str(finish).strip().upper().replace(" ", "").replace("-", "")
    if key not in _FINISH_ALIASES:
        raise ValueError(
            f"Unknown finish {finish!r}. Expected nickel, B, BAG, or WT."
        )
    return _FINISH_ALIASES[key]


def _flip_gender(gender):
    return "male" if gender == "female" else "female"


def _mate_mpn(parsed, gender, finish):
    family = parsed["family"]
    suffix = f"-{finish}" if finish else ""
    if family == "XLR":
        code = "M" if gender == "male" else "F"
        return f"NC{parsed['poles']}{code}XX{suffix}"
    if family == "powerCON" and parsed.get("true1"):
        body = "MX" if gender == "male" else "FX"
        tail = parsed["mpn"].split("-", 1)[1]  # W, W-TOP, W-TOP-L
        return f"NAC3{body}-{tail}"
    if family == "speakON" and parsed["series"] == "STX":
        code = "MX" if gender == "male" else "FX"
        return f"NLT{parsed['poles']}{code}{suffix}"
    return ""


def _require_unique(matches, filters):
    if len(matches) == 1:
        return matches[0]["mpn"]
    interesting = {
        key: value
        for key, value in filters.items()
        if key in {"family", "poles", "gender", "finish", "series", "bushing", "mpn"}
        and value is not None
    }
    pns = [cfg["mpn"] for cfg in matches]
    if not matches:
        raise ValueError(
            f"No Neutrik cable connector matches {interesting}. "
            f"Legal PNs: {', '.join(list_parts())}."
        )
    raise ValueError(
        f"Several Neutrik cable connectors match {interesting}: {', '.join(pns)}. "
        "Add poles / gender / finish / series / bushing until one remains."
    )


if __name__ == "__main__":
    raise SystemExit(
        "neutrik.py is the chooser. Emit SKUs with: python neutrik_generator.py"
    )
