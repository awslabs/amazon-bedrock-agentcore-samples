import React from "react";

interface ConnectionButtonProps {
  status: "disconnected" | "connecting" | "connected" | "recording";
  onConnect: () => void;
  onDisconnect: () => void;
  connectText?: string;
  disconnectText?: string;
  className?: string;
  disabled?: boolean;
}

export const ConnectionButton: React.FC<ConnectionButtonProps> = ({
  status,
  onConnect,
  onDisconnect,
  connectText = "Connect",
  disconnectText = "Disconnect",
  className,
  disabled = false,
}) => {
  const isConnected = status === "connected" || status === "recording";
  const isConnecting = status === "connecting";

  const handleClick = () => {
    if (isConnected) {
      onDisconnect();
    } else {
      onConnect();
    }
  };

  return (
    <button
      onClick={handleClick}
      className={className}
      disabled={disabled || isConnecting}
      data-state={isConnected ? "connected" : "disconnected"}
    >
      {isConnected ? disconnectText : connectText}
    </button>
  );
};
