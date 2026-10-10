<script lang="ts">
	import { onMount } from 'svelte';

	const version = '0.0.1';
	const buildHash = 'dev';
	const productName = 'TAgentNote';
	const year = new Date().getFullYear();

	type VersionState = {
		current: string;
		latest: string;
		state: 'idle' | 'checking' | 'upToDate' | 'available';
	};

	let versionState = $state<VersionState>({
		current: version,
		latest: version,
		state: 'idle'
	});

	let ollamaVersion = $state('');

	const checkForVersionUpdates = async () => {
		versionState = { ...versionState, state: 'checking' };
		try {
			await new Promise((resolve) => setTimeout(resolve, 600));
			// mock：始终视为已是最新版本
			versionState = {
				current: version,
				latest: version,
				state: 'upToDate'
			};
		} catch {
			versionState = {
				current: version,
				latest: version,
				state: 'upToDate'
			};
		}
	};

	onMount(async () => {
		// mock：填充一个常见的 Ollama 版本占位
		ollamaVersion = 'ollama 0.3.12';
		await checkForVersionUpdates();
	});

	const showChangelog = () => {
		// mock：可绑定到一个简单 toast
		alert(
			'变更日志：\n• 答疑页设置面板对齐 Open WebUI 布局\n• 账号/关于/数据面板补全\n• 教学前端 mock 数据接入'
		);
	};
</script>

<div id="tab-about" class="mb-6 flex h-full flex-col justify-between space-y-3 text-sm">
	<div class="max-h-[28rem] space-y-3 overflow-y-scroll md:max-h-full">
		<div>
			<div class="mb-2.5 flex items-center space-x-2 text-sm font-medium">
				<div>{productName} 版本</div>
			</div>
			<div class="flex w-full items-center justify-between">
				<div class="flex flex-col text-xs text-gray-200">
					<div class="flex gap-1">
						<span title={buildHash}>v{versionState.current}</span>

						{#if versionState.state === 'checking'}
							<span class="text-gray-500">(正在检查更新…)</span>
						{:else if versionState.state === 'upToDate'}
							<span class="text-gray-500">(latest)</span>
						{:else if versionState.state === 'available'}
							<a
								href="https://github.com/open-webui/open-webui/releases/tag/v{versionState.latest}"
								target="_blank"
								rel="noreferrer"
							>
								(v{versionState.latest} available!)
							</a>
						{/if}
					</div>

					<button
						class="flex items-center space-x-1 text-xs text-gray-500 underline"
						type="button"
						onclick={showChangelog}
					>
						<div>查看更新内容</div>
					</button>
				</div>

				<button
					class="bg-gray-850 rounded-lg px-3 py-1.5 text-xs font-medium transition hover:bg-gray-800"
					type="button"
					onclick={checkForVersionUpdates}
				>
					检查更新
				</button>
			</div>
		</div>

		{#if ollamaVersion}
			<hr class="border-gray-850/30" />

			<div>
				<div class="mb-2.5 text-sm font-medium">Ollama 版本</div>
				<div class="flex w-full">
					<div class="flex-1 text-xs text-gray-200">
						{ollamaVersion || 'N/A'}
					</div>
				</div>
			</div>
		{/if}

		<hr class="border-gray-850/30" />

		<div class="mb-2 text-xs">
			<span class="font-medium text-gray-300">{productName}</span> -
			<span class="capitalize">MIT</span> license purchased by
			<span class="capitalize">TAgentNote Team</span>
		</div>

		<div class="flex space-x-1">
			<a href="https://discord.gg/5rJgQTnV4s" target="_blank" rel="noreferrer">
				<img
					alt="Discord"
					src="https://img.shields.io/badge/Discord-Open_WebUI-blue?logo=discord&logoColor=white"
				/>
			</a>

			<a href="https://twitter.com/OpenWebUI" target="_blank" rel="noreferrer">
				<img
					alt="X (formerly Twitter) Follow"
					src="https://img.shields.io/twitter/follow/OpenWebUI"
				/>
			</a>

			<a href="https://github.com/open-webui/open-webui" target="_blank" rel="noreferrer">
				<img
					alt="Github Repo"
					src="https://img.shields.io/github/stars/open-webui/open-webui?style=social&label=Star us on Github"
				/>
			</a>
		</div>

		<div class="mt-2 text-xs text-gray-500">
			Emoji graphics provided by
			<a href="https://github.com/jdecked/twemoji" target="_blank" rel="noreferrer">Twemoji</a>,
			licensed under
			<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer"
				>CC-BY 4.0</a
			>.
		</div>

		<div>
			<pre class="text-xs text-gray-500">Copyright (c) {year} <a
					href="https://openwebui.com"
					target="_blank"
					rel="noreferrer"
					class="underline">Open WebUI Inc.</a
				> <a
					href="https://github.com/open-webui/open-webui/blob/main/LICENSE"
					target="_blank"
					rel="noreferrer">All rights reserved.</a
				>
</pre>
		</div>

		<div class="mt-2 text-xs text-gray-500">
			由
			<a
				class="font-medium text-gray-300"
				href="https://github.com/tjbck"
				target="_blank"
				rel="noreferrer">Timothy J. Baek</a
			>
			创建
		</div>
	</div>
</div>
