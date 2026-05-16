/**
 * Windows-safe bootstrap for fred-mcp-server.
 * Upstream bin exits immediately on Windows (import.meta.url guard).
 */
import { createServer, startServer } from "fred-mcp-server/build/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = createServer();
const transport = new StdioServerTransport();
const ok = await startServer(server, transport);
if (!ok) {
  process.exit(1);
}
