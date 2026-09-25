<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import ConfirmDialog from '$lib/components/workspace/common/ConfirmDialog.svelte';
	import EditorShell from '$lib/components/workspace/EditorShell.svelte';
	import {
		deleteKnowledge,
		getKnowledge,
		relativeTime,
		upsertKnowledge,
		type KnowledgeDoc,
		type WorkspaceKnowledge
	} from '$lib/data/workspaceResources';

	let saving = $state(false);
	let missing = $state(false);
	let item = $state<WorkspaceKnowledge | null>(null);
	let name = $state('');
	let description = $state('');
	let notebookId = $state('');
	let showDocModal = $state(false);
	let docName = $state('');
	let docContent = $state('');
	let confirmShow = $state(false);
	let confirmDocId = $state<string | null>(null);
	let confirmKb = $state(false);

	const withParams = (path: string) => {
		const params = new URLSearchParams();
		const model = $page.url.searchParams.get('model');
		const chat = $page.url.searchParams.get('chat');
		if (model) params.set('model', model);
		if (chat) params.set('chat', chat);
		const search = params.toString();
		return search ? `${path}?${search}` : path;
	};

	const field =
		'w-full rounded-xl border border-gray-800 bg-gray-850 px-3 py-2 text-sm text-white outline-none placeholder:text-gray-500 focus:border-gray-600';
	const label = 'mb-1.5 block text-xs font-medium text-gray-400';

	const load = () => {
		const id = $page.params.id;
		const existing = id ? getKnowledge(id) : null;
		if (!existing) {
			missing = true;
			item = null;
			return;
		}
		missing = false;
		item = existing;
		name = existing.name;
		description = existing.description || '';
		notebookId = existing.notebookId || '';
	};

	const persist = (patch?: Partial<WorkspaceKnowledge>) => {
		if (!item) return;
		const next: WorkspaceKnowledge = {
			...item,
			name: name.trim() || item.name,
			description: description.trim(),
			notebookId: notebookId.trim() || null,
			...patch,
			updatedAt: Date.now()
		};
		upsertKnowledge(next);
		item = next;
	};

	const onSave = () => {
		saving = true;
		persist();
		saving = false;
	};

	const addDoc = () => {
		if (!item || !docName.trim()) return;
		const doc: KnowledgeDoc = {
			id: `doc-${Date.now().toString(36)}`,
			name: docName.trim(),
			content: docContent,
			createdAt: Date.now()
		};
		persist({ docs: [...item.docs, doc] });
		docName = '';
		docContent = '';
		showDocModal = false;
	};

	const removeDoc = (docId: string) => {
		if (!item) return;
		persist({ docs: item.docs.filter((d) => d.id !== docId) });
	};

	const openNotebook = () => {
		if (!notebookId.trim()) return;
		const params = new URLSearchParams($page.url.searchParams);
		params.set('notebook', notebookId.trim());
		params.set('from', 'workspace');
		void goto(`/notebook?${params.toString()}`);
	};

	onMount(load);
</script>

{#if missing || !item}
	<div class="px-2 py-16 text-center text-sm text-gray-500">
		未找到该知识库。
		<button
			type="button"
			class="mt-3 block w-full text-white underline"
			onclick={() => void goto(withParams('/workspace/knowledge'))}
		>
			返回列表
		</button>
	</div>
{:else}
	<EditorShell
		title="编辑知识库"
		subtitle={item.id}
		{saving}
		saveLabel="保存"
		onBack={() => void goto(withParams('/workspace/knowledge'))}
		{onSave}
	>
		<div>
			<label class={label} for="kb-name">名称</label>
			<input id="kb-name" class={field} bind:value={name} />
		</div>
		<div>
			<label class={label} for="kb-desc">描述</label>
			<textarea id="kb-desc" class="{field} min-h-[4rem] resize-y" bind:value={description} rows="3"
			></textarea>
		</div>
		<div>
			<label class={label} for="kb-nb">Notebook ID</label>
			<div class="flex gap-2">
				<input
					id="kb-nb"
					class={field}
					bind:value={notebookId}
					placeholder="绑定 OpenNoteBook 笔记本 ID"
				/>
				<button
					type="button"
					class="shrink-0 rounded-xl bg-gray-800 px-3 py-2 text-xs text-gray-200 hover:bg-gray-700 disabled:opacity-40"
					disabled={!notebookId.trim()}
					onclick={openNotebook}
				>
					打开笔记本
				</button>
			</div>
		</div>

		<div class="border-t border-gray-800 pt-4">
			<div class="mb-3 flex items-center justify-between">
				<div class="text-sm font-medium text-white">文档 ({item.docs.length})</div>
				<button
					type="button"
					class="rounded-xl bg-white px-2.5 py-1 text-xs font-medium text-black hover:bg-gray-200"
					onclick={() => {
						showDocModal = true;
					}}
				>
					添加文本
				</button>
			</div>
			{#if item.docs.length === 0}
				<div class="py-6 text-center text-xs text-gray-500">暂无文档</div>
			{:else}
				<div class="divide-y divide-white/[0.04] rounded-xl border border-gray-800">
					{#each item.docs as doc (doc.id)}
						<div class="flex items-start justify-between gap-2 px-3 py-2.5">
							<div class="min-w-0">
								<div class="truncate text-sm text-white">{doc.name}</div>
								<div class="mt-0.5 line-clamp-2 text-xs text-gray-500">{doc.content}</div>
								<div class="mt-1 text-[10px] text-gray-600">{relativeTime(doc.createdAt)}</div>
							</div>
							<button
								type="button"
								class="shrink-0 text-xs text-red-400 hover:text-red-300"
								onclick={() => {
									confirmDocId = doc.id;
									confirmShow = true;
								}}
							>
								删除
							</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<div class="border-t border-gray-800 pt-4">
			<button
				type="button"
				class="rounded-xl bg-red-600/20 px-3 py-1.5 text-sm text-red-400 hover:bg-red-600/30"
				onclick={() => {
					confirmKb = true;
				}}
			>
				删除知识库
			</button>
		</div>
	</EditorShell>
{/if}

{#if showDocModal}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 px-4"
		onclick={() => (showDocModal = false)}
	>
		<div
			class="w-full max-w-md rounded-2xl border border-gray-800 bg-gray-850 p-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
		>
			<h3 class="text-base font-medium text-white">添加文本文档</h3>
			<div class="mt-3 space-y-3">
				<div>
					<label class={label} for="doc-name">名称</label>
					<input id="doc-name" class={field} bind:value={docName} />
				</div>
				<div>
					<label class={label} for="doc-content">内容</label>
					<textarea
						id="doc-content"
						class="{field} min-h-[8rem] resize-y"
						bind:value={docContent}
						rows="6"
					></textarea>
				</div>
			</div>
			<div class="mt-4 flex justify-end gap-2">
				<button
					type="button"
					class="rounded-xl px-3 py-1.5 text-sm text-gray-400 hover:bg-gray-800"
					onclick={() => (showDocModal = false)}
				>
					取消
				</button>
				<button
					type="button"
					class="rounded-xl bg-white px-3 py-1.5 text-sm font-medium text-black hover:bg-gray-200"
					onclick={addDoc}
				>
					添加
				</button>
			</div>
		</div>
	</div>
{/if}

<ConfirmDialog
	bind:show={confirmShow}
	title="删除文档？"
	message="此操作无法撤销。"
	onConfirm={() => {
		if (confirmDocId) {
			removeDoc(confirmDocId);
			confirmDocId = null;
		}
	}}
/>

<ConfirmDialog
	bind:show={confirmKb}
	title="删除知识库？"
	message="将永久删除此知识库及其文档。"
	onConfirm={() => {
		if (item) {
			deleteKnowledge(item.id);
			void goto(withParams('/workspace/knowledge'));
		}
	}}
/>
