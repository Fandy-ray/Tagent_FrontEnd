<script lang="ts">
	import Switch from '$lib/components/common/Switch.svelte';

	type ToolItem = { id: string; name: string; description?: string };

	type Props = {
		webSearchEnabled?: boolean;
		imageGenerationEnabled?: boolean;
		codeInterpreterEnabled?: boolean;
		selectedToolIds?: string[];
		tools?: ToolItem[];
		onClose?: () => void;
		children?: import('svelte').Snippet;
	};

	let {
		webSearchEnabled = $bindable(false),
		imageGenerationEnabled = $bindable(false),
		codeInterpreterEnabled = $bindable(false),
		selectedToolIds = $bindable([] as string[]),
		tools = [
			{ id: 'calculator', name: '计算器', description: '执行基础数学运算' },
			{ id: 'time', name: '时间查询', description: '查询当前时间与时区' }
		],
		onClose = () => {},
		children
	}: Props = $props();

	let open = $state(false);
	let tab = $state<'main' | 'tools'>('main');
	let rootEl = $state<HTMLDivElement | null>(null);
	let menuEl = $state<HTMLDivElement | null>(null);
	let menuStyle = $state('');

	const updateMenuPosition = () => {
		if (!rootEl) return;
		const rect = rootEl.getBoundingClientRect();
		const width = 280;
		let left = rect.left;
		left = Math.max(8, Math.min(left, window.innerWidth - width - 8));
		menuStyle = `position:fixed;left:${left}px;bottom:${window.innerHeight - rect.top + 8}px;width:${width}px;z-index:120;`;
	};

	const close = () => {
		open = false;
		tab = 'main';
		onClose();
	};

	const toggleTool = (id: string) => {
		if (selectedToolIds.includes(id)) {
			selectedToolIds = selectedToolIds.filter((item) => item !== id);
		} else {
			selectedToolIds = [...selectedToolIds, id];
		}
	};

	const portal = (node: HTMLElement) => {
		document.body.appendChild(node);
		return {
			destroy() {
				node.remove();
			}
		};
	};

	$effect(() => {
		if (!open) return;
		const onPointerDown = (event: PointerEvent) => {
			const target = event.target as Node;
			if (rootEl?.contains(target) || menuEl?.contains(target)) return;
			close();
		};
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') close();
		};
		const timer = window.setTimeout(() => {
			window.addEventListener('pointerdown', onPointerDown, true);
			window.addEventListener('keydown', onKeyDown);
		}, 0);
		return () => {
			window.clearTimeout(timer);
			window.removeEventListener('pointerdown', onPointerDown, true);
			window.removeEventListener('keydown', onKeyDown);
		};
	});
</script>

<div class="relative" bind:this={rootEl}>
	<button
		type="button"
		id="integration-menu-button"
		class="flex size-8 items-center justify-center rounded-full text-white outline-none transition hover:bg-gray-800"
		title="扩展功能"
		aria-label="扩展功能"
		aria-expanded={open}
		onclick={(e) => {
			e.preventDefault();
			e.stopPropagation();
			open = !open;
			if (open) updateMenuPosition();
			else tab = 'main';
		}}
	>
		{#if children}
			{@render children()}
		{/if}
	</button>
</div>

{#if open}
	<div
		bind:this={menuEl}
		use:portal
		class="fixed z-[120] max-h-72 overflow-y-auto rounded-2xl border border-gray-800 bg-gray-850 px-1 py-1 text-sm text-white shadow-lg"
		style={menuStyle}
		role="menu"
		aria-label="扩展功能"
	>
		{#if tab === 'main'}
			<button
				type="button"
				class="flex w-full cursor-pointer items-center justify-between gap-2 rounded-xl px-3 py-1.5 text-left hover:bg-gray-800/50"
				onclick={() => {
					tab = 'tools';
				}}
			>
				<span class="flex items-center gap-2">
					<svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M11.42 15.17 17.25 21A2.652 2.652 0 0 0 21 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 1 1-3.586-3.586l6.837-5.63m5.108-.233c.55-.05 1.095-.244 1.568-.575a2.25 2.25 0 0 0 .812-2.177l-.876-3.065a2.25 2.25 0 0 0-1.58-1.58l-3.065-.876a2.25 2.25 0 0 0-2.177.812 4.5 4.5 0 0 1-.575 1.568"
						></path>
					</svg>
					<span>
						工具
						<span class="ml-0.5 text-gray-500">{tools.length}</span>
					</span>
				</span>
				<svg class="size-4 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
					<path stroke-linecap="round" stroke-linejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5"></path>
				</svg>
			</button>

			<div class="flex w-full items-center justify-between gap-2 rounded-xl px-3 py-1.5">
				<span class="flex items-center gap-2">
					<svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582"
						></path>
					</svg>
					<span>联网搜索</span>
				</span>
				<Switch bind:state={webSearchEnabled} />
			</div>

			<div class="flex w-full items-center justify-between gap-2 rounded-xl px-3 py-1.5">
				<span class="flex items-center gap-2">
					<svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z"
						></path>
					</svg>
					<span>图像</span>
				</span>
				<Switch bind:state={imageGenerationEnabled} />
			</div>

			<div class="flex w-full items-center justify-between gap-2 rounded-xl px-3 py-1.5">
				<span class="flex items-center gap-2">
					<svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="m6.75 7.5 3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0 0 21 18V6a2.25 2.25 0 0 0-2.25-2.25H5.25A2.25 2.25 0 0 0 3 6v12a2.25 2.25 0 0 0 2.25 2.25Z"
						></path>
					</svg>
					<span>代码解释器</span>
				</span>
				<Switch bind:state={codeInterpreterEnabled} />
			</div>
		{:else}
			<button
				type="button"
				class="mb-1 flex w-full items-center gap-2 rounded-xl px-3 py-1.5 text-left text-gray-300 hover:bg-gray-800/50"
				onclick={() => {
					tab = 'main';
				}}
			>
				<svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
					<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5"></path>
				</svg>
				<span>返回</span>
			</button>
			{#each tools as tool (tool.id)}
				<div class="flex w-full items-center justify-between gap-2 rounded-xl px-3 py-1.5">
					<span class="min-w-0">
						<span class="block truncate">{tool.name}</span>
						{#if tool.description}
							<span class="block truncate text-xs text-gray-500">{tool.description}</span>
						{/if}
					</span>
					<Switch
						state={selectedToolIds.includes(tool.id)}
						onChange={() => toggleTool(tool.id)}
					/>
				</div>
			{/each}
		{/if}
	</div>
{/if}
