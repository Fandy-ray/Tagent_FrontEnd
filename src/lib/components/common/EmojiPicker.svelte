<script lang="ts">
	type Props = {
		align?: 'start' | 'end';
		selected?: string;
		onClose?: () => void;
		onSubmit?: (emoji: string) => void;
		children?: import('svelte').Snippet;
	};

	let {
		align = 'start',
		selected = '',
		onClose = () => {},
		onSubmit = () => {},
		children
	}: Props = $props();

	let open = $state(false);
	let search = $state('');
	let rootEl = $state<HTMLDivElement | null>(null);
	let panelEl = $state<HTMLDivElement | null>(null);

	const groups: { label: string; emojis: string[] }[] = [
		{
			label: '表情与情感',
			emojis: [
				'😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃', '😉', '😊', '😇', '🥰', '😍', '🤩',
				'😘', '😗', '☺️', '😚', '😙', '🥲', '😋', '😛', '😜', '🤪', '😝', '🤑', '🤗', '🤭', '🤫', '🤔',
				'🤐', '🤨', '😐', '😑', '😶', '😏', '😒', '🙄', '😬', '🤥', '😌', '😔', '😪', '🤤', '😴', '😷',
				'🤒', '🤕', '🤢', '🤮', '🥵', '🥶', '🥴', '😵', '🤯', '🤠', '🥳', '🥸', '😎', '🤓', '🧐', '😕',
				'😟', '🙁', '☹️', '😮', '😯', '😲', '😳', '🥺', '😦', '😧', '😨', '😰', '😥', '😢', '😭', '😱',
				'😖', '😣', '😞', '😓', '😩', '😫', '🥱', '😤', '😡', '😠', '🤬', '😈', '👿', '💀', '☠️', '💩',
				'🤡', '👹', '👺', '👻', '👽', '👾', '🤖', '😺', '😸', '😹', '😻', '😼', '😽', '🙀', '😿', '😾'
			]
		},
		{
			label: '手势与人物',
			emojis: [
				'👋', '🤚', '🖐️', '✋', '🖖', '👌', '🤌', '🤏', '✌️', '🤞', '🤟', '🤘', '🤙', '👈', '👉', '👆',
				'🖕', '👇', '☝️', '👍', '👎', '✊', '👊', '🤛', '🤜', '👏', '🙌', '👐', '🤲', '🤝', '🙏', '✍️',
				'💅', '🤳', '💪', '🦾', '🦵', '🦶', '👂', '🦻', '👃', '🧠', '👀', '👁️', '👅', '👄', '👶', '🧒',
				'👦', '👧', '🧑', '👨', '👩', '🧔', '🧓', '👴', '👵', '🙍', '🙎', '🙅', '🙆', '💁', '🙋', '🧏'
			]
		},
		{
			label: '物品与符号',
			emojis: [
				'💌', '💘', '💝', '💖', '💗', '💓', '💞', '💕', '💟', '❣️', '💔', '❤️', '🧡', '💛', '💚', '💙',
				'💜', '🖤', '🤍', '🤎', '💯', '💢', '💥', '💫', '💦', '💨', '🕳️', '💬', '🗨️', '🗯️', '💭', '💤',
				'🔥', '⭐', '🌟', '✨', '⚡', '☀️', '🌈', '☁️', '❄️', '💧', '🌊', '🎯', '🏆', '🥇', '🎖️', '🏅',
				'📚', '📖', '📝', '✏️', '📌', '📎', '💼', '💻', '🖥️', '📱', '⌨️', '🖱️', '💡', '🔦', '🔔', '🔒'
			]
		},
		{
			label: '食物与活动',
			emojis: [
				'🍎', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🫐', '🍈', '🍒', '🍑', '🥭', '🍍', '🥥', '🥝', '🍅',
				'🥑', '🥦', '🥬', '🥒', '🌶️', '🫑', '🌽', '🥕', '🫒', '🧄', '🧅', '🥔', '🍠', '🥐', '🥯', '🍞',
				'☕', '🍵', '🧃', '🥤', '🧋', '🍶', '🍺', '🍻', '🥂', '🍷', '🍾', '🍸', '🍹', '🧉', '🧊', '⚽',
				'🏀', '🏈', '⚾', '🎾', '🏐', '🏉', '🥏', '🎱', '🪀', '🏓', '🏸', '🏒', '🏑', '🥍', '🏏', '🪃'
			]
		}
	];

	const filteredGroups = $derived.by(() => {
		const q = search.trim().toLowerCase();
		if (!q) return groups;
		return groups
			.map((group) => ({
				...group,
				emojis: group.emojis.filter(
					(emoji) => emoji.includes(q) || group.label.toLowerCase().includes(q)
				)
			}))
			.filter((group) => group.emojis.length > 0);
	});

	const toggle = (event: MouseEvent) => {
		event.preventDefault();
		event.stopPropagation();
		open = !open;
		if (!open) {
			search = '';
			onClose();
		}
	};

	const pick = (emoji: string) => {
		onSubmit(selected === emoji ? '' : emoji);
		open = false;
		search = '';
		onClose();
	};

	$effect(() => {
		if (!open) return;
		const onPointerDown = (event: PointerEvent) => {
			const target = event.target as Node;
			if (rootEl?.contains(target) || panelEl?.contains(target)) return;
			open = false;
			search = '';
			onClose();
		};
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				open = false;
				search = '';
				onClose();
			}
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
	<button type="button" class="flex items-center" aria-expanded={open} aria-haspopup="dialog" onclick={toggle}>
		{#if children}
			{@render children()}
		{:else}
			<span class="text-base">{selected || '☺️'}</span>
		{/if}
	</button>

	{#if open}
		<div
			bind:this={panelEl}
			class={`absolute top-full z-[110] mt-2 w-80 max-w-[min(20rem,calc(100vw-2rem))] rounded-3xl border border-gray-800 bg-gray-850 text-white shadow-lg ${
				align === 'end' ? 'right-0' : 'left-0'
			}`}
			role="dialog"
			aria-label="表情选择器"
		>
			<div class="mb-1 px-4 pt-2.5 pb-2">
				<input
					type="text"
					class="w-full bg-transparent text-sm outline-none placeholder:text-gray-600"
					placeholder="搜索全部表情"
					bind:value={search}
				/>
			</div>
			<div class="h-80 overflow-y-auto px-3 pb-3 text-sm">
				{#if filteredGroups.length === 0}
					<div class="py-8 text-center text-xs text-gray-500">无结果</div>
				{:else}
					{#each filteredGroups as group (group.label)}
						<div class="mb-2 text-xs font-medium text-gray-500">{group.label}</div>
						<div class="mb-3 flex flex-wrap gap-1.5">
							{#each group.emojis as emoji}
								<button
									type="button"
									class={`cursor-pointer rounded-lg p-1.5 text-lg transition hover:bg-gray-700 ${
										selected === emoji ? 'bg-gray-700' : ''
									}`}
									onclick={() => pick(emoji)}
									title={emoji}
								>
									{emoji}
								</button>
							{/each}
						</div>
					{/each}
				{/if}
			</div>
		</div>
	{/if}
</div>
