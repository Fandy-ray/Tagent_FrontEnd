<script lang="ts">
	import { untrack } from 'svelte';
	import type { UserSettings } from '$lib/data/userSettings';

	import Textarea from '$lib/components/common/Textarea.svelte';
	import UserProfileImage from './Account/UserProfileImage.svelte';

	type Props = {
		settings: UserSettings;
		saveSettings: (updated: Partial<UserSettings>) => Promise<void> | void;
		onSave?: () => void;
	};

	let { settings, saveSettings, onSave = () => {} }: Props = $props();

	let name = $state(untrack(() => settings.displayName));
	let bio = $state(untrack(() => settings.bio || settings.userBio));
	let gender = $state(untrack(() => settings.gender));
	let genderSelect = $state(untrack(() => settings.gender));
	let dateOfBirth = $state(untrack(() => settings.dateOfBirth));
	let profileImageUrl = $state(untrack(() => settings.profileImageUrl ?? ''));

	const submitHandler = async () => {
		const avatarText = name.trim() ? name.trim().slice(0, 1).toUpperCase() : settings.avatarText;
		await saveSettings({
			displayName: name,
			avatarText,
			bio,
			userBio: bio,
			gender: gender || '',
			dateOfBirth,
			profileImageUrl
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
				<UserProfileImage
					bind:profileImageUrl
					userName={settings.displayName}
					imageClassName="size-14 md:size-18"
				/>

				<div class="flex flex-1 flex-col">
					<div class="flex-1">
						<div class="flex w-full flex-col">
							<div class="mb-1 text-xs font-medium">名称</div>
							<input
								class="w-full bg-transparent text-sm outline-none"
								type="text"
								bind:value={name}
								aria-label="名称"
								required
								placeholder="输入你的名称"
							/>
						</div>

						<div class="mt-2 flex w-full flex-col">
							<div class="mb-1 text-xs font-medium">简介</div>
							<Textarea
								className="w-full bg-transparent text-sm outline-none"
								minSize={60}
								bind:value={bio}
								ariaLabel="简介"
								placeholder="分享你的背景与兴趣"
							/>
						</div>

						<div class="mt-2 flex w-full flex-col">
							<div class="mb-1 text-xs font-medium">性别</div>
							<select
								class="w-full bg-transparent text-sm outline-none"
								bind:value={genderSelect}
								aria-label="性别"
								onchange={() => {
									gender = genderSelect === 'custom' ? '' : genderSelect;
								}}
							>
								<option value="" class="bg-gray-800">不愿透露</option>
								<option value="male" class="bg-gray-800">男</option>
								<option value="female" class="bg-gray-800">女</option>
								<option value="custom" class="bg-gray-800">自定义</option>
							</select>

							{#if genderSelect === 'custom'}
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
