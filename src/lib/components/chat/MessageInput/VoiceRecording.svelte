<script lang="ts">
	type Props = {
		recording?: boolean;
		speechAutoSend?: boolean;
		onCancel?: () => void;
		onConfirm?: (text: string) => void;
	};

	let {
		recording = $bindable(false),
		speechAutoSend = false,
		onCancel = () => {},
		onConfirm = () => {}
	}: Props = $props();

	let loading = $state(false);
	let durationSeconds = $state(0);
	let transcription = $state('');
	let visualizerData = $state<number[]>(Array(40).fill(0.08));
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let recognition: any = null;
	let durationTimer: number | null = null;
	let visualizerTimer: number | null = null;

	const formatSeconds = (seconds: number) => {
		const minutes = Math.floor(seconds / 60);
		const remaining = seconds % 60;
		return `${minutes}:${remaining < 10 ? `0${remaining}` : remaining}`;
	};

	const stopRecognition = () => {
		try {
			recognition?.stop();
		} catch {
			/* ignore */
		}
		recognition = null;
		if (durationTimer) {
			window.clearInterval(durationTimer);
			durationTimer = null;
		}
		if (visualizerTimer) {
			window.clearInterval(visualizerTimer);
			visualizerTimer = null;
		}
	};

	const startRecording = async () => {
		transcription = '';
		durationSeconds = 0;
		loading = false;

		durationTimer = window.setInterval(() => {
			durationSeconds += 1;
		}, 1000);

		visualizerTimer = window.setInterval(() => {
			visualizerData = Array.from({ length: 40 }, () => 0.08 + Math.random() * 0.7);
		}, 120);

		const SpeechRecognitionCtor =
			(window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

		if (!SpeechRecognitionCtor) {
			transcription = '（浏览器不支持语音识别，确认后将插入演示文本）';
			return;
		}

		recognition = new SpeechRecognitionCtor();
		recognition.lang = 'zh-CN';
		recognition.continuous = true;
		recognition.interimResults = true;
		recognition.onresult = (event: any) => {
			let text = '';
			for (let i = 0; i < event.results.length; i += 1) {
				text += event.results[i][0].transcript;
			}
			transcription = text.trim();
		};
		recognition.onerror = () => {
			if (!transcription) transcription = '语音识别失败，可手动确认插入演示文本';
		};
		try {
			recognition.start();
		} catch {
			transcription = '无法启动语音识别';
		}
	};

	const cancel = () => {
		stopRecognition();
		recording = false;
		onCancel();
	};

	const confirm = async () => {
		loading = true;
		stopRecognition();
		const text =
			transcription.trim() ||
			`语音输入演示 ${new Date().toLocaleTimeString()}`;
		onConfirm(text);
		recording = false;
		loading = false;
		if (speechAutoSend) {
			/* parent handles send via onConfirm path */
		}
	};

	$effect(() => {
		if (recording) {
			void startRecording();
			return () => stopRecognition();
		}
		stopRecognition();
	});
</script>

{#if recording}
	<div class="flex w-full max-w-full items-center gap-3 p-2.5">
		<button
			type="button"
			class="flex size-8 shrink-0 items-center justify-center rounded-full text-gray-300 transition hover:bg-gray-800 hover:text-white"
			onclick={cancel}
			aria-label="取消录音"
			disabled={loading}
		>
			<svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
				<path stroke-linecap="round" d="M6 6l12 12M18 6L6 18"></path>
			</svg>
		</button>

		<div class="min-w-0 flex-1">
			<div class="mb-1 flex h-8 items-end justify-center gap-[2px]">
				{#each visualizerData as value, i (i)}
					<span
						class="w-[3px] rounded-full bg-emerald-400/80"
						style={`height:${Math.max(10, value * 100)}%`}
					></span>
				{/each}
			</div>
			<div class="truncate text-center text-xs text-gray-400">
				{transcription || '正在倾听...'} · {formatSeconds(durationSeconds)}
			</div>
		</div>

		<button
			id="confirm-recording-button"
			type="button"
			class="flex size-8 shrink-0 items-center justify-center rounded-full bg-white text-black transition hover:bg-gray-100 disabled:opacity-60"
			onclick={() => void confirm()}
			aria-label="确认语音输入"
			disabled={loading}
		>
			{#if loading}
				<span
					class="size-3.5 animate-spin rounded-full border-2 border-black/20 border-t-black"
				></span>
			{:else}
				<svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
					<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5"></path>
				</svg>
			{/if}
		</button>
	</div>
{/if}
