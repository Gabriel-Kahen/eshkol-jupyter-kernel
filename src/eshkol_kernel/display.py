from __future__ import annotations

import html
import json
from typing import Any

SUPPORTED_DISPLAY_FORMATS = {
    "html": "text/html",
    "json": "application/json",
    "latex": "text/latex",
    "markdown": "text/markdown",
    "md": "text/markdown",
    "png": "image/png",
    "png-base64": "image/png",
    "svg": "image/svg+xml",
    "text": "text/plain",
}
DisplayPayloadResult = tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]


def parse_display_payload(payload: dict[str, Any]) -> DisplayPayloadResult | None:
    payload_type = payload.get("type")
    if payload_type == "display_data":
        return parse_raw_display_data(payload)
    if payload_type == "eshkol_display":
        return parse_eshkol_display(payload)
    if payload_type == "eshkol_pretty":
        return parse_eshkol_pretty(payload)
    if payload_type == "eshkol_table":
        return parse_eshkol_table(payload)
    if payload_type == "eshkol_tree":
        return parse_eshkol_tree(payload)
    return None


def parse_raw_display_data(payload: dict[str, Any]) -> DisplayPayloadResult | None:
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    return data, clean_metadata(payload.get("metadata")), clean_transient(payload.get("transient"))


def parse_eshkol_display(payload: dict[str, Any]) -> DisplayPayloadResult | None:
    display_format = payload.get("format")
    value = payload.get("value")
    if not isinstance(display_format, str):
        return None
    mime_type = SUPPORTED_DISPLAY_FORMATS.get(display_format.lower())
    if mime_type is None:
        return None

    explicit_plain = "text/plain" in payload or "text" in payload
    plain = payload.get("text/plain", payload.get("text", plain_text(value)))
    data: dict[str, Any] = {"text/plain": str(plain)}
    if mime_type == "application/json":
        parsed_json = json_value(value)
        data[mime_type] = parsed_json
        if not explicit_plain:
            data["text/plain"] = pretty_json(parsed_json)
    else:
        data[mime_type] = str(value)
    return data, clean_metadata(payload.get("metadata")), clean_transient(payload.get("transient"))


def parse_eshkol_pretty(payload: dict[str, Any]) -> DisplayPayloadResult:
    value = payload.get("value")
    data: dict[str, Any] = {"text/plain": pretty_text(value)}
    if isinstance(value, (dict, list, int, float, bool)) or value is None:
        data["application/json"] = value
    return data, clean_metadata(payload.get("metadata")), clean_transient(payload.get("transient"))


def parse_eshkol_table(payload: dict[str, Any]) -> DisplayPayloadResult | None:
    columns = payload.get("columns")
    rows = payload.get("rows")
    if not isinstance(columns, list) or not all(is_scalar(column) for column in columns):
        return None
    if not isinstance(rows, list) or not all(isinstance(row, list) for row in rows):
        return None
    string_columns = [plain_text(column) for column in columns]
    string_rows = [[plain_text(cell) for cell in row] for row in rows]
    data = {
        "text/plain": table_to_text(string_columns, string_rows),
        "text/html": table_to_html(string_columns, string_rows),
    }
    return data, clean_metadata(payload.get("metadata")), clean_transient(payload.get("transient"))


def parse_eshkol_tree(payload: dict[str, Any]) -> DisplayPayloadResult:
    value = payload.get("value")
    data = {
        "text/plain": tree_to_text(value),
        "text/html": tree_to_html(value),
    }
    return data, clean_metadata(payload.get("metadata")), clean_transient(payload.get("transient"))


def clean_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def clean_transient(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def pretty_text(value: Any) -> str:
    if isinstance(value, list):
        return list_to_scheme(value)
    if isinstance(value, dict):
        return pretty_json(value)
    return plain_text(value)


def list_to_scheme(value: list[Any]) -> str:
    return "(" + " ".join(pretty_text(item) for item in value) + ")"


def plain_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    if value is True:
        return "#t"
    if value is False:
        return "#f"
    if value is None:
        return "null"
    return str(value)


def is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def table_to_text(columns: list[str], rows: list[list[str]]) -> str:
    widths = [len(column) for column in columns]
    for row in rows:
        for index, cell in enumerate(row[: len(columns)]):
            widths[index] = max(widths[index], len(cell))

    def render_row(values: list[str]) -> str:
        padded = [value.ljust(widths[index]) for index, value in enumerate(values[: len(columns)])]
        padded.extend("".ljust(width) for width in widths[len(padded) :])
        return " | ".join(padded)

    separator = "-+-".join("-" * width for width in widths)
    lines = [render_row(columns), separator]
    lines.extend(render_row(row) for row in rows)
    return "\n".join(lines)


def table_to_html(columns: list[str], rows: list[list[str]]) -> str:
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = [html.escape(cell) for cell in row[: len(columns)]]
        cells.extend("" for _ in range(len(columns) - len(cells)))
        body_rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    return "<table><thead><tr>" + header + "</tr></thead><tbody>" + "".join(body_rows) + "</tbody></table>"


def tree_to_text(value: Any, indent: int = 0) -> str:
    prefix = "  " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}{plain_text(key)}")
                lines.append(tree_to_text(child, indent + 1))
            else:
                lines.append(f"{prefix}{plain_text(key)}: {plain_text(child)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for child in value:
            if isinstance(child, (dict, list)):
                lines.append(tree_to_text(child, indent))
            else:
                lines.append(f"{prefix}{plain_text(child)}")
        return "\n".join(lines)
    return f"{prefix}{plain_text(value)}"


def tree_to_html(value: Any) -> str:
    if isinstance(value, dict):
        items = "".join(
            f"<li><span>{html.escape(plain_text(key))}</span>{tree_to_html(child)}</li>"
            for key, child in value.items()
        )
        return f"<ul>{items}</ul>"
    if isinstance(value, list):
        items = "".join(f"<li>{tree_to_html(child)}</li>" for child in value)
        return f"<ul>{items}</ul>"
    return html.escape(plain_text(value))
