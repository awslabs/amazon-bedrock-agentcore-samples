'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { getCurrentUser, fetchUserAttributes, signOut } from 'aws-amplify/auth';
import outputs from '../../../../amplify_outputs.json';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import { Assistant, type AssistantConfig } from '../../components/assistant';

interface AssistantClientProps {
  assistantConfig: AssistantConfig;
}

function AssistantContent({ assistantConfig }: { assistantConfig: AssistantConfig }) {
  const [userName, setUserName] = useState('Guest User');
  const effectRan = useRef(false);
  const router = useRouter();

  useEffect(() => {
    if (effectRan.current) return;
    effectRan.current = true;

    (async () => {
      try {
        const currentUser = await getCurrentUser();
        const loginId = currentUser.signInDetails?.loginId || '';
        const fallbackName = loginId.split('@')[0];
        setUserName(fallbackName.charAt(0).toUpperCase() + fallbackName.slice(1).toLowerCase());

        const attrs = await fetchUserAttributes();
        if (attrs.name) setUserName(attrs.name);
      } catch {
        // user not authenticated or error — keep Guest User
      }
    })();
  }, []);

  const handleSignOut = async () => {
    try {
      await signOut();
      router.push('/app');
    } catch (err) {
      console.error('Error signing out:', err);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-white">
      {/* Header bar */}
      <header
        className="flex items-center justify-between px-5 sm:px-6 py-3"
        style={{
          borderBottom: '1px solid rgba(124,58,237,0.08)',
          background: 'linear-gradient(180deg, rgba(124,58,237,0.03) 0%, rgba(255,255,255,1) 100%)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <h1 className="text-lg sm:text-xl font-semibold text-purple-700" style={{ letterSpacing: '-0.01em' }}>{assistantConfig.appName}</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-700 hidden sm:inline">{userName}</span>
          <button
            onClick={handleSignOut}
            className="p-1.5"
            style={{
              color: '#7c3aed',
              cursor: 'pointer',
              background: 'none',
              border: 'none',
              transition: 'color 0.15s',
            }}
            aria-label="Sign out"
            title="Sign out"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3-3l3-3m0 0l-3-3m3 3H9" />
            </svg>
          </button>
        </div>
      </header>

      {/* Chat area — takes remaining space; min-h-0 lets flex child shrink so inner scroll works */}
      <main className="flex-1 min-h-0 overflow-hidden">
        <Assistant
          config={assistantConfig}
          identityPoolId={outputs.auth.identity_pool_id}
          userPoolId={outputs.auth.user_pool_id}
        />
      </main>

      {/* Footer */}
      <footer className="text-center" style={{ padding: '8px 16px 12px' }}>
        <p style={{ fontSize: '0.8125rem', color: '#6b7280', margin: '0 0 6px', lineHeight: 1.5 }}>
          &copy;{new Date().getFullYear()}, Amazon Web Services, Inc. or its affiliates. All rights reserved.
        </p>
        <img
          src="/images/Powered-By_logo-horiz_RGB.png"
          alt="Powered by AWS"
          style={{ height: 26, margin: '0 auto', display: 'block', paddingBottom: 2 }}
        />
      </footer>
    </div>
  );
}

export function AssistantClient({ assistantConfig }: AssistantClientProps) {
  return (
    <ProtectedRoute>
      <AssistantContent assistantConfig={assistantConfig} />
    </ProtectedRoute>
  );
}
