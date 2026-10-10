<script lang="ts">
	import { resolve } from '$app/paths';

	import DataControls from '$lib/components/chat/Settings/DataControls.svelte';
	import General from '$lib/components/chat/Settings/General.svelte';
	import AppNotification from '$lib/components/icons/AppNotification.svelte';
	import DatabaseSettings from '$lib/components/icons/DatabaseSettings.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import SettingsAlt from '$lib/components/icons/SettingsAlt.svelte';
	import SoundHigh from '$lib/components/icons/SoundHigh.svelte';
	import UserBadgeCheck from '$lib/components/icons/UserBadgeCheck.svelte';
	import UserCircle from '$lib/components/icons/UserCircle.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import {
		applyTextScale,
		applyTheme,
		loadUserSettings,
		saveUserSettings,
		type UserSettings
	} from '$lib/data/userSettings';
	import { tick, type Component } from 'svelte';
	import { getI18nContext } from '$lib/i18n';

	const i18n = getI18nContext();

	type TabId = 'general' | 'interface' | 'audio' | 'data_controls' | 'account';

	type Props = {
		open?: boolean;
		userRole?: string;
		onClose?: () => void;
		onSettingsChange?: (settings: UserSettings) => void;
		onImportChats?: (file: File) => void;
		onExportChats?: () => void;
		onArchiveAllChats?: () => void;
		onDeleteAllChats?: () => void;
		onToast?: (message: string) => void;
		/** 当前版本暂不提供管理员面板入口。 */
		showAdminPanel?: boolean;
		/** 打开时先显示哪个标签页，默认「通用」（导航栏的「数据」按钮用它直达数据管理） */
		initialTab?: TabId;
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
		onToast = () => {},
		showAdminPanel = false,
		initialTab = 'general'
	}: Props = $props();

	let selectedTab = $state<TabId>('general');
	let search = $state('');
	let settings = $state<UserSettings>(loadUserSettings());
	let searchDebounce: ReturnType<typeof setTimeout> | null = null;
	let prevOpen = false;
	let tabLoading = $state(false);
	let lazyTabs = $state<Partial<Record<TabId, Component<Record<string, unknown>>>>>({});

	const allTabs: { id: TabId; title: string; keywords: string[] }[] = [
		{
			id: 'general',
			title: 'General',
			keywords: [
				'general',
				'theme',
				'language',
				'notification',
				'system prompt',
				'advanced params',
				'通用',
				'主题',
				'语言',
				'通知',
				'系统提示',
				'高级参数'
			]
		},
		{
			id: 'interface',
			title: 'Interface',
			keywords: ['interface', 'wide', 'bubble', 'zoom', '界面', '宽屏', '气泡', '缩放']
		},
		{ id: 'audio', title: 'Audio', keywords: ['audio', 'voice', 'stt', 'tts', '语音'] },
		{
			id: 'data_controls',
			title: 'Data',
			keywords: ['data', 'import', 'export', 'archive', '数据', '导入', '导出', '归档']
		},
		{
			id: 'account',
			title: 'Account',
			keywords: ['account', 'name', 'avatar', '账号', '名称', '头像']
		}
	];

	let filteredIds = $state<TabId[]>(allTabs.filter((t) => t.id !== 'audio').map((t) => t.id));

	// Tab titles with i18n
	const tabTitles: Record<TabId, string> = $derived({
		general: $i18n.t('General'),
		interface: $i18n.t('Interface'),
		audio: $i18n.t('音频'),
		data_controls: $i18n.t('数据'),
		account: $i18n.t('Account')
	});

	const tabLoaders = {
		interface: () => import('$lib/components/chat/Settings/Interface.svelte'),
		audio: () => import('$lib/components/chat/Settings/Audio.svelte'),
		account: () => import('$lib/components/chat/Settings/Account.svelte')
	};

	const ensureTab = async (id: TabId) => {
		if (id === 'general' || id === 'data_controls' || lazyTabs[id]) return;
		const loader = tabLoaders[id];
		if (!loader) return;
		tabLoading = true;
		try {
			const mod = await loader();
			lazyTabs = {
				...lazyTabs,
				[id]: mod.default as unknown as Component<Record<string, unknown>>
			};
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
			.filter((tab) => tab.id !== 'audio')
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
			// 走 selectTab：懒加载的标签页要它去加载组件，直接赋值会是一片空白
			void selectTab(initialTab);
			filteredIds = allTabs.filter((t) => t.id !== 'audio').map((t) => t.id);
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
			class="bg-gray-850 mx-1 w-full max-w-5xl overflow-hidden rounded-2xl border border-gray-800 text-gray-100 shadow-2xl"
			onclick={(event) => event.stopPropagation()}
			role="dialog"
			tabindex="-1"
			aria-modal="true"
			aria-label={$i18n.t('Settings')}
		>
			<div class="flex justify-between px-4 pt-4.5 pb-0.5 text-gray-300 md:px-4.5 md:pb-2.5">
				<div class="self-center text-lg font-medium">{$i18n.t('Settings')}</div>
				<button type="button" class="self-center" aria-label={$i18n.t('Close')} onclick={onClose}>
					<XMark className="h-5 w-5" />
				</button>
			</div>

			<div class="flex w-full flex-col pt-1 pb-4 md:flex-row">
				<div
					role="tablist"
					id="settings-tabs-container"
					class="tabs mx-3 mb-1 flex flex-1 -translate-y-1 flex-row gap-2.5 overflow-x-auto text-left text-sm text-gray-200 md:mb-0 md:max-h-[42rem] md:min-h-[42rem] md:w-[12.5rem] md:flex-none md:flex-col md:gap-1 md:pr-4"
				>
					<div
						class="my-1 mb-1.5 hidden w-full gap-2 rounded-full bg-gray-900/80 px-2.5 backdrop-blur-2xl md:flex"
						id="settings-search"
					>
						<div class="self-center rounded-l-xl bg-transparent">
							<Search className="size-3.5" strokeWidth="1.5" />
						</div>
						<label class="sr-only" for="search-input-settings-modal">{$i18n.t('Search')}</label>
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
									onclick={() => {
										void selectTab('general');
									}}
								>
									<div class="mr-2 self-center"><SettingsAlt strokeWidth="2" /></div>
									<div class="self-center">{tabTitles.general}</div>
								</button>
							{:else if tabId === 'interface'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'interface'}
									class={tabClass('interface')}
									onclick={() => {
										void selectTab('interface');
									}}
								>
									<div class="mr-2 self-center"><AppNotification strokeWidth="2" /></div>
									<div class="self-center">{tabTitles.interface}</div>
								</button>
							{:else if tabId === 'audio'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'audio'}
									class={tabClass('audio')}
									onclick={() => {
										void selectTab('audio');
									}}
								>
									<div class="mr-2 self-center"><SoundHigh strokeWidth="2" /></div>
									<div class="self-center">{tabTitles.audio}</div>
								</button>
							{:else if tabId === 'data_controls'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'data_controls'}
									class={tabClass('data_controls')}
									onclick={() => {
										void selectTab('data_controls');
									}}
								>
									<div class="mr-2 self-center"><DatabaseSettings strokeWidth="2" /></div>
									<div class="self-center">{tabTitles.data_controls}</div>
								</button>
							{:else if tabId === 'account'}
								<button
									type="button"
									role="tab"
									aria-selected={selectedTab === 'account'}
									class={tabClass('account')}
									onclick={() => {
										void selectTab('account');
									}}
								>
									<div class="mr-2 self-center"><UserCircle strokeWidth="2" /></div>
									<div class="self-center">{tabTitles.account}</div>
								</button>
							{/if}
						{/each}
					{:else}
						<div class="mt-4 text-center text-gray-500">{$i18n.t('No results found')}</div>
					{/if}

					{#if userRole === 'admin' && showAdminPanel}
						<a
							href={resolve('/admin')}
							class="mt-0 flex min-w-fit flex-1 rounded-xl px-0.5 py-1 text-left transition select-none md:mt-auto md:flex-none md:px-2.5 {settings.highContrastMode
								? 'hover:bg-gray-800'
								: 'text-gray-600 hover:text-white'}"
							onclick={(e) => {
								e.preventDefault();
								onClose();
								window.location.assign('/admin');
							}}
						>
							<div class="mr-2 self-center"><UserBadgeCheck strokeWidth="2" /></div>
							<div class="self-center">{$i18n.t('Admin Settings')}</div>
						</a>
					{/if}
				</div>

				<div
					class="flex h-[min(42rem,calc(90vh-5rem))] min-h-0 flex-1 flex-col overflow-hidden px-3.5 md:pr-4.5 md:pl-0"
				>
					{#if selectedTab === 'general'}
						<General {settings} {saveSettings} onSave={notifySaved} />
					{:else if selectedTab === 'data_controls'}
						<DataControls
							onImport={onImportChats}
							onExport={onExportChats}
							onArchiveAll={onArchiveAllChats}
							onDeleteAll={onDeleteAllChats}
						/>
					{:else if tabLoading && !lazyTabs[selectedTab]}
						<p class="py-6 text-xs text-gray-500">{$i18n.t('Loading...')}</p>
					{:else if lazyTabs[selectedTab]}
						{@const Tab = lazyTabs[selectedTab]}
						<Tab {settings} {saveSettings} onSave={notifySaved} />
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
