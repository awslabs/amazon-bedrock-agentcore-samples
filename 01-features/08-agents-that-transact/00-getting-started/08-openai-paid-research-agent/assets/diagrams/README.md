# Diagram Assets

The SVG files are the editable, publication-quality sources. Standard PNGs are
1600 x 900, and the `@2x.png` files are 3200 x 1800 exports for high-density
displays and publishing systems that do not accept SVG.

## Assets

- `paid-research-architecture`: three-agent manager workflow and end-to-end
  x402 payment sequence.
- `agentcore-openai-paid-research.drawio`: AWS reference architecture with
  official service icons, external provider boundaries, and a numbered flow
  legend. The editable source is in `../../docs/`.
- `three-control-layers`: editorial overview of research, merchant, and
  financial policy around the premium specialist.

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
```

The palette uses AWS orange for the payment boundary, green for the research
lead, blue for public research, and purple for premium research. All essential
distinctions are also expressed with labels and structure rather than color
alone.
