/* Copyright 2024 Marimo. All rights reserved. */

import { useEffect, useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Logger } from '@/utils/Logger';

interface MCPServer {
  name: string;
  tools: Array<{ name: string; description: string }>;
  resources: Array<{ name: string; description: string }>;
  prompts: Array<{ name: string; description: string }>;
}

interface ServerResponse {
  servers: MCPServer[];
}

interface ServerSelectorProps {
  onServerSelect: (serverName: string | null) => void;
}

export const ServerSelector = ({ onServerSelect }: ServerSelectorProps): JSX.Element => {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [selectedServer, setSelectedServer] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const fetchServers = async () => {
    try {
      const response = await fetch('/api/mcp/servers');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data: ServerResponse = await response.json();
      setServers(data.servers || []);

      // If selected server no longer exists, clear selection
      if (selectedServer && !data.servers.some(s => s.name === selectedServer)) {
        setSelectedServer(null);
        onServerSelect(null);
      }
    } catch (error) {
      Logger.error('Failed to fetch MCP servers', error);
      setServers([]);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchServers();
    }
  }, [isOpen]);

  const handleServerChange = (value = '') => {
    const newValue = value === '' ? null : value;
    setSelectedServer(newValue);
    onServerSelect(newValue);
  };

  const selectedServerData = selectedServer ? servers.find(s => s.name === selectedServer) : null;

  return (
    <div className="w-full p-4">
      <Select
        value={selectedServer || ''}
        onValueChange={handleServerChange}
        open={isOpen}
        onOpenChange={setIsOpen}
      >
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Select MCP Server" />
        </SelectTrigger>
        <SelectContent>
          {servers.map((server) => (
            <SelectItem key={server.name} value={server.name}>
              {server.name}
              <span className="text-sm text-gray-500 ml-2">
                ({server.tools.length} tools, {server.resources.length} resources, {server.prompts.length} prompts)
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {selectedServer && selectedServerData && (
        <div className="mt-4 text-sm text-gray-500">
          <div className="mb-2">
            <strong>Available:</strong>
          </div>
          <div className="ml-2">
            <div>@resource - {selectedServerData.resources.length} resources</div>
            <div>!tool - {selectedServerData.tools.length} tools</div>
            <div>/prompt - {selectedServerData.prompts.length} prompts</div>
          </div>
        </div>
      )}
    </div>
  );
}; 
