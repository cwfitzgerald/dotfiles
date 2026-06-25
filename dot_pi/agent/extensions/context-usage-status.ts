import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const STATUS_KEY = "context-usage";
const numberFormat = new Intl.NumberFormat("en-US");

function formatCount(count: number): string {
	return numberFormat.format(Math.max(0, Math.round(count)));
}

function formatContextUsage(ctx: ExtensionContext): { text: string; severity: "normal" | "warning" | "error" } {
	const usage = ctx.getContextUsage();
	const contextWindow = usage?.contextWindow ?? ctx.model?.contextWindow;

	if (!contextWindow || contextWindow <= 0 || !usage) {
		return { text: "ctx ?", severity: "normal" };
	}

	if (usage.tokens === null || usage.percent === null) {
		return { text: `ctx ?% ?/${formatCount(contextWindow)} tok`, severity: "normal" };
	}

	const percent = usage.percent.toFixed(1);
	const text = `ctx ${percent}% ${formatCount(usage.tokens)}/${formatCount(contextWindow)} tok`;
	const severity = usage.percent > 90 ? "error" : usage.percent > 70 ? "warning" : "normal";
	return { text, severity };
}

function updateStatus(ctx: ExtensionContext): void {
	const { text, severity } = formatContextUsage(ctx);
	const theme = ctx.ui.theme;

	const styled =
		severity === "error"
			? theme.fg("error", text)
			: severity === "warning"
				? theme.fg("warning", text)
				: theme.fg("dim", text);

	ctx.ui.setStatus(STATUS_KEY, styled);
}

export default function (pi: ExtensionAPI) {
	pi.on("session_start", (_event, ctx) => {
		updateStatus(ctx);
	});

	pi.on("model_select", (_event, ctx) => {
		updateStatus(ctx);
	});

	pi.on("message_end", (_event, ctx) => {
		updateStatus(ctx);
	});

	pi.on("turn_end", (_event, ctx) => {
		updateStatus(ctx);
	});

	pi.on("session_compact", (_event, ctx) => {
		updateStatus(ctx);
	});
}
