import type { ExtensionAPI, MessageUpdateEvent } from "@earendil-works/pi-coding-agent";

const STATUS_KEY = "token-speed";
const EMA_ALPHA = 0.3;
/** Deltas are folded together until this much time passes, so a short gap cannot fabricate a rate. */
const MIN_SAMPLE_MS = 50;
/** Only the finished message carries real token counts, so the live rate estimates from characters. */
const CHARS_PER_TOKEN = 4;

type StreamEvent = MessageUpdateEvent["assistantMessageEvent"];

type Run = {
	startTime: number;
	firstTokenTime: number | undefined;
	sampleTime: number;
	pendingChars: number;
	estimatedTokens: number;
	rate: number | undefined;
};

function deltaLength(event: StreamEvent): number {
	switch (event.type) {
		case "text_delta":
		case "thinking_delta":
		case "toolcall_delta":
			return event.delta.length;
		default:
			return 0;
	}
}

function formatStatus(run: Run, average: number | undefined): string {
	const parts: string[] = [];
	if (run.firstTokenTime !== undefined) {
		parts.push(`ttft ${((run.firstTokenTime - run.startTime) / 1000).toFixed(2)}s`);
	}
	if (average !== undefined) parts.push(`tok/s avg ${average.toFixed(1)}`);
	else if (run.rate !== undefined) parts.push(`tok/s ${run.rate.toFixed(1)}`);
	return parts.join(" ");
}

function rate(tokens: number, elapsedMs: number): number | undefined {
	if (elapsedMs < MIN_SAMPLE_MS) return undefined;
	return (tokens / elapsedMs) * 1000;
}

export default function (pi: ExtensionAPI) {
	let run: Run | undefined;
	/** Set when the request leaves, so ttft covers request latency and not just the stream. */
	let requestTime: number | undefined;

	pi.on("agent_start", (_event, ctx) => {
		run = undefined;
		requestTime = undefined;
		ctx.ui.setStatus(STATUS_KEY, undefined);
	});

	pi.on("before_provider_request", () => {
		requestTime = Date.now();
	});

	pi.on("message_start", (event, ctx) => {
		if (event.message.role !== "assistant") return;

		const now = Date.now();
		run = {
			startTime: requestTime ?? now,
			firstTokenTime: undefined,
			sampleTime: now,
			pendingChars: 0,
			estimatedTokens: 0,
			rate: undefined,
		};
		requestTime = undefined;
		ctx.ui.setStatus(STATUS_KEY, "…");
	});

	pi.on("message_update", (event, ctx) => {
		if (!run) return;

		const chars = deltaLength(event.assistantMessageEvent);
		if (chars === 0) return;

		const now = Date.now();
		if (run.firstTokenTime === undefined) {
			run.firstTokenTime = now;
			run.sampleTime = now;
			run.estimatedTokens = chars / CHARS_PER_TOKEN;
			ctx.ui.setStatus(STATUS_KEY, formatStatus(run, undefined));
			return;
		}

		run.pendingChars += chars;
		const sample = rate(run.pendingChars / CHARS_PER_TOKEN, now - run.sampleTime);
		if (sample === undefined) return;

		run.rate = run.rate === undefined ? sample : run.rate * (1 - EMA_ALPHA) + sample * EMA_ALPHA;
		run.estimatedTokens += run.pendingChars / CHARS_PER_TOKEN;
		run.pendingChars = 0;
		run.sampleTime = now;
		ctx.ui.setStatus(STATUS_KEY, formatStatus(run, undefined));
	});

	pi.on("message_end", (event, ctx) => {
		if (event.message.role !== "assistant") return;
		if (!run) {
			ctx.ui.setStatus(STATUS_KEY, undefined);
			return;
		}

		const estimated = run.estimatedTokens + run.pendingChars / CHARS_PER_TOKEN;
		const tokens = event.message.usage.output || estimated;
		const average = rate(tokens, Date.now() - (run.firstTokenTime ?? run.startTime));

		ctx.ui.setStatus(STATUS_KEY, formatStatus(run, average) || undefined);
		run = undefined;
	});
}
