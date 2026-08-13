<script lang="ts">
	import { onDestroy, tick } from 'svelte';

	import MockMessageInput from '$lib/components/chat/MockMessageInput.svelte';
	import MockMessages, {
		type MockMessage
	} from '$lib/components/chat/MockMessages.svelte';
	import MockNavbar from '$lib/components/chat/MockNavbar.svelte';
	import MockPlaceholder from '$lib/components/chat/MockPlaceholder.svelte';
	import MockSidebar from '$lib/components/chat/MockSidebar.svelte';

	let sidebarOpen = $state(true);
	let activeChatId = $state<string | null>(null);
	let selectedModelId = $state('deepseek');
	let prompt = $state('');
	let generating = $state(false);
	let messages = $state<MockMessage[]>([]);
	let messagesContainer = $state<HTMLDivElement | null>(null);
	let responseTimer: number | null = null;

	const mockConversationByChatId: Record<string, MockMessage[]> = {
		'chat-1': [
			{
				id: 'chat-1-user',
				role: 'user',
				content: '什么是离散事件仿真？'
			},
			{
				id: 'chat-1-assistant',
				role: 'assistant',
				model: 'deepseek',
				content:
					'离散事件仿真是一种对系统状态只在离散事件发生时产生变化的系统进行建模和分析的方法。常见的事件包括顾客到达、服务完成、设备故障和任务结束等。'
			}
		],
		'chat-2': [
			{
				id: 'chat-2-user',
				role: 'user',
				content: '系统模型一般如何分类？'
			},
			{
				id: 'chat-2-assistant',
				role: 'assistant',
				model: 'deepseek',
				content:
					'系统模型可以按照不同标准分类，例如静态模型与动态模型、确定性模型与随机模型、连续模型与离散模型，以及解析模型与仿真模型。'
			}
		],
		'chat-3': [
			{
				id: 'chat-3-user',
				role: 'user',
				content: '连续系统仿真常用什么方法？'
			},
			{
				id: 'chat-3-assistant',
				role: 'assistant',
				model: 'deepseek',
				content:
					'连续系统通常使用微分方程描述其状态变化，并通过欧拉法、改进欧拉法、龙格－库塔法等数值积分方法进行仿真求解。'
			}
		]
	};

	const createMockAnswer = (question: string) => {
		if (question.includes('离散事件')) {
			return '离散事件仿真是一种对状态只在离散事件发生时变化的系统进行建模和分析的方法。它通常包含系统状态、事件、仿真时钟、未来事件表和统计指标等基本要素，常用于排队系统、生产线、交通系统和计算机网络等场景。';
		}

		if (question.includes('连续')) {
			return '连续系统的状态会随时间连续变化，通常使用微分方程描述。连续系统仿真一般通过数值积分方法计算系统状态，例如欧拉法和龙格－库塔法。';
		}

		if (question.includes('模型')) {
			return '系统模型是对真实系统结构、行为和规律的抽象描述。根据研究目标不同，可以建立物理模型、数学模型、静态模型、动态模型、确定性模型或随机模型。';
		}

		return `这是对“${question}”的 Mock 回答。当前页面尚未调用真实模型 API，回复由前端固定逻辑生成，用于验证 tAgent 聊天界面的交互流程。`;
	};

	const scrollToBottom = async () => {
		await tick();

		if (messagesContainer) {
			messagesContainer.scrollTop = messagesContainer.scrollHeight;
		}
	};

	const clearResponseTimer = () => {
		if (responseTimer !== null) {
			window.clearTimeout(responseTimer);
			responseTimer = null;
		}
	};

	const createNewChat = () => {
		clearResponseTimer();

		activeChatId = null;
		messages = [];
		prompt = '';
		generating = false;
	};

	const selectChat = (chatId: string) => {
		clearResponseTimer();

		activeChatId = chatId;
		messages = (mockConversationByChatId[chatId] ?? []).map((message) => ({
			...message
		}));
		prompt = '';
		generating = false;

		void scrollToBottom();
	};

	const openExam = () => {
		window.alert('智能测评暂为 Mock 功能');
	};

	const submitPrompt = (content: string) => {
		const trimmedContent = content.trim();

		if (!trimmedContent || generating) {
			return;
		}

		clearResponseTimer();

		const userMessage: MockMessage = {
			id: `user-${Date.now()}`,
			role: 'user',
			content: trimmedContent
		};

		messages = [...messages, userMessage];
		prompt = '';
		generating = true;

		if (!activeChatId) {
			activeChatId = `mock-chat-${Date.now()}`;
		}

		void scrollToBottom();

		responseTimer = window.setTimeout(() => {
			const assistantMessage: MockMessage = {
				id: `assistant-${Date.now()}`,
				role: 'assistant',
				model: 'deepseek',
				content: createMockAnswer(trimmedContent)
			};

			messages = [...messages, assistantMessage];
			generating = false;
			responseTimer = null;

			void scrollToBottom();
		}, 1200);
	};

	const stopResponse = () => {
		clearResponseTimer();
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

		messages = messages.filter((message) => message.id !== messageId);
		generating = true;

		void scrollToBottom();

		responseTimer = window.setTimeout(() => {
			messages = [
				...messages,
				{
					id: `assistant-${Date.now()}`,
					role: 'assistant',
					model: 'deepseek',
					content: createMockAnswer(lastUserQuestion)
				}
			];

			generating = false;
			responseTimer = null;

			void scrollToBottom();
		}, 1000);
	};

	onDestroy(() => {
		clearResponseTimer();
	});
</script>

<svelte:head>
	<title>答疑页面复刻测试</title>
</svelte:head>

<main class="flex h-screen overflow-hidden bg-[#171717] text-white">
	{#if sidebarOpen}
		<MockSidebar
			{activeChatId}
			onNewChat={createNewChat}
			onSelectChat={selectChat}
			onClose={() => {
				sidebarOpen = false;
			}}
		/>
	{/if}

	<section class="relative flex min-w-0 flex-1 flex-col bg-[#171717]">
		<MockNavbar
			{sidebarOpen}
			bind:selectedModelId
			hasActiveChat={messages.length > 0}
			onOpenSidebar={() => {
				sidebarOpen = true;
			}}
			onNewChat={createNewChat}
			onOpenExam={openExam}
		/>

		{#if messages.length === 0}
			<div class="flex min-h-0 flex-1 items-center">
				<MockPlaceholder
					modelName="deepseek"
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
					modelName="deepseek"
					onRegenerate={regenerateResponse}
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
					TAgent 可能会生成不准确的信息，请核实重要内容。
				</p>
			</div>
		{/if}
	</section>
</main>