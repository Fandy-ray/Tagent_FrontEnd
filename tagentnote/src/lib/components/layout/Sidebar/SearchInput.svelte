<script lang="ts">
	import { fade } from 'svelte/transition';
	import { tick } from 'svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	type TagItem = { id: string; name: string };
	type FolderItem = { id: string; name: string };

	type Props = {
		value?: string;
		placeholder?: string;
		showClearButton?: boolean;
		tags?: TagItem[];
		folders?: FolderItem[];
		onInput?: () => void;
		onFocus?: () => void;
		onKeydown?: (e: KeyboardEvent) => void;
	};

	let {
		value = $bindable(''),
		placeholder = '搜索',
		showClearButton = false,
		tags = [],
		folders = [],
		onInput = () => {},
		onFocus = () => {},
		onKeydown = () => {}
	}: Props = $props();

	let selectedIdx = $state<number | null>(0);
	let selectedOption = $state('');
	let focused = $state(false);
	let hovering = $state(false);
	let loading = $state(false);
	let filteredItems = $state<{ id: string; name: string; type: string }[]>([]);

	const lastWord = $derived(value ? (value.split(' ').at(-1) ?? '') : value);

	const options = [
		{ name: 'tag:', description: '按标签搜索' },
		{ name: 'folder:', description: '按分组搜索' },
		{ name: 'pinned:', description: '搜索置顶对话' },
		{ name: 'shared:', description: '搜索分享对话' },
		{ name: 'archived:', description: '搜索归档对话' }
	];

	const filteredOptions = $derived(options.filter((option) => option.name.startsWith(lastWord)));

	const initItems = async () => {
		loading = true;
		await tick();

		if (lastWord.startsWith('tag:')) {
			filteredItems = [
				...tags,
				{ id: 'none', name: '无标签' }
			]
				.filter((tag) => {
					const tagName = lastWord.slice(4);
					if (tagName) {
						const tagId = tagName.replaceAll(' ', '_').toLowerCase();
						return tag.id !== tagId && tag.id.startsWith(tagId);
					}
					return true;
				})
				.map((tag) => ({ id: tag.id, name: tag.name, type: 'tag' }));
		} else if (lastWord.startsWith('folder:')) {
			filteredItems = folders
				.filter((folder) => {
					const folderName = lastWord.slice(7);
					if (folderName) {
						const id = folder.name.replaceAll(' ', '_').toLowerCase();
						const folderId = folderName.replaceAll(' ', '_').toLowerCase();
						return id !== folderId && id.startsWith(folderId);
					}
					return true;
				})
				.map((folder) => ({
					id: folder.name.replaceAll(' ', '_').toLowerCase(),
					name: folder.name,
					type: 'folder'
				}));
		} else if (lastWord.startsWith('pinned:')) {
			filteredItems = [
				{ id: 'true', name: 'true', type: 'pinned' },
				{ id: 'false', name: 'false', type: 'pinned' }
			].filter((item) => {
				const pinnedValue = lastWord.slice(7);
				return pinnedValue ? item.id.startsWith(pinnedValue) && item.id !== pinnedValue : true;
			});
		} else if (lastWord.startsWith('shared:')) {
			filteredItems = [
				{ id: 'true', name: 'true', type: 'shared' },
				{ id: 'false', name: 'false', type: 'shared' }
			].filter((item) => {
				const sharedValue = lastWord.slice(7);
				return sharedValue ? item.id.startsWith(sharedValue) && item.id !== sharedValue : true;
			});
		} else if (lastWord.startsWith('archived:')) {
			filteredItems = [
				{ id: 'true', name: 'true', type: 'archived' },
				{ id: 'false', name: 'false', type: 'archived' }
			].filter((item) => {
				const archivedValue = lastWord.slice(9);
				return archivedValue
					? item.id.startsWith(archivedValue) && item.id !== archivedValue
					: true;
			});
		} else {
			filteredItems = [];
		}

		loading = false;
	};

	$effect(() => {
		if (lastWord) {
			void initItems();
		} else {
			filteredItems = [];
		}
	});

	const clearSearchInput = () => {
		value = '';
		onInput();
	};
</script>

<div class="relative z-10 mb-1 flex justify-center space-x-2 px-1" id="search-container">
	<div class="flex w-full rounded-xl" id="chat-search">
		<div class="self-center rounded-l-xl bg-transparent py-2 text-gray-300">
			<Search />
		</div>

		<input
			id="search-input"
			class="w-full rounded-r-xl bg-transparent py-1.5 pl-2.5 text-sm text-gray-200 outline-none"
			{placeholder}
			autocomplete="off"
			maxlength="500"
			bind:value
			oninput={() => onInput()}
			onclick={() => {
				if (!focused) {
					onFocus();
					hovering = false;
					focused = true;
				}
			}}
			onblur={() => {
				if (!hovering) focused = false;
			}}
			onkeydown={(e) => {
				if (e.key === 'Enter') {
					if (filteredItems.length > 0) {
						document.getElementById(`search-item-${selectedIdx}`)?.click();
						return;
					}
					if (filteredOptions.length > 0) {
						document.getElementById(`search-option-${selectedIdx}`)?.click();
						return;
					}
				}

				if (e.key === 'ArrowUp') {
					e.preventDefault();
					selectedIdx = Math.max(0, (selectedIdx ?? 0) - 1);
				} else if (e.key === 'ArrowDown') {
					e.preventDefault();
					if (filteredItems.length > 0) {
						if (selectedIdx === filteredItems.length - 1) focused = false;
						else selectedIdx = Math.min((selectedIdx ?? 0) + 1, filteredItems.length - 1);
					} else if (selectedIdx === filteredOptions.length - 1) {
						focused = false;
					} else {
						selectedIdx = Math.min((selectedIdx ?? 0) + 1, filteredOptions.length - 1);
					}
				} else {
					if (!focused) {
						onFocus();
						hovering = false;
						focused = true;
					}
					selectedIdx = 0;
				}

				document
					.querySelector('[data-selected="true"]')
					?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });

				if (!document.getElementById('search-options-container')) {
					onKeydown(e);
				}
			}}
		/>

		{#if showClearButton && value}
			<div class="translate-y-[0.5px] self-center rounded-l-xl bg-transparent pl-1.5">
				<button
					type="button"
					class="rounded-full p-0.5 transition hover:bg-gray-800"
					onclick={clearSearchInput}
					aria-label="清除搜索"
				>
					<XMark className="size-3" strokeWidth="2" />
				</button>
			</div>
		{/if}
	</div>

	{#if focused && (filteredOptions.length > 0 || filteredItems.length > 0)}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="absolute top-0 right-1 left-0 z-10 mt-8 rounded-2xl border border-gray-800 bg-gray-950 shadow-lg"
			id="search-options-container"
			transition:fade={{ duration: 50 }}
			onmouseenter={() => {
				hovering = true;
				selectedIdx = null;
			}}
			onmouseleave={() => {
				hovering = false;
				selectedIdx = 0;
			}}
		>
			<div class="px-3 py-2.5 text-xs">
				{#if filteredItems.length > 0}
					<div class="mb-1 px-1 font-medium capitalize text-gray-300">
						{loading ? '…' : selectedOption}
					</div>
					<div class="max-h-60 overflow-auto">
						{#each filteredItems as item, itemIdx}
							<button
								type="button"
								class="flex w-full gap-1 rounded px-1.5 py-0.5 hover:bg-gray-900 {selectedIdx ===
								itemIdx
									? 'bg-gray-900'
									: ''}"
								data-selected={selectedIdx === itemIdx ? 'true' : undefined}
								id="search-item-{itemIdx}"
								onclick={(e) => {
									e.stopPropagation();
									const words = value.split(' ');
									words.pop();
									words.push(`${item.type}:${item.id} `);
									value = words.join(' ');
									filteredItems = [];
									onInput();
								}}
							>
								<div class="line-clamp-1 shrink-0 font-medium text-gray-300">{item.name}</div>
								<div class="line-clamp-1 text-gray-500">{item.id}</div>
							</button>
						{/each}
					</div>
				{:else if filteredOptions.length > 0}
					<div class="mb-1 px-1 font-medium text-gray-300">搜索选项</div>
					<div class="max-h-60 overflow-auto">
						{#each filteredOptions as option, optionIdx}
							<button
								type="button"
								class="flex w-full gap-1 rounded px-1.5 py-0.5 hover:bg-gray-900 {selectedIdx ===
								optionIdx
									? 'bg-gray-900'
									: ''}"
								id="search-option-{optionIdx}"
								onclick={(e) => {
									e.stopPropagation();
									const words = value.split(' ');
									words.pop();
									words.push(`${option.name}`);
									selectedOption = option.name.replace(':', '');
									value = words.join(' ');
									onInput();
								}}
							>
								<div class="font-medium text-gray-300">{option.name}</div>
								<div class="line-clamp-1 text-gray-500">{option.description}</div>
							</button>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
