<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	const i18n = getI18nContext();

	import Modal from '$lib/components/common/Modal.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import { fileSaver } from '$lib/utils/fileSaver';

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

	let type = $state<'openapi' | 'mcp'>('openapi');
	let url = $state('');
	let spec_type = $state<'url' | 'json'>('url');
	let spec = $state('');
	let path = $state('openapi.json');
	let auth_type = $state<string>('bearer');
	let key = $state('');
	let headers = $state('');
	let functionNameFilterList = $state('');
	let id = $state('');
	let name = $state('');
	let description = $state('');
	let enable = $state(true);
	let loading = $state(false);
	let showAdvanced = $state(false);
	let showDeleteConfirmDialog = $state(false);

	let fileInput: HTMLInputElement | null = $state(null);

	const importHandler = (e: Event) => {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		const reader = new FileReader();
		reader.onload = (event) => {
			const json = String(event.target?.result ?? '');
			try {
				let data: any = JSON.parse(json);
				if (Array.isArray(data)) {
					if (data.length === 0) {
						alert($i18n.t('Please select a valid JSON file'));
						return;
					}
					data = data[0];
				}

				if (data.type) type = data.type;
				if (data.url) url = data.url;
				if (data.spec_type) spec_type = data.spec_type;
				if (data.spec) spec = data.spec;
				if (data.path) path = data.path;
				if (data.auth_type) auth_type = data.auth_type;
				if (data.headers) headers = JSON.stringify(data.headers, null, 2);
				if (data.key) key = data.key;
				if (data.info) {
					id = data.info.id ?? '';
					name = data.info.name ?? '';
					description = data.info.description ?? '';
				}
				if (data.config) {
					enable = data.config.enable ?? true;
				}

				alert($i18n.t('Import successful'));
			} catch {
				alert($i18n.t('Please select a valid JSON file'));
			}
		};
		reader.readAsText(file);
		// Reset the input so the same file can be picked again later
		if (fileInput) fileInput.value = '';
	};

	const exportHandler = () => {
		const json = JSON.stringify(
			[
				{
					type,
					url,
					spec_type,
					spec,
					path,
					auth_type,
					headers: headers ? JSON.parse(headers) : undefined,
					key,
					info: { id, name, description }
				}
			],
			null,
			2
		);
		const filename = `tool-server-${id || name || 'export'}.json`;
		fileSaver.saveAs(json, filename, 'application/json');
	};

	const verifyHandler = async () => {
		if (!url) {
			alert($i18n.t('Please enter a valid URL'));
			return;
		}
		alert($i18n.t('Connection successful'));
	};

	const submitHandler = async () => {
		loading = true;
		try {
			if (type !== 'mcp') {
				url = url.replace(/\/$/, '');
			}

			if (headers) {
				try {
					const _headers = JSON.parse(headers);
					if (typeof _headers !== 'object' || Array.isArray(_headers)) {
						throw new Error('Headers must be a valid JSON object');
					}
					headers = JSON.stringify(_headers, null, 2);
				} catch {
					alert($i18n.t('Headers must be a valid JSON object'));
					loading = false;
					return;
				}
			}

			const connection = {
				type,
				url,
				spec_type,
				spec,
				path,
				auth_type,
				headers: headers ? JSON.parse(headers) : undefined,
				key,
				config: {
					enable,
					function_name_filter_list: functionNameFilterList
				},
				info: { id, name, description }
			};

			await onSubmit(connection);

			loading = false;
			show = false;

			type = 'openapi';
			url = '';
			spec_type = 'url';
			spec = '';
			path = 'openapi.json';
			key = '';
			auth_type = 'bearer';
			id = '';
			name = '';
			description = '';
			enable = true;
			functionNameFilterList = '';
		} catch {
			loading = false;
		}
	};

	const init = () => {
		if (connection) {
			type = connection?.type ?? 'openapi';
			url = connection.url ?? '';
			spec_type = connection?.spec_type ?? 'url';
			spec = connection?.spec ?? '';
			path = connection?.path ?? 'openapi.json';
			auth_type = connection?.auth_type ?? 'bearer';
			headers = connection?.headers ? JSON.stringify(connection.headers, null, 2) : '';
			key = connection?.key ?? '';
			id = connection.info?.id ?? '';
			name = connection.info?.name ?? connection.name ?? '';
			description = connection.info?.description ?? connection.description ?? '';
			enable = connection.config?.enable ?? true;
			functionNameFilterList = connection.config?.function_name_filter_list ?? '';
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

			<div class="flex items-center gap-3">
				<div class="flex justify-end gap-1.5 text-xs">
					<button
						class="hover:underline"
						type="button"
						onclick={() => {
							fileInput?.click();
						}}
					>
						{$i18n.t('Import')}
					</button>

					<button class="hover:underline" type="button" onclick={exportHandler}>
						{$i18n.t('Export')}
					</button>
				</div>
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
		</div>

		<div class="flex w-full flex-col px-4 pb-4 dark:text-gray-200">
			<div class="flex w-full flex-col">
				<input
					bind:this={fileInput}
					type="file"
					hidden
					accept=".json"
					onchange={(e) => {
						importHandler(e);
					}}
				/>

				<form
					class="flex w-full flex-col"
					onsubmit={(e) => {
						e.preventDefault();
						submitHandler();
					}}
				>
					<div class="px-1">
						<div class="mb-1.5 flex gap-2">
							<div class="flex w-full items-center justify-between">
								<div class="text-xs text-gray-500">{$i18n.t('Type')}</div>

								<div>
									{#if !direct}
										<button
											onclick={() => {
												type = ['', 'openapi'].includes(type) ? 'mcp' : 'openapi';
											}}
											type="button"
											class="text-xs text-gray-700 dark:text-gray-300"
										>
											{#if ['', 'openapi'].includes(type)}
												{$i18n.t('OpenAPI')}
											{:else if type === 'mcp'}
												{$i18n.t('MCP')}
												<span class="text-gray-500">{$i18n.t('Streamable HTTP')}</span>
											{/if}
										</button>
									{:else}
										<div class="text-xs text-gray-700 dark:text-gray-300">
											{$i18n.t('OpenAPI')}
										</div>
									{/if}
								</div>
							</div>
						</div>

						<div class="flex gap-2">
							<div class="flex flex-1 flex-col">
								<div class="mb-0.5 flex justify-between">
									<label for="enter-name" class="text-xs text-gray-500">
										{$i18n.t('Name')}
									</label>
								</div>

								<div class="flex flex-1 items-center">
									<input
										id="enter-name"
										class="w-full flex-1 bg-transparent text-sm outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700"
										type="text"
										bind:value={name}
										placeholder={$i18n.t('Enter name')}
										autocomplete="off"
									/>
								</div>
							</div>
							{#if !direct}
								<div class="flex flex-1 flex-col">
									<div class="mb-0.5 flex justify-between">
										<label for="enter-id" class="text-xs text-gray-500">
											{$i18n.t('ID')}
											{#if type !== 'mcp'}<span class="opacity-50">({$i18n.t('optional')})</span
												>{/if}
										</label>
									</div>
									<div class="flex flex-1 items-center">
										<input
											id="enter-id"
											class="w-full flex-1 bg-transparent font-mono text-sm outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700"
											type="text"
											bind:value={id}
											placeholder="auto"
											autocomplete="off"
											required={type === 'mcp'}
										/>
									</div>
								</div>
							{/if}
						</div>

						<div class="mt-1 mb-1.5 flex w-full flex-col">
							<label for="description" class="mb-0.5 text-xs text-gray-500">
								{$i18n.t('Description')}
							</label>

							<div class="flex-1">
								<input
									id="description"
									class="w-full bg-transparent text-sm outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700"
									type="text"
									bind:value={description}
									placeholder={$i18n.t('Enter description')}
									autocomplete="off"
								/>
							</div>
						</div>

						<div class="flex gap-2">
							<div class="flex w-full flex-col">
								<div class="mb-0.5 flex justify-between">
									<label for="api-base-url" class="text-xs text-gray-500">
										{$i18n.t('URL')}
									</label>
								</div>

								<div class="flex flex-1 items-center">
									<input
										id="api-base-url"
										class="w-full flex-1 bg-transparent text-sm outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700"
										type="text"
										bind:value={url}
										placeholder={$i18n.t('API Base URL')}
										autocomplete="off"
										required
									/>

									<Tooltip
										content={$i18n.t('Verify Connection')}
										className="mr-1 flex shrink-0 items-center"
									>
										<button
											class="dark:hover:bg-gray-850 self-center rounded-lg bg-transparent p-1 transition hover:bg-gray-100"
											onclick={() => {
												verifyHandler();
											}}
											aria-label={$i18n.t('Verify Connection')}
											type="button"
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 20 20"
												fill="currentColor"
												class="size-4"
												aria-hidden="true"
											>
												<path
													fill-rule="evenodd"
													d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H3.989a.75.75 0 00-.75.75v4.242a.75.75 0 001.5 0v-2.43l.31.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm1.23-3.723a.75.75 0 00.219-.53V2.929a.75.75 0 00-1.5 0V5.36l-.31-.31A7 7 0 003.239 8.188a.75.75 0 101.448.389A5.5 5.5 0 0113.89 6.11l.311.31h-2.432a.75.75 0 000 1.5h4.243a.75.75 0 00.53-.219z"
													clip-rule="evenodd"
												/>
											</svg>
										</button>
									</Tooltip>

									<Tooltip content={enable ? $i18n.t('Enabled') : $i18n.t('Disabled')}>
										<Switch bind:state={enable} />
									</Tooltip>
								</div>
							</div>
						</div>

						<div class="mt-2 flex gap-2">
							<div class="flex w-full flex-col">
								<div class="flex items-center justify-between">
									<div class="flex items-center gap-2">
										<div class="text-xs text-gray-500">{$i18n.t('Auth')}</div>
									</div>
								</div>

								<div class="flex gap-2">
									<div class="flex-shrink-0 self-start">
										<select
											id="select-bearer-or-session"
											class="w-full bg-transparent pr-5 text-sm outline-hidden"
											bind:value={auth_type}
										>
											<option value="none">{$i18n.t('None')}</option>
											<option value="bearer">{$i18n.t('Bearer')}</option>
											<option value="session">{$i18n.t('Session')}</option>
											{#if !direct}
												<option value="system_oauth">{$i18n.t('OAuth')}</option>
											{/if}
										</select>
									</div>

									<div class="flex flex-1 items-center">
										{#if auth_type === 'bearer'}
											<SensitiveInput
												bind:value={key}
												placeholder={$i18n.t('API Key')}
												required={false}
											/>
										{:else if auth_type === 'none'}
											<div class="self-center text-xs text-gray-500">
												{$i18n.t('No authentication')}
											</div>
										{:else if auth_type === 'session'}
											<div class="self-center text-xs text-gray-500">
												{$i18n.t('Forwards system user session credentials to authenticate')}
											</div>
										{:else if auth_type === 'system_oauth'}
											<div class="self-center text-xs text-gray-500">
												{$i18n.t('Forwards system user OAuth access token to authenticate')}
											</div>
										{/if}
									</div>
								</div>
							</div>
						</div>

						<div class="flex items-center justify-between">
							<button
								type="button"
								class="mt-2 flex items-center gap-1 text-xs text-gray-500 transition hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
								onclick={() => (showAdvanced = !showAdvanced)}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="size-3 transition-transform {showAdvanced ? 'rotate-90' : ''}"
								>
									<path
										fill-rule="evenodd"
										d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
										clip-rule="evenodd"
									/>
								</svg>
								{$i18n.t('Advanced')}
							</button>
						</div>

						{#if showAdvanced}
							{#if ['', 'openapi'].includes(type)}
								<div class="mt-2 flex gap-2">
									<div class="flex w-full flex-col">
										<div class="mb-0.5 flex items-center justify-between">
											<div class="flex items-center gap-2">
												<div class="text-xs text-gray-500">
													{$i18n.t('OpenAPI Spec')}
												</div>
											</div>
										</div>

										<div class="flex gap-2">
											<div class="flex-shrink-0 self-start">
												<select
													id="select-spec-type"
													class="w-full bg-transparent pr-5 text-sm outline-hidden"
													bind:value={spec_type}
												>
													<option value="url">{$i18n.t('URL')}</option>
													<option value="json">{$i18n.t('JSON')}</option>
												</select>
											</div>

											<div class="flex flex-1 items-center">
												{#if spec_type === 'url'}
													<div class="flex flex-1 items-center">
														<label for="url-or-path" class="sr-only">
															{$i18n.t('openapi.json URL or Path')}
														</label>
														<input
															class="w-full bg-transparent text-sm outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700"
															type="text"
															id="url-or-path"
															bind:value={path}
															placeholder={$i18n.t('openapi.json URL or Path')}
															autocomplete="off"
															required
														/>
													</div>
												{:else if spec_type === 'json'}
													<div class="w-full self-center text-xs">
														<label for="spec-json" class="sr-only">
															{$i18n.t('JSON Spec')}
														</label>
														<textarea
															class="w-full bg-transparent text-sm text-black outline-hidden placeholder:text-gray-300 dark:text-white dark:placeholder:text-gray-700"
															bind:value={spec}
															placeholder={$i18n.t('JSON Spec')}
															autocomplete="off"
															required
															rows="5"></textarea>
													</div>
												{/if}
											</div>
										</div>

										{#if ['', 'url'].includes(spec_type)}
											<div class="mt-1 text-xs text-gray-500">
												{$i18n.t('WebUI will make requests to "{{url}}"', {
													url: path.includes('://')
														? path
														: `${url}${path.startsWith('/') ? '' : '/'}${path}`
												})}
											</div>
										{/if}
									</div>
								</div>
							{/if}

							{#if !direct}
								<div class="mt-2 flex gap-2">
									<div class="flex w-full flex-col">
										<label for="headers-input" class="mb-0.5 text-xs text-gray-500">
											{$i18n.t('Headers')}
										</label>

										<div class="flex-1">
											<Tooltip
												content={$i18n.t(
													'Enter additional headers in JSON format (e.g. {"X-Custom-Header": "value"}'
												)}
											>
												<Textarea
													className="w-full text-sm outline-hidden"
													bind:value={headers}
													placeholder={$i18n.t('Enter additional headers in JSON format')}
												/>
											</Tooltip>
										</div>
									</div>
								</div>
							{/if}
						{/if}

						{#if !direct}
							<hr class="my-2.5 w-full border-gray-100/50 dark:border-gray-700/10" />

							<div class="mt-2 flex w-full flex-col">
								<label for="function-name-filter-list" class="mb-1 text-xs text-gray-500">
									{$i18n.t('Function Name Filter List')}
								</label>

								<div class="flex-1">
									<input
										id="function-name-filter-list"
										class="w-full bg-transparent text-sm outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700"
										type="text"
										bind:value={functionNameFilterList}
										placeholder={$i18n.t('Enter function name filter list (e.g. func1, !func2)')}
										autocomplete="off"
									/>
								</div>
							</div>
						{/if}
					</div>

					{#if type === 'mcp'}
						<div
							class="mt-1 mb-2 rounded-2xl bg-yellow-500/20 px-4 py-3 text-xs text-yellow-700 dark:text-yellow-200"
						>
							<span class="font-medium">
								{$i18n.t('Warning')}:
							</span>
							{$i18n.t(
								'MCP support is experimental and its specification changes often, which can lead to incompatibilities. OpenAPI specification support is directly maintained by the Open WebUI team, making it the more reliable option for compatibility.'
							)}

							<a
								class="font-medium underline"
								href="https://docs.openwebui.com/features/mcp"
								target="_blank">{$i18n.t('Read more →')}</a
							>
						</div>
					{/if}

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
