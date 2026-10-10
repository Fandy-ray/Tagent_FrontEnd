<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	const i18n = getI18nContext();

	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import AddTerminalServerModal from './AddTerminalServerModal.svelte';
	import Cloud from '$lib/components/icons/Cloud.svelte';

	type Connection = {
		url: string;
		key: string;
		name: string;
		path: string;
		enabled: boolean;
		auth_type?: string;
		[key: string]: any;
	};

	type Props = {
		connection?: Connection;
		onSubmit?: (c: Connection) => void;
		onDelete?: () => void;
		onEnable?: () => void;
		onDisable?: () => void;
	};

	let {
		connection = $bindable({ url: '', key: '', name: '', path: '/openapi.json', enabled: false }),
		onSubmit = () => {},
		onDelete = () => {},
		onEnable = () => {},
		onDisable = () => {}
	}: Props = $props();

	let showConfigModal = $state(false);
	let showDeleteConfirmDialog = $state(false);
</script>

<AddTerminalServerModal
	direct
	edit
	bind:show={showConfigModal}
	{connection}
	onDelete={() => {
		showDeleteConfirmDialog = true;
	}}
	onSubmit={(c: any) => {
		connection = c;
		onSubmit(c);
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
	<Tooltip className="w-full relative" content={''} placement="top-start">
		<div class="flex w-full">
			<div class={`flex flex-1 items-center gap-1.5 ${!connection?.enabled ? 'opacity-50' : ''}`}>
				<Tooltip content={$i18n.t('Terminal')}>
					<Cloud className="size-4" strokeWidth="1.5" />
				</Tooltip>

				<div class="w-full bg-transparent text-sm outline-hidden">
					{connection.name || connection.url || $i18n.t('New Terminal')}
				</div>
			</div>
		</div>
	</Tooltip>

	<div class="flex items-center gap-1">
		<Tooltip content={$i18n.t('Configure')}>
			<button
				class="dark:hover:bg-gray-850 self-center rounded-lg bg-transparent p-1 transition hover:bg-gray-100"
				onclick={() => {
					showConfigModal = true;
				}}
				type="button"
			>
				<Cog6 />
			</button>
		</Tooltip>

		<Tooltip content={connection?.enabled ? $i18n.t('Enabled') : $i18n.t('Disabled')}>
			<Switch
				state={connection?.enabled}
				onChange={() => (connection?.enabled ? onDisable() : onEnable())}
			/>
		</Tooltip>
	</div>
</div>
