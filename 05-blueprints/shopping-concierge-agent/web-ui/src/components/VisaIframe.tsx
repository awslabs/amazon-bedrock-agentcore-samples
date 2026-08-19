import React, { useEffect, useRef, useState } from 'react';

interface VisaIframeProps {
  config: {
    iframeUrl: string;
    apiKey: string;
    clientAppId: string;
    locale: string;
    sessionId: string;
  };
  onTokenReceived: (token: string) => void;
  onError?: (error: string) => void;
}

export const VisaIframe: React.FC<VisaIframeProps> = ({ config, onTokenReceived, onError }) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [status, setStatus] = useState<string>('Loading...');

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Verify origin - must be exactly visa.com or a proper subdomain of visa.com
      try {
        const originUrl = new URL(event.origin);
        const hostname = originUrl.hostname;
        const isVisaDomain = hostname === 'visa.com' || hostname.endsWith('.visa.com');
        if (!isVisaDomain) return;
      } catch {
        return; // Invalid URL
      }

      console.log('Visa iframe message:', event.data);

      if (event.data.type === 'SECURE_TOKEN_RECEIVED') {
        setStatus('Token received!');
        onTokenReceived(event.data.secureToken);
      } else if (event.data.type === 'ERROR') {
        setStatus('Error occurred');
        onError?.(event.data.message);
      }
    };

    window.addEventListener('message', handleMessage);

    return () => window.removeEventListener('message', handleMessage);
  }, [onTokenReceived, onError]);

  useEffect(() => {
    // Send CREATE_AUTH_SESSION when iframe loads
    const iframe = iframeRef.current;
    if (!iframe) return;

    const handleLoad = () => {
      setStatus('Initializing Visa session...');
      iframe.contentWindow?.postMessage(
        {
          command: 'CREATE_AUTH_SESSION',
          apiKey: config.apiKey,
          clientAppId: config.clientAppId,
        },
        config.iframeUrl
      );
    };

    iframe.addEventListener('load', handleLoad);
    return () => iframe.removeEventListener('load', handleLoad);
  }, [config]);

  const iframeSrc = `${config.iframeUrl}?apiKey=${config.apiKey}&clientAppId=${config.clientAppId}&locale=${config.locale}`;

  return (
    <div className="visa-iframe-container">
      <div className="status-bar">{status}</div>
      <iframe
        ref={iframeRef}
        src={iframeSrc}
        style={{
          width: '100%',
          height: '600px',
          border: 'none',
          borderRadius: '8px',
        }}
        allow="payment; publickey-credentials-get"
        title="Visa Card Verification"
      />
    </div>
  );
};
