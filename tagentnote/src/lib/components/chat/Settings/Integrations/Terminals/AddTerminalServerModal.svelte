<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	const i18n = getI18nContext();

	import Modal from '$lib/components/common/Modal.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	type Props = {
		show?: boolean;
		edit?: boolean;
		direct?: boolean;
		connection?: any;
		onSubmit?: (c: any) => void;
		onDelete?: () => void;
	};

	let {
		show = $bindable(false),
		edit = false,
		direct = false,
		connection = null,
		onSubmit = () => {},
		onDelete = () => {}
	}: Props = $props();

	let url = $state('');
	let key = $state('');
	let auth_type = $state<string>('bearer');
	let name = $state('');
	let path = $state('/openapi.json');
	let enable = $state(true);
	let loading = $state(false);
	let showDeleteConfirmDialog = $state(false);

	const submitHandler = async () => {
		loading = true;
		try {
			const payload = {
				url: url.replace(/\/$/, ''),
				key,
				auth_type,
				name,
				path: path || '/openapi.json',
				enabled: enable
			};

			await onSubmit(payload);

			loading = false;
			show = false;

			url = '';
			key = '';
			auth_type = 'bearer';
			name = '';
			path = '/openapi.json';
			enable = true;
		} catch {
			loading = false;
		}
	};

	const init = () => {
		if (connection) {
			url = connection.url ?? '';
			key = connection.key ?? '';
			auth_type = connection.auth_type ?? 'bearer';
			name = connection.name ?? '';
			path = connection.path ?? '/openapi.json';
			enable = connection.enabled ?? connection.enable ?? true;
		}
	};

	$effect(() => {
		if (show) {
			init();
		}
	});
</script>

<Modal size="sm" bind:show>
	<div>
		<div class="flex justify-between px-5 pt-4 pb-2 dark:text-gray-100">
			<h1 class="self-center text-lg font-medium">
				{#if edit}
					{$i18n.t('Edit Connection')}
				{:else}
					{$i18n.t('Add Connection')}
				{/if}
			</h1>

			<button
				class="self-center"
				aria-label={$i18n.t('Close')}
				onclick={() => {
					show = false;
				}}
			>
				<XMark className={'size-5'} />
			</button>
		</div>

		<div class="flex w-full flex-col px-4 pb-4 dark:text-gray-200">
			<form
				class="flex w-full flex-col"
				onsubmit={(e) => {
					e.preventDefault();
					submitHandler();
				}}
			>
				<div class="px-1">
					<div class="flex flex-col gap-2">
						<div class="flex flex-col">
							<label for="term-name" class="mb-0.5 text-xs text-gray-500">
								{$i18n.t('Name')}
							</label>
							<input
								id="term-name"
								class="bg-transparent text-sm outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700"
								type="text"
								bind:value={name}
								placeholder={$i18n.t('Enter name')}
							/>
						</div>

						<div class="flex flex-col">
							<label for="term-url" class="mb-0.5 text-xs text-gray-500">
								{$i18n.t('URL')}
							</label>
							<div class="flex items-center gap-1">
								<input
									id="term-url"
									class="w-full flex-1 bg-transparent text-sm outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700"
									type="text"
									bind:value={url}
									placeholder={$i18n.t('API Base URL')}
									required
								/>
								<Tooltip content={enable ? $i18n.t('Enabled') : $i18n.t('Disabled')}>
									<Switch bind:state={enable} />
								</Tooltip>
							</div>
						</div>

						<div class="flex flex-col">
							<label for="term-auth" class="text-xs text-gray-500">
								{$i18n.t('Auth')}
							</label>
							<div class="flex gap-2">
								<div class="flex-shrink-0 self-start">
									<select
										id="term-auth"
										class="w-full bg-transparent pr-5 text-sm outline-hidden"
										bind:value={auth_type}
									>
										<option value="none">{$i18n.t('None')}</option>
										<option value="bearer">{$i18n.t('Bearer')}</option>
									</select>
								</div>
								<div class="flex flex-1 items-center">
									{#if auth_type === 'bearer'}
										<SensitiveInput
											bind:value={key}
											placeholder={$i18n.t('API Key')}
											required={false}
										/>
									{:else}
										<div class="self-center text-xs text-gray-500">
											{$i18n.t('No authentication')}
										</div>
									{/if}
								</div>
							</div>
						</div>

						<div class="flex flex-col">
							<label for="term-path" class="mb-0.5 text-xs text-gray-500">
								{$i18n.t('OpenAPI Spec')}
							</label>
							<input
								id="term-path"
								class="bg-transparent text-sm outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700"
								type="text"
								bind:value={path}
								placeholder="/openapi.json"
							/>
						</div>
					</div>
				</div>

				<div class="flex items-center justify-between pt-3 text-sm font-medium">
					<div>
						{#if edit}
							<button
								class="px-1 py-1.5 text-sm font-medium text-gray-500 transition hover:text-gray-700 hover:underline dark:text-gray-400 dark:hover:text-gray-200"
								type="button"
								onclick={() => {
									showDeleteConfirmDialog = true;
								}}
							>
								{$i18n.t('Delete')}
							</button>
						{/if}
					</div>

					<button
						class={`flex items-center gap-2 rounded-full bg-black px-3.5 py-1.5 text-sm font-medium whitespace-nowrap text-white transition hover:bg-gray-900 dark:bg-white dark:text-black dark:hover:bg-gray-100 ${loading ? 'cursor-not-allowed' : ''}`}
						type="submit"
						disabled={loading}
					>
						{$i18n.t('Save')}

						{#if loading}
							<span class="shrink-0">
								<Spinner />
							</span>
						{/if}
					</button>
				</div>
			</form>
		</div>
	</div>
</Modal>

<ConfirmDialog
	bind:show={showDeleteConfirmDialog}
	message={$i18n.t(
		'Are you sure you want to delete this connection? This action cannot be undone.'
	)}
	confirmLabel={$i18n.t('Delete')}
	onConfirm={() => {
		onDelete();
		show = false;
	}}
/>
