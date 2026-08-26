/**
 * The slim top bar of the main column.
 *
 * Mostly chrome: a menu button that reveals the sidebar on narrow screens, the current context, and
 * the theme toggle. On desktop the menu button is hidden — the sidebar is always there.
 */
import { MenuIcon } from './icons';
import { ThemeToggle } from './ThemeToggle';

export interface TopBarProps {
  onMenu: () => void;
  /** The tenant the traveller belongs to, shown as the workspace name beside the title. */
  tenant?: string;
}

export function TopBar({ onMenu, tenant }: TopBarProps) {
  return (
    <header className="topbar">
      <button type="button" className="icon-btn menu-btn" onClick={onMenu} aria-label="Open menu">
        <MenuIcon />
      </button>
      {tenant && <span className="topbar-tenant">{tenant}</span>}
      <span className="topbar-title">Travel assistant</span>
      <div className="topbar-actions">
        <ThemeToggle />
      </div>
    </header>
  );
}
