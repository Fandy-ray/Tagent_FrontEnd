<script lang="ts">
	const version = '0.0.1';
</script>

<div id="tab-about" class="mb-6 flex h-full flex-col justify-between space-y-3 text-sm">
	<div class="max-h-[28rem] space-y-3 overflow-y-scroll md:max-h-full">
		<div>
			<div class="mb-2.5 flex items-center space-x-2 text-sm font-medium">
				<div>TAgentNote 版本</div>
			</div>
			<div class="flex w-full items-center justify-between">
				<div class="flex flex-col text-xs text-gray-200">
					<div class="flex gap-1">
						<span>v{version}</span>
						<span class="text-gray-500">(latest)</span>
					</div>
					<a
						class="flex items-center space-x-1 text-xs text-gray-500 underline"
						href="https://github.com/open-webui/open-webui/releases"
						target="_blank"
						rel="noreferrer"
					>
						查看更新内容
					</a>
				</div>
			</div>
		</div>

		<hr class="border-gray-850/30" />

		<div class="space-y-2 text-xs leading-5 text-gray-400">
			<p>
				本教学前端参考 Open WebUI / TAgent 的设置命名与布局。课程答疑能力由 basic-agent 与
				OpenNoteBook 提供。
			</p>
		</div>

		<div class="flex flex-wrap gap-2 text-xs">
			<a
				class="rounded-lg bg-gray-850 px-3 py-1.5 font-medium transition hover:bg-gray-800"
				href="https://docs.openwebui.com"
				target="_blank"
				rel="noreferrer"
			>
				帮助文档
			</a>
			<a
				class="rounded-lg bg-gray-850 px-3 py-1.5 font-medium transition hover:bg-gray-800"
				href="https://github.com/open-webui/open-webui"
				target="_blank"
				rel="noreferrer"
			>
				GitHub
			</a>
			<a
				class="rounded-lg bg-gray-850 px-3 py-1.5 font-medium transition hover:bg-gray-800"
				href="https://discord.gg/5rJgQTnV4s"
				target="_blank"
				rel="noreferrer"
			>
				Discord
			</a>
		</div>
	</div>
</div>
