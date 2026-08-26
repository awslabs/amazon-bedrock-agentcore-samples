/**
 * The app shell: sign in, ask, read, click.
 *
 * **The UI does not branch on tenant anywhere.** It renders what the cards say — which is what makes
 * the two-tenant contrast visible without the frontend knowing that tenants exist. Globex's booking
 * summary carries confirm/decline actions and Initech's carries a checkout link, and the difference
 * comes entirely from the card.
 *
 * There is also no token in this file, or anywhere in the SPA. The session is an httpOnly cookie the
 * browser attaches on its own, so an XSS bug here finds nothing to exfiltrate.
 *
 * This file only *composes* — every visible piece is its own component under `components/`. It owns
 * the session check and wires the conversation hook to the shell.
 */
import { useEffect, useState } from 'react';
import './styles/index.css';
import { Composer } from './components/Composer';
import { Sidebar } from './components/Sidebar';
import { SignIn } from './components/SignIn';
import { TopBar } from './components/TopBar';
import { Transcript } from './components/Transcript';
import { currentSession, logout, type Session } from './lib/api';
import { useConversation } from './lib/useConversation';

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const { turns, pills, busy, send, act, startNew, streamedText, spentActions } = useConversation();

  useEffect(() => {
    currentSession().then(setSession);
  }, []);

  // `null` means "not known yet", distinct from "signed out" — rendering the sign-in screen during
  // the check would flash it at an already-authenticated traveller on every load.
  if (session === null) return <div className="boot" />;
  if (!session.authenticated) return <SignIn />;

  const submit = (text: string) => {
    if (busy) return;
    send(text);
  };

  return (
    <div className="shell">
      <Sidebar
        session={session}
        open={menuOpen}
        onNewConversation={startNew}
        onSignOut={() => logout().then(() => setSession({ authenticated: false }))}
        onClose={() => setMenuOpen(false)}
      />

      <main className="app">
        <TopBar onMenu={() => setMenuOpen(true)} tenant={session.tenant_id} />
        <Transcript
          turns={turns}
          pills={pills}
          busy={busy}
          onAction={act}
          onPick={submit}
          streamedText={streamedText}
          spentActions={spentActions}
        />
        <Composer busy={busy} onSend={submit} />
      </main>
    </div>
  );
}
