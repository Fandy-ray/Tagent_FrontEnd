<script lang="ts">
	import Switch from '$lib/components/common/Switch.svelte';
	import Minus from '$lib/components/icons/Minus.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import ManageFloatingActionButtonsModal from './Interface/ManageFloatingActionButtonsModal.svelte';
	import ManageImageCompressionModal from './Interface/ManageImageCompressionModal.svelte';
	import {
		applyHighContrast,
		applyTextScale,
		type UserSettings
	} from '$lib/data/userSettings';

	type Props = {
		settings: UserSettings;
		saveSettings: (updated: Partial<UserSettings>) => Promise<void> | void;
		onSave?: () => void;
	};

	let { settings, saveSettings, onSave = () => {} }: Props = $props();

	let textScale = $state<number | null>(settings.textScale);
	let highContrastMode = $state(settings.highContrastMode);
	let showChatTitleInTab = $state(settings.showChatTitleInTab);
	let notificationSound = $state(settings.notificationSound);
	let notificationSoundAlways = $state(settings.notificationSoundAlways);
	let userLocation = $state(settings.userLocation);
	let hapticFeedback = $state(settings.hapticFeedback);
	let copyFormatted = $state(settings.copyFormatted);
	let showUpdateToast = $state(settings.showUpdateToast);
	let showChangelog = $state(settings.showChangelog);
	let enableMessageQueue = $state(settings.enableMessageQueue);
	let chatDirection = $state(settings.chatDirection);
	let landingPageMode = $state(settings.landingPageMode);
	let backgroundImageUrl = $state<string | null>(settings.backgroundImageUrl);
	let chatBubble = $state(settings.chatBubble);
	let showUsername = $state(settings.showUsername);
	let widescreenMode = $state(settings.widescreenMode);
	let temporaryChatByDefault = $state(settings.temporaryChatByDefault);
	let chatFadeStreamingText = $state(settings.chatFadeStreamingText);
	let titleAutoGenerate = $state(settings.titleAutoGenerate);
	let autoFollowUps = $state(settings.autoFollowUps);
	let autoTags = $state(settings.autoTags);
	let responseAutoCopy = $state(settings.responseAutoCopy);
	let insertSuggestionPrompt = $state(settings.insertSuggestionPrompt);
	let keepFollowUpPrompts = $state(settings.keepFollowUpPrompts);
	let insertFollowUpPrompt = $state(settings.insertFollowUpPrompt);
	let regenerateMenu = $state(settings.regenerateMenu);
	let collapseCodeBlocks = $state(settings.collapseCodeBlocks);
	let expandDetails = $state(settings.expandDetails);
	let renderMarkdownInPreviews = $state(settings.renderMarkdownInPreviews);
	let displayMultiModelResponsesInTabs = $state(settings.displayMultiModelResponsesInTabs);
	let scrollOnBranchChange = $state(settings.scrollOnBranchChange);
	let stylizedPdfExport = $state(settings.stylizedPdfExport);
	let showFloatingActionButtons = $state(settings.showFloatingActionButtons);
	let floatingActionButtons = $state(settings.floatingActionButtons);
	let webSearchAlways = $state(settings.webSearchAlways);
	let ctrlEnterToSend = $state(settings.ctrlEnterToSend);
	let richTextInput = $state(settings.richTextInput);
	let promptAutocomplete = $state(settings.promptAutocomplete);
	let showFormattingToolbar = $state(settings.showFormattingToolbar);
	let insertPromptAsRichText = $state(settings.insertPromptAsRichText);
	let largeTextAsFile = $state(settings.largeTextAsFile);
	let detectArtifacts = $state(settings.detectArtifacts);
	let iframeSandboxAllowSameOrigin = $state(settings.iframeSandboxAllowSameOrigin);
	let iframeSandboxAllowForms = $state(settings.iframeSandboxAllowForms);
	let voiceInterruption = $state(settings.voiceInterruption);
	let showEmojiInCall = $state(settings.showEmojiInCall);
	let imageCompression = $state(settings.imageCompression);
	let imageCompressionSize = $state({ ...settings.imageCompressionSize });
	let imageCompressionInChannels = $state(settings.imageCompressionInChannels);

	let filesInputElement: HTMLInputElement | null = $state(null);
	let showManageFloating = $state(false);
	let showManageCompression = $state(false);

	const setTextScaleHandler = (scale: number | null) => {
		textScale = scale === 1 ? null : scale;
		applyTextScale(textScale);
		saveSettings({ textScale });
	};

	const toggleChatDirection = () => {
		if (chatDirection === 'auto') chatDirection = 'LTR';
		else if (chatDirection === 'LTR') chatDirection = 'RTL';
		else chatDirection = 'auto';
		saveSettings({ chatDirection });
	};

	const toggleLanding = () => {
		landingPageMode = landingPageMode === '' ? 'chat' : '';
		saveSettings({ landingPageMode });
	};

	const toggleWebSearch = () => {
		webSearchAlways = !webSearchAlways;
		saveSettings({ webSearchAlways });
	};

	const toggleCtrlEnter = () => {
		ctrlEnterToSend = !ctrlEnterToSend;
		saveSettings({ ctrlEnterToSend });
	};

	const toggleUserLocation = async () => {
		if (userLocation && 'geolocation' in navigator) {
			try {
				await new Promise<GeolocationPosition>((resolve, reject) => {
					navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 8000 });
				});
			} catch {
				userLocation = false;
				alert('无法获取位置，请检查浏览器权限。');
				return;
			}
		}
		await saveSettings({ userLocation });
	};

	const toggleResponseAutoCopy = async () => {
		if (responseAutoCopy) {
			try {
				await navigator.clipboard.readText();
			} catch {
				responseAutoCopy = false;
				alert('剪贴板权限被拒绝，请在浏览器设置中允许访问。');
				return;
			}
		}
		await saveSettings({ responseAutoCopy });
	};
</script>

<ManageFloatingActionButtonsModal
	bind:show={showManageFloating}
	bind:floatingActionButtons
	onSave={(buttons) => {
		floatingActionButtons = buttons;
		saveSettings({ floatingActionButtons: buttons });
	}}
/>

<ManageImageCompressionModal
	bind:show={showManageCompression}
	bind:size={imageCompressionSize}
	onSave={(size) => {
		imageCompressionSize = size;
		saveSettings({ imageCompressionSize: size });
	}}
/>

<form
	id="tab-interface"
	class="flex h-full min-h-0 flex-col justify-between space-y-3 text-sm"
	onsubmit={(e) => {
		e.preventDefault();
		saveSettings({
			imageCompressionSize,
			floatingActionButtons
		});
		onSave();
	}}
>
	<input
		bind:this={filesInputElement}
		type="file"
		hidden
		accept="image/*"
		onchange={(e) => {
			const file = (e.currentTarget as HTMLInputElement).files?.[0];
			if (!file) return;
			if (!['image/gif', 'image/webp', 'image/jpeg', 'image/png'].includes(file.type)) return;
			const reader = new FileReader();
			reader.onload = () => {
				backgroundImageUrl = String(reader.result);
				saveSettings({ backgroundImageUrl });
			};
			reader.readAsDataURL(file);
		}}
	/>

	<div class="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
		<h1 class="mb-2 text-sm font-medium">界面</h1>

		<div class="flex w-full justify-between py-0.5">
			<label class="self-center text-xs" for="ui-scale-slider">界面缩放比例</label>
			<button
				class="p-1 text-xs"
				type="button"
				onclick={() => {
					if (textScale === null) textScale = 1;
					else setTextScaleHandler(1);
				}}
			>
				{textScale === null ? '默认' : `${textScale}x`}
			</button>
		</div>
		{#if textScale !== null}
			<div class="flex items-center gap-2 px-1 pb-1">
				<button type="button" class="rounded-lg p-1 hover:bg-gray-800" onclick={() => setTextScaleHandler(Math.max(1, +(textScale! - 0.1).toFixed(2)))}>
					<Minus className="h-3.5 w-3.5" />
				</button>
				<input id="ui-scale-slider" class="w-full" type="range" min="1" max="1.5" step="0.01" bind:value={textScale} onchange={() => setTextScaleHandler(textScale)} />
				<button type="button" class="rounded-lg p-1 hover:bg-gray-800" onclick={() => setTextScaleHandler(Math.min(1.5, +(textScale! + 0.1).toFixed(2)))}>
					<Plus className="h-3.5 w-3.5" />
				</button>
			</div>
		{/if}

		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">高对比度模式（Beta）</div>
			<Switch bind:state={highContrastMode} onChange={() => { applyHighContrast(highContrastMode); saveSettings({ highContrastMode }); }} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">在标签页中显示对话标题</div>
			<Switch bind:state={showChatTitleInTab} onChange={() => saveSettings({ showChatTitleInTab })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">通知提示音</div>
			<Switch bind:state={notificationSound} onChange={() => saveSettings({ notificationSound })} />
		</div>
		{#if notificationSound}
			<div class="flex w-full justify-between py-0.5">
				<div class="self-center text-xs">始终播放通知提示音</div>
				<Switch bind:state={notificationSoundAlways} onChange={() => saveSettings({ notificationSoundAlways })} />
			</div>
		{/if}
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">允许使用用户位置</div>
			<Switch bind:state={userLocation} onChange={toggleUserLocation} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">触觉反馈（Android）</div>
			<Switch bind:state={hapticFeedback} onChange={() => saveSettings({ hapticFeedback })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">复制格式化文本</div>
			<Switch bind:state={copyFormatted} onChange={() => saveSettings({ copyFormatted })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">检测到新版本时显示更新通知</div>
			<Switch bind:state={showUpdateToast} onChange={() => saveSettings({ showUpdateToast })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">版本更新后首次登录时显示“新功能介绍”弹窗</div>
			<Switch bind:state={showChangelog} onChange={() => saveSettings({ showChangelog })} />
		</div>

		<div class="my-2 text-sm font-medium">对话</div>

		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">启用消息队列</div>
			<Switch bind:state={enableMessageQueue} onChange={() => saveSettings({ enableMessageQueue })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">对话方向</div>
			<button class="rounded-sm px-3 py-1 text-xs" type="button" onclick={toggleChatDirection}>
				{chatDirection === 'LTR' ? 'LTR' : chatDirection === 'RTL' ? 'RTL' : '自动'}
			</button>
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">默认主页样式</div>
			<button class="rounded-sm px-3 py-1 text-xs" type="button" onclick={toggleLanding}>
				{landingPageMode === '' ? '默认' : '对话'}
			</button>
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">对话背景图片</div>
			<button
				class="rounded-sm px-3 py-1 text-xs"
				type="button"
				onclick={() => {
					if (backgroundImageUrl) {
						backgroundImageUrl = null;
						saveSettings({ backgroundImageUrl: null });
					} else filesInputElement?.click();
				}}
			>
				{backgroundImageUrl ? '重置' : '上传'}
			</button>
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">以聊天气泡的形式显示对话内容</div>
			<Switch bind:state={chatBubble} onChange={() => saveSettings({ chatBubble })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">在对话中显示用户名而不是“你”</div>
			<Switch bind:state={showUsername} onChange={() => saveSettings({ showUsername })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">宽屏模式</div>
			<Switch bind:state={widescreenMode} onChange={() => saveSettings({ widescreenMode })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">默认使用临时对话</div>
			<Switch bind:state={temporaryChatByDefault} onChange={() => saveSettings({ temporaryChatByDefault })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">流式输出内容时启用动态渐显效果</div>
			<Switch bind:state={chatFadeStreamingText} onChange={() => saveSettings({ chatFadeStreamingText })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">自动生成标题</div>
			<Switch bind:state={titleAutoGenerate} onChange={() => saveSettings({ titleAutoGenerate })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">自动生成追问</div>
			<Switch bind:state={autoFollowUps} onChange={() => saveSettings({ autoFollowUps })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">自动生成对话标签</div>
			<Switch bind:state={autoTags} onChange={() => saveSettings({ autoTags })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">自动复制回答内容到剪贴板</div>
			<Switch bind:state={responseAutoCopy} onChange={toggleResponseAutoCopy} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">回填推荐提示词到输入框</div>
			<Switch bind:state={insertSuggestionPrompt} onChange={() => saveSettings({ insertSuggestionPrompt })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">在对话中保留追问提示词</div>
			<Switch bind:state={keepFollowUpPrompts} onChange={() => saveSettings({ keepFollowUpPrompts })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">回填追问提示词到输入框</div>
			<Switch bind:state={insertFollowUpPrompt} onChange={() => saveSettings({ insertFollowUpPrompt })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">显示重新生成选项菜单</div>
			<Switch bind:state={regenerateMenu} onChange={() => saveSettings({ regenerateMenu })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">始终折叠代码块</div>
			<Switch bind:state={collapseCodeBlocks} onChange={() => saveSettings({ collapseCodeBlocks })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">始终展开详细信息</div>
			<Switch bind:state={expandDetails} onChange={() => saveSettings({ expandDetails })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">在文件和引用预览中渲染 Markdown</div>
			<Switch bind:state={renderMarkdownInPreviews} onChange={() => saveSettings({ renderMarkdownInPreviews })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">以标签页的形式展示多个模型的回答</div>
			<Switch bind:state={displayMultiModelResponsesInTabs} onChange={() => saveSettings({ displayMultiModelResponsesInTabs })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">切换对话分支时滚动到最新回答</div>
			<Switch bind:state={scrollOnBranchChange} onChange={() => saveSettings({ scrollOnBranchChange })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">美化 PDF 导出</div>
			<Switch bind:state={stylizedPdfExport} onChange={() => saveSettings({ stylizedPdfExport })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">快捷操作浮窗</div>
			<div class="flex items-center gap-3 p-1">
				{#if showFloatingActionButtons}
					<button class="text-xs text-gray-400 underline" type="button" onclick={() => { showManageFloating = true; }}>管理</button>
				{/if}
				<Switch bind:state={showFloatingActionButtons} onChange={() => saveSettings({ showFloatingActionButtons })} />
			</div>
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">在对话时进行联网搜索</div>
			<button class="rounded-sm px-3 py-1 text-xs" type="button" onclick={toggleWebSearch}>
				{webSearchAlways ? '始终' : '默认'}
			</button>
		</div>

		<div class="my-2 text-sm font-medium">输入</div>

		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">Enter 键行为</div>
			<button class="rounded-sm px-3 py-1 text-xs" type="button" onclick={toggleCtrlEnter}>
				{ctrlEnterToSend ? 'Ctrl+Enter 发送' : 'Enter 键发送'}
			</button>
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">富文本对话框</div>
			<Switch bind:state={richTextInput} onChange={() => saveSettings({ richTextInput })} />
		</div>
		{#if richTextInput}
			<div class="flex w-full justify-between py-0.5">
				<div class="self-center text-xs">自动补全提示词</div>
				<Switch bind:state={promptAutocomplete} onChange={() => saveSettings({ promptAutocomplete })} />
			</div>
			<div class="flex w-full justify-between py-0.5">
				<div class="self-center text-xs">显示格式工具栏</div>
				<Switch bind:state={showFormattingToolbar} onChange={() => saveSettings({ showFormattingToolbar })} />
			</div>
			<div class="flex w-full justify-between py-0.5">
				<div class="self-center text-xs">以富文本的形式回填提示词</div>
				<Switch bind:state={insertPromptAsRichText} onChange={() => saveSettings({ insertPromptAsRichText })} />
			</div>
		{/if}
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">将大段文本粘贴为文件</div>
			<Switch bind:state={largeTextAsFile} onChange={() => saveSettings({ largeTextAsFile })} />
		</div>

		<div class="my-2 text-sm font-medium">产物</div>

		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">自动检测对话产物</div>
			<Switch bind:state={detectArtifacts} onChange={() => saveSettings({ detectArtifacts })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">iframe 沙盒允许同源访问</div>
			<Switch bind:state={iframeSandboxAllowSameOrigin} onChange={() => saveSettings({ iframeSandboxAllowSameOrigin })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">iframe 沙盒允许表单提交</div>
			<Switch bind:state={iframeSandboxAllowForms} onChange={() => saveSettings({ iframeSandboxAllowForms })} />
		</div>

		<div class="my-2 text-sm font-medium">语音</div>

		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">允许语音通话时打断对话</div>
			<Switch bind:state={voiceInterruption} onChange={() => saveSettings({ voiceInterruption })} />
		</div>
		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">在通话中显示 Emoji</div>
			<Switch bind:state={showEmojiInCall} onChange={() => saveSettings({ showEmojiInCall })} />
		</div>

		<div class="my-2 text-sm font-medium">文件</div>

		<div class="flex w-full justify-between py-0.5">
			<div class="self-center text-xs">压缩图像</div>
			<div class="flex items-center gap-3 p-1">
				{#if imageCompression}
					<button class="text-xs text-gray-400 underline" type="button" onclick={() => { showManageCompression = true; }}>管理</button>
				{/if}
				<Switch bind:state={imageCompression} onChange={() => saveSettings({ imageCompression })} />
			</div>
		</div>
		{#if imageCompression}
			<div class="flex w-full justify-between py-0.5">
				<div class="self-center text-xs">压缩频道中的图片</div>
				<Switch bind:state={imageCompressionInChannels} onChange={() => saveSettings({ imageCompressionInChannels })} />
			</div>
		{/if}
	</div>

	<div class="flex shrink-0 justify-end pt-2 text-sm font-medium">
		<button
			class="rounded-full bg-white px-3.5 py-1.5 text-sm font-medium text-black transition hover:bg-gray-100"
			type="submit"
		>
			保存
		</button>
	</div>
</form>
