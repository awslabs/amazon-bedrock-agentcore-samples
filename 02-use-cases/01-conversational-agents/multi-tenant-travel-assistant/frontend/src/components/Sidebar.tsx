/**
 * The left rail: brand, new-conversation action, and the traveller chip.
 *
 * A pure layout composition — it owns none of the data, just arranges the pieces and, on narrow
 * screens, slides in over a scrim. The `open`/`onClose` props drive that mobile behaviour; on desktop
 * it is always present.
 */
import type { Session } from '../lib/api';
import { Wordmark } from './Brand';
import { EditIcon } from './icons';
import { UserMenu } from './UserMenu';

export interface SidebarProps {
  session: Session;
  open: boolean;
  onNewConversation: () => void;
  onSignOut: () => void;
  onClose: () => void;
}

export function Sidebar({ session, open, onNewConversation, onSignOut, onClose }: SidebarProps) {
  const newConversation = () => {
    onNewConversation();
    onClose();
  };

  return (
    <>
      <div className={open ? 'scrim open' : 'scrim'} onClick={onClose} aria-hidden="true" />
      <aside className={open ? 'sidebar open' : 'sidebar'}>
        <div className="sidebar-head">
          <Wordmark />
        </div>
        <button type="button" className="btn new-conversation" onClick={newConversation}>
          <EditIcon size={17} />
          New conversation
        </button>
        <UserMenu session={session} onSignOut={onSignOut} />
      </aside>
    </>
  );
}
