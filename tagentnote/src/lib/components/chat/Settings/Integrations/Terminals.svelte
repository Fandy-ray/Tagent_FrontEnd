<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	const i18n = getI18nContext();

	import Plus from '$lib/components/icons/Plus.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Connection from './Terminals/Connection.svelte';
	import AddTerminalServerModal from './Terminals/AddTerminalServerModal.svelte';

	type TerminalServer = {
		url: string;
		key: string;
		name: string;
		path: string;
		enabled: boolean;
		auth_type?: string;
	};

	type Props = {
		servers?: TerminalServer[];
		onChange?: (servers: TerminalServer[]) => void;
	};

	let { servers = $bindable([]), onChange = () => {} }: Props = $props();

	let showAddModal = $state(false);

	const addServer = (server: TerminalServer) => {
		servers = [...servers, server];
		onChange(servers);
	};

	const enableServer = (idx: number) => {
		servers = servers.map((s, i) => ({ ...s, enabled: i === idx }));
		onChange(servers);
	};

	const disableServer = (idx: number) => {
		servers = servers.map((s, i) => (i === idx ? { ...s, enabled: false } : s));
		onChange(servers);
	};

	const updateServer = (idx: number, updated: TerminalServer) => {
		servers = servers.map((s, i) => (i === idx ? updated : s));
		onChange(servers);
	};

	const deleteServer = (idx: number) => {
		servers = servers.filter((_, i) => i !== idx);
		onChange(servers);
	};
</script>

<AddTerminalServerModal
	bind:show={showAddModal}
	onSubmit={(server: TerminalServer) => addServer(server)}
/>

<div>
	<div class="mb-1 flex items-center justify-between">
		<div class="flex items-center gap-2">
			<div class="font-medium">{$i18n.t('Open Terminal')}</div>
			<span
				class="rounded-full bg-gray-100 px-1.5 py-0.5 text-[0.65rem] font-medium text-gray-500 uppercase dark:bg-gray-800 dark:text-gray-400"
				>{$i18n.t('Experimental')}</span
			>
		</div>
		<Tooltip content={$i18n.t('Add Connection')}>
			<button
				class="px-1"
				onclick={() => (showAddModal = true)}
				type="button"
				aria-label={$i18n.t('Add Connection')}
			>
				<Plus />
			</button>
		</Tooltip>
	</div>

	<div class="flex flex-col gap-1.5">
		{#each servers as server, idx (server.url || idx)}
			<Connection
				bind:connection={servers[idx]}
				onSubmit={(updated: TerminalServer) => updateServer(idx, updated)}
				onDelete={() => deleteServer(idx)}
				onEnable={() => enableServer(idx)}
				onDisable={() => disableServer(idx)}
			/>
		{/each}
	</div>

	{#if servers.length === 0}
		<div class="text-xs text-gray-400 dark:text-gray-500">
			{$i18n.t('No terminal connections configured.')}
			<a
				href="https://github.com/open-webui/open-terminal"
				target="_blank"
				rel="noopener noreferrer"
				class="underline hover:text-gray-700 dark:hover:text-gray-200"
			>
				{$i18n.t('Learn more')} ↗
			</a>
		</div>
	{/if}
</div>
