/**
 * The empty state: a greeting and a few starting points.
 *
 * Suggestions are tiles with an icon and a one-line intent, not bare chips — they teach what the
 * assistant is *for* (policy, search, trips, entry rules) at a glance, which a plain input box never
 * does. Clicking one sends it as the first turn.
 */
import { Logomark } from './Brand';
import { PlaneIcon, PolicyIcon, TripIcon, PassportIcon } from './icons';
import type { ComponentType } from 'react';

interface Suggestion {
  icon: ComponentType<{ size?: number }>;
  title: string;
  prompt: string;
}

const SUGGESTIONS: Suggestion[] = [
  { icon: PolicyIcon, title: 'Check my policy', prompt: 'What is my hotel nightly cap?' },
  { icon: PlaneIcon, title: 'Find a flight', prompt: 'Find me a flight to London on 10 November' },
  { icon: TripIcon, title: 'See my trips', prompt: 'Show me my trips' },
  { icon: PassportIcon, title: 'Entry rules', prompt: 'Do I need a visa for Japan?' },
];

export function Welcome({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="welcome">
      <div className="welcome-mark">
        <Logomark size={52} />
      </div>
      <h1 className="welcome-title">Where are we headed?</h1>
      <p className="welcome-sub">
        Ask about your trips, check what is in policy, search flights and hotels, or book — in plain
        language.
      </p>

      <div className="suggestions">
        {SUGGESTIONS.map(({ icon: Icon, title, prompt }) => (
          <button key={title} type="button" className="suggestion" onClick={() => onPick(prompt)}>
            <span className="suggestion-icon">
              <Icon size={18} />
            </span>
            <span className="suggestion-text">
              <span className="suggestion-title">{title}</span>
              <span className="suggestion-prompt">{prompt}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
