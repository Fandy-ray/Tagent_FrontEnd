<script lang="ts">
	import type { UserSettings } from '$lib/data/userSettings';

	import Textarea from '$lib/components/common/Textarea.svelte';
	import UpdatePassword from './Account/UpdatePassword.svelte';
	import UserProfileImage from './Account/UserProfileImage.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';

	// 轻量 toast：仅做记录，可被宿主页面挂载的 toast 系统替换
	const notify = (message: string, _kind: 'success' | 'error' | 'info' = 'info') => {
		// eslint-disable-next-line no-console
		console.log(`[toast][${_kind}] ${message}`);
		try {
			window.dispatchEvent(
				new CustomEvent('tagent-toast', { detail: { message, kind: _kind } })
			);
		} catch {
			// 忽略：非浏览器环境
		}
	};
	// 下面调用的是 toast.success / toast.error / toast.info：只有一个函数的话，运行时会报
	// 「toast.success is not a function」（比如保存账号信息后对话框关不上）
	const toast = {
		info: (message: string) => notify(message, 'info'),
		success: (message: string) => notify(message, 'success'),
		error: (message: string) => notify(message, 'error')
	};

	type Props = {
		settings: UserSettings;
		saveSettings: (updated: Partial<UserSettings>) => Promise<void> | void;
		onSave?: () => void;
	};

	let { settings, saveSettings, onSave = () => {} }: Props = $props();

	let name = $state(settings.displayName);
	let bio = $state(settings.bio || settings.userBio);
	let _gender = $state(settings.gender);
	let gender = $state(settings.gender);
	let dateOfBirth = $state(settings.dateOfBirth);
	let webhookUrl = $state(settings.webhookUrl);
	let profileImageUrl = $state(settings.profileImageUrl ?? '');

	let showAPIKeys = $state(false);
	let apiKey = $state('');
	let apiKeyCopied = $state(false);
	let jwtTokenCopied = $state(false);
	const mockToken = 'mock-jwt-token-xxxxxxxxxxxxxxxxxxxx';

	$effect(() => {
		name = settings.displayName;
		bio = settings.bio || settings.userBio;
		_gender = settings.gender;
		gender = settings.gender;
		dateOfBirth = settings.dateOfBirth;
		webhookUrl = settings.webhookUrl;
		profileImageUrl = settings.profileImageUrl ?? '';
	});

	const submitHandler = async () => {
		const avatarText = name.trim() ? name.trim().slice(0, 1).toUpperCase() : settings.avatarText;
		await saveSettings({
			displayName: name,
			avatarText,
			bio,
			userBio: bio,
			gender: gender || '',
			dateOfBirth,
			webhookUrl,
			profileImageUrl
		});
		toast.success('账号信息已保存');
		onSave();
	};

	const copyToClipboard = async (text: string, label: string) => {
		try {
			await navigator.clipboard.writeText(text);
			toast.success(`${label} 已复制到剪贴板`);
		} catch {
			toast.error('复制失败，请手动复制');
		}
	};

	const onCopyToken = async () => {
		await copyToClipboard(mockToken, 'JWT Token');
		jwtTokenCopied = true;
		setTimeout(() => (jwtTokenCopied = false), 2000);
	};

	const onCopyApiKey = async () => {
		if (!apiKey) return;
		await copyToClipboard(apiKey, 'API Key');
		apiKeyCopied = true;
		setTimeout(() => (apiKeyCopied = false), 2000);
	};

	const createApiKey = () => {
		apiKey = `sk-mock-${Math.random().toString(36).slice(2, 18)}`;
		toast.success('API Key 已创建（mock）');
	};

	// mock：默认显示 API 密钥区
	const isAdmin = $derived(true);
</script>

<div id="tab-account" class="flex h-full flex-col justify-between text-sm">
	<div class="max-h-[28rem] overflow-y-scroll md:max-h-full">
		<div class="space-y-1">
			<div>
				<div class="text-base font-medium">您的账号</div>
				<div class="mt-0.5 text-xs text-gray-500">管理你的账号信息。</div>
			</div>

			<div class="my-4 flex space-x-5">
				<UserProfileImage
					bind:profileImageUrl
					userName={settings.displayName}
					imageClassName="size-14 md:size-18"
				/>

				<div class="flex flex-1 flex-col">
					<div class="flex-1">
						<div class="flex w-full flex-col">
							<div class="mb-1 text-xs font-medium">名称</div>

							<div class="flex-1">
								<input
									class="w-full bg-transparent text-sm outline-none"
									type="text"
									bind:value={name}
									aria-label="名称"
									required
									placeholder="输入你的名称"
								/>
							</div>
						</div>

						<div class="mt-2 flex w-full flex-col">
							<div class="mb-1 text-xs font-medium">简介</div>

							<div class="flex-1">
								<Textarea
									className="w-full bg-transparent text-sm outline-none"
									minSize={60}
									bind:value={bio}
									ariaLabel="简介"
									placeholder="分享你的背景与兴趣"
								/>
							</div>
						</div>

						<div class="mt-2 flex w-full flex-col">
							<div class="mb-1 text-xs font-medium">性别</div>

							<div class="flex-1">
								<select
									class="w-full bg-transparent text-sm outline-none"
									bind:value={_gender}
									aria-label="性别"
									onchange={() => {
										if (_gender === 'custom') gender = '';
										else gender = _gender;
									}}
								>
									<option value="" class="bg-gray-800">不愿透露</option>
									<option value="male" class="bg-gray-800">男</option>
									<option value="female" class="bg-gray-800">女</option>
									<option value="custom" class="bg-gray-800">自定义</option>
								</select>
							</div>

							{#if _gender === 'custom'}
								<input
									class="mt-1 w-full bg-transparent text-sm outline-none"
									type="text"
									required
									aria-label="自定义性别"
									placeholder="输入自定义性别"
									bind:value={gender}
								/>
							{/if}
						</div>

						<div class="mt-2 flex w-full flex-col">
							<div class="mb-1 text-xs font-medium">出生日期</div>

							<div class="flex-1">
								<input
									class="w-full bg-transparent text-sm outline-none placeholder:text-gray-300"
									type="date"
									aria-label="出生日期"
									bind:value={dateOfBirth}
									required
								/>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<div class="mt-2">
			<div class="flex w-full flex-col">
				<div class="mb-1 text-xs font-medium">通知 Webhook</div>

				<div class="flex-1">
					<input
						class="w-full text-sm outline-none"
						type="url"
						placeholder="输入 Webhook URL"
						aria-label="通知 Webhook"
						bind:value={webhookUrl}
						required
					/>
				</div>
			</div>
		</div>

		<hr class="my-4 border-gray-850/30" />

		<div class="mt-2">
			<UpdatePassword />
		</div>

		{#if isAdmin}
			<div class="mt-2 flex items-center justify-between text-sm">
				<div class="font-medium">API 密钥</div>
				<button
					class="text-xs font-medium text-gray-500"
					type="button"
					onclick={() => {
						showAPIKeys = !showAPIKeys;
					}}
				>
					{showAPIKeys ? '隐藏' : '显示'}
				</button>
			</div>

			{#if showAPIKeys}
				<div class="flex flex-col">
					<div class="mt-2 w-full">
						<div class="flex w-full justify-between">
							<div class="mb-1 self-center text-xs font-medium">JWT Token</div>
						</div>

						<div class="flex">
							<SensitiveInput
								id="jwt-token-input"
								value={mockToken}
								readonly={true}
								ariaLabel="JWT Token"
							/>

							<button
								class="ml-1.5 rounded-lg px-1.5 py-1 transition hover:bg-gray-850"
								aria-label="复制 Token"
								onclick={onCopyToken}
							>
								{#if jwtTokenCopied}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										class="size-4"
									>
										<path
											fill-rule="evenodd"
											d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 1 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143z"
											clip-rule="evenodd"
										/>
									</svg>
								{:else}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 16 16"
										fill="currentColor"
										class="size-4"
									>
										<path
											fill-rule="evenodd"
											d="M11.986 3H12a2 2 0 0 1 2 2v6a2 2 0 0 1-1.5 1.937V7A2.5 2.5 0 0 0 10 4.5H4.063A2 2 0 0 1 6 3h.014A2.25 2.25 0 0 1 8.25 1h1.5a2.25 2.25 0 0 1 2.236 2ZM10.5 4v-.75a.75.75 0 0 0-.75-.75h-1.5a.75.75 0 0 0-.75.75V4h3Z"
											clip-rule="evenodd"
										/>
										<path
											fill-rule="evenodd"
											d="M3 6a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H3Zm1.75 2.5a.75.75 0 0 0 0 1.5h3.5a.75.75 0 0 0 0-1.5h-3.5ZM4 11.75a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 0 1.5h-3.5a.75.75 0 0 1-.75-.75Z"
											clip-rule="evenodd"
										/>
									</svg>
								{/if}
							</button>
						</div>
					</div>

					<div class="mt-2 w-full">
						<div class="flex w-full justify-between">
							<div class="mb-1 self-center text-xs font-medium">API Key</div>
						</div>
						<div class="flex">
							{#if apiKey}
								<SensitiveInput
									id="api-key-input"
									bind:value={apiKey}
									readonly={true}
									ariaLabel="API Key"
								/>

								<button
									class="ml-1.5 rounded-lg px-1.5 py-1 transition hover:bg-gray-850"
									aria-label="复制 API Key"
									onclick={onCopyApiKey}
								>
									{#if apiKeyCopied}
										<svg
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 20 20"
											fill="currentColor"
											class="size-4"
										>
											<path
												fill-rule="evenodd"
												d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 1 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143z"
												clip-rule="evenodd"
											/>
										</svg>
									{:else}
										<svg
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 16 16"
											fill="currentColor"
											class="size-4"
										>
											<path
												fill-rule="evenodd"
												d="M11.986 3H12a2 2 0 0 1 2 2v6a2 2 0 0 1-1.5 1.937V7A2.5 2.5 0 0 0 10 4.5H4.063A2 2 0 0 1 6 3h.014A2.25 2.25 0 0 1 8.25 1h1.5a2.25 2.25 0 0 1 2.236 2ZM10.5 4v-.75a.75.75 0 0 0-.75-.75h-1.5a.75.75 0 0 0-.75.75V4h3Z"
												clip-rule="evenodd"
											/>
											<path
												fill-rule="evenodd"
												d="M3 6a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H3Zm1.75 2.5a.75.75 0 0 0 0 1.5h3.5a.75.75 0 0 0 0-1.5h-3.5ZM4 11.75a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 0 1.5h-3.5a.75.75 0 0 1-.75-.75Z"
												clip-rule="evenodd"
											/>
										</svg>
									{/if}
								</button>

								<button
									class="ml-1 rounded-lg px-1.5 py-1 transition hover:bg-gray-850"
									aria-label="重建 Key"
									title="重建 Key"
									onclick={createApiKey}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										fill="none"
										viewBox="0 0 24 24"
										stroke-width="2"
										stroke="currentColor"
										class="size-4"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"
										/>
									</svg>
								</button>
							{:else}
								<button
									type="button"
									class="flex items-center gap-1.5 rounded-lg bg-gray-100/70 px-3.5 py-1.5 font-medium transition hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-850"
									onclick={createApiKey}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										class="size-3.5"
									>
										<path
											d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z"
										/>
									</svg>
									创建新密钥
								</button>
							{/if}
						</div>
					</div>
				</div>
			{/if}
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="rounded-full bg-white px-3.5 py-1.5 text-sm font-medium text-black transition hover:bg-gray-100"
			type="button"
			onclick={submitHandler}
		>
			保存
		</button>
	</div>
</div>
