<script lang="ts">
	import { countCharacters, ESSAY_MAX_CHARS, ESSAY_MIN_CHARS } from '$lib/data/essay';
	import { listPrompts } from '$lib/data/workspaceResources';
	import { getI18nContext } from '$lib/i18n';

	const i18n = getI18nContext();

	type Props = {
		prompt?: string;
		placeholder?: string;
		disabled?: boolean;
		generating?: boolean;
		ctrlEnterToSend?: boolean;
		enableMessageQueue?: boolean;
		showFormattingToolbar?: boolean;
		richTextInput?: boolean;
		promptAutocomplete?: boolean;
		lastUserMessage?: string;
		onSubmit?: (content: string) => void;
		onStop?: () => void;
		onEditLastMessage?: (content: string) => void;
		/**
		 * 论文模式才传：显示「交稿批改」，把输入框里的**原始正文**交出去。
		 * 不走 buildPayload——那个会加「[附件:…]」之类的前缀，批注下标就对不上原文了。
		 */
		onReview?: ((text: string) => void) | null;
		/** 本机有范例论文时才传：显示「填入范例」，演示批改用 */
		onFillSample?: (() => void) | null;
		/** 输入 `#` 时可选的知识库（笔记本）列表 */
		knowledgeOptions?: { id: string; name: string }[];
		/** 输入 `@` 时可选的知识库（模型）列表 */
		modelOptions?: { id: string; name: string }[];
		onSelectKnowledge?: (id: string, name: string) => void;
		onSelectModel?: (id: string, name: string) => void;
	};

	let {
		prompt = $bindable(''),
		placeholder = $i18n.t('Send a Message'),
		disabled = false,
		generating = false,
		ctrlEnterToSend = false,
		enableMessageQueue = true,
		showFormattingToolbar = false,
		richTextInput = true,
		promptAutocomplete = false,
		lastUserMessage = '',
		onSubmit = () => {},
		onStop = () => {},
		onEditLastMessage = () => {},
		onReview = null,
		onFillSample = null,
		knowledgeOptions = [],
		modelOptions = [],
		onSelectKnowledge = () => {},
		onSelectModel = () => {}
	}: Props = $props();

	let textareaElement = $state<HTMLTextAreaElement | null>(null);
	let commandIndex = $state(0);

	const canSendWhileGenerating = $derived(enableMessageQueue && generating);

	const suggestions = $derived([
		$i18n.t('Summarize the key points of this lesson'),
		$i18n.t('Explain in simpler terms'),
		$i18n.t('Provide related exercises'),
		$i18n.t('Compare related concepts')
	]);

	const autocompleteHint = $derived.by(() => {
		if (!promptAutocomplete || !prompt.trim()) return '';
		const q = prompt.trim();
		return suggestions.find((s) => s.startsWith(q) && s !== q) ?? '';
	});

	const slashQuery = $derived.by(() => {
		const m = prompt.match(/^\/([^\s]*)$/);
		return m ? m[1].toLowerCase() : null;
	});

	const slashCommands = $derived.by(() => {
		if (slashQuery === null) return [];
		return listPrompts()
			.filter((p) => p.isActive !== false)
			.filter((p) => p.command.replace(/^\/+/, '').toLowerCase().includes(slashQuery))
			.sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'));
	});

	$effect(() => {
		void slashCommands;
		commandIndex = 0;
	});

	const applySlashPrompt = (item: (typeof slashCommands)[number]) => {
		let content = item.content || '';
		// Simple {{var}} → leave for user to fill; replace common system vars
		const now = new Date();
		content = content
			.replaceAll('{{CURRENT_DATE}}', now.toLocaleDateString())
			.replaceAll('{{CURRENT_TIME}}', now.toLocaleTimeString())
			.replaceAll('{{CURRENT_DATETIME}}', now.toLocaleString());
		prompt = content;
		queueMicrotask(() => {
			const el = textareaElement;
			if (!el) return;
			el.focus();
			const len = el.value.length;
			el.setSelectionRange(len, len);
		});
	};

	// 输入 `#` 或 `@` 触发：# 列出知识库（笔记本）、@ 列出模型。
	// 只认「句子末尾、前面是行首或空白」的那个 token，避免把正文里的 #/@ 也当触发。
	const trigger = $derived.by(() => {
		const m = prompt.match(/(?:^|\s)([#@])([^\s]*)$/);
		if (!m) return null;
		return { symbol: m[1] as '#' | '@', query: m[2].toLowerCase() };
	});

	const triggerItems = $derived.by(() => {
		if (!trigger) return [] as { id: string; name: string }[];
		const source = trigger.symbol === '#' ? knowledgeOptions : modelOptions;
		return source.filter((item) => item.name.toLowerCase().includes(trigger.query));
	});

	$effect(() => {
		void triggerItems;
		commandIndex = 0;
	});

	const applyTrigger = (item: { id: string; name: string }) => {
		const t = trigger;
		if (!t) return;
		if (t.symbol === '#') onSelectKnowledge(item.id, item.name);
		else onSelectModel(item.id, item.name);
		// 把输入框里的 `#frag` / `@frag` 这一段去掉
		prompt = prompt.replace(/[#@][^\s]*$/, '');
		queueMicrotask(() => textareaElement?.focus());
	};

	// 字数按后端的算法（去空白后的码点数），和交稿时的长度闸是同一个数
	const reviewChars = $derived(onReview ? countCharacters(prompt) : 0);
	const reviewReady = $derived(reviewChars >= ESSAY_MIN_CHARS && reviewChars <= ESSAY_MAX_CHARS);
	const reviewTitle = $derived(
		reviewChars < ESSAY_MIN_CHARS
			? `正文至少 ${ESSAY_MIN_CHARS} 字才能批改（现在 ${reviewChars} 字）`
			: reviewChars > ESSAY_MAX_CHARS
				? `超过单次批改上限 ${ESSAY_MAX_CHARS} 字，请删减或分段交`
				: '把输入框里的正文交给批改：三个维度打分 + 逐句批注'
	);

	const submitReview = () => {
		if (!onReview || disabled || generating) return;
		onReview(prompt);
	};

	const submit = () => {
		const content = prompt.trim();
		if (!content || disabled) return;
		if (generating && !enableMessageQueue) return;
		onSubmit(content);
	};

	const handleKeydown = (event: KeyboardEvent) => {
		if (event.key === 'Escape' && generating) {
			event.preventDefault();
			onStop();
			return;
		}

		if (triggerItems.length > 0) {
			if (event.key === 'ArrowDown') {
				event.preventDefault();
				commandIndex = Math.min(commandIndex + 1, triggerItems.length - 1);
				return;
			}
			if (event.key === 'ArrowUp') {
				event.preventDefault();
				commandIndex = Math.max(commandIndex - 1, 0);
				return;
			}
			if (event.key === 'Enter' || event.key === 'Tab') {
				event.preventDefault();
				const item = triggerItems[commandIndex];
				if (item) applyTrigger(item);
				return;
			}
			if (event.key === 'Escape') {
				event.preventDefault();
				prompt = prompt.replace(/[#@][^\s]*$/, '');
				return;
			}
		}

		if (slashCommands.length > 0) {
			if (event.key === 'ArrowDown') {
				event.preventDefault();
				commandIndex = Math.min(commandIndex + 1, slashCommands.length - 1);
				return;
			}
			if (event.key === 'ArrowUp') {
				event.preventDefault();
				commandIndex = Math.max(commandIndex - 1, 0);
				return;
			}
			if (event.key === 'Enter' || event.key === 'Tab') {
				event.preventDefault();
				const item = slashCommands[commandIndex];
				if (item) applySlashPrompt(item);
				return;
			}
			if (event.key === 'Escape') {
				event.preventDefault();
				prompt = '';
				return;
			}
		}

		if (event.key === 'ArrowUp' && !prompt.trim() && lastUserMessage) {
			event.preventDefault();
			prompt = lastUserMessage;
			onEditLastMessage(lastUserMessage);
			queueMicrotask(() => {
				const el = textareaElement;
				if (!el) return;
				el.focus();
				const len = el.value.length;
				el.setSelectionRange(len, len);
			});
			return;
		}

		if (event.key === 'Tab' && autocompleteHint) {
			event.preventDefault();
			prompt = autocompleteHint;
			return;
		}

		if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && event.shiftKey) {
			event.preventDefault();
			submit();
			return;
		}

		if (event.key !== 'Enter') return;
		if (ctrlEnterToSend) {
			if (event.ctrlKey || event.metaKey) {
				event.preventDefault();
				submit();
			}
			return;
		}
		if (!event.shiftKey) {
			event.preventDefault();
			submit();
		}
	};

	const wrapSelection = (prefix: string, suffix = prefix) => {
		const el = textareaElement;
		if (!el) {
			prompt = `${prefix}${prompt}${suffix}`;
			return;
		}
		const start = el.selectionStart;
		const end = el.selectionEnd;
		const selected = prompt.slice(start, end) || '文本';
		prompt = `${prompt.slice(0, start)}${prefix}${selected}${suffix}${prompt.slice(end)}`;
		queueMicrotask(() => {
			el.focus();
			el.setSelectionRange(start + prefix.length, start + prefix.length + selected.length);
		});
	};

</script>

<div
	id="message-input-container"
	class="relative flex w-full flex-1 flex-col rounded-3xl border border-white/[0.08] bg-white/[0.035] px-1 text-gray-100 backdrop-blur-sm transition hover:border-white/[0.12] focus-within:border-white/[0.16]"
>
	{#if showFormattingToolbar && richTextInput}
			<div class="flex items-center gap-1 border-b border-white/[0.06] px-2 pt-2 pb-1">
				<button type="button" class="rounded px-1.5 py-0.5 text-xs text-gray-400 hover:bg-white/[0.06] hover:text-white" onclick={() => wrapSelection('**')} title="粗体">B</button>
				<button type="button" class="rounded px-1.5 py-0.5 text-xs italic text-gray-400 hover:bg-white/[0.06] hover:text-white" onclick={() => wrapSelection('*')} title="斜体">I</button>
				<button type="button" class="rounded px-1.5 py-0.5 text-xs text-gray-400 hover:bg-white/[0.06] hover:text-white" onclick={() => wrapSelection('`')} title="代码">`</button>
				<button type="button" class="rounded px-1.5 py-0.5 text-xs text-gray-400 hover:bg-white/[0.06] hover:text-white" onclick={() => wrapSelection('[', '](url)')} title="链接">链接</button>
			</div>
		{/if}

		{#if slashCommands.length > 0}
			<div
				class="absolute bottom-full left-0 z-20 mb-2 max-h-56 w-full max-w-md overflow-y-auto rounded-xl border border-gray-800 bg-gray-850 py-1 shadow-lg"
			>
				<div class="px-3 py-1 text-xs text-gray-500">提示词</div>
				{#each slashCommands as item, idx (item.id)}
					<button
						type="button"
						class="flex w-full flex-col px-3 py-1.5 text-left transition {idx === commandIndex
							? 'bg-gray-800'
							: 'hover:bg-gray-800/70'}"
						onclick={() => applySlashPrompt(item)}
						onmousemove={() => {
							commandIndex = idx;
						}}
					>
						<div class="flex items-center gap-2 text-sm text-white">
							<span class="font-medium">{item.title}</span>
							<span class="text-xs text-gray-500">/{item.command.replace(/^\/+/, '')}</span>
						</div>
						{#if item.content}
							<div class="line-clamp-1 text-xs text-gray-500">{item.content}</div>
						{/if}
					</button>
				{/each}
			</div>
		{/if}
		{#if triggerItems.length > 0}
			<div
				class="absolute bottom-full left-0 z-20 mb-2 max-h-56 w-full max-w-md overflow-y-auto rounded-xl border border-gray-800 bg-gray-850 py-1 shadow-lg"
			>
				<div class="px-3 py-1 text-xs text-gray-500">
					{trigger?.symbol === '#' ? '引用知识库' : '选择模型'}
				</div>
				{#each triggerItems as item, idx (item.id)}
					<button
						type="button"
						class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-white transition {idx ===
						commandIndex
							? 'bg-gray-800'
							: 'hover:bg-gray-800/70'}"
						onclick={() => applyTrigger(item)}
						onmousemove={() => {
							commandIndex = idx;
						}}
					>
						<span class="font-medium">{item.name}</span>
					</button>
				{/each}
			</div>
		{/if}
		<div class="relative max-h-[18rem] min-h-[3rem] overflow-y-auto">
			{#if autocompleteHint}
				<div class="pointer-events-none absolute top-3 left-3 right-3 truncate text-sm leading-6 text-gray-600" aria-hidden="true">
					<span class="invisible">{prompt}</span><span>{autocompleteHint.slice(prompt.length)}</span>
				</div>
			{/if}
			<textarea
				id="chat-input"
				bind:this={textareaElement}
				bind:value={prompt}
				rows="1"
				class="relative z-[1] block min-h-[52px] w-full resize-none bg-transparent px-3 pt-3 pb-1 text-sm leading-6 text-gray-100 outline-none placeholder:text-gray-500 disabled:cursor-not-allowed disabled:opacity-50"
				{placeholder}
				{disabled}
				onkeydown={handleKeydown}
				aria-label={placeholder}
			></textarea>
		</div>

		<div class="mx-0.5 mt-0.5 mb-2.5 flex max-w-full items-end justify-between" dir="ltr">
			<div class="ml-1 flex max-w-[80%] flex-1 items-center gap-0.5 self-end">
				{#if canSendWhileGenerating}
					<span class="ml-2 text-[11px] text-gray-500">生成中 · 发送将加入队列</span>
				{/if}
			</div>

			<div class="mr-1 flex shrink-0 items-center gap-1 self-end">
				{#if generating}
					<button
						type="button"
						class="flex size-8 items-center justify-center rounded-full bg-white text-black transition hover:bg-gray-200"
						onclick={onStop}
						title="停止生成"
						aria-label="停止生成"
					>
						<span class="size-2.5 rounded-[2px] bg-black"></span>
					</button>
					{#if enableMessageQueue && prompt.trim()}
						<button
							type="button"
							class="flex size-8 items-center justify-center rounded-full border border-white/20 text-white transition hover:bg-white/[0.08]"
							onclick={submit}
							disabled={disabled}
							title="加入队列"
							aria-label="加入队列"
						>
							<svg class="size-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
								<path d="M12 19V5"></path>
								<path d="m5 12 7-7 7 7"></path>
							</svg>
						</button>
					{/if}
				{:else}
					{#if onReview}
						{#if onFillSample && !prompt.trim()}
							<button
								type="button"
								class="rounded-full px-2.5 py-1 text-xs text-gray-400 transition hover:bg-white/[0.06] hover:text-white"
								onclick={onFillSample}
								title="把本机的范例论文填进输入框，演示批改用"
							>
								填入范例
							</button>
						{/if}
						{#if prompt.trim()}
							<span
								class={`text-[11px] tabular-nums ${reviewReady ? 'text-gray-500' : 'text-amber-300/80'}`}
							>
								{reviewChars.toLocaleString()} 字
							</span>
						{/if}
						<button
							type="button"
							class="rounded-full border border-amber-300/40 px-3 py-1 text-xs font-medium text-amber-100 transition hover:bg-amber-300/10 disabled:cursor-not-allowed disabled:border-white/15 disabled:text-gray-500"
							onclick={submitReview}
							disabled={disabled || !reviewReady}
							title={reviewTitle}
						>
							交稿批改
						</button>
					{/if}
					<button
						type="button"
						id="send-message-button"
						class="flex size-8 items-center justify-center rounded-full bg-white text-black transition hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-30"
						onclick={submit}
						disabled={disabled || !prompt.trim()}
						title="发送消息"
						aria-label="发送消息"
					>
						<svg
							class="size-[18px]"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							stroke-linejoin="round"
							aria-hidden="true"
						>
							<path d="M12 19V5"></path>
							<path d="m5 12 7-7 7 7"></path>
						</svg>
					</button>
				{/if}
			</div>
		</div>
</div>
