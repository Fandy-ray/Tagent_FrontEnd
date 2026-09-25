<script lang="ts">
	import { SvelteFlowProvider, type Edge, type Node } from '@xyflow/svelte';
	import { tick } from 'svelte';

	import type { MockMessage } from '$lib/components/chat/MockMessages.svelte';
	import Flow from './Flow.svelte';

	type Props = {
		messages?: MockMessage[];
		modelName?: string;
		currentMessageId?: string | null;
		onNodeClick?: (messageId: string) => void;
	};

	let {
		messages = [],
		modelName = '',
		currentMessageId = null,
		onNodeClick = () => {}
	}: Props = $props();

	let layoutDirection = $state<'vertical' | 'horizontal'>('vertical');
	let nodes = $state.raw<Node[]>([]);
	let edges = $state.raw<Edge[]>([]);

	const buildGraph = (direction: 'vertical' | 'horizontal') => {
		const levelOffset = direction === 'vertical' ? 140 : 280;
		const focusId = currentMessageId ?? messages.at(-1)?.id ?? null;

		const nextNodes: Node[] = messages.map((message, index) => {
			const x = direction === 'vertical' ? 40 : index * levelOffset + 20;
			const y = direction === 'vertical' ? index * levelOffset + 20 : 40;

			return {
				id: message.id,
				type: 'custom',
				position: { x, y },
				data: {
					message: {
						id: message.id,
						role: message.role,
						content: message.content,
						model: message.model
					},
					modelName,
					userName: '我'
				}
			};
		});

		const nextEdges: Edge[] = [];
		for (let i = 1; i < messages.length; i += 1) {
			const source = messages[i - 1].id;
			const target = messages[i].id;
			nextEdges.push({
				id: `${source}-${target}`,
				source,
				target,
				type: 'smoothstep',
				animated: Boolean(focusId && (focusId === target || messages.slice(i).some((m) => m.id === focusId))),
				selectable: false,
				style: 'stroke: #9ca3af;'
			});
		}

		nodes = nextNodes;
		edges = nextEdges;
	};

	$effect(() => {
		void messages;
		void modelName;
		void currentMessageId;
		void layoutDirection;
		buildGraph(layoutDirection);
	});
</script>

<SvelteFlowProvider>
	<div class="relative h-full w-full min-h-[280px]">
		{#if messages.length === 0}
			<div class="flex h-full items-center justify-center px-4 text-center text-sm text-gray-500">
				暂无消息可展示
			</div>
		{:else if nodes.length > 0}
			{#key `${layoutDirection}-${messages.map((m) => m.id).join('|')}`}
				<Flow
					bind:nodes
					bind:edges
					onNodeClick={async (messageId) => {
						onNodeClick(messageId);
						await tick();
					}}
					onToggleLayout={(direction) => {
						layoutDirection = direction;
					}}
				/>
			{/key}
		{/if}
	</div>
</SvelteFlowProvider>
