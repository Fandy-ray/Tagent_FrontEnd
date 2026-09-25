import fs from 'node:fs';

const path = 'src/lib/components/chat/SettingsModal.svelte';
let s = fs.readFileSync(path, 'utf8');

const scriptStart = s.indexOf('<script lang="ts">');
const scriptEnd = s.indexOf('</script>');
if (scriptStart < 0 || scriptEnd < 0) throw new Error('script not found');

const newScript = `<script lang="ts">
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
		return \`px-0.5 md:px-2.5 py-1 min-w-fit rounded-xl flex-1 md:flex-none flex text-left transition \${
			active
				? hc
					? 'bg-gray-800'
					: 'bg-gray-800 text-white'
				: hc
					? 'hover:bg-gray-800'
					: 'text-gray-600 hover:text-white'
		}\`;
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
`;

s = s.slice(0, scriptStart) + newScript + s.slice(scriptEnd);

// Update tab click handlers
s = s.replace(
	/onclick=\{\(\) => \{\s*selectedTab = '(\w+)';\s*\}\}/g,
	"onclick={() => { void selectTab('$1'); }}"
);

// Replace content panel
const contentOld = `				<div
					class="flex h-[min(42rem,calc(90vh-5rem))] min-h-0 flex-1 flex-col overflow-hidden px-3.5 md:pl-0 md:pr-4.5"
				>
					{#if selectedTab === 'general'}
						<General
							{settings}
							{saveSettings}
							onSave={notifySaved}
						/>
					{:else if selectedTab === 'interface'}
						<Interface {settings} {saveSettings} onSave={notifySaved} />
					{:else if selectedTab === 'connections'}
						<Connections {settings} {saveSettings} onSave={notifySaved} />
					{:else if selectedTab === 'tools'}
						<Integrations {settings} {saveSettings} onSave={notifySaved} />
					{:else if selectedTab === 'personalization'}
						<Personalization {settings} {saveSettings} onSave={notifySaved} />
					{:else if selectedTab === 'audio'}
						<Audio {settings} {saveSettings} onSave={notifySaved} />
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
					{:else if selectedTab === 'account'}
						<Account {settings} {saveSettings} onSave={notifySaved} />
					{:else if selectedTab === 'about'}
						<About />
					{/if}
				</div>`;

const contentNew = `				<div
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
						<Tab {settings} {saveSettings} onSave={notifySaved} />
					{/if}
				</div>`;

if (!s.includes(contentOld)) {
	console.error('content block not found');
} else {
	s = s.replace(contentOld, contentNew);
}

fs.writeFileSync(path, s);
console.log('SettingsModal rewritten');
