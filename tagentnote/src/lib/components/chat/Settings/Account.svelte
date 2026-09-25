<script lang="ts">
	import type { UserSettings } from '$lib/data/userSettings';

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

	$effect(() => {
		name = settings.displayName;
		bio = settings.bio || settings.userBio;
		_gender = settings.gender;
		gender = settings.gender;
		dateOfBirth = settings.dateOfBirth;
		webhookUrl = settings.webhookUrl;
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
			webhookUrl
		});
		onSave();
	};
</script>

<div id="tab-account" class="flex h-full flex-col justify-between text-sm">
	<div class="max-h-[28rem] overflow-y-scroll md:max-h-full">
		<div class="space-y-1">
			<div>
				<div class="text-base font-medium">您的账号</div>
				<div class="mt-0.5 text-xs text-gray-500">管理你的账号信息。</div>
			</div>

			<div class="my-4 flex space-x-5">
				<div
					class="flex size-16 shrink-0 items-center justify-center rounded-full bg-amber-500 text-lg font-semibold text-white"
				>
					{(name || 'T').trim().slice(0, 1).toUpperCase()}
				</div>

				<div class="flex flex-1 flex-col">
					<div class="mb-1 text-xs font-medium">名称</div>
					<input
						class="w-full bg-transparent text-sm outline-none"
						type="text"
						bind:value={name}
						required
						placeholder="输入你的名称"
					/>

					<div class="mt-2 mb-1 text-xs font-medium">简介</div>
					<textarea
						class="w-full resize-y bg-transparent text-sm outline-none"
						rows="3"
						bind:value={bio}
						placeholder="分享你的背景与兴趣"
					></textarea>

					<div class="mt-2 mb-1 text-xs font-medium">性别</div>
					<select
						class="w-full bg-transparent text-sm outline-none"
						bind:value={_gender}
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
					{#if _gender === 'custom'}
						<input
							class="mt-1 w-full bg-transparent text-sm outline-none"
							bind:value={gender}
							placeholder="自定义性别"
						/>
					{/if}

					<div class="mt-2 mb-1 text-xs font-medium">出生日期</div>
					<input
						class="w-full bg-transparent text-sm outline-none"
						type="date"
						bind:value={dateOfBirth}
					/>
				</div>
			</div>

			<hr class="my-3 border-gray-850/30" />

			<div class="mb-1 text-xs font-medium">通知 Webhook URL</div>
			<input
				class="w-full bg-transparent text-sm outline-none"
				bind:value={webhookUrl}
				placeholder="https://..."
			/>
			<div class="mt-1 text-xs text-gray-500">可选：接收通知事件的 Webhook 地址。</div>
		</div>
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
