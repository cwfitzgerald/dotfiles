import { isAbsolute, relative, resolve, sep } from "node:path";
import type { AssistantMessage } from "@earendil-works/pi-ai";
import { CustomEditor, type ExtensionAPI, type ExtensionContext, type KeybindingsManager } from "@earendil-works/pi-coding-agent";
import { Key, matchesKey, truncateToWidth, visibleWidth, wrapTextWithAnsi, type EditorTheme, type TUI } from "@earendil-works/pi-tui";

const LEGACY_STATUS_KEY = "context-usage";

type CostBreakdown = {
	input: number;
	output: number;
	cacheRead: number;
	cacheWrite: number;
	total: number;
};

type TokenBreakdown = CostBreakdown;

type SessionStats = {
	sessionFile: string | undefined;
	sessionId: string;
	name: string | undefined;
	userMessages: number;
	assistantMessages: number;
	toolCalls: number;
	toolResults: number;
	totalMessages: number;
	tokens: TokenBreakdown;
	cost: CostBreakdown;
};

function sanitizeStatusText(text: string): string {
	return text.replace(/[\r\n\t]/g, " ").replace(/ +/g, " ").trim();
}

function formatCompact(count: number): string {
	const sign = count < 0 ? "-" : "";
	let value = Math.abs(count);
	let unitIndex = 0;
	const units = ["", "k", "M", "B", "T"];

	while (value >= 1000 && unitIndex < units.length - 1) {
		value /= 1000;
		unitIndex++;
	}

	let rounded = Number(value.toPrecision(3));
	if (rounded >= 1000 && unitIndex < units.length - 1) {
		value /= 1000;
		unitIndex++;
		rounded = Number(value.toPrecision(3));
	}

	return `${sign}${rounded}${units[unitIndex]}`;
}

function formatInteger(count: number): string {
	return Math.round(count).toLocaleString();
}

function formatCost(cost: number): string {
	return `$${cost.toFixed(4)}`;
}

function formatTokenCost(tokens: number, cost: number): string {
	return `${formatInteger(tokens)} (${formatCost(cost)})`;
}

function formatCwdForFooter(cwd: string, home: string | undefined): string {
	if (!home) return cwd;

	const resolvedCwd = resolve(cwd);
	const resolvedHome = resolve(home);
	const relativeToHome = relative(resolvedHome, resolvedCwd);
	const isInsideHome =
		relativeToHome === "" ||
		(relativeToHome !== ".." && !relativeToHome.startsWith(`..${sep}`) && !isAbsolute(relativeToHome));

	if (!isInsideHome) return cwd;
	return relativeToHome === "" ? "~" : `~${sep}${relativeToHome}`;
}

function formatContext(ctx: ExtensionContext, autoCompactEnabled: boolean): { text: string; severity: "normal" | "warning" | "error" } {
	const usage = ctx.getContextUsage();
	const contextWindow = usage?.contextWindow ?? ctx.model?.contextWindow ?? 0;
	const autoIndicator = autoCompactEnabled ? " (auto)" : "";

	if (!contextWindow || contextWindow <= 0 || !usage || usage.tokens === null || usage.percent === null) {
		return { text: `?/${formatCompact(contextWindow)}${autoIndicator}`, severity: "normal" };
	}

	const text = `${usage.percent.toFixed(1)}% ${formatCompact(usage.tokens)}/${formatCompact(contextWindow)}${autoIndicator}`;
	const severity = usage.percent > 90 ? "error" : usage.percent > 70 ? "warning" : "normal";
	return { text, severity };
}

function getSessionStats(ctx: ExtensionContext): SessionStats {
	let userMessages = 0;
	let assistantMessages = 0;
	let toolCalls = 0;
	let toolResults = 0;
	const tokens: TokenBreakdown = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 };
	const cost: CostBreakdown = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 };

	for (const entry of ctx.sessionManager.getBranch()) {
		if (entry.type !== "message") continue;

		const message = entry.message;
		if (message.role === "user") {
			userMessages++;
		} else if (message.role === "assistant") {
			assistantMessages++;
			const assistant = message as AssistantMessage;
			toolCalls += assistant.content.filter((content) => content.type === "toolCall").length;

			tokens.input += assistant.usage.input ?? 0;
			tokens.output += assistant.usage.output ?? 0;
			tokens.cacheRead += assistant.usage.cacheRead ?? 0;
			tokens.cacheWrite += assistant.usage.cacheWrite ?? 0;

			cost.input += assistant.usage.cost?.input ?? 0;
			cost.output += assistant.usage.cost?.output ?? 0;
			cost.cacheRead += assistant.usage.cost?.cacheRead ?? 0;
			cost.cacheWrite += assistant.usage.cost?.cacheWrite ?? 0;
			cost.total += assistant.usage.cost?.total ?? 0;
		} else if (message.role === "toolResult") {
			toolResults++;
		}
	}

	tokens.total = tokens.input + tokens.output + tokens.cacheRead + tokens.cacheWrite;
	if (cost.total === 0) cost.total = cost.input + cost.output + cost.cacheRead + cost.cacheWrite;

	return {
		sessionFile: ctx.sessionManager.getSessionFile(),
		sessionId: ctx.sessionManager.getSessionId(),
		name: ctx.sessionManager.getSessionName(),
		userMessages,
		assistantMessages,
		toolCalls,
		toolResults,
		totalMessages: userMessages + assistantMessages + toolResults,
		tokens,
		cost,
	};
}

function buildSessionInfo(ctx: ExtensionContext): string {
	const stats = getSessionStats(ctx);
	const theme = ctx.ui.theme;
	const lines: string[] = [];

	lines.push(theme.bold("Session Info"), "");
	if (stats.name) lines.push(`${theme.fg("dim", "Name:")} ${stats.name}`);
	lines.push(`${theme.fg("dim", "File:")} ${stats.sessionFile ?? "In-memory"}`);
	lines.push(`${theme.fg("dim", "ID:")} ${stats.sessionId}`);
	lines.push("");

	lines.push(theme.bold("Messages"));
	lines.push(`${theme.fg("dim", "User:")} ${stats.userMessages}`);
	lines.push(`${theme.fg("dim", "Assistant:")} ${stats.assistantMessages}`);
	lines.push(`${theme.fg("dim", "Tool Calls:")} ${stats.toolCalls}`);
	lines.push(`${theme.fg("dim", "Tool Results:")} ${stats.toolResults}`);
	lines.push(`${theme.fg("dim", "Total:")} ${stats.totalMessages}`);
	lines.push("");

	lines.push(theme.bold("Tokens (pseudo-cost)"));
	lines.push(theme.fg("dim", "Input:") + ` ${formatTokenCost(stats.tokens.input, stats.cost.input)}`);
	lines.push(theme.fg("dim", "Output:") + ` ${formatTokenCost(stats.tokens.output, stats.cost.output)}`);
	if (stats.tokens.cacheRead > 0 || stats.cost.cacheRead > 0) {
		lines.push(theme.fg("dim", "Cache Read:") + ` ${formatTokenCost(stats.tokens.cacheRead, stats.cost.cacheRead)}`);
	}
	if (stats.tokens.cacheWrite > 0 || stats.cost.cacheWrite > 0) {
		lines.push(theme.fg("dim", "Cache Write:") + ` ${formatTokenCost(stats.tokens.cacheWrite, stats.cost.cacheWrite)}`);
	}
	lines.push(theme.fg("dim", "Total:") + ` ${formatTokenCost(stats.tokens.total, stats.cost.total)}`);
	lines.push("");
	lines.push(theme.fg("dim", "Esc/Enter close"));

	return lines.join("\n");
}

function showSessionInfo(ctx: ExtensionContext): Promise<void> {
	return ctx.ui.custom<void>((tui, theme, _keybindings, done) => {
		const content = buildSessionInfo(ctx);
		return {
			render(width: number): string[] {
				const horizontal = theme.fg("border", "─".repeat(Math.max(0, width)));
				const body = content.flatMap((line) => (line ? wrapTextWithAnsi(line, Math.max(1, width)) : [""]));
				return [horizontal, ...body.map((line) => truncateToWidth(line, width)), horizontal];
			},
			invalidate() {},
			handleInput(data: string) {
				if (matchesKey(data, Key.escape) || matchesKey(data, Key.enter) || matchesKey(data, Key.ctrl("c"))) {
					done();
					return;
				}
				tui.requestRender();
			},
		};
	});
}

class SessionInterceptEditor extends CustomEditor {
	private submitHandler: ((text: string) => void) | undefined;

	constructor(tui: TUI, theme: EditorTheme, keybindings: KeybindingsManager, private readonly ctx: ExtensionContext) {
		super(tui, theme, keybindings);
		// Base Editor creates an own onSubmit field; remove it so our accessor below can intercept submissions.
		delete (this as { onSubmit?: (text: string) => void }).onSubmit;
	}

	get onSubmit(): ((text: string) => void) | undefined {
		return this.submitHandler;
	}

	set onSubmit(handler: ((text: string) => void) | undefined) {
		this.submitHandler = handler
			? (text: string) => {
					if (text.trim() === "/session") {
						this.setText("");
						void showSessionInfo(this.ctx);
						return;
					}
					handler(text);
				}
			: undefined;
	}
}

export default function (_pi: ExtensionAPI) {
	_pi.on("session_start", (_event, ctx) => {
		ctx.ui.setStatus(LEGACY_STATUS_KEY, undefined);
		ctx.ui.setEditorComponent((tui, theme, keybindings) => new SessionInterceptEditor(tui, theme, keybindings, ctx));

		ctx.ui.setFooter((tui, theme, footerData) => {
			const unsubscribeBranch = footerData.onBranchChange(() => tui.requestRender());

			return {
				dispose: unsubscribeBranch,
				invalidate() {},
				render(width: number): string[] {
					let totalInput = 0;
					let totalOutput = 0;
					let totalCacheRead = 0;
					let totalCacheWrite = 0;
					let totalCost = 0;
					let latestCacheHitRate: number | undefined;

					for (const entry of ctx.sessionManager.getEntries()) {
						if (entry.type !== "message" || entry.message.role !== "assistant") continue;

						const message = entry.message as AssistantMessage;
						totalInput += message.usage.input;
						totalOutput += message.usage.output;
						totalCacheRead += message.usage.cacheRead;
						totalCacheWrite += message.usage.cacheWrite;
						totalCost += message.usage.cost.total;

						const latestPromptTokens = message.usage.input + message.usage.cacheRead + message.usage.cacheWrite;
						latestCacheHitRate = latestPromptTokens > 0 ? (message.usage.cacheRead / latestPromptTokens) * 100 : undefined;
					}

					let pwd = formatCwdForFooter(ctx.sessionManager.getCwd(), process.env.HOME || process.env.USERPROFILE);
					const branch = footerData.getGitBranch();
					if (branch) pwd = `${pwd} (${branch})`;

					const sessionName = ctx.sessionManager.getSessionName();
					if (sessionName) pwd = `${pwd} • ${sessionName}`;

					const statsParts: string[] = [];
					if (totalInput) statsParts.push(`↑${formatCompact(totalInput)}`);
					if (totalOutput) statsParts.push(`↓${formatCompact(totalOutput)}`);
					if (totalCacheRead) statsParts.push(`R${formatCompact(totalCacheRead)}`);
					if (totalCacheWrite) statsParts.push(`W${formatCompact(totalCacheWrite)}`);
					if ((totalCacheRead > 0 || totalCacheWrite > 0) && latestCacheHitRate !== undefined) {
						statsParts.push(`CH${latestCacheHitRate.toFixed(1)}%`);
					}

					const usingSubscription = ctx.model ? ctx.modelRegistry.isUsingOAuth(ctx.model) : false;
					if (totalCost || usingSubscription) {
						statsParts.push(`$${totalCost.toFixed(3)}${usingSubscription ? " (sub)" : ""}`);
					}

					const context = formatContext(ctx, true);
					const contextText =
						context.severity === "error"
							? theme.fg("error", context.text)
							: context.severity === "warning"
								? theme.fg("warning", context.text)
								: context.text;
					statsParts.push(contextText);

					let statsLeft = statsParts.join(" ");
					let statsLeftWidth = visibleWidth(statsLeft);
					if (statsLeftWidth > width) {
						statsLeft = truncateToWidth(statsLeft, width, "...");
						statsLeftWidth = visibleWidth(statsLeft);
					}

					const modelName = ctx.model?.id || "no-model";
					let rightSideWithoutProvider = modelName;
					if (ctx.model?.reasoning) {
						const thinkingLevel = _pi.getThinkingLevel();
						rightSideWithoutProvider =
							thinkingLevel === "off" ? `${modelName} • thinking off` : `${modelName} • ${thinkingLevel}`;
					}

					let rightSide = rightSideWithoutProvider;
					if (footerData.getAvailableProviderCount() > 1 && ctx.model) {
						rightSide = `(${ctx.model.provider}) ${rightSideWithoutProvider}`;
						if (statsLeftWidth + 2 + visibleWidth(rightSide) > width) rightSide = rightSideWithoutProvider;
					}

					const rightSideWidth = visibleWidth(rightSide);
					let statsLine: string;
					if (statsLeftWidth + 2 + rightSideWidth <= width) {
						statsLine = statsLeft + " ".repeat(width - statsLeftWidth - rightSideWidth) + rightSide;
					} else {
						const availableForRight = width - statsLeftWidth - 2;
						if (availableForRight > 0) {
							const truncatedRight = truncateToWidth(rightSide, availableForRight, "");
							statsLine = statsLeft + " ".repeat(Math.max(0, width - statsLeftWidth - visibleWidth(truncatedRight))) + truncatedRight;
						} else {
							statsLine = statsLeft;
						}
					}

					const dimStatsLeft = theme.fg("dim", statsLeft);
					const dimRemainder = theme.fg("dim", statsLine.slice(statsLeft.length));
					const lines = [
						truncateToWidth(theme.fg("dim", pwd), width, theme.fg("dim", "...")),
						dimStatsLeft + dimRemainder,
					];

					const extensionStatuses = footerData.getExtensionStatuses();
					if (extensionStatuses.size > 0) {
						const statusLine = Array.from(extensionStatuses.entries())
							.filter(([key]) => key !== LEGACY_STATUS_KEY)
							.sort(([a], [b]) => a.localeCompare(b))
							.map(([, text]) => sanitizeStatusText(text))
							.join(" ");
						if (statusLine) lines.push(truncateToWidth(statusLine, width, theme.fg("dim", "...")));
					}

					return lines;
				},
			};
		});
	});
}
