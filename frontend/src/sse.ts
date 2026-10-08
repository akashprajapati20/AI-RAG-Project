export interface SSEEvent {
  event: string;
  data: string;
}

/**
 * Incremental parser for a `text/event-stream` body.
 *
 * The browser's EventSource only supports GET, but /chat/stream is a POST (the question is in the
 * body), so we read the response stream ourselves. Network chunks can split an event anywhere,
 * even mid-line, so text is buffered until a blank line marks the end of an event.
 */
export class SSEParser {
  private buffer = "";

  push(chunk: string): SSEEvent[] {
    // Normalise CRLF on the whole buffer, so a "\r" / "\n" pair split across chunks still merges.
    this.buffer = (this.buffer + chunk).replace(/\r\n/g, "\n");
    const events: SSEEvent[] = [];
    let end: number;
    while ((end = this.buffer.indexOf("\n\n")) !== -1) {
      const event = parseBlock(this.buffer.slice(0, end));
      this.buffer = this.buffer.slice(end + 2);
      if (event) events.push(event);
    }
    return events;
  }
}

function parseBlock(block: string): SSEEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue; // ":" lines are comments, e.g. keep-alive pings
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length ? { event, data: data.join("\n") } : null;
}
