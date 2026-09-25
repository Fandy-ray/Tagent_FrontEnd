<script lang="ts">
	import {
		createNote,
		createNotebook,
		listNotebooks,
		type NotebookSummary
	} from '$lib/apis/opennotebook';

	type Props = {
		open?: boolean;
		title?: string;
		content?: string;
		onClose?: () => void;
		onSaved?: (notebookName: string) => void;
	};

	let {
		open = false,
		title = '答疑摘录',
		content = '',
		onClose = () => {},
		onSaved = () => {}
	}: Props = $props();

	let notebooks = $state<NotebookSummary[]>([]);
	let loadStatus = $state<'loading' | 'ready' | 'offline'>('loading');
	let selectedId = $state('');
	let creating = $state(false);
	let newName = $state('');
	let saving = $state(false);
	let errorMsg = $state('');

	const load = async () => {
		const controller = new AbortController();
		const timer = window.setTimeout(() => controller.abort(), 4000);

		loadStatus = 'loading';
		errorMsg = '';

		try {
			notebooks = await listNotebooks(controller.signal);
			loadStatus = 'ready';

			if (!creating && !selectedId && notebooks[0]) {
				selectedId = notebooks[0].id;
			}

			if (notebooks.length === 0) {
				creating = true;
			}
		} catch {
			notebooks = [];
			loadStatus = 'offline';
			creating = true;
		} finally {
			window.clearTimeout(timer);
		}
	};

	$effect(() => {
		if (open) {
			void load();
		}
	});

	const save = async () => {
		if (saving) {
			return;
		}

		saving = true;
		errorMsg = '';

		try {
			let notebook = notebooks.find((item) => item.id === selectedId) ?? null;

			if (creating) {
				const name = newName.trim();

				if (!name) {
					errorMsg = '请填写新笔记本名称。';
					saving = false;
					return;
				}

				notebook = await createNotebook(name, '由答疑智能体创建');
			}

			if (!notebook) {
				errorMsg = '请选择或新建一个笔记本。';
				saving = false;
				return;
			}

			await createNote({
				title: title.trim() || '答疑摘录',
				content,
				notebookId: notebook.id,
				noteType: 'ai'
			});

			onSaved(notebook.name);
			onClose();
		} catch {
			errorMsg =
				loadStatus === 'offline'
					? '无法连接 OpenNoteBook，请先启动笔记本服务。'
					: '写入笔记本失败，请稍后重试。';
		} finally {
			saving = false;
		}
	};
</script>

{#if open}
	<div class="fixed inset-0 z-[60] flex items-center justify-center px-4">
		<button type="button" class="absolute inset-0 bg-black/60" aria-label="关闭" onclick={onClose}
		></button>

		<div
			class="relative w-full max-w-md rounded-2xl border border-white/10 bg-[#242424] p-4 text-left shadow-2xl"
			role="dialog"
			aria-labelledby="save-to-notebook-title"
		>
			<h2 id="save-to-notebook-title" class="text-base font-semibold text-white">加入笔记本</h2>
			<p class="mt-1 text-sm text-gray-400">将这轮问答写入所选笔记本的笔记中。</p>

			<div class="mt-4 max-h-56 space-y-1 overflow-y-auto">
				{#if loadStatus === 'loading'}
					<div class="px-2 py-3 text-sm text-gray-500">正在读取笔记本…</div>
				{:else if loadStatus === 'offline'}
					<div class="px-2 py-3 text-sm text-gray-500">
						无法连接 OpenNoteBook，仍可填写名称，但需要服务启动后才能保存。
					</div>
				{:else if notebooks.length === 0}
					<div class="px-2 py-3 text-sm text-gray-500">还没有笔记本，请在下方新建一个。</div>
				{:else}
					{#each notebooks as notebook (notebook.id)}
						<label
							class={`flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${
								!creating && selectedId === notebook.id
									? 'bg-white/[0.08] text-white'
									: 'text-gray-300 hover:bg-white/[0.04]'
							}`}
						>
							<input
								type="radio"
								name="save-notebook"
								class="accent-blue-500"
								checked={!creating && selectedId === notebook.id}
								onchange={() => {
									creating = false;
									selectedId = notebook.id;
								}}
							/>
							<span class="min-w-0 flex-1 truncate">{notebook.name}</span>
							<span class="text-[11px] text-gray-500">
								{notebook.note_count ?? 0} 条笔记
							</span>
						</label>
					{/each}
				{/if}
			</div>

			<label
				class={`mt-3 flex cursor-pointer items-start gap-3 rounded-xl px-3 py-2 text-sm transition ${
					creating ? 'bg-white/[0.08] text-white' : 'text-gray-300 hover:bg-white/[0.04]'
				}`}
			>
				<input
					type="radio"
					name="save-notebook"
					class="mt-2 accent-blue-500"
					checked={creating}
					onchange={() => {
						creating = true;
					}}
				/>
				<span class="min-w-0 flex-1">
					<span class="block">新建笔记本</span>
					<input
						class="mt-2 w-full rounded-lg border border-white/15 bg-transparent px-3 py-1.5 text-sm text-gray-100 outline-none placeholder:text-gray-500 focus:border-blue-400"
						placeholder="例如：计算机网络答疑"
						bind:value={newName}
						onfocus={() => {
							creating = true;
						}}
					/>
				</span>
			</label>

			{#if errorMsg}
				<p class="mt-3 text-sm text-red-400">{errorMsg}</p>
			{/if}

			<div class="mt-4 flex justify-end gap-2">
				<button
					type="button"
					class="rounded-xl px-4 py-2 text-sm text-gray-300 transition hover:bg-white/10"
					onclick={onClose}
				>
					取消
				</button>
				<button
					type="button"
					class="rounded-xl bg-white px-4 py-2 text-sm font-medium text-gray-900 transition hover:bg-gray-200 disabled:opacity-50"
					disabled={saving}
					onclick={() => void save()}
				>
					{saving ? '正在加入…' : '加入'}
				</button>
			</div>
		</div>
	</div>
{/if}
