<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import Switch from '$lib/components/common/Switch.svelte';
	import ConfirmDialog from '$lib/components/workspace/common/ConfirmDialog.svelte';
	import ItemMenu from '$lib/components/workspace/common/ItemMenu.svelte';
	import WorkspaceShell from '$lib/components/workspace/WorkspaceShell.svelte';
	import {
		deleteSkill,
		downloadJson,
		filterByView,
		listSkills,
		matchQuery,
		slugify,
		upsertSkill,
		type WorkspaceSkill,
		type WorkspaceView
	} from '$lib/data/workspaceResources';

	let query = $state('');
	let viewOption = $state<WorkspaceView>(
		(typeof localStorage !== 'undefined'
			? (localStorage.workspaceViewOption as WorkspaceView)
			: '') || ''
	);
	let skills = $state<WorkspaceSkill[]>([]);
	let fileInput: HTMLInputElement | null = $state(null);
	let confirmShow = $state(false);
	let pendingDeleteId = $state<string | null>(null);

	const withParams = (path: string) => {
		const params = new URLSearchParams();
		const model = $page.url.searchParams.get('model');
		const chat = $page.url.searchParams.get('chat');
		if (model) params.set('model', model);
		if (chat) params.set('chat', chat);
		const search = params.toString();
		return search ? `${path}?${search}` : path;
	};

	const filtered = $derived(
		filterByView(skills, viewOption).filter((s) =>
			matchQuery(`${s.name} ${s.id} ${s.description ?? ''} ${s.content}`, query)
		)
	);

	const reload = () => {
		skills = listSkills();
	};

	const cloneSkill = (s: WorkspaceSkill) => {
		sessionStorage.setItem(
			'skill',
			JSON.stringify({
				...s,
				id: `${s.id}-copy`,
				name: `${s.name} (副本)`
			})
		);
		void goto(withParams('/workspace/skills/create'));
	};

	const onImport = () => fileInput?.click();

	const handleImportFile = async (e: Event) => {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		try {
			const text = await file.text();
			const isMd = file.name.toLowerCase().endsWith('.md');
			if (isMd) {
				const base = file.name.replace(/\.md$/i, '');
				upsertSkill({
					id: `skill-${slugify(base) || Date.now().toString(36)}`,
					name: base,
					description: '',
					content: text,
					isActive: true,
					owner: 'you',
					createdAt: Date.now(),
					updatedAt: Date.now()
				});
			} else {
				const data = JSON.parse(text) as WorkspaceSkill[] | WorkspaceSkill;
				const items = Array.isArray(data) ? data : [data];
				for (const item of items) {
					if (!item?.id || !item?.name) continue;
					upsertSkill({
						...item,
						owner: item.owner === 'shared' ? 'shared' : 'you',
						createdAt: item.createdAt || Date.now(),
						updatedAt: Date.now()
					});
				}
			}
			reload();
		} catch {
			/* ignore */
		}
		input.value = '';
	};

	onMount(reload);
</script>

<input
	bind:this={fileInput}
	type="file"
	accept="application/json,.json,.md,text/markdown"
	class="hidden"
	onchange={handleImportFile}
/>

<WorkspaceShell
	title="技能"
	count={filtered.length}
	searchPlaceholder="搜索技能"
	bind:query
	bind:viewOption
	primaryHref={withParams('/workspace/skills/create')}
	primaryLabel="创建技能"
	importLabel="导入"
	{onImport}
	showEmpty={filtered.length === 0}
	emptyTitle="未找到任何技能"
>
	<div class="divide-y divide-white/[0.04]">
		{#each filtered as skill (skill.id)}
			<div class="flex items-center gap-3 px-4 py-3">
				<div class="min-w-0 flex-1">
					<div class="truncate text-sm font-medium text-white">{skill.name}</div>
					<div class="truncate text-xs text-gray-500">
						{skill.description || skill.id}
					</div>
				</div>
				<Switch
					state={skill.isActive !== false}
					onChange={(state) => {
						upsertSkill({ ...skill, isActive: state });
						reload();
					}}
				/>
				<ItemMenu
					items={[
						{
							label: '编辑',
							onClick: () =>
								void goto(
									withParams(`/workspace/skills/edit?id=${encodeURIComponent(skill.id)}`)
								)
						},
						{ label: '克隆', onClick: () => cloneSkill(skill) },
						{ label: '导出', onClick: () => downloadJson(`${skill.id}.json`, skill) },
						{
							label: '删除',
							danger: true,
							onClick: () => {
								pendingDeleteId = skill.id;
								confirmShow = true;
							}
						}
					]}
				/>
			</div>
		{/each}
	</div>
</WorkspaceShell>

<ConfirmDialog
	bind:show={confirmShow}
	title="删除技能？"
	message="此操作无法撤销。"
	onConfirm={() => {
		if (pendingDeleteId) {
			deleteSkill(pendingDeleteId);
			pendingDeleteId = null;
			reload();
		}
	}}
/>
