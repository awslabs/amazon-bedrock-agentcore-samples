# Diagram Assets

The SVG files are the editable, publication-quality sources. Standard PNGs are
1600 x 900, and the `@2x.png` files are 3200 x 1800 exports for high-density
displays and publishing systems that do not accept SVG.

## Assets

- `paid-research-architecture`: end-to-end technical architecture.
- `three-control-layers`: editorial overview of research, merchant, and
  financial policy.

## Export

```bash
rsvg-convert -w 3200 -h 1800 \
  assets/diagrams/paid-research-architecture.svg \
  -o assets/diagrams/paid-research-architecture@2x.png

rsvg-convert -w 3200 -h 1800 \
  assets/diagrams/three-control-layers.svg \
  -o assets/diagrams/three-control-layers@2x.png
```

The palette uses AWS orange and dark navy for the payment boundary, OpenAI
green for model-led research, blue for application policy, and purple for the
reader-facing research workflow. All essential distinctions are also expressed
with labels and structure rather than color alone.
