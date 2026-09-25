<script lang="ts">
	import Switch from '$lib/components/common/Switch.svelte';
	import type { UserSettings } from '$lib/data/userSettings';
	import { onMount } from 'svelte';

	type Props = {
		settings: UserSettings;
		saveSettings: (updated: Partial<UserSettings>) => Promise<void> | void;
		onSave?: () => void;
	};

	let { settings, saveSettings, onSave = () => {} }: Props = $props();

	let speechAutoSend = $state(settings.speechAutoSend);
	let responseAutoPlayback = $state(settings.responseAutoPlayback);
	let STTEngine = $state(settings.sttEngine);
	let STTLanguage = $state(settings.sttLanguage);
	let TTSEngine = $state(settings.ttsEngine);
	let voice = $state(settings.ttsVoice);
	let playbackRate = $state(settings.ttsPlaybackRate);
	let nonLocalVoices = $state(settings.nonLocalVoices);
	let voices = $state<SpeechSynthesisVoice[]>([]);

	const loadVoices = () => {
		voices = window.speechSynthesis?.getVoices?.() ?? [];
	};

	onMount(() => {
		loadVoices();
		window.speechSynthesis?.addEventListener?.('voiceschanged', loadVoices);
		return () => {
			window.speechSynthesis?.removeEventListener?.('voiceschanged', loadVoices);
		};
	});

	$effect(() => {
		speechAutoSend = settings.speechAutoSend;
		responseAutoPlayback = settings.responseAutoPlayback;
		STTEngine = settings.sttEngine;
		STTLanguage = settings.sttLanguage;
		TTSEngine = settings.ttsEngine;
		voice = settings.ttsVoice;
		playbackRate = settings.ttsPlaybackRate;
		nonLocalVoices = settings.nonLocalVoices;
	});
</script>

<form
	id="tab-audio"
	class="flex h-full flex-col justify-between space-y-3 text-sm"
	onsubmit={(e) => {
		e.preventDefault();
		saveSettings({
			speechAutoSend,
			responseAutoPlayback,
			sttEngine: STTEngine,
			sttLanguage: STTLanguage,
			ttsEngine: TTSEngine,
			ttsVoice: voice,
			ttsPlaybackRate: playbackRate,
			nonLocalVoices
		});
		onSave();
	}}
>
	<div class="max-h-[28rem] space-y-3 overflow-y-scroll md:max-h-full">
		<div>
			<div class="mb-1 text-sm font-medium">语音转文本设置</div>

			<div class="flex w-full justify-between py-0.5">
				<div class="self-center text-xs font-medium">语音转文本引擎</div>
				<select
					class="w-fit rounded-sm bg-transparent p-1 px-2 pr-8 text-right text-xs outline-none"
					bind:value={STTEngine}
				>
					<option value="" class="bg-gray-800">默认</option>
					<option value="web" class="bg-gray-800">Web API</option>
				</select>
			</div>

			<div class="flex w-full justify-between py-0.5">
				<div class="self-center text-xs font-medium">语言</div>
				<input
					type="text"
					bind:value={STTLanguage}
					placeholder="例如 zh"
					class="bg-transparent px-3 text-right text-sm outline-none"
				/>
			</div>

			<div class="flex w-full justify-between py-0.5">
				<div class="self-center text-xs font-medium">语音转录文字后即时自动发送</div>
				<button
					class="rounded-sm px-3 py-1 text-xs"
					type="button"
					role="switch"
					aria-checked={speechAutoSend}
					onclick={() => {
						speechAutoSend = !speechAutoSend;
						saveSettings({ speechAutoSend });
					}}
				>
					{speechAutoSend ? '开启' : '关闭'}
				</button>
			</div>
		</div>

		<div>
			<div class="mb-1 text-sm font-medium">文本转语音设置</div>

			<div class="flex w-full justify-between py-0.5">
				<div class="self-center text-xs font-medium">文本转语音引擎</div>
				<select
					class="w-fit rounded-sm bg-transparent p-1 px-2 pr-8 text-right text-xs outline-none"
					bind:value={TTSEngine}
				>
					<option value="" class="bg-gray-800">默认（浏览器）</option>
				</select>
			</div>

			<div class="flex w-full justify-between py-0.5">
				<div class="self-center text-xs font-medium">自动播放回复</div>
				<button
					class="rounded-sm px-3 py-1 text-xs"
					type="button"
					role="switch"
					aria-checked={responseAutoPlayback}
					onclick={() => {
						responseAutoPlayback = !responseAutoPlayback;
						saveSettings({ responseAutoPlayback });
					}}
				>
					{responseAutoPlayback ? '开启' : '关闭'}
				</button>
			</div>

			<div class="flex w-full justify-between py-0.5">
				<div class="self-center text-xs font-medium">语音播放速度</div>
				<div class="flex items-center px-3 text-xs">
					<input
						type="number"
						min="0"
						step="0.01"
						bind:value={playbackRate}
						class="bg-transparent text-right text-sm outline-none"
					/>
					x
				</div>
			</div>
		</div>

		<hr class="border-gray-850/30" />

		<div>
			<div class="mb-2.5 text-sm font-medium">设置音色</div>
			<select class="w-full bg-transparent text-sm outline-none" bind:value={voice}>
				<option value="" class="bg-gray-800" selected={voice !== ''}>默认</option>
				{#each voices.filter((v) => nonLocalVoices || v.localService) as _voice}
					<option value={_voice.name} class="bg-gray-800" selected={voice === _voice.name}>
						{_voice.name}
					</option>
				{/each}
			</select>
			<div class="my-1.5 flex items-center justify-between">
				<div class="text-xs">允许非本地音色</div>
				<Switch bind:state={nonLocalVoices} />
			</div>
		</div>
	</div>

	<div class="flex justify-end text-sm font-medium">
		<button
			class="rounded-full bg-white px-3.5 py-1.5 text-sm font-medium text-black transition hover:bg-gray-100"
			type="submit"
		>
			保存
		</button>
	</div>
</form>
