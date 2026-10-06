"""The two tools for the model: `lookup` and `calculate`.

Both tools always return a dict and never raise. A problem becomes
{"error": "..."} that the model can read and react to.

`run_tool(name, arguments)` is the entry point for the loop: it takes the raw
`arguments` string from a tool call, checks its shape, runs the tool and
returns the result as a JSON string.
"""
import ast
import difflib
import json
import math
import operator
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parent / "data" / "corpus.jsonl"

# --------------------------------------------------------------------------
# Tool definitions, exactly as sent to the model (they are the same as in
# Part A of SUBMISSION.md; tests/test_tools_definitions.py checks that).
# --------------------------------------------------------------------------
FIELDS = ["founded_year", "area_km2", "population_2020", "population_2025",
          "budget_2025_million_tenge", "water_use_2025_megalitres", "schools",
          "pupils_2025_26", "paved_road_km", "water_tariff_2025_tenge_per_m3"]

UNITS = {
    "founded_year": "year",
    "area_km2": "km2",
    "population_2020": "residents",
    "population_2025": "residents",
    "budget_2025_million_tenge": "million tenge",
    "water_use_2025_megalitres": "megalitres",
    "schools": "schools",
    "pupils_2025_26": "pupils",
    "paved_road_km": "km",
    "water_tariff_2025_tenge_per_m3": "tenge per m3",
}
TARIFF_FIELD = "water_tariff_2025_tenge_per_m3"

LOOKUP_DEF = {"type": "function", "function": {
    "name": "lookup",
    "description": ("Look up ONE fact about ONE district of the Nine Rivers Region in the official 2025 profiles. "
                    "Returns a single number, its unit and the ids of the documents it came from. "
                    "Call it once for every number you need; never guess or remember numbers. "
                    "Old archived (2019) profiles are never used, and published corrections are already applied "
                    "(the 'note' field tells you when). Water use is always returned in megalitres, even if a profile "
                    "uses another unit. The water tariff is the same in every district: use district 'region'. "
                    "This tool does no arithmetic: use 'calculate' for that."),
    "parameters": {"type": "object", "properties": {
        "district": {"type": "string", "description": "Exact district name: Ossbridge, Ossford, Tarnvale, Kelmarsh, Brightwater, Stonecairn, Harrowfield, Lindenmoor, Redfen, Ashgrove, Millbrook or Coldharbour. Use 'region' only for water_tariff_2025_tenge_per_m3."},
        "field": {"type": "string", "enum": FIELDS, "description": "The fact to read. population_2020 and population_2025 are census counts; budget is in million tenge; pupils_2025_26 and schools are for the 2025/26 school year."}},
        "required": ["district", "field"], "additionalProperties": False}}}

CALC_DEF = {"type": "function", "function": {
    "name": "calculate",
    "description": ("Evaluate ONE arithmetic expression exactly and return the number. Allowed: numbers, + - * / and "
                    "parentheses, and a minus sign in front of a number. No variables, no functions, no powers. "
                    "Write the real numbers from 'lookup' into the expression, for example '44675 / 921.4'. "
                    "Use it for every calculation, even a simple one, and do not do arithmetic in your head. "
                    "Intermediate results are not rounded; give 'decimals' to get a rounded copy in 'rounded'."),
    "parameters": {"type": "object", "properties": {
        "expression": {"type": "string", "description": "The arithmetic expression, at most 200 characters, for example '(37203 / 34590 - 1) * 100'."},
        "decimals": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Optional. Number of decimal places for the 'rounded' value."}},
        "required": ["expression"], "additionalProperties": False}}}

TOOLS = [LOOKUP_DEF, CALC_DEF]


# ==========================================================================
# lookup
# ==========================================================================
def _num(text):
    """'1,284.6' -> 1284.6 ; '52,904' -> 52904"""
    text = text.replace(",", "")
    return float(text) if "." in text else int(text)


# Each profile is written in one of three sentence templates, so every field has
# a few patterns. The group number says which captured number to use.
PATTERNS = {
    "founded_year": [(r"[Ff]ounded in (\d{4})", 1)],
    "area_km2": [(r"([\d,]+(?:\.\d+)?) square kilometres", 1)],
    "population_2025": [(r"2025 census (?:recorded|counted) ([\d,]+) residents", 1),
                        (r"Census population: [\d,]+ in 2020 and ([\d,]+) in 2025", 1)],
    "population_2020": [(r"2020 census had recorded ([\d,]+)", 1),
                        (r"up from ([\d,]+) at the 2020 census", 1),
                        (r"Census population: ([\d,]+) in 2020 and", 1)],
    "budget_2025_million_tenge": [(r"([\d,]+(?:\.\d+)?) million tenge", 1)],
    "schools": [(r"There are (\d+) schools", 1), (r"has (\d+) schools", 1), (r"runs (\d+) schools", 1)],
    "pupils_2025_26": [(r"attended by ([\d,]+) pupils", 1), (r"enrolled ([\d,]+) pupils", 1),
                       (r"with ([\d,]+) pupils enrolled", 1)],
    "paved_road_km": [(r"network is ([\d,]+(?:\.\d+)?) km long", 1),
                      (r"keeps ([\d,]+(?:\.\d+)?) km of paved road", 1),
                      (r"maintains ([\d,]+(?:\.\d+)?) km of paved road", 1)],
}
# water use has a unit that differs between profiles
WATER_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s+(megalitres|cubic metres)")
WATER_ANY_RE = re.compile(r"(?:used|came to)\s+([\d,]+(?:\.\d+)?)\s+([A-Za-z ]+?)(?:\s+of water|\s+during|[.,])")
PROFILE_TITLE_RE = re.compile(r"^(\w+) district profile \((2025|ARCHIVED 2019)\)")
CORRECTION_TITLE_RE = re.compile(r"^Correction notice - (\w+)")
CORRECTION_TEXT_RE = re.compile(
    r"gives the district's (\w+) as ([\d,]+(?:\.\d+)?) [^.]*\.[^.]*\.\s*The correct \1 is ([\d,]+(?:\.\d+)?)")
CORRECTABLE = {"area": "area_km2"}      # what a correction notice may change
TARIFF_RE = re.compile(r"regional household water tariff is ([\d,]+(?:\.\d+)?) tenge per cubic metre")


class Facts:
    """All facts, read from the documents by code (nothing is typed by hand)."""

    def __init__(self, records):
        self.facts = {}          # district -> field -> dict(value, unit, source, note)
        self.archived = {}       # district -> id of its archived profile
        self.tariff = None       # dict(value, source)
        self.warnings = []       # things the parser could not use (shown in tests)
        self._parse(records)

    # ---- reading the documents ------------------------------------------
    def _parse(self, records):
        corrections = []
        for rec in records:
            title, text, rid = rec["title"], rec["text"], rec["id"]
            m = PROFILE_TITLE_RE.match(title)
            if m:
                district, edition = m.group(1), m.group(2)
                if edition == "ARCHIVED 2019":
                    self.archived[district] = rid       # superseded: never used for facts
                else:
                    self.facts[district] = self._parse_profile(district, rid, text)
                continue
            m = CORRECTION_TITLE_RE.match(title)
            if m:
                corrections.append((m.group(1), rid, text))
                continue
            t = TARIFF_RE.search(text)
            if t and self.tariff is None:
                self.tariff = {"value": _num(t.group(1)), "source": [rid]}
        for district, rid, text in corrections:
            self._apply_correction(district, rid, text)

    def _parse_profile(self, district, rid, text):
        out = {}
        for field, patterns in PATTERNS.items():
            for pattern, group in patterns:
                m = re.search(pattern, text)
                if m:
                    out[field] = {"value": _num(m.group(group)), "unit": UNITS[field],
                                  "source": [rid], "note": None, "error": None}
                    break
        w = WATER_RE.search(text)
        if w:
            value, unit = _num(w.group(1)), w.group(2)
            note = None
            if unit == "cubic metres":                  # 1 megalitre = 1,000 cubic metres
                note = f"{w.group(1)} cubic metres in {rid}, converted to megalitres (divided by 1,000)"
                value = value / 1000
            out["water_use_2025_megalitres"] = {"value": value, "unit": "megalitres",
                                                "source": [rid], "note": note, "error": None}
        else:
            any_unit = WATER_ANY_RE.search(text)
            if any_unit:
                out["water_use_2025_megalitres"] = {
                    "value": None, "unit": None, "source": [rid], "note": None,
                    "error": f"cannot read 'water_use_2025_megalitres' in {rid}: unknown unit '{any_unit.group(2).strip()}'"}
        return out

    def _apply_correction(self, district, rid, text):
        m = CORRECTION_TEXT_RE.search(text)
        if not m or m.group(1) not in CORRECTABLE or district not in self.facts:
            self.warnings.append(f"{rid}: correction not understood, ignored")
            return
        field = CORRECTABLE[m.group(1)]
        old, new = _num(m.group(2)), _num(m.group(3))
        fact = self.facts[district].get(field)
        if not fact or fact["value"] != old:            # only correct what the notice says is wrong
            self.warnings.append(f"{rid}: the profile does not say {old}, correction ignored")
            return
        fact["value"] = new
        fact["source"] = fact["source"] + [rid]
        fact["note"] = f"{rid} corrects the {m.group(1)} in {fact['source'][0]} from {m.group(2)} to {m.group(3)}; the corrected value is returned"

    # ---- names -----------------------------------------------------------
    @property
    def districts(self):
        return list(self.facts)

    def resolve(self, name):
        """Exact match only. Returns (canonical name, None) or (None, error message)."""
        cleaned = name.strip()
        if not cleaned:
            return None, "'district' is empty"
        if len(cleaned) > 100:
            return None, "'district' is too long (limit 100 characters)"
        for d in self.districts:
            if d.casefold() == cleaned.casefold():
                return d, None
        low = cleaned.casefold()
        prefix = [d for d in self.districts if len(low) >= 2 and d.casefold().startswith(low)]
        if len(prefix) >= 2:
            return None, f"'{cleaned}' could mean {_or(prefix)}; use the full name"
        close = difflib.get_close_matches(low, [d.casefold() for d in self.districts], n=3, cutoff=0.6)
        close = [d for d in self.districts if d.casefold() in close]
        suggestions = list(dict.fromkeys(prefix + close))
        if suggestions:
            return None, f"no district named '{cleaned}'; did you mean {_or(suggestions)}?"
        return None, f"no district named '{cleaned}'; valid districts: {', '.join(self.districts)}"


def _or(names):
    quoted = [f"'{n}'" for n in names]
    return quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + " or " + quoted[-1]


_DEFAULT = None


def default_facts():
    global _DEFAULT
    if _DEFAULT is None:
        records = [json.loads(line) for line in open(CORPUS_PATH, encoding="utf-8") if line.strip()]
        _DEFAULT = Facts(records)
    return _DEFAULT


def lookup(district, field, facts=None):
    """One fact about one district. Never raises."""
    try:
        facts = facts or default_facts()
        if not isinstance(district, str):
            return {"error": "'district' must be a string"}
        if not isinstance(field, str):
            return {"error": "'field' must be a string"}
        if field not in FIELDS:
            return {"error": f"unknown field '{field[:60]}'; valid fields: {', '.join(FIELDS)}"}

        # the tariff is the same everywhere
        if field == TARIFF_FIELD:
            if facts.tariff is None:
                return {"error": "the water tariff is not in the documents"}
            if district.strip().casefold() == "region":
                name = "region"
            else:
                name, err = facts.resolve(district)
                if err:
                    return {"error": err, "valid_districts": facts.districts}
            return {"district": name, "field": field, "value": facts.tariff["value"],
                    "unit": UNITS[field], "source": facts.tariff["source"],
                    "note": "the same tariff in every district (from 1 January 2025)"}

        if district.strip().casefold() == "region":
            return {"error": f"'region' can only be used with {TARIFF_FIELD}; give a district name"}
        name, err = facts.resolve(district)
        if err:
            return {"error": err, "valid_districts": facts.districts}
        fact = facts.facts[name].get(field)
        if fact is None:
            return {"error": f"cannot read '{field}' for {name}: not found in its 2025 profile"}
        if fact["error"]:
            return {"error": fact["error"]}
        notes = [n for n in (fact["note"],) if n]
        if name in facts.archived:
            notes.append(f"an archived 2019 profile ({facts.archived[name]}) also exists and was ignored")
        return {"district": name, "field": field, "value": fact["value"], "unit": fact["unit"],
                "source": fact["source"], "note": "; ".join(notes) or None}
    except Exception as exc:                            # a tool must never crash the loop
        return {"error": f"lookup failed: {type(exc).__name__}"}


# ==========================================================================
# calculate
# ==========================================================================
MAX_EXPRESSION = 200
MAX_NODES = 100
LIMIT = 1e15
BIN_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}
OP_NAMES = {ast.Pow: "**", ast.Mod: "%", ast.FloorDiv: "//", ast.MatMult: "@", ast.BitXor: "^",
            ast.BitAnd: "&", ast.BitOr: "|", ast.LShift: "<<", ast.RShift: ">>"}


class Refused(Exception):
    pass


def _describe(node):
    if isinstance(node, ast.Call):
        return "function call"
    if isinstance(node, ast.Attribute):
        return "attribute access"
    if isinstance(node, ast.Name):
        return f"name '{node.id}'"
    if isinstance(node, ast.Tuple):
        return "a comma (write numbers without thousands separators, for example 44675 not 44,675)"
    if isinstance(node, ast.Constant):
        return f"a {type(node.value).__name__} value"
    return type(node).__name__


def _check_size(x):
    if not math.isfinite(x) or abs(x) > LIMIT:
        raise Refused("number too large (limit 1e15)")
    return x


def _eval(node):
    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float):          # refuses bool, str, None, complex
            raise Refused(f"not allowed: {_describe(node)}")
        return _check_size(node.value)
    if isinstance(node, ast.BinOp):
        op = BIN_OPS.get(type(node.op))
        if op is None:
            sym = OP_NAMES.get(type(node.op), type(node.op).__name__)
            raise Refused(f"not allowed: operator '{sym}'")
        left, right = _eval(node.left), _eval(node.right)
        try:
            return _check_size(op(left, right))
        except ZeroDivisionError:
            raise Refused("division by zero")
    if isinstance(node, ast.UnaryOp):
        op = UNARY_OPS.get(type(node.op))
        if op is None:
            raise Refused(f"not allowed: operator {type(node.op).__name__}")
        return _check_size(op(_eval(node.operand)))
    raise Refused(f"not allowed: {_describe(node)}")


def calculate(expression, decimals=None):
    """Arithmetic with numbers, + - * / and brackets only. Never runs the text as code."""
    try:
        if not isinstance(expression, str):
            return {"error": "'expression' must be a string"}
        if decimals is not None and (isinstance(decimals, bool) or not isinstance(decimals, int)
                                     or not 0 <= decimals <= 10):
            return {"error": "'decimals' must be an integer from 0 to 10"}
        if len(expression) > MAX_EXPRESSION:
            return {"error": f"expression longer than {MAX_EXPRESSION} characters"}
        if not expression.strip():
            return {"error": "the expression is empty"}
        try:
            tree = ast.parse(expression.strip(), mode="eval")
        except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
            return {"error": f"cannot read the expression: {getattr(exc, 'msg', 'invalid syntax')}"}
        if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
            return {"error": "expression too complicated"}
        result = _eval(tree.body)
        rounded = None
        if decimals is not None:
            quantum = Decimal(1).scaleb(-decimals)
            rounded = float(Decimal(repr(result)).quantize(quantum, rounding=ROUND_HALF_UP))
        return {"result": result, "rounded": rounded}
    except Refused as exc:
        return {"error": str(exc)}
    except Exception as exc:                            # never crash the loop
        return {"error": f"calculate failed: {type(exc).__name__}"}


# ==========================================================================
# Entry point for the loop: raw arguments string in, JSON string out
# ==========================================================================
def run_tool(name, arguments):
    """`arguments` is the string the model sent. Returns a JSON string (always)."""
    defs = {d["function"]["name"]: d["function"] for d in TOOLS}
    try:
        if name not in defs:
            return json.dumps({"error": f"unknown tool '{str(name)[:40]}'; available tools: {', '.join(defs)}"})
        try:
            args = json.loads(arguments) if arguments not in (None, "") else {}
        except (json.JSONDecodeError, TypeError):
            return json.dumps({"error": "the arguments are not valid JSON"})
        if not isinstance(args, dict):
            return json.dumps({"error": "the arguments must be a JSON object"})
        schema = defs[name]["parameters"]
        missing = [k for k in schema["required"] if k not in args]
        extra = [k for k in args if k not in schema["properties"]]
        if missing:
            return json.dumps({"error": f"missing required argument(s): {', '.join(missing)}"})
        if extra:
            return json.dumps({"error": f"unexpected argument(s): {', '.join(extra)}"})
        func = lookup if name == "lookup" else calculate
        return json.dumps(func(**args))
    except Exception as exc:
        return json.dumps({"error": f"tool failed: {type(exc).__name__}"})
