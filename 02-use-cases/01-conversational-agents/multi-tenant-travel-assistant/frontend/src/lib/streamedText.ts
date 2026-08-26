/**
 * The active assistant prose, kept outside transcript state while it streams.
 *
 * Updating the full conversation for every model chunk makes React re-render old turns, cards and
 * Markdown repeatedly. This store publishes at most once per animation frame, so only the active
 * prose subscriber updates while the browser still gets regular chances to paint it. If an upstream
 * layer coalesces several tokens into one large event, it drains that event at a readable pace rather
 * than turning an otherwise-streamed answer into a visual dump.
 */
export class StreamedTextStore {
  private static readonly CHARACTERS_PER_SECOND = 300;
  private static readonly MINIMUM_CHARS_PER_FRAME = 4;

  private visible = '';
  private pending = '';
  private frame: number | undefined;
  private lastPaintAt: number | undefined;
  private listeners = new Set<() => void>();
  private settled = new Set<(text: string) => void>();

  /** The text currently visible to React. */
  getSnapshot = (): string => this.visible;

  /** All received text, including chunks waiting for the next animation frame. */
  current(): string {
    return this.visible + this.pending;
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  append(chunk: string): void {
    if (!chunk) return;
    this.pending += chunk;
    this.schedulePaint();
  }

  /** Make queued text visible now, returning the complete answer for error recovery. */
  flush(): string {
    if (this.pending) {
      this.visible += this.pending;
      this.pending = '';
      this.notify();
    }
    this.resolveSettled();
    return this.visible;
  }

  /**
   * Finish revealing the text before the completed turn shows its cards.
   *
   * This is deliberately different from `flush()`: a complete response may have arrived in one
   * coarse event even though the model generated it incrementally. Letting the queued text drain
   * preserves the perception of streaming without inventing a network delay.
   */
  settle(): Promise<string> {
    if (!this.pending && this.frame === undefined) return Promise.resolve(this.visible);
    return new Promise((resolve) => {
      this.settled.add(resolve);
      this.schedulePaint();
    });
  }

  reset(): void {
    if (this.frame !== undefined && typeof window !== 'undefined') {
      window.cancelAnimationFrame(this.frame);
    }
    this.frame = undefined;
    this.lastPaintAt = undefined;
    const changed = Boolean(this.visible || this.pending);
    this.visible = '';
    this.pending = '';
    if (changed) this.notify();
    this.resolveSettled();
  }

  private schedulePaint(): void {
    if (this.frame !== undefined) return;
    // The SPA is browser-only, but flushing immediately keeps this tiny store safe in non-DOM tests.
    if (typeof window === 'undefined') {
      this.flush();
      return;
    }
    this.frame = window.requestAnimationFrame(() => {
      this.frame = undefined;
      this.paint();
    });
  }

  private paint(): void {
    if (!this.pending) {
      this.resolveSettled();
      return;
    }

    const now = typeof performance === 'undefined' ? Date.now() : performance.now();
    const elapsed =
      this.lastPaintAt === undefined ? 1000 / 60 : Math.max(now - this.lastPaintAt, 1000 / 60);
    const budget = Math.max(
      StreamedTextStore.MINIMUM_CHARS_PER_FRAME,
      Math.ceil((StreamedTextStore.CHARACTERS_PER_SECOND * elapsed) / 1000),
    );
    const length = this.readableChunkLength(budget);
    this.visible += this.pending.slice(0, length);
    this.pending = this.pending.slice(length);
    this.lastPaintAt = now;
    this.notify();

    if (this.pending) this.schedulePaint();
    else {
      this.lastPaintAt = undefined;
      this.resolveSettled();
    }
  }

  /** Prefer a nearby word boundary so a large coalesced event still reads naturally while animating. */
  private readableChunkLength(budget: number): number {
    if (this.pending.length <= budget) return this.pending.length;

    const before = this.pending.lastIndexOf(' ', budget);
    if (before >= Math.ceil(budget / 2)) return before + 1;

    const after = this.pending.indexOf(' ', budget);
    if (after !== -1 && after <= budget + StreamedTextStore.MINIMUM_CHARS_PER_FRAME)
      return after + 1;

    return budget;
  }

  private resolveSettled(): void {
    if (this.pending || this.frame !== undefined) return;
    for (const resolve of this.settled) resolve(this.visible);
    this.settled.clear();
  }

  private notify(): void {
    for (const listener of this.listeners) listener();
  }
}
