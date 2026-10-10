<script lang="ts">
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';

	// 轻量 toast（无第三方依赖）
	const notify = (message: string, _kind: 'success' | 'error' | 'info' = 'info') => {
		console.log(`[toast][${_kind}] ${message}`);
		try {
			window.dispatchEvent(new CustomEvent('tagent-toast', { detail: { message, kind: _kind } }));
		} catch {
			// ignore
		}
	};
	// 下面调用的是 toast.success / toast.error / toast.info：只有一个函数的话，运行时会报
	// 「toast.success is not a function」（比如保存账号信息后对话框关不上）
	const toast = {
		info: (message: string) => notify(message, 'info'),
		success: (message: string) => notify(message, 'success'),
		error: (message: string) => notify(message, 'error')
	};

	let show = $state(false);
	let currentPassword = $state('');
	let newPassword = $state('');
	let newPasswordConfirm = $state('');

	const updatePasswordHandler = async () => {
		if (!currentPassword || !newPassword || !newPasswordConfirm) {
			toast.error('请填写所有密码字段');
			return;
		}
		if (newPassword !== newPasswordConfirm) {
			toast.error('两次输入的新密码不一致，请检查后重试');
			newPassword = '';
			newPasswordConfirm = '';
			return;
		}
		// mock：仅弹 toast
		toast.success('密码已更新（mock）');
		currentPassword = '';
		newPassword = '';
		newPasswordConfirm = '';
	};
</script>

<form
	class="flex flex-col text-sm"
	onsubmit={(event) => {
		event.preventDefault();
		void updatePasswordHandler();
	}}
>
	<div class="flex items-center justify-between text-sm">
		<div class="font-medium">修改密码</div>
		<button
			class="text-xs font-medium text-gray-500"
			type="button"
			onclick={() => {
				show = !show;
			}}
		>
			{show ? '隐藏' : '显示'}
		</button>
	</div>

	{#if show}
		<div class="space-y-1.5 py-2.5">
			<div class="flex w-full flex-col">
				<div class="mb-1 text-xs text-gray-500">当前密码</div>

				<div class="flex-1">
					<SensitiveInput
						className="w-full bg-transparent text-sm placeholder:opacity-30 outline-none"
						type="password"
						bind:value={currentPassword}
						placeholder="输入当前密码"
						autocomplete="current-password"
						required
					/>
				</div>
			</div>

			<div class="flex w-full flex-col">
				<div class="mb-1 text-xs text-gray-500">新密码</div>

				<div class="flex-1">
					<SensitiveInput
						className="w-full bg-transparent text-sm placeholder:opacity-30 outline-none"
						type="password"
						bind:value={newPassword}
						placeholder="输入新密码"
						autocomplete="new-password"
						required
					/>
				</div>
			</div>

			<div class="flex w-full flex-col">
				<div class="mb-1 text-xs text-gray-500">确认密码</div>

				<div class="flex-1">
					<SensitiveInput
						className="w-full bg-transparent text-sm placeholder:opacity-30 outline-none"
						type="password"
						bind:value={newPasswordConfirm}
						placeholder="再次输入新密码"
						autocomplete="off"
						required
					/>
				</div>
			</div>
		</div>

		<div class="mt-3 flex justify-end">
			<button
				type="submit"
				class="rounded-full bg-white px-3.5 py-1.5 text-sm font-medium text-black transition hover:bg-gray-100"
			>
				更新密码
			</button>
		</div>
	{/if}
</form>
