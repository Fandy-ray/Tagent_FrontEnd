<script lang="ts">
	import DataControls from '$lib/components/chat/Settings/DataControls.svelte';
	import General from '$lib/components/chat/Settings/General.svelte';
	import AppNotification from '$lib/components/icons/AppNotification.svelte';
	import DatabaseSettings from '$lib/components/icons/DatabaseSettings.svelte';
	import Face from '$lib/components/icons/Face.svelte';
	import InfoCircle from '$lib/components/icons/InfoCircle.svelte';
	import Link from '$lib/components/icons/Link.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import SettingsAlt from '$lib/components/icons/SettingsAlt.svelte';
	import SoundHigh from '$lib/components/icons/SoundHigh.svelte';
	import UserBadgeCheck from '$lib/components/icons/UserBadgeCheck.svelte';
	import UserCircle from '$lib/components/icons/UserCircle.svelte';
	import WrenchAlt from '$lib/components/icons/WrenchAlt.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import {
		applyTextScale,
		applyTheme,
		loadUserSettings,
		saveUserSettings,
		type UserSettings
	} from '$lib/data/userSettings';
	import { tick, type Component } from 'svelte';

	type TabId =
		| 'general'
		| 'interface'
		| 'connections'
		| 'tools'
		| 'personalization'
		| 'audio'
		| 'data_controls'
		| 'account'
		| 'about';

	type Props = {
		open?: boolean;
		userRole?: string;
		onClose?: () => void;
		onSettingsChange?: (settings: UserSettings) => void;
		onImportChats?: (file: File) => void;
		onExportChats?: () => void;
		onArchiveAllChats?: () => void;
		onDeleteAllChats?: () => void;
		onOpenArchived?: () => void;
		onToast?: (message: string) => void;
	};

	let {
		open = false,
		userRole = 'admin',
		onClose = () => {},
		onSettingsChange = () => {},
		onImportChats = () => {},
		onExportChats = () => {},
		onArchiveAllChats = () => {},
		onDeleteAllChats = () => {},
		onOpenArchived = () => {},
		onToast = () => {}
	}: Props = $props();

	let selectedTab = $state<TabId>('general');
	let search = $state('');
	let settings = $state<UserSettings>(loadUserSettings());
	let searchDebounce: ReturnType<typeof setTimeout> | null = null;
	let prevOpen = false;
	let tabLoading = $state(false);
	let lazyTabs = $state<Partial<Record<TabId, Component<any>>>>({});

	const allTabs: { id: TabId; title: string; keywords: string[] }[] = [
		{ id: 'general', title: '通用', keywords: ['general', '主题', '语言', '通知', '系统提示', '高级参数', 'theme'] },
		{ id: 'interface', title: '界面', keywords: ['interface', '界面', '宽屏', '气泡', '缩放'] },
		{ id: 'connections', title: '外部连接', keywords: ['connections', '外部连接', 'openai', 'api'] },
		{ id: 'tools', title: '扩展功能', keywords: ['integrations', '扩展功能', '工具', 'openapi'] },
		{ id: 'personalization', title: '个性化', keywords: ['personalization', '个性化', '记忆'] },
		{ id: 'audio', title: '语音', keywords: ['audio', '语音', 'stt', 'tts'] },
		{ id: 'data_controls', title: '数据', keywords: ['data', '数据', '导入', '导出', '归档'] },
		{ id: 'account', title: '账号', keywords: ['account', '账号', '名称', '头像'] },
		{ id: 'about', title: '关于', keywords: ['about', '关于', '版本'] }
	];

	let filteredIds = $state<TabId[]>(allTabs.map((t) => t.id));

	const tabLoaders: Partial<Record<TabId, () => Promise<{ default: Component<any> }>>> = {
		interface: () => import('$lib/components/chat/Settings/Interface.svelte'),
		connections: () => import('$lib/components/chat/Settings/Connections.svelte'),
		tools: () => import('$lib/components/chat/Settings/Integrations.svelte'),
		personalization: () => import('$lib/components/chat/Settings/Personalization.svelte'),
		audio: () => import('$lib/components/chat/Settings/Audio.svelte'),
		account: () => import('$lib/components/chat/Settings/Account.svelte'),
		about: () => import('$lib/components/chat/Settings/About.svelte')
	};

	const ensureTab = async (id: TabId) => {
		if (id === 'general' || id === 'data_controls' || lazyTabs[id]) return;
		const loader = tabLoaders[id];
		if (!loader) return;
		tabLoading = true;
		try {
			const mod = await loader();
			lazyTabs = { ...lazyTabs, [id]: mod.default };
		} finally {
			tabLoading = false;
		}
	};

	const selectTab = async (id: TabId) => {
		selectedTab = id;
		await ensureTab(id);
	};

	const tabClass = (id: TabId) => {
		const active = selectedTab === id;
		const hc = settings.highContrastMode;
		return `px-0.5 md:px-2.5 py-1 min-w-fit rounded-xl flex-1 md:flex-none flex text-left transition ${
			active
				? hc
					? 'bg-gray-800'
					: 'bg-gray-800 text-white'
				: hc
					? 'hover:bg-gray-800'
					: 'text-gray-600 hover:text-white'
		}`;
	};

	const refreshFilter = () => {
		const q = search.toLowerCase().trim();
		const next = allTabs
			.filter((tab) => {
				if (!q) return true;
				return (
					tab.title.toLowerCase().includes(q) ||
					tab.keywords.some((k) => k.toLowerCase().includes(q))
				);
			})
			.map((t) => t.id);
		filteredIds = next;
		if (next.length > 0 && !next.includes(selectedTab)) {
			void selectTab(next[0]);
		}
	};

	const onSearchInput = () => {
		if (searchDebounce) clearTimeout(searchDebounce);
		searchDebounce = setTimeout(refreshFilter, 100);
	};

	const persist = (partial: Partial<UserSettings>) => {
		const next = { ...settings, ...partial };
		settings = next;
		saveUserSettings(next);
		onSettingsChange(next);
	};

	const saveSettings = async (updated: Partial<UserSettings>) => {
		persist(updated);
	};

	const notifySaved = () => {
		onToast('设置已成功保存！');
	};

	const scrollHandler = (event: WheelEvent) => {
		const el = document.getElementById('settings-tabs-container');
		if (!el) return;
		event.preventDefault();
		el.scrollLeft += event.deltaY;
	};

	$effect(() => {
		const isOpen = open;
		if (isOpen && !prevOpen) {
			const next = loadUserSettings();
			applyTheme(next.theme);
			applyTextScale(next.textScale);
			settings = next;
			search = '';
			selectedTab = 'general';
			filteredIds = allTabs.map((t) => t.id);
			tick().then(() => {
				document
					.getElementById('settings-tabs-container')
					?.addEventListener('wheel', scrollHandler, { passive: false });
			});
		}
		if (!isOpen && prevOpen) {
			document
				.getElementById('settings-tabs-container')
				?.removeEventListener('wheel', scrollHandler);
		}
		prevOpen = isOpen;
	});
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 px-3"
		onclick={onClose}
	>
		<div
			class="mx-1 w-full max-w-5xl overflow-hidden rounded-2xl border border-gray-800 bg-gray-850 text-gray-100 shadow-2xl"
			onclick={(event) => event.stopPropagation()}
			role="dialog"
			tabindex="-1"
			aria-modal="true"
			aria-label="设置"
		>
			<div class="flex justify-between px-4 pt-4.5 pb-0.5 text-gray-300 md:px-4.5 md:pb-2.5">
				<div class="self-center text-lg font-medium">设置</div>
				<button
					type="button"
					class="self-center"
					aria-label="关闭设置"
					onclick={onClose}
				>
					<XMark className="h-5 w-5" />
				</button>
			</div>

			<div class="flex w-full flex-col pb-4 pt-1 md:flex-row">
				<div
					role="tablist"
					id="settings-tabs-container"
					class="tabs mx-3 mb-1 flex flex-1 -translate-y-1 flex-row gap-2.5 overflow-x-auto text-left text-sm text-gray-200 md:mb-0 md:w-[12.5rem] md:min-h-[42rem] md:max-h-[42rem] md:flex-none md:flex-col md:gap-1 md:pr-4"
				>
					<div
						class="my-1 mb-1.5 hidden w-full gap-2 rounded-full bg-gray-900/80 px-2.5 backdrop-blur-2xl md:flex"
						id="settings-search"
					>
						<div class="self-center rounded-l-xl bg-transparent">
							<Search className="size-3.5" strokeWidth="1.5" />
						</div>
						<label class="sr-only" for="search-input-settings-modal">搜索</label>
						<input
							class="w-full bg-transparent py-1 text-sm outline-none"
							bind:value={search}
							id="search-input-settings-modal"
							oninput={onSearchInput}
							placeholder="搜索"
						/>
					</div>

					{#if filteredIds.length > 0}
						{#each filteredIds as tabId (tabId)}
							{#if tabId === 'general'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'general'}
									class={tabClass('general')}
									onclick={() => { void selectTab('general'); }}
								>
									<div class="mr-2 self-center"><SettingsAlt strokeWidth="2" /></div>
									<div class="self-center">通用</div>
								</button>
							{:else if tabId === 'interface'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'interface'}
									class={tabClass('interface')}
									onclick={() => { void selectTab('interface'); }}
								>
									<div class="mr-2 self-center"><AppNotification strokeWidth="2" /></div>
									<div class="self-center">界面</div>
								</button>
							{:else if tabId === 'connections'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'connections'}
									class={tabClass('connections')}
									onclick={() => { void selectTab('connections'); }}
								>
									<div class="mr-2 self-center"><Link strokeWidth="2" /></div>
									<div class="self-center">外部连接</div>
								</button>
							{:else if tabId === 'tools'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'tools'}
									class={tabClass('tools')}
									onclick={() => { void selectTab('tools'); }}
								>
									<div class="mr-2 self-center"><WrenchAlt strokeWidth="2" /></div>
									<div class="self-center">扩展功能</div>
								</button>
							{:else if tabId === 'personalization'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'personalization'}
									class={tabClass('personalization')}
									onclick={() => { void selectTab('personalization'); }}
								>
									<div class="mr-2 self-center"><Face strokeWidth="2" /></div>
									<div class="self-center">个性化</div>
								</button>
							{:else if tabId === 'audio'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'audio'}
									class={tabClass('audio')}
									onclick={() => { void selectTab('audio'); }}
								>
									<div class="mr-2 self-center"><SoundHigh strokeWidth="2" /></div>
									<div class="self-center">语音</div>
								</button>
							{:else if tabId === 'data_controls'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'data_controls'}
									class={tabClass('data_controls')}
									onclick={() => { void selectTab('data_controls'); }}
								>
									<div class="mr-2 self-center"><DatabaseSettings strokeWidth="2" /></div>
									<div class="self-center">数据</div>
								</button>
							{:else if tabId === 'account'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'account'}
									class={tabClass('account')}
									onclick={() => { void selectTab('account'); }}
								>
									<div class="mr-2 self-center"><UserCircle strokeWidth="2" /></div>
									<div class="self-center">账号</div>
								</button>
							{:else if tabId === 'about'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'about'}
									class={tabClass('about')}
									onclick={() => { void selectTab('about'); }}
								>
									<div class="mr-2 self-center"><InfoCircle strokeWidth="2" /></div>
									<div class="self-center">关于</div>
								</button>
							{/if}
						{/each}
					{:else}
						<div class="mt-4 text-center text-gray-500">无匹配结果</div>
					{/if}

					{#if userRole === 'admin'}
						<a
							href="/admin"
							class="mt-0 flex min-w-fit flex-1 select-none rounded-xl px-0.5 py-1 text-left transition md:mt-auto md:flex-none md:px-2.5 {settings.highContrastMode
								? 'hover:bg-gray-800'
								: 'text-gray-600 hover:text-white'}"
							onclick={(e) => {
								e.preventDefault();
								onClose();
								window.location.assign('/admin');
							}}
						>
							<div class="mr-2 self-center"><UserBadgeCheck strokeWidth="2" /></div>
							<div class="self-center">管理员设置</div>
						</a>
					{/if}
				</div>

				<div
					class="flex h-[min(42rem,calc(90vh-5rem))] min-h-0 flex-1 flex-col overflow-hidden px-3.5 md:pl-0 md:pr-4.5"
				>
					{#if selectedTab === 'general'}
						<General {settings} {saveSettings} onSave={notifySaved} />
					{:else if selectedTab === 'data_controls'}
						<DataControls
							onImport={onImportChats}
							onExport={onExportChats}
							onArchiveAll={onArchiveAllChats}
							onDeleteAll={onDeleteAllChats}
							onOpenArchived={() => {
								onClose();
								onOpenArchived();
							}}
						/>
					{:else if tabLoading && !lazyTabs[selectedTab]}
						<p class="py-6 text-xs text-gray-500">加载中…</p>
					{:else if lazyTabs[selectedTab]}
						{@const Tab = lazyTabs[selectedTab]}
						{#if selectedTab === 'about'}
							<Tab />
						{:else}
							<Tab {settings} {saveSettings} onSave={notifySaved} />
						{/if}
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}

<style>
	.tabs::-webkit-scrollbar {
		display: none;
	}

	.tabs {
		-ms-overflow-style: none;
		scrollbar-width: none;
	}

	:global(input[type='number']) {
		appearance: textfield;
		-moz-appearance: textfield;
	}
</style>
