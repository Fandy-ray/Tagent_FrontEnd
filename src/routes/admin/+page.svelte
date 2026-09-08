<script lang="ts">
	import { goto } from '$app/navigation';
</script>

<svelte:head>
	<title>管理员面板 | TAgent</title>
</svelte:head>

<main class="flex min-h-screen items-center justify-center bg-[#171717] px-4 text-white">
	<div class="w-full max-w-md rounded-2xl border border-gray-800 bg-gray-850 p-6 text-center">
		<h1 class="text-xl font-medium">管理员面板</h1>
		<p class="mt-3 text-sm leading-6 text-gray-400">
			对应 Open WebUI 的 Admin Panel。教学前端暂提供入口占位，后续可接入用户与系统管理。
		</p>
		<button
			type="button"
			class="mt-6 rounded-xl bg-gray-800 px-4 py-2 text-sm transition hover:bg-gray-700"
			onclick={() => goto('/qa')}
		>
			返回答疑
		</button>
	</div>
</main>
