<script lang="ts">
	import { browser } from '$app/environment';

	import Collapsible from '$lib/components/common/Collapsible.svelte';

	type Props = {
		params?: Record<string, any>;
		embed?: boolean;
		onClose?: () => void;
		onChange?: (params: Record<string, any>) => void;
	};

	let {
		params = $bindable({}),
		embed = false,
		onClose = () => {},
		onChange = () => {}
	}: Props = $props();

	const getOpen = (key: string, fallback = true): boolean => {
		if (!browser) return fallback;
		const v = localStorage.getItem(`chatControls.${key}`);
		return v !== null ? v === 'true' : fallback;
	};

	const setOpen = (key: string) => (open: boolean) => {
		if (!browser) return;
		localStorage.setItem(`chatControls.${key}`, String(open));
	};

	let showSystemPrompt = $state(getOpen('systemPrompt'));
	let showAdvancedParams = $state(false);
	let AdvancedParamsComp = $state<any>(null);
	let advancedLoading = $state(false);

	const notify = () => {
		onChange(params);
	};

	const toggleAdvanced = async (open: boolean) => {
		showAdvancedParams = open;
		setOpen('advancedParams')(open);
		if (!open) {
			notify();
			return;
		}
		if (!AdvancedParamsComp) {
			advancedLoading = true;
			try {
				const mod = await import('$lib/components/chat/Settings/Advanced/AdvancedParams.svelte');
				AdvancedParamsComp = mod.default;
			} finally {
				advancedLoading = false;
			}
		}
	};
</script>

<div class="text-white">
	{#if !embed}
		<div class="mb-2 flex items-center justify-between text-gray-100">
			<div class="text-md self-center font-medium">对话高级设置</div>
			<button type="button" class="self-center" aria-label="关闭对话控制" onclick={onClose}>
				<svg
					class="size-3.5"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
				>
					<path stroke-linecap="round" d="M6 6l12 12M18 6L6 18"></path>
				</svg>
			</button>
		</div>
	{/if}

	<div class="px-0.5 py-0.5 text-sm text-gray-200">
		<Collapsible
			title="系统提示词"
			bind:open={showSystemPrompt}
			onChange={setOpen('systemPrompt')}
			buttonClassName="w-full text-gray-200 hover:text-white transition"
		>
			{#snippet content()}
				<textarea
					bind:value={params.system}
					class="w-full resize-y bg-transparent py-1.5 text-xs text-gray-100 outline-none placeholder:text-gray-500"
					rows="4"
					placeholder="输入系统提示词"
					oninput={notify}></textarea>
			{/snippet}
		</Collapsible>

		<hr class="my-2 border-gray-800" />

		<Collapsible
			title="高级参数"
			bind:open={showAdvancedParams}
			onChange={toggleAdvanced}
			buttonClassName="w-full text-gray-200 hover:text-white transition"
		>
			{#snippet content()}
				<div class="mt-1.5 text-sm text-gray-200">
					{#if advancedLoading || !AdvancedParamsComp}
						<p class="py-2 text-xs text-gray-500">正在加载高级参数…</p>
					{:else}
						<AdvancedParamsComp admin={true} custom={true} bind:params />
					{/if}
				</div>
			{/snippet}
		</Collapsible>
	</div>
</div>
