<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/stores';
	import { onDestroy, onMount, tick } from 'svelte';

	import { getAgentModels, streamAgentChat } from '$lib/apis/agent';
	import { listNotebooks, type NotebookSummary } from '$lib/apis/opennotebook';
	import { sourceHref } from '$lib/data/knowledge';
	import MockMessageInput from '$lib/components/chat/MockMessageInput.svelte';
	import MockMessages, { type MockMessage } from '$lib/components/chat/MockMessages.svelte';
	import MockNavbar from '$lib/components/chat/MockNavbar.svelte';
	import MockPlaceholder from '$lib/components/chat/MockPlaceholder.svelte';
	import MockSidebar, { type ChatSummary } from '$lib/components/chat/MockSidebar.svelte';
	import SaveToNotebookDialog from '$lib/components/chat/SaveToNotebookDialog.svelte';

	let sidebarOpen = $state(true);
	let activeChatId = $state<string | null>(null);
	let selectedModelId = $state($page.url.searchParams.get('model') ?? '');
	let prompt = $state('');
	let generating = $state(false);
	let messages = $state<MockMessage[]>([]);
	let messagesContainer = $state<HTMLDivElement | null>(null);
	let modelOptions = $state<{ id: string; name: string }[]>([]);
	let collectionId = $state($page.url.searchParams.get('notebook') ?? '');
	let notebooks = $state<NotebookSummary[]>([]);
	let notebooksLoading = $state(true);
	let generationSeq = 0;
	let abortController: AbortController | null = null;
	let saveOpen = $state(false);
	let saveTitle = $state('答疑摘录');
	let saveContent = $state('');
	let saveToast = $state('');

	// 会话只活在这次页面停留期间：后端没有会话存储接口，
	// 与其编三条假历史，不如把用户真发过的问题记下来。
	let chats = $state<ChatSummary[]>([]);
	let conversations = $state<Record<string, MockMessage[]>>({});

	// messages 是当前会话的可写副本，改完同步回 conversations。
	$effect(() => {
		const id = activeChatId;
		const snapshot = messages;

		if (id) {
			conversations[id] = snapshot;
		}
	});

	const currentModelName = $derived(
		modelOptions.find((model) => model.id === selectedModelId)?.name ?? selectedModelId
	);

	onMount(() => {
		void getAgentModels()
			.then((list) => {
				modelOptions = list.data.map((model) => ({
					id: model.id,
					name: model.name || model.id
				}));
				const ids = modelOptions.map((model) => model.id);
				if (ids.length > 0 && !ids.includes(selectedModelId)) {
					selectedModelId = ids[0];
				}
			})
			.catch(() => {
				// basic-agent 没起来。留空列表，让顶栏显示"选择模型"而不是抛未捕获异常。
				modelOptions = [];
				selectedModelId = '';
			});
		void listNotebooks()
			.then((items) => {
				notebooks = items;
				if (collectionId && !items.some((item) => item.id === collectionId)) {
					collectionId = '';
				}
			})
			.catch(() => {
				notebooks = [];
			})
			.finally(() => {
				notebooksLoading = false;
			});
	});

	const scrollToBottom = async () => {
		await tick();

		if (messagesContainer) {
			messagesContainer.scrollTop = messagesContainer.scrollHeight;
		}
	};

	const finishStreamingMessages = () => {
		messages = messages.map((message) =>
			message.streaming ? { ...message, streaming: false } : message
		);
	};

	const bumpGeneration = () => {
		generationSeq += 1;
		abortController?.abort();
		abortController = null;
		return generationSeq;
	};

	const returnToSelect = () => {
		bumpGeneration();
		generating = false;
		void goto(resolve('/agent-select'));
	};

	const createEmptyChat = () => {
		bumpGeneration();
		activeChatId = null;
		messages = [];
		prompt = '';
		generating = false;
	};

	const selectChat = (chatId: string) => {
		bumpGeneration();
		activeChatId = chatId;
		messages = conversations[chatId] ?? [];
		prompt = '';
		generating = false;
		void scrollToBottom();
	};

	const openExam = () => {
		void goto(
			resolve(
				`/exam?model=${encodeURIComponent(selectedModelId)}&from=qa&topic=${encodeURIComponent(collectionId)}`
			)
		);
	};

	// 论文辅助：带上当前笔记本，批改时按它检索课程材料，返回时也原样带回来
	const openEssay = () => {
		const query = `model=${encodeURIComponent(selectedModelId)}&from=qa${
			collectionId ? `&notebook=${encodeURIComponent(collectionId)}` : ''
		}`;

		void goto(resolve(`/essay?${query}`));
	};

	const clipTitle = (text: string) => {
		const trimmed = text.trim().replace(/\s+/g, ' ');

		return trimmed.length > 40 ? `${trimmed.slice(0, 40)}…` : trimmed || '答疑摘录';
	};

	const openSaveToNotebook = (messageId: string) => {
		const index = messages.findIndex((message) => message.id === messageId);
		const assistant = index >= 0 ? messages[index] : null;

		if (!assistant || assistant.role !== 'assistant') {
			return;
		}

		let question = '';

		for (let i = index - 1; i >= 0; i -= 1) {
			if (messages[i].role === 'user') {
				question = messages[i].content;
				break;
			}
		}

		const citations = (assistant.citations ?? [])
			.map((citation) => `- ${citation.collectionName} · ${citation.title}`)
			.join('\n');

		saveTitle = clipTitle(question);
		saveContent = [
			'## 问',
			'',
			question || '（无对应提问）',
			'',
			'## 答',
			'',
			assistant.content,
			citations ? `\n## 引用\n\n${citations}` : ''
		]
			.join('\n')
			.trim();
		saveOpen = true;
	};

	const ask = async (question: string, seq: number) => {
		const controller = new AbortController();
		abortController = controller;
		const assistantId = `assistant-${Date.now()}`;
		let created = false;

		const writeDelta = (content: string, streaming = true) => {
			if (seq !== generationSeq) {
				return;
			}

			if (!created) {
				messages = [
					...messages,
					{
						id: assistantId,
						role: 'assistant',
						model: selectedModelId,
						content,
						streaming
					}
				];
				created = true;
			} else {
				messages = messages.map((message) =>
					message.id === assistantId ? { ...message, content, streaming } : message
				);
			}

			void scrollToBottom();
		};

		try {
			const result = await streamAgentChat(
				question,
				selectedModelId,
				writeDelta,
				controller.signal,
				collectionId ? [collectionId] : undefined
			);

			if (seq !== generationSeq) {
				return;
			}

			if (!result.content.trim()) {
				writeDelta('没有生成回答，请重试。', false);
			} else {
				writeDelta(result.content, false);
				const notebook = notebooks.find((item) => item.id === collectionId);
				messages = messages.map((message) =>
					message.id === assistantId
						? {
								...message,
								model: result.model || selectedModelId,
								// 后端只回答案正文，没有逐条出处。这里能诚实标注的只有
								// 本次检索限定在哪个笔记本——没选就什么都不标。
								citations: notebook
									? [
											{
												id: notebook.id,
												collectionId: notebook.id,
												collectionName: notebook.name,
												fileId: '',
												title: '本次检索范围',
												kind: 'note',
												href: sourceHref(notebook.id, '', 'qa')
											}
										]
									: []
							}
						: message
				);
			}

			generating = false;
			void scrollToBottom();
		} finally {
			if (abortController === controller) {
				abortController = null;
			}
		}
	};

	const syncModelToUrl = () => {
		const current = $page.url.searchParams.get('model') ?? '';

		if (selectedModelId === current) {
			return;
		}

		void goto(resolve(`/qa?model=${encodeURIComponent(selectedModelId)}`), {
			replaceState: true,
			keepFocus: true,
			noScroll: true
		});
	};

	const submitPrompt = (content: string) => {
		const trimmedContent = content.trim();

		if (!trimmedContent || generating) {
			return;
		}

		const seq = bumpGeneration();
		const userMessage: MockMessage = {
			id: `user-${Date.now()}`,
			role: 'user',
			content: trimmedContent
		};

		messages = [...messages, userMessage];
		prompt = '';
		generating = true;

		if (!activeChatId) {
			// 第一句话定标题，之后只更新时间，侧栏据此排序。
			activeChatId = `chat-${Date.now()}`;
			chats = [
				{ id: activeChatId, title: clipTitle(trimmedContent), updatedAt: Date.now() },
				...chats
			];
		} else {
			const id = activeChatId;
			chats = chats.map((chat) => (chat.id === id ? { ...chat, updatedAt: Date.now() } : chat));
		}

		void scrollToBottom();
		void ask(trimmedContent, seq).catch((error: unknown) => {
			if (seq !== generationSeq || (error instanceof DOMException && error.name === 'AbortError')) {
				return;
			}

			messages = [
				...messages,
				{
					id: `assistant-${Date.now()}`,
					role: 'assistant',
					model: selectedModelId,
					content: error instanceof Error ? error.message : '回答生成失败，请重试。'
				}
			];
			generating = false;
		});
	};

	const stopResponse = () => {
		bumpGeneration();
		finishStreamingMessages();
		generating = false;
	};

	const regenerateResponse = (messageId: string) => {
		if (generating) {
			return;
		}

		const messageIndex = messages.findIndex((message) => message.id === messageId);

		if (messageIndex < 0) {
			return;
		}

		let lastUserQuestion = '';

		for (let index = messageIndex - 1; index >= 0; index -= 1) {
			if (messages[index].role === 'user') {
				lastUserQuestion = messages[index].content;
				break;
			}
		}

		if (!lastUserQuestion) {
			return;
		}

		const seq = bumpGeneration();
		messages = messages.filter((message) => message.id !== messageId);
		generating = true;
		void scrollToBottom();
		void ask(lastUserQuestion, seq).catch((error: unknown) => {
			if (seq !== generationSeq || (error instanceof DOMException && error.name === 'AbortError')) {
				return;
			}

			generating = false;
		});
	};

	onDestroy(() => {
		bumpGeneration();
	});
</script>

<svelte:head>
	<title>答疑智能体 | TAgent</title>
</svelte:head>

<main class="flex h-screen overflow-hidden bg-[#171717] text-white">
	{#if sidebarOpen}
		<MockSidebar
			{activeChatId}
			{chats}
			modelId={selectedModelId}
			onHome={returnToSelect}
			onNewChat={createEmptyChat}
			onSelectChat={selectChat}
			onClose={() => {
				sidebarOpen = false;
			}}
		/>
	{/if}

	<section class="relative flex min-w-0 flex-1 flex-col bg-[#171717]">
		<MockNavbar
			{sidebarOpen}
			models={modelOptions}
			bind:selectedModelId
			{collectionId}
			{notebooks}
			{notebooksLoading}
			onOpenSidebar={() => {
				sidebarOpen = true;
			}}
			onNewChat={createEmptyChat}
			onOpenExam={openExam}
			onOpenEssay={openEssay}
			onHome={returnToSelect}
			onModelChange={syncModelToUrl}
			onCollectionChange={(id) => {
				collectionId = id;
			}}
		/>

		{#if messages.length === 0}
			<div class="flex min-h-0 flex-1 items-center">
				<MockPlaceholder
					modelName={currentModelName}
					bind:prompt
					{generating}
					onSubmit={submitPrompt}
					onStop={stopResponse}
				/>
			</div>
		{:else}
			<div
				bind:this={messagesContainer}
				id="messages-container"
				class="min-h-0 flex-1 overflow-y-auto"
			>
				<MockMessages
					{messages}
					{generating}
					modelName={currentModelName}
					onRegenerate={regenerateResponse}
					onSaveToNotebook={openSaveToNotebook}
				/>
			</div>

			<div
				class="relative z-10 shrink-0 bg-gradient-to-t from-gray-900 via-gray-900 to-transparent px-4 pt-4 pb-2"
			>
				<div class="mx-auto w-full max-w-3xl">
					<MockMessageInput
						bind:prompt
						placeholder="发送消息"
						{generating}
						onSubmit={submitPrompt}
						onStop={stopResponse}
					/>
				</div>

				<p class="mt-2 text-center text-[11px] text-gray-600">
					回答来自 basic-agent 检索的教材与笔记，请核实重要内容。
				</p>
			</div>
		{/if}
	</section>
</main>

<SaveToNotebookDialog
	open={saveOpen}
	title={saveTitle}
	content={saveContent}
	onClose={() => {
		saveOpen = false;
	}}
	onSaved={(notebookName) => {
		saveToast = `已加入笔记本「${notebookName}」`;
		window.setTimeout(() => {
			saveToast = '';
		}, 3200);
	}}
/>

{#if saveToast}
	<div
		class="fixed bottom-6 left-1/2 z-[70] -translate-x-1/2 rounded-xl border border-white/10 bg-[#242424] px-4 py-2 text-sm text-gray-100 shadow-lg"
	>
		{saveToast}
	</div>
{/if}
