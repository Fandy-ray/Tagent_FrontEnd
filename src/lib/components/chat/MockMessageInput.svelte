<script lang="ts">
	import PlusAlt from '$lib/components/icons/PlusAlt.svelte';
	import ComponentIcon from '$lib/components/icons/Component.svelte';
	import VoiceIcon from '$lib/components/icons/Voice.svelte';
	import InputMenu, { type InputAttachment } from './MessageInput/InputMenu.svelte';
	import IntegrationsMenu from './MessageInput/IntegrationsMenu.svelte';
	import VoiceRecording from './MessageInput/VoiceRecording.svelte';
	import CallOverlay from './MessageInput/CallOverlay.svelte';

	type Props = {
		prompt?: string;
		placeholder?: string;
		disabled?: boolean;
		generating?: boolean;
		ctrlEnterToSend?: boolean;
		largeTextAsFile?: boolean;
		enableMessageQueue?: boolean;
		showFormattingToolbar?: boolean;
		richTextInput?: boolean;
		promptAutocomplete?: boolean;
		imageCompression?: boolean;
		imageCompressionSize?: { width: string; height: string };
		lastUserMessage?: string;
		speechAutoSend?: boolean;
		webSearchAlways?: boolean;
		knowledgeOptions?: { id: string; name: string }[];
		noteOptions?: { id: string; name: string }[];
		chatOptions?: { id: string; name: string }[];
		modelName?: string;
		onSubmit?: (content: string) => void;
		onStop?: () => void;
		onPasteAsFile?: (file: File) => void;
		onEditLastMessage?: (content: string) => void;
		onToast?: (message: string) => void;
	};

	let {
		prompt = $bindable(''),
		placeholder = '发送消息',
		disabled = false,
		generating = false,
		ctrlEnterToSend = false,
		largeTextAsFile = false,
		enableMessageQueue = true,
		showFormattingToolbar = false,
		richTextInput = true,
		promptAutocomplete = false,
		imageCompression = false,
		imageCompressionSize = { width: '', height: '' },
		lastUserMessage = '',
		speechAutoSend = false,
		webSearchAlways = false,
		knowledgeOptions = [],
		noteOptions = [],
		chatOptions = [],
		modelName = '',
		onSubmit = () => {},
		onStop = () => {},
		onPasteAsFile = () => {},
		onEditLastMessage = () => {},
		onToast = () => {}
	}: Props = $props();

	let textareaElement = $state<HTMLTextAreaElement | null>(null);
	let attachments = $state<InputAttachment[]>([]);
	let webSearchEnabled = $state(false);
	let imageGenerationEnabled = $state(false);
	let codeInterpreterEnabled = $state(false);
	let selectedToolIds = $state<string[]>([]);
	let recording = $state(false);
	let callOpen = $state(false);

	const canSendWhileGenerating = $derived(enableMessageQueue && generating);
	const showVoiceMode = $derived(!prompt.trim() && attachments.length === 0 && !generating);

	$effect(() => {
		if (webSearchAlways) webSearchEnabled = true;
	});

	const suggestions = ['帮我总结这节课的要点', '用更简单的话解释', '给出相关练习题', '对比一下相关概念'];
	const autocompleteHint = $derived.by(() => {
		if (!promptAutocomplete || !prompt.trim()) return '';
		const q = prompt.trim();
		return suggestions.find((s) => s.startsWith(q) && s !== q) ?? '';
	});

	const buildPayload = (content: string) => {
		const parts: string[] = [];
		if (webSearchEnabled || webSearchAlways) parts.push('[联网搜索]');
		if (imageGenerationEnabled) parts.push('[图像生成]');
		if (codeInterpreterEnabled) parts.push('[代码解释器]');
		if (selectedToolIds.length) parts.push(`[工具:${selectedToolIds.join(',')}]`);
		if (attachments.length) {
			parts.push(
				`[附件:${attachments.map((a) => a.name).join(' | ')}]`
			);
		}
		const prefix = parts.length ? `${parts.join(' ')}\n` : '';
		return `${prefix}${content}`.trim();
	};

	const submit = () => {
		const content = prompt.trim();
		if ((!content && attachments.length === 0) || disabled) return;
		if (generating && !enableMessageQueue) return;
		onSubmit(buildPayload(content || '请结合附件回答'));
		attachments = [];
	};

	const handleKeydown = (event: KeyboardEvent) => {
		if (event.key === 'Escape' && generating) {
			event.preventDefault();
			onStop();
			return;
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

	const compressImageFile = async (file: File): Promise<File> => {
		if (!imageCompression || !file.type.startsWith('image/')) return file;
		const maxW = Number(imageCompressionSize.width) || 1280;
		const maxH = Number(imageCompressionSize.height) || 1280;
		const bitmap = await createImageBitmap(file);
		const scale = Math.min(1, maxW / bitmap.width, maxH / bitmap.height);
		const w = Math.max(1, Math.round(bitmap.width * scale));
		const h = Math.max(1, Math.round(bitmap.height * scale));
		const canvas = document.createElement('canvas');
		canvas.width = w;
		canvas.height = h;
		const ctx = canvas.getContext('2d');
		if (!ctx) return file;
		ctx.drawImage(bitmap, 0, 0, w, h);
		const blob = await new Promise<Blob | null>((resolve) =>
			canvas.toBlob(resolve, 'image/jpeg', 0.82)
		);
		if (!blob) return file;
		return new File([blob], file.name.replace(/\.\w+$/, '.jpg'), { type: 'image/jpeg' });
	};

	const handlePaste = async (event: ClipboardEvent) => {
		const items = event.clipboardData?.items;
		if (items) {
			for (const item of items) {
				if (item.type.startsWith('image/')) {
					event.preventDefault();
					const raw = item.getAsFile();
					if (!raw) return;
					const file = await compressImageFile(raw);
					onPasteAsFile(file);
					attachments = [
						...attachments,
						{ id: `paste-${Date.now()}`, type: 'file', name: file.name }
					];
					onToast('内容已转为本地文件引用');
					return;
				}
			}
		}

		if (!largeTextAsFile) return;
		const text = event.clipboardData?.getData('text/plain') ?? '';
		if (text.length < 1500) return;
		event.preventDefault();
		const file = new File([text], `paste-${Date.now()}.txt`, { type: 'text/plain' });
		onPasteAsFile(file);
		attachments = [
			...attachments,
			{ id: `paste-text-${Date.now()}`, type: 'file', name: file.name }
		];
		onToast('内容已转为本地文件引用');
	};

	const startDictate = async () => {
		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			stream.getTracks().forEach((track) => track.stop());
			recording = true;
		} catch {
			onToast('无法访问麦克风');
		}
	};

	const startVoiceMode = async () => {
		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			stream.getTracks().forEach((track) => track.stop());
			callOpen = true;
		} catch {
			onToast('无法访问麦克风，语音模式未开启');
		}
	};

	const focus = () => {
		textareaElement?.focus();
	};

	export { focus };
</script>

<div
	id="message-input-container"
	class="relative flex w-full flex-1 flex-col rounded-3xl border border-white/[0.08] bg-white/[0.035] px-1 text-gray-100 shadow-lg shadow-black/10 backdrop-blur-sm transition hover:border-white/[0.12] focus-within:border-white/[0.16]"
>
	{#if recording}
		<VoiceRecording
			bind:recording
			{speechAutoSend}
			onCancel={() => {
				recording = false;
			}}
			onConfirm={(text) => {
				prompt = `${prompt}${prompt ? ' ' : ''}${text}`.trim();
				recording = false;
				if (speechAutoSend) {
					queueMicrotask(() => submit());
				} else {
					focus();
				}
			}}
		/>
	{:else}
		{#if showFormattingToolbar && richTextInput}
			<div class="flex items-center gap-1 border-b border-white/[0.06] px-2 pt-2 pb-1">
				<button type="button" class="rounded px-1.5 py-0.5 text-xs text-gray-400 hover:bg-white/[0.06] hover:text-white" onclick={() => wrapSelection('**')} title="粗体">B</button>
				<button type="button" class="rounded px-1.5 py-0.5 text-xs italic text-gray-400 hover:bg-white/[0.06] hover:text-white" onclick={() => wrapSelection('*')} title="斜体">I</button>
				<button type="button" class="rounded px-1.5 py-0.5 text-xs text-gray-400 hover:bg-white/[0.06] hover:text-white" onclick={() => wrapSelection('`')} title="代码">`</button>
				<button type="button" class="rounded px-1.5 py-0.5 text-xs text-gray-400 hover:bg-white/[0.06] hover:text-white" onclick={() => wrapSelection('[', '](url)')} title="链接">链接</button>
			</div>
		{/if}

		{#if attachments.length > 0}
			<div class="flex flex-wrap gap-1.5 px-2.5 pt-2.5">
				{#each attachments as item (item.id)}
					<span
						class="inline-flex max-w-full items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] text-gray-300"
					>
						<span class="truncate">{item.name}</span>
						<button
							type="button"
							class="shrink-0 text-gray-500 hover:text-white"
							aria-label={`移除 ${item.name}`}
							onclick={() => {
								attachments = attachments.filter((a) => a.id !== item.id);
							}}
						>
							×
						</button>
					</span>
				{/each}
			</div>
		{/if}

		{#if webSearchEnabled || imageGenerationEnabled || codeInterpreterEnabled || selectedToolIds.length}
			<div class="flex flex-wrap gap-1.5 px-2.5 pt-2">
				{#if webSearchEnabled}
					<span class="rounded-full bg-sky-500/15 px-2 py-0.5 text-[11px] text-sky-300">联网搜索</span>
				{/if}
				{#if imageGenerationEnabled}
					<span class="rounded-full bg-violet-500/15 px-2 py-0.5 text-[11px] text-violet-300">图像</span>
				{/if}
				{#if codeInterpreterEnabled}
					<span class="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] text-amber-300">代码解释器</span>
				{/if}
				{#if selectedToolIds.length}
					<span class="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] text-emerald-300">
						工具 {selectedToolIds.length}
					</span>
				{/if}
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
				onpaste={handlePaste}
				aria-label={placeholder}
			></textarea>
		</div>

		<div class="mx-0.5 mt-0.5 mb-2.5 flex max-w-full items-end justify-between" dir="ltr">
			<div class="ml-1 flex max-w-[80%] flex-1 items-center gap-0.5 self-end">
				<InputMenu
					bind:attachments
					{knowledgeOptions}
					{noteOptions}
					{chatOptions}
					onToast={onToast}
					onClose={focus}
				>
					<PlusAlt className="size-[22px]" />
				</InputMenu>

				<span class="mx-0.5 h-4 w-px bg-white/10" aria-hidden="true"></span>

				<IntegrationsMenu
					bind:webSearchEnabled
					bind:imageGenerationEnabled
					bind:codeInterpreterEnabled
					bind:selectedToolIds
					onClose={focus}
				>
					<ComponentIcon className="size-[18px]" strokeWidth="1.5" />
				</IntegrationsMenu>

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
					{#if enableMessageQueue && (prompt.trim() || attachments.length)}
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
					<button
						type="button"
						class="flex size-8 items-center justify-center rounded-full text-white outline-none transition hover:bg-gray-800"
						title="语音输入"
						aria-label="语音输入"
						onclick={() => void startDictate()}
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="size-5 translate-y-[0.5px]">
							<path d="M7 4a3 3 0 016 0v6a3 3 0 11-6 0V4z" />
							<path
								d="M5.5 9.643a.75.75 0 00-1.5 0V10c0 3.06 2.29 5.585 5.25 5.954V17.5h-1.5a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5h-1.5v-1.546A6.001 6.001 0 0016 10v-.357a.75.75 0 00-1.5 0V10a4.5 4.5 0 01-9 0v-.357z"
							/>
						</svg>
					</button>

					{#if showVoiceMode}
						<button
							type="button"
							class="flex items-center self-center rounded-full bg-white p-1.5 text-black transition hover:bg-gray-100"
							title="语音模式"
							aria-label="语音模式"
							onclick={() => void startVoiceMode()}
						>
							<VoiceIcon className="size-5" strokeWidth="2.5" />
						</button>
					{:else}
						<button
							type="button"
							id="send-message-button"
							class="flex size-8 items-center justify-center rounded-full bg-white text-black transition hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-30"
							onclick={submit}
							disabled={disabled || (!prompt.trim() && attachments.length === 0)}
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
				{/if}
			</div>
		</div>
	{/if}
</div>

<CallOverlay
	bind:open={callOpen}
	{modelName}
	onClose={() => {
		callOpen = false;
	}}
	onSubmit={(content) => {
		onSubmit(content);
	}}
/>
