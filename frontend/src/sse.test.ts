import { describe, expect, it } from "vitest";
import { SSEParser } from "./sse";

const STREAM =
  'event: meta\ndata: {"conversation_id": "abc"}\n\n' +
  ": ping\n\n" +
  'event: token\ndata: {"text": "Hel"}\n\n' +
  'event: answer\ndata: {"answer": "Hello [1]."}\n\n';

describe("SSEParser", () => {
  it("parses a whole stream and skips comment lines", () => {
    const events = new SSEParser().push(STREAM);
    expect(events.map((e) => e.event)).toEqual(["meta", "token", "answer"]);
    expect(JSON.parse(events[0].data)).toEqual({ conversation_id: "abc" });
  });

  it("gives the same result when the network splits the stream anywhere", () => {
    const parser = new SSEParser();
    const events = [...STREAM].flatMap((char) => parser.push(char)); // one character per chunk
    expect(events).toEqual(new SSEParser().push(STREAM));
  });

  it("keeps an incomplete event buffered until it ends", () => {
    const parser = new SSEParser();
    expect(parser.push('event: token\ndata: {"te')).toEqual([]);
    expect(parser.push('xt": "a"}\n\n')).toEqual([{ event: "token", data: '{"text": "a"}' }]);
  });

  it("handles CRLF line endings, even split across chunks", () => {
    const parser = new SSEParser();
    expect(parser.push("event: step\r\ndata: 1\r")).toEqual([]);
    expect(parser.push("\n\r\n")).toEqual([{ event: "step", data: "1" }]);
  });

  it("joins multi-line data with newlines", () => {
    expect(new SSEParser().push("data: a\ndata: b\n\n")).toEqual([{ event: "message", data: "a\nb" }]);
  });
});
