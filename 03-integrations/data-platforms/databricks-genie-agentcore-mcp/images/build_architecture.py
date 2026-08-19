"""Regenerate architecture.svg for the databricks-genie-agentcore-mcp sample.

The committed architecture.svg embeds its icons as data URIs, so it is
self-contained: it renders in GitHub, in a browser, and through rsvg-convert
with no external assets. This script is the source used to produce it, so a
future icon refresh or layout change is an edit here rather than a rebuild by
hand.

AWS marks come from the official AWS Architecture Icons toolkit
(https://aws.amazon.com/architecture/icons/, 04302026 release). The toolkit
publishes a single Amazon Bedrock AgentCore mark with no per-capability
variants, so Runtime / Gateway / Identity each use that mark with a text
label -- the same convention as the AgentCore workshops in this repo.

Usage:
    python build_architecture.py --icons /path/to/unpacked/asset-package
    rsvg-convert -w 2064 architecture.svg -o architecture.png

ICON_SOURCES maps each diagram icon to its path inside the unpacked AWS
toolkit; Databricks marks come from the Databricks brand icon set.
"""

import argparse
import base64
import json
import os

ICON_SOURCES = {
    # AWS Architecture Icons toolkit (Asset-Package_04302026)
    "agentcore": "Architecture-Service-Icons_04302026/Arch_Artificial-Intelligence/64/Arch_Amazon-Bedrock-AgentCore_64.svg",
    "bedrock": "Architecture-Service-Icons_04302026/Arch_Artificial-Intelligence/64/Arch_Amazon-Bedrock_64.svg",
    "cognito": "Architecture-Service-Icons_04302026/Arch_Security-Identity/64/Arch_Amazon-Cognito_64.svg",
    "cloudwatch": "Architecture-Service-Icons_04302026/Arch_Management-Tools/64/Arch_Amazon-CloudWatch_64.svg",
    # Databricks brand icons
    "connectors": "databricks/connectors.png",
    "chat": "databricks/chat.png",
    "unity-catalog": "databricks/unity-catalog.png",
    "delta-table": "databricks/delta-table.png",
    "data-analyst-persona": "databricks/data-analyst-persona.png",
}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--icons",
    default=".",
    help="Root holding the unpacked AWS toolkit and a databricks/ folder.",
)
parser.add_argument("--cache", default="icons_b64.json", help="Data-URI cache.")
args = parser.parse_args()


def load_icons() -> dict:
    """Return {name: data-URI}, reading from source icons or a local cache."""
    if os.path.exists(args.cache):
        with open(args.cache) as f:
            return json.load(f)

    icons = {}
    for name, rel in ICON_SOURCES.items():
        path = os.path.join(args.icons, rel)
        if not os.path.exists(path):
            raise SystemExit(
                f"Icon not found: {path}\nPass --icons pointing at the unpacked AWS Architecture Icons asset package."
            )
        mime = "image/svg+xml" if path.endswith(".svg") else "image/png"
        with open(path, "rb") as f:
            blob = base64.b64encode(f.read()).decode()
        icons[name] = f"data:{mime};base64,{blob}"

    with open(args.cache, "w") as f:
        json.dump(icons, f)
    return icons


ICONS = load_icons()

W, H = 1720, 900

INK = "#232F3E"  # AWS squid ink, body text
MUTED = "#5A6B7B"  # secondary labels
LINE = "#57728B"
BOX_AWS_BG = "#FBF6EF"
BOX_AWS_EDGE = "#ED7100"
BOX_AC_BG = "#F1FAF8"
BOX_AC_EDGE = "#01A88D"
BOX_DBX_BG = "#FEF3F1"
BOX_DBX_EDGE = "#FF3621"

p = []
a = p.append

a(
    f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
    f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
    f'font-family="Helvetica Neue, Helvetica, Arial, sans-serif">'
)
a(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>')

a("<defs>")
a(
    f'<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
    f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{LINE}"/></marker>'
)
a(
    f'<marker id="ahd" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
    f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{MUTED}"/></marker>'
)
a("</defs>")


def box(x, y, w, h, label, bg, edge, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{bg}" stroke="{edge}" stroke-width="2"{d}/>')
    a(f'<text x="{x + 18}" y="{y + 27}" font-size="17" font-weight="600" fill="{edge}">{label}</text>')


def node(cx, cy, icon, title, sub=None, sub2=None, size=60):
    a(f'<image x="{cx - size / 2}" y="{cy - size / 2}" width="{size}" height="{size}" xlink:href="{ICONS[icon]}"/>')
    ty = cy + size / 2 + 21
    a(f'<text x="{cx}" y="{ty}" font-size="15.5" font-weight="600" fill="{INK}" text-anchor="middle">{title}</text>')
    if sub:
        a(f'<text x="{cx}" y="{ty + 18}" font-size="13.5" fill="{MUTED}" text-anchor="middle">{sub}</text>')
    if sub2:
        a(f'<text x="{cx}" y="{ty + 35}" font-size="13.5" fill="{MUTED}" text-anchor="middle">{sub2}</text>')


def arrow(x1, y1, x2, y2, dashed=False):
    d = ' stroke-dasharray="6 5"' if dashed else ""
    m = "ahd" if dashed else "ah"
    col = MUTED if dashed else LINE
    a(f'<path d="M {x1} {y1} L {x2} {y2}" fill="none" stroke="{col}" stroke-width="2"{d} marker-end="url(#{m})"/>')


def elbow(x1, y1, x2, y2, dashed=False):
    """Right-angle connector: horizontal from the source, then vertical."""
    d = ' stroke-dasharray="6 5"' if dashed else ""
    m = "ahd" if dashed else "ah"
    col = MUTED if dashed else LINE
    a(
        f'<path d="M {x1} {y1} L {x2} {y1} L {x2} {y2}" fill="none" stroke="{col}" '
        f'stroke-width="2"{d} marker-end="url(#{m})"/>'
    )


def label(x, y, text, anchor="middle", mono=False, small=False):
    fam = ' font-family="SFMono-Regular, Menlo, Consolas, monospace"' if mono else ""
    fs = 13 if small else 14
    a(f'<text x="{x}" y="{y}" font-size="{fs}" fill="{INK}" text-anchor="{anchor}"{fam}>{text}</text>')


# ---------------------------------------------------------------- title
a(
    f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}">'
    f"Databricks Genie as a governed MCP tool, via Amazon Bedrock AgentCore</text>"
)
a(
    f'<text x="40" y="73" font-size="15" fill="{MUTED}">'
    f"Machine-to-machine (client-credentials) auth end to end — Genie runs as a Databricks "
    f"service principal</text>"
)

# ---------------------------------------------------------------- end user
node(86, 292, "data-analyst-persona", "End user", "(business analyst)", size=56)

# ---------------------------------------------------------------- AWS account
box(190, 112, 800, 700, "AWS account", BOX_AWS_BG, BOX_AWS_EDGE)

# AgentCore boundary: Runtime -> Gateway across the top, Identity beneath Gateway.
box(216, 152, 700, 430, "Amazon Bedrock AgentCore", BOX_AC_BG, BOX_AC_EDGE)

node(350, 262, "agentcore", "AgentCore Runtime", "Strands agent", "(BedrockAgentCoreApp)")
node(760, 262, "agentcore", "AgentCore Gateway", "MCP endpoint", "mcpServer target")
node(760, 486, "agentcore", "AgentCore Identity", "outbound credential provider")

# Amazon Bedrock is a sibling of AgentCore, not its parent.
box(216, 620, 300, 170, "Amazon Bedrock", "#FFFFFF", MUTED, dash="5 4")
node(366, 700, "bedrock", "Claude / Nova", "model inference", size=52)

# Supporting services
node(700, 700, "cognito", "Amazon Cognito", "inbound auth", "(CUSTOM_JWT)", size=52)
node(893, 700, "cloudwatch", "CloudWatch", "traces / logs", size=52)

# ---------------------------------------------------------------- Databricks
box(1052, 112, 630, 620, "Databricks workspace on AWS", BOX_DBX_BG, BOX_DBX_EDGE)

node(1367, 232, "connectors", "Managed MCP server", "/api/2.0/mcp/genie/{space_id}", size=56)
node(1367, 402, "chat", "Genie space", "Trusted Assets", size=56)
node(1204, 600, "unity-catalog", "Unity Catalog", "permissions + lineage", size=56)
node(1532, 600, "delta-table", "Delta tables", "governed data", size=56)

# ---------------------------------------------------------------- flows
# end user -> Runtime
arrow(122, 288, 310, 268)
label(215, 268, "NL question")

# Runtime -> Gateway
arrow(400, 252, 720, 252)
label(560, 242, "MCP tool call")

# Gateway <-> Identity (vertical pair: request down, token back up)
arrow(748, 372, 748, 446)
label(739, 412, "GetResourceOauth2Token", anchor="end", small=True)
arrow(776, 446, 776, 372, dashed=True)
label(786, 412, "OAuth2 M2M token", anchor="start", small=True)

# Runtime -> Bedrock (model inference)
arrow(350, 312, 358, 662, dashed=True)
label(366, 480, "invoke model", anchor="start")

# Cognito -> Gateway (inbound JWT), into the Gateway's left edge
a(
    f'<path d="M 700 668 L 580 668 L 580 262 L 726 262" fill="none" stroke="{MUTED}" '
    f'stroke-width="2" stroke-dasharray="6 5" marker-end="url(#ahd)"/>'
)
label(570, 470, "JWT", anchor="end")

# Gateway -> CloudWatch, out of the Gateway's right edge
a(
    f'<path d="M 794 262 L 962 262 L 962 700 L 926 700" fill="none" stroke="{MUTED}" '
    f'stroke-width="2" stroke-dasharray="6 5" marker-end="url(#ahd)"/>'
)
label(972, 470, "traces", anchor="start")

# Gateway -> Databricks managed MCP (the governed hop)
arrow(800, 232, 1307, 222)
label(1035, 200, "MCP / HTTPS · client credentials")

# Managed MCP -> Genie
arrow(1367, 268, 1367, 364)
label(1379, 322, "invoke", anchor="start")

# Genie -> Unity Catalog
arrow(1335, 442, 1235, 552)
label(1247, 505, "governed SQL", anchor="end")

# Unity Catalog -> Delta
arrow(1240, 600, 1490, 600)
label(1365, 590, "authorized read")

# ---------------------------------------------------------------- footnote
a(
    f'<text x="1052" y="772" font-size="14" fill="{MUTED}">'
    f"Unity Catalog enforces the service principal’s permissions and audits SQL under that identity.</text>"
)
a(
    f'<text x="1052" y="793" font-size="14" fill="{MUTED}">'
    f"For per-user identity and attribution, see databricks-dbsql-per-user-delegation.</text>"
)

a("</svg>")

with open("architecture.svg", "w") as f:
    f.write("\n".join(p))
print("wrote architecture.svg")
