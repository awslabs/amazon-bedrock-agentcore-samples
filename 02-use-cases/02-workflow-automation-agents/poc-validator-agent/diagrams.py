"""
Regenerate the POC Validator architecture diagram PNG.

Requirements:
    brew install graphviz
    pip install diagrams

Usage:
    python3 diagrams.py
"""

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here in sys.path:
    sys.path.remove(_here)

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.network import CloudFront
from diagrams.aws.security import Cognito
from diagrams.aws.storage import S3
from diagrams.custom import Custom
from diagrams.onprem.client import User

GRAPH = {
    "bgcolor": "white",
    "pad": "0.5",
    "fontsize": "13",
    "fontname": "Helvetica",
    "splines": "ortho",
}
NODE = {"fontsize": "11", "fontname": "Helvetica"}
EDGE = {"fontsize": "9", "fontname": "Helvetica"}

_ICONS = os.path.join(_here, "icons")
ICON_RUNTIME = os.path.join(_ICONS, "agentcore-runtime.png")

_C_CLIENT = dict(bgcolor="#EBF5FB", style="rounded", pencolor="#90CAF9", penwidth="2")
_C_EDGE = dict(bgcolor="#EBF5FB", style="rounded", pencolor="#90CAF9", penwidth="2")
_C_WEB = dict(bgcolor="#FFF3E0", style="rounded", pencolor="#FFB74D", penwidth="2", margin="24")
_C_AGENTCORE = dict(bgcolor="#F0FFF4", style="rounded", pencolor="#81C995", penwidth="3", margin="28")
_C_GATEWAY_TARGET = dict(bgcolor="#F0FFF4", style="rounded", pencolor="#81C995", penwidth="2")
_C_SECURITY = dict(bgcolor="#FFF0F0", style="rounded", pencolor="#EF9A9A", penwidth="2")

with Diagram(
    "POC Validator | AWS Architecture | v1.1",
    filename=os.path.join(_here, "architecture"),
    show=False,
    direction="LR",
    graph_attr={**GRAPH, "nodesep": "0.7", "ranksep": "1.1", "size": "34,20"},
    node_attr=NODE,
    edge_attr=EDGE,
):
    user = User("Anyone with\nthe URL")

    with Cluster("CloudFront\n(single domain, 3 routed behaviors)", graph_attr=_C_EDGE):
        cdn = CloudFront("CloudFront +\nBasic Auth Function")

    with Cluster("Web layer", graph_attr=_C_WEB):
        site = S3("S3\nstatic page +\nshare/view.html")
        web_fn = Lambda("web-invoke Lambda\nPOST /api/invoke\nGET /share/*.json")
        views = Dynamodb("view-count table\n(3 views, 30d TTL)")
        web_fn >> Edge(label="atomic\nUpdateItem") >> views

    with Cluster("Amazon Bedrock AgentCore", graph_attr=_C_AGENTCORE):
        runtime = Custom("AgentCore Runtime\n5 phases + 2 optional", ICON_RUNTIME)
        memory = Custom("Memory\nSEMANTIC + SUMMARIZATION\n+ USER_PREFERENCE", ICON_RUNTIME)
        gateway = Custom("Gateway\nMCP, semantic search", ICON_RUNTIME)
        code_interp = Custom("Code Interpreter\naws.codeinterpreter.v1\n(what-if pricing, optional)", ICON_RUNTIME)
        knowledge_base = Custom("Knowledge Base (FMKB)\nPocValidatorFaqKB\n(FAQ search, optional)", ICON_RUNTIME)

        with Cluster("Policy Engine (Cedar)", graph_attr=_C_SECURITY):
            policy_note = Custom("read-only tools\nenforced, not prompted", ICON_RUNTIME)

        runtime >> Edge(label="session\nrecall\n(short + long term)") >> memory
        runtime >> Edge(label="MCP\ntools/call") >> gateway
        runtime >> Edge(style="dashed", label="sandbox exec\n(optional)") >> code_interp
        runtime >> Edge(style="dashed", label="Retrieve\n(optional)") >> knowledge_base
        gateway >> Edge(style="dashed", label="every call\nchecked") >> policy_note

    with Cluster("Identity", graph_attr=_C_SECURITY):
        cognito = Cognito("Cognito M2M\nOAuth client_credentials")

    with Cluster("Gateway target", graph_attr=_C_GATEWAY_TARGET):
        docs_fn = Lambda("aws-documentation\nMCP Lambda")

    with Cluster("Knowledge base source", graph_attr=_C_GATEWAY_TARGET):
        faq_bucket = S3("S3\nagentcore/faq/*.md")

    user >> Edge(label="HTTPS") >> cdn
    cdn >> Edge(label="default,\n/share/*") >> site
    cdn >> Edge(label="/api/invoke,\n/share/*.json\n(OAC-signed)") >> web_fn
    web_fn >> Edge(label="InvokeAgentRuntime\n(IAM, scoped)") >> runtime
    gateway >> Edge(label="Lambda\ninvoke") >> docs_fn
    gateway >> Edge(style="dashed", label="CUSTOM_JWT") >> cognito
    knowledge_base >> Edge(style="dashed", label="ingested from") >> faq_bucket
    web_fn >> Edge(style="dashed", label="share_url") >> site

# Cost: $0.02-0.08/review (Runtime+Bedrock) + fractions of a cent per what-if/FAQ call
# (Code Interpreter, Knowledge Base) + near-zero idle (Lambda/DynamoDB/S3 on-demand)
