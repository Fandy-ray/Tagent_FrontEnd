<script lang="ts">
	import Plus from '$lib/components/icons/Plus.svelte';

	type SuggestionPrompt = {
		content: string;
		title: [string, string];
	};

	type Props = {
		promptSuggestions?: SuggestionPrompt[];
	};

	let { promptSuggestions = $bindable([]) }: Props = $props();

	let fileInput: HTMLInputElement | null = $state(null);

	const addPrompt = () => {
		if (promptSuggestions.length === 0 || promptSuggestions.at(-1)?.content !== '') {
			promptSuggestions = [...promptSuggestions, { content: '', title: ['', ''] }];
		}
	};

	const onImport = async (e: Event) => {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		try {
			const raw = JSON.parse(await file.text()) as unknown;
			const list = Array.isArray(raw) ? raw : [raw];
			const mapped: SuggestionPrompt[] = list.map((item) => {
				if (typeof item === 'string') return { content: item, title: ['', ''] };
				const obj = item as { content?: string; title?: string | [string, string] };
				let title: [string, string] = ['', ''];
				if (typeof obj.title === 'string') title = [obj.title, ''];
				else if (Array.isArray(obj.title)) title = [obj.title[0] ?? '', obj.title[1] ?? ''];
				return { content: obj.content ?? '', title };
			});
			promptSuggestions = [...promptSuggestions, ...mapped];
		} catch {
			/* ignore */
		}
		input.value = '';
	};

	const onExport = () => {
		const blob = new Blob([JSON.stringify(promptSuggestions, null, 2)], {
			type: 'application/json'
		});
		const href = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = href;
		a.download = `prompt-suggestions-export-${Date.now()}.json`;
		a.click();
		URL.revokeObjectURL(href);
	};
</script>

<input
	bind:this={fileInput}
	id="prompt-suggestions-import-input"
	type="file"
	accept=".json,application/json"
	class="hidden"
	onchange={onImport}
/>

<div class="space-y-3">
	<div class="mb-1.5 flex w-full items-center justify-between gap-2">
		<div class="w-full flex-1 shrink-0 self-center text-xs text-gray-200">默认推荐提示词</div>
		<div class="flex justify-end gap-2">
			<button
				class="flex items-center rounded-xl bg-transparent py-1 text-xs font-medium text-gray-200 transition"
				type="button"
				onclick={() => fileInput?.click()}
			>
				导入
			</button>
			{#if promptSuggestions.length}
				<button
					class="flex items-center rounded-xl bg-transparent py-1 text-xs font-medium text-gray-200 transition"
					type="button"
					onclick={onExport}
				>
					导出
				</button>
			{/if}
			<button
				class="flex items-center rounded-xl px-1.5 text-sm font-medium transition"
				type="button"
				aria-label="添加提示词"
				onclick={addPrompt}
			>
				<Plus className="size-3" />
			</button>
		</div>
	</div>

	{#if promptSuggestions.length > 0}
		<div class="flex flex-col gap-2">
			{#each promptSuggestions as prompt, promptIdx (promptIdx)}
				<div class="flex rounded-2xl border border-gray-850/30 bg-transparent p-2">
					<div class="flex w-full flex-col gap-1 px-2 md:flex-row md:gap-2">
						<div class="min-w-60 gap-0.5">
							<input
								class="w-full bg-transparent text-sm outline-none placeholder:text-gray-500"
								placeholder="标题"
								bind:value={prompt.title[0]}
							/>
							<input
								class="w-full bg-transparent text-sm text-gray-400 outline-none placeholder:text-gray-600"
								placeholder="副标题"
								bind:value={prompt.title[1]}
							/>
						</div>
						<textarea
							class="w-full resize-none self-center bg-transparent text-sm outline-none placeholder:text-gray-500"
							placeholder="提示词"
							rows="2"
							bind:value={prompt.content}
						></textarea>
					</div>
					<button
						aria-label="删除"
						class="self-start p-1 text-gray-400 hover:text-white"
						type="button"
						onclick={() => {
							promptSuggestions = promptSuggestions.filter((_, i) => i !== promptIdx);
						}}
					>
						<svg viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4" aria-hidden="true">
							<path
								d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
							/>
						</svg>
					</button>
				</div>
			{/each}
		</div>
	{:else}
		<div class="mb-1.5 w-full text-center text-xs text-gray-500">暂无提示词</div>
	{/if}
</div>
