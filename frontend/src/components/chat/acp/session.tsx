import { useAcpClient } from "use-acp";

function App() {
  const {
    connect,
    disconnect,
    connectionState,
    notifications,
    pendingPermission,
    resolvePermission,
  } = useAcpClient({
    wsUrl: "ws://localhost:8080",
    autoConnect: true,
  });

  return (
    <div>
      <div>Status: {connectionState.status}</div>
      <button
        onClick={connectionState.status === "connected" ? disconnect : connect}
      >
        {connectionState.status === "connected" ? "Disconnect" : "Connect"}
      </button>

      {pendingPermission && (
        <div>
          <h3>Permission Request</h3>
          {pendingPermission.options.map((option) => (
            <button
              key={option.optionId}
              onClick={() => resolvePermission(option)}
            >
              {option.name}
            </button>
          ))}
        </div>
      )}

      <div>Notifications: {notifications.length}</div>
      <ul>
        {notifications.map((notification) => (
          <li key={notification.id}>{JSON.stringify(notification)}</li>
        ))}
      </ul>
    </div>
  );
}
