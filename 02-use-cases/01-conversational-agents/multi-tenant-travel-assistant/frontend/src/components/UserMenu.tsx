/**
 * The signed-in traveller chip at the foot of the sidebar: who you are, and the way out.
 *
 * Shows the tenant and traveller id (both from the verified session, never a name typed anywhere) and
 * a sign-out action. Deliberately plain — identity here is a fact to display, not something the UI
 * lets you change.
 */
import type { Session } from '../lib/api';
import { LogoutIcon, UserIcon } from './icons';

export interface UserMenuProps {
  session: Session;
  onSignOut: () => void;
}

export function UserMenu({ session, onSignOut }: UserMenuProps) {
  return (
    <div className="user-menu">
      <span className="user-avatar" aria-hidden="true">
        <UserIcon size={18} />
      </span>
      <span className="user-detail">
        <span className="user-name">{session.username ?? session.traveler_id}</span>
        {session.role && <span className="user-role">{session.role}</span>}
      </span>
      <button
        type="button"
        className="icon-btn"
        onClick={onSignOut}
        aria-label="Sign out"
        title="Sign out"
      >
        <LogoutIcon size={18} />
      </button>
    </div>
  );
}
