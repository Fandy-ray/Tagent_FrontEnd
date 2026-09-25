<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import AddConnectionModal from './AddConnectionModal.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	const i18n = getI18nContext();

	type Props = {
		url?: string;
		key?: string;
		config?: Record<string, any>;
		highContrastMode?: boolean;
		onSubmit?: (connection: any) => void;
		onDelete?: () => void;
	};

	let {
		url = $bindable(''),
		key = $bindable(''),
		config = $bindable({}),
		highContrastMode = false,
		onSubmit = () => {},
		onDelete = () => {}
	}: Props = $props();

	let showConfigModal = $state(false);
	let showDeleteConfirmDialog = $state(false);
</script>

<AddConnectionModal
	edit
	bind:show={showConfigModal}
	connection={{
		url,
		key,
		config
	}}
	onDelete={() => {
		showDeleteConfirmDialog = true;
	}}
	onSubmit={(connection: any) => {
		url = connection.url;
		key = connection.key;
		config = connection.config;
		onSubmit(connection);
	}}
/>

<ConfirmDialog
	bind:show={showDeleteConfirmDialog}
	onConfirm={() => {
		onDelete();
		showConfigModal = false;
	}}
/>

<div class="flex w-full items-center gap-2">
	<Tooltip
		className="w-full relative"
		content={$i18n.t('WebUI will make requests to "{{url}}/chat/completions"', {
			url
		})}
		placement="top-start"
	>
		{#if !(config?.enable ?? true)}
			<div
				class="absolute inset-0 z-10 bg-white opacity-60 dark:bg-gray-900"
			></div>
		{/if}
		<div class="flex w-full gap-2">
			<div class="relative flex-1">
				<input
					class={`w-full bg-transparent ${highContrastMode ? '' : 'outline-hidden'}`}
					placeholder={$i18n.t('API Base URL')}
					bind:value={url}
					autocomplete="off"
				/>
			</div>
		</div>
	</Tooltip>

	<div class="flex items-center gap-1">
		<Tooltip content={$i18n.t('Configure')}>
			<button
				aria-label={$i18n.t('Open modal to configure connection')}
				class="self-center rounded-lg bg-transparent p-1 transition hover:bg-gray-100 dark:hover:bg-gray-850"
				onclick={() => {
					showConfigModal = true;
				}}
				type="button"
			>
				<Cog6 />
			</button>
		</Tooltip>

		<Tooltip content={(config?.enable ?? true) ? $i18n.t('Enabled') : $i18n.t('Disabled')}>
			<Switch
				bind:state={config.enable}
				onChange={() => {
					config.enable = config.enable ?? false;
					onSubmit({ url, key, config });
				}}
			/>
		</Tooltip>
	</div>
</div>
