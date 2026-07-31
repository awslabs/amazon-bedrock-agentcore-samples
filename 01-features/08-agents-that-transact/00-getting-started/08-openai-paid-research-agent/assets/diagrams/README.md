# Diagram Assets

The SVG files are the editable, publication-quality sources. Standard PNGs are
1600 x 900, and the `@2x.png` files are 3200 x 1800 exports for high-density
displays and publishing systems that do not accept SVG.

## Assets

- `agentcore-openai-paid-research.drawio`: AWS reference architecture with
  official service icons and clearly separated application, AWS Cloud, and
  external-service boundaries. The editable source is in `../../docs/`.
- `agentcore-openai-paid-research-flow`: eight-step editorial workflow. The
  right-side turn keeps the request and payment phases readable without
  crossing labels.
- `paid-research-architecture`: earlier editorial overview of the three-agent
  manager workflow and x402 sequence.
- `three-control-layers`: research, merchant, and financial policy around the
  premium specialist.

## Export

```bash
rsvg-convert -w 3200 -h 1800 \
  assets/diagrams/paid-research-architecture.svg \
  -o assets/diagrams/paid-research-architecture@2x.png

rsvg-convert -w 3200 -h 1800 \
  assets/diagrams/three-control-layers.svg \
  -o assets/diagrams/three-control-layers@2x.png

drawio -x -f png -e -b 20 -s 2 \
  -o assets/diagrams/agentcore-openai-paid-research.drawio.png \
  docs/agentcore-openai-paid-research.drawio

drawio -x -f svg -e -b 20 \
  -o assets/diagrams/agentcore-openai-paid-research.drawio.svg \
  docs/agentcore-openai-paid-research.drawio

rsvg-convert -w 3600 -h 2000 \
  assets/diagrams/agentcore-openai-paid-research-flow.svg \
  -o assets/diagrams/agentcore-openai-paid-research-flow.png
```

The palette uses AWS orange for the payment boundary, green for the research
lead, blue for public research, and purple for premium research. All essential
distinctions are also expressed with labels and structure rather than color
alone.
