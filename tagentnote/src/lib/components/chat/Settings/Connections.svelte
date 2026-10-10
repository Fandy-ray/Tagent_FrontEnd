<script lang="ts">
	import { onMount } from 'svelte';
	import { getI18nContext } from '$lib/i18n';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import Star from '$lib/components/icons/Star.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	const i18n = getI18nContext();

	type Provider = {
		id: string;
		name: string;
		base_url: string;
		upstream_model: string;
		auth_mode: 'bearer' | 'none';
		api_key_masked?: string;
		model_id?: string;
		temperature: number;
		enabled: boolean;
	};

	type Props = {
		settings: any;
		saveSettings: (updated: any) => Promise<void> | void;
		onSave?: () => void;
	};

	let { settings, saveSettings, onSave = () => {} }: Props = $props();

	let providers: Provider[] = $state([]);
	let defaultModelId = $state('');
	let loading = $state(true);
	let saving = $state(false);
	let showForm = $state(false);
	let editingId = $state('');
	let error = $state('');
	let showConfirm = $state(false);
	let confirmAction: null | { title: string; message: string; run: () => Promise<void> | void } =
		$state(null);

	const emptyForm = () => ({
		name: '',
		base_url: 'https://',
		upstream_model: '',
		auth_mode: 'bearer' as 'bearer' | 'none',
		api_key: '',
		temperature: 0.1,
		enabled: true
	});

	let form = $state(emptyForm());

	// Load existing providers from settings.directConnections
	const load = () => {
		loading = true;
		error = '';
		try {
			const stored: any = settings?.directConnections;
			if (Array.isArray(stored)) {
				providers = stored as Provider[];
			} else if (stored && typeof stored === 'object') {
				// Migrate from old OPENAI_API_BASE_URLS/KEYS/CONFIGS format to array
				const urls: any[] = stored.OPENAI_API_BASE_URLS ?? [];
				const keys: any[] = stored.OPENAI_API_KEYS ?? [];
				const configs: any = stored.OPENAI_API_CONFIGS ?? {};
				providers = urls.map((url: any, idx: number) => ({
					id: `migrated-${idx}-${Date.now()}`,
					name: configs?.[idx]?.name || `Connection ${idx + 1}`,
					base_url: url,
					upstream_model: configs?.[idx]?.upstream_model || '',
					auth_mode: 'bearer',
					api_key_masked: keys[idx]
						? `${String(keys[idx]).slice(0, 4)}${'*'.repeat(Math.max(4, String(keys[idx]).length - 4))}`
						: undefined,
					model_id: configs?.[idx]?.model_id,
					temperature: configs?.[idx]?.temperature ?? 0.1,
					enabled: configs?.[idx]?.enable ?? true
				}));
			} else {
				providers = [];
			}
			defaultModelId = settings?.defaultAgentModelId ?? '';
		} catch (exception) {
			error = exception instanceof Error ? exception.message : 'Unable to load models.';
		} finally {
			loading = false;
		}
	};

	const persist = async () => {
		await saveSettings({
			directConnections: providers,
			defaultAgentModelId: defaultModelId
		});
		onSave();
	};

	const startCreate = () => {
		editingId = '';
		form = emptyForm();
		error = '';
		showForm = true;
	};

	const startEdit = (provider: Provider) => {
		editingId = provider.id;
		form = {
			name: provider.name,
			base_url: provider.base_url,
			upstream_model: provider.upstream_model,
			auth_mode: provider.auth_mode,
			api_key: '',
			temperature: provider.temperature,
			enabled: provider.enabled
		};
		error = '';
		showForm = true;
	};

	const save = async () => {
		error = '';
		if (!form.name.trim() || !form.base_url.trim() || !form.upstream_model.trim()) {
			error = 'Name, Base URL, and model are required.';
			return;
		}
		if (!editingId && form.auth_mode === 'bearer' && !form.api_key) {
			error = 'API Key is required for Bearer authentication.';
			return;
		}
		saving = true;
		try {
			const id = editingId || `provider-${Date.now()}`;
			const newProvider: Provider = {
				id,
				name: form.name.trim(),
				base_url: form.base_url.trim(),
				upstream_model: form.upstream_model.trim(),
				auth_mode: form.auth_mode,
				api_key_masked: form.api_key
					? `${form.api_key.slice(0, 4)}${'*'.repeat(Math.max(4, form.api_key.length - 4))}`
					: providers.find((p) => p.id === id)?.api_key_masked,
				model_id: `${form.name.trim().toLowerCase().replace(/\s+/g, '-')}__${form.upstream_model.trim()}`,
				temperature: form.temperature,
				enabled: form.enabled
			};

			if (editingId) {
				providers = providers.map((p) => (p.id === id ? newProvider : p));
			} else {
				providers = [...providers, newProvider];
			}

			showForm = false;
			await persist();
		} catch (exception) {
			error = exception instanceof Error ? exception.message : 'Save failed.';
		} finally {
			saving = false;
		}
	};

	const updateEnabled = async (provider: Provider, enabled: boolean) => {
		providers = providers.map((p) => (p.id === provider.id ? { ...p, enabled } : p));
		await persist();
	};

	const requestToggle = (provider: Provider, enabled: boolean) => {
		if (enabled) {
			updateEnabled(provider, true).catch((exception) => (error = exception.message ?? ''));
			return;
		}
		confirmAction = {
			title: 'Disable model',
			message: 'This model will immediately disappear from your model selector.',
			run: () => updateEnabled(provider, false)
		};
		showConfirm = true;
	};

	const requestDelete = (provider: Provider) => {
		confirmAction = {
			title: 'Delete model configuration',
			message: 'This action cannot be undone.',
			run: async () => {
				providers = providers.filter((p) => p.id !== provider.id);
				if (defaultModelId === provider.model_id) defaultModelId = '';
				await persist();
			}
		};
		showConfirm = true;
	};

	const setDefault = async (provider: Provider) => {
		defaultModelId = provider.model_id ?? provider.id;
		await persist();
	};

	onMount(load);
</script>

<ConfirmDialog
	bind:show={showConfirm}
	title={confirmAction?.title ?? ''}
	message={confirmAction?.message ?? ''}
	onConfirm={async () => {
		try {
			await confirmAction?.run();
		} catch (exception) {
			error = exception instanceof Error ? exception.message : 'Update failed.';
		}
	}}
/>

<section
	class="dark:border-gray-850 mb-5 border-b border-gray-100 pb-5"
	aria-labelledby="private-models-title"
>
	<div class="mb-2 flex items-center justify-between">
		<div>
			<div id="private-models-title" class="font-medium">
				{$i18n.t('Private Agent Models')}
			</div>
			<div class="text-xs text-gray-500">
				{$i18n.t('Keys are encrypted and stored by the server.')}
			</div>
		</div>
		<Tooltip content={$i18n.t('Add model')}>
			<button
				type="button"
				class="dark:hover:bg-gray-850 rounded-lg p-1 hover:bg-gray-100"
				aria-label={$i18n.t('Add model')}
				onclick={startCreate}
			>
				<Plus />
			</button>
		</Tooltip>
	</div>

	{#if loading}
		<div class="flex h-16 items-center justify-center">
			<Spinner className="size-5" />
		</div>
	{:else if providers.length === 0 && !showForm}
		<div
			class="rounded-lg border border-dashed border-gray-200 px-3 py-4 text-center text-xs text-gray-500 dark:border-gray-800"
		>
			{$i18n.t('No private models configured.')}
		</div>
	{:else}
		<div class="flex flex-col gap-1.5">
			{#each providers as provider (provider.id)}
				<div
					class:opacity-60={!provider.enabled}
					class="dark:border-gray-850 flex min-w-0 items-center gap-2 rounded-lg border border-gray-100 px-2.5 py-2"
				>
					<div class="min-w-0 flex-1">
						<div class="flex items-center gap-1.5">
							<span class="truncate font-medium">{provider.name}</span>
							{#if provider.model_id === defaultModelId}
								<span class="dark:bg-gray-850 rounded bg-gray-100 px-1.5 py-0.5 text-[10px]">
									{$i18n.t('Default')}
								</span>
							{/if}
						</div>
						<div class="truncate text-xs text-gray-500">
							{provider.upstream_model} · {provider.api_key_masked || $i18n.t('No authentication')}
						</div>
					</div>
					<Tooltip content={$i18n.t('Set as default')}>
						<button
							type="button"
							class="dark:hover:bg-gray-850 rounded p-1 hover:bg-gray-100"
							aria-label={$i18n.t('Set as default')}
							onclick={() => setDefault(provider)}
						>
							<Star className="size-4" />
						</button>
					</Tooltip>
					<Tooltip content={$i18n.t('Edit')}>
						<button
							type="button"
							class="dark:hover:bg-gray-850 rounded p-1 hover:bg-gray-100"
							aria-label={$i18n.t('Edit')}
							onclick={() => startEdit(provider)}
						>
							<Pencil className="size-4" />
						</button>
					</Tooltip>
					<Tooltip content={provider.enabled ? $i18n.t('Enabled') : $i18n.t('Disabled')}>
						<Switch state={provider.enabled} onChange={(value) => requestToggle(provider, value)} />
					</Tooltip>
					<Tooltip content={$i18n.t('Delete')}>
						<button
							type="button"
							class="dark:hover:bg-gray-850 rounded p-1 hover:bg-gray-100"
							aria-label={$i18n.t('Delete')}
							onclick={() => requestDelete(provider)}
						>
							<XMark className="size-4" />
						</button>
					</Tooltip>
				</div>
			{/each}
		</div>
	{/if}

	{#if showForm}
		<div
			class="mt-3 grid grid-cols-1 gap-2 rounded-lg bg-gray-50 p-3 sm:grid-cols-2 dark:bg-gray-900"
		>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">{$i18n.t('Configuration name')}</span>
				<input
					bind:value={form.name}
					maxlength="128"
					class="rounded-lg border border-gray-200 bg-white px-3 py-2 outline-hidden focus:border-gray-400 dark:border-gray-800 dark:bg-gray-950"
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">{$i18n.t('Upstream model')}</span>
				<input
					bind:value={form.upstream_model}
					maxlength="256"
					class="rounded-lg border border-gray-200 bg-white px-3 py-2 outline-hidden focus:border-gray-400 dark:border-gray-800 dark:bg-gray-950"
				/>
			</label>
			<label class="flex flex-col gap-1 sm:col-span-2">
				<span class="text-xs text-gray-500">Base URL</span>
				<input
					bind:value={form.base_url}
					maxlength="2048"
					class="rounded-lg border border-gray-200 bg-white px-3 py-2 outline-hidden focus:border-gray-400 dark:border-gray-800 dark:bg-gray-950"
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">{$i18n.t('Authentication')}</span>
				<select
					bind:value={form.auth_mode}
					class="rounded-lg border border-gray-200 bg-white px-3 py-2 outline-hidden dark:border-gray-800 dark:bg-gray-950"
				>
					<option value="bearer">Bearer</option>
					<option value="none">{$i18n.t('None')}</option>
				</select>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">Temperature</span>
				<input
					type="number"
					min="0"
					max="2"
					step="0.1"
					bind:value={form.temperature}
					class="rounded-lg border border-gray-200 bg-white px-3 py-2 outline-hidden dark:border-gray-800 dark:bg-gray-950"
				/>
			</label>
			{#if form.auth_mode === 'bearer'}
				<label class="flex flex-col gap-1 sm:col-span-2">
					<span class="text-xs text-gray-500">API Key</span>
					<div
						class="rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-gray-950"
					>
						<SensitiveInput
							id="agent-user-provider-key"
							bind:value={form.api_key}
							required={!editingId}
							placeholder={editingId
								? $i18n.t('Leave blank to keep the existing key')
								: $i18n.t('Enter API Key')}
						/>
					</div>
				</label>
			{/if}
			{#if error}
				<div class="text-xs text-red-600 sm:col-span-2" role="alert">{error}</div>
			{/if}
			<div class="flex justify-end gap-2 sm:col-span-2">
				<button
					type="button"
					class="rounded-lg px-3 py-1.5 hover:bg-gray-200 dark:hover:bg-gray-800"
					onclick={() => (showForm = false)}
				>
					{$i18n.t('Cancel')}
				</button>
				<button
					type="button"
					disabled={saving}
					class="rounded-lg bg-gray-900 px-3 py-1.5 font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
					onclick={save}
				>
					{saving ? $i18n.t('Saving...') : $i18n.t('Save')}
				</button>
			</div>
		</div>
	{:else if error}
		<div class="mt-2 text-xs text-red-600" role="alert">{error}</div>
	{/if}
</section>

<div
	class="dark:border-gray-850 flex flex-col gap-1 border-t border-gray-100 pt-3 text-xs text-gray-500"
>
	<div>{$i18n.t('Connect to your own OpenAI compatible API endpoints.')}</div>
	<div>
		{$i18n.t('CORS must be properly configured by the provider to allow requests from Open WebUI.')}
	</div>
</div>
